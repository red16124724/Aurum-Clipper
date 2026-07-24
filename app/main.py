"""FastAPI app wiring the local pipeline together.

Startup loads the whisper model once and ensures the bundled font exists. The
heavy pipeline (download -> transcribe -> select -> render) runs on a background
thread as a :class:`~app.jobs.Job` so the request returns instantly; the
frontend then streams live progress over Server-Sent Events. Every domain error
is captured on the job (and surfaced in the stream) so the server never crashes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import sys
import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import captions, fonts, history, jobs, mood, music, prefetch, pretranscribe, reframe, transcriber, uploads
from .clipper import ClipOptions, generate_clip
from .models import ClipGenerationError, Device, GenerateRequest, InvalidVideoURLError, TranscriptionError
from .paths import CLIPS_DIR, FONTS_DIR, MUSIC_DIR, STATIC_DIR, WEB_DIST_DIR, ensure_dirs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("ai_video_clipper")


def _load_model_background() -> None:
    """Load whisper off the startup path (see lifespan() for why)."""
    try:
        transcriber.load_model()
        logger.info(
            "Startup complete. Whisper '%s' on %s. No external AI APIs are used.",
            transcriber.get_model_size(),
            transcriber.get_device(),
        )
    except Exception:  # noqa: BLE001 - status already recorded by transcriber
        logger.exception("Background whisper model load failed.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create dirs, ensure the font, and start loading whisper.

    The model load runs on a background thread rather than blocking startup:
    on first run it also downloads the model (up to ~3GB), and a server that
    isn't accepting connections yet looks like a dead install rather than a
    progress bar. Starting immediately lets the frontend poll
    /api/model-status and show real download progress instead of a refused
    connection.
    """
    ensure_dirs()
    fonts.ensure_fonts()
    threading.Thread(target=_load_model_background, daemon=True).start()
    yield


app = FastAPI(title="Local AI Video Clipper", version="0.1.0", lifespan=lifespan)

# Permissive CORS for local development (frontend served from the same origin).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve generated clips so the frontend can preview/download them.
app.mount("/clips", StaticFiles(directory=str(CLIPS_DIR)), name="clips")
# Serve caption fonts so the UI can @font-face them for an accurate live preview.
app.mount("/fonts", StaticFiles(directory=str(FONTS_DIR)), name="fonts")
# Serve the music library so the UI can preview tracks with an <audio> element.
app.mount("/music", StaticFiles(directory=str(MUSIC_DIR)), name="music")
# Serve the built React dashboard's hashed JS/CSS bundles (web/dist/assets) when a
# production build exists, so the backend can serve the React app at "/" directly.
if (WEB_DIST_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(WEB_DIST_DIR / "assets")), name="assets")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "device": transcriber.get_device()}


@app.get("/api/model-status")
def model_status() -> dict:
    """Whisper load/download progress — polled by the frontend's first-run
    splash screen so a multi-GB model download reads as progress, not a
    stuck/broken app."""
    return transcriber.model_status()


@app.get("/api/caption-styles")
def caption_styles() -> list[dict]:
    """Return the caption style presets for the UI (chips + live preview)."""
    return captions.get_presets_for_api()


@app.get("/api/devices")
def devices() -> dict:
    """Report compute devices the UI may offer for transcription.

    Lets the frontend enable/disable the GPU option and show the active device.
    """
    return {
        "devices": transcriber.available_devices(),
        "default": transcriber.get_device(),
        "cuda_available": transcriber.cuda_available(),
        "gpu_name": transcriber.gpu_name(),
        "model_size": transcriber.get_model_size(),
    }


@app.post("/api/warmup")
def warmup(device: Device = Device.AUTO) -> dict:
    """Load the Whisper model on the chosen device and report readiness.

    The frontend calls this when the user changes the Compute dropdown so it can
    show a live "loading / ready / failed" status. Loads are cached per device,
    so re-selecting a warm device returns instantly.
    """
    already = device.value != "auto" and transcriber.is_loaded(device.value)
    try:
        transcriber.load_model(device.value)
        return {
            "status": "ready",
            "device": transcriber.get_device(),
            "model_size": transcriber.get_model_size(),
            "cached": already,
        }
    except TranscriptionError as exc:
        return {"status": "error", "device": device.value, "message": str(exc)}


@app.post("/api/upload")
def upload(file: UploadFile = File(...)) -> dict:
    """Accept a video file from the user's machine and return an upload reference.

    The returned ``upload_id`` is then passed to ``POST /api/generate`` instead of
    a ``video_url``. Runs in the threadpool (sync def) so streaming a large file
    to disk doesn't block the event loop.
    """
    try:
        info = uploads.save_upload(file.filename, file.file)
    except InvalidVideoURLError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        file.file.close()
    return {"status": "ok", **info}


@app.get("/api/fonts")
def get_fonts() -> dict:
    """List caption fonts the UI can offer (bundled trending set + user uploads)."""
    return fonts.list_fonts()


@app.post("/api/fonts/upload")
def upload_font(file: UploadFile = File(...)) -> dict:
    """Accept a user .ttf/.otf font and register it for use in captions."""
    try:
        info = fonts.save_user_font(file.filename, file.file)
    except InvalidVideoURLError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        file.file.close()
    return {"status": "ok", **info}


@app.get("/api/music")
def get_music() -> dict:
    """List background-music tracks (files in assets/music + uploads)."""
    return {"tracks": music.list_tracks()}


@app.post("/api/music/upload")
def upload_music(file: UploadFile = File(...)) -> dict:
    """Accept a user audio file and add it to the background-music library."""
    try:
        info = music.save_track(file.filename, file.file)
    except InvalidVideoURLError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        file.file.close()
    return {"status": "ok", **info}


class PrefetchRequest(BaseModel):
    """Body for POST /api/prefetch — start fetching a URL video in the background."""

    video_url: str


@app.post("/api/prefetch")
def prefetch_start(req: PrefetchRequest) -> dict:
    """Begin downloading a URL video ahead of time and return a prefetch id.

    The frontend calls this when the user reaches Step 2 with a pasted link, then
    polls ``GET /api/prefetch/{id}`` for progress. When done, the returned
    ``download_id`` is passed to ``/api/generate`` so the pipeline reuses the file.
    """
    url = (req.video_url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="No video URL was provided.")
    pf = prefetch.start(url)
    return {"prefetch_id": pf.id, **pf.snapshot()}


@app.get("/api/prefetch/{prefetch_id}")
def prefetch_status(prefetch_id: str) -> dict:
    """Return the current progress/result of a background prefetch."""
    pf = prefetch.get(prefetch_id)
    if pf is None:
        raise HTTPException(status_code=404, detail="Unknown prefetch id.")
    return pf.snapshot()


class PretranscribeRequest(BaseModel):
    """Body for POST /api/pretranscribe — transcribe a ready video in the background."""

    source_id: str
    device: Device = Device.AUTO
    language: Optional[str] = None


@app.post("/api/pretranscribe")
def pretranscribe_start(req: PretranscribeRequest) -> dict:
    """Begin transcribing an already-downloaded/uploaded video ahead of Generate.

    Called once the video is on disk (download finished, or an upload). The
    result is cached by source id, so the Generate pipeline reuses it and skips
    the transcribe stage. The frontend polls ``GET /api/pretranscribe/{id}``.
    """
    source_id = (req.source_id or "").strip()
    if not source_id:
        raise HTTPException(status_code=400, detail="No source id was provided.")
    job = pretranscribe.start(source_id, req.device.value, req.language)
    return {"pretranscribe_id": job.id, **job.snapshot()}


@app.get("/api/pretranscribe/{job_id}")
def pretranscribe_status(job_id: str) -> dict:
    """Return the current progress/result of a background pre-transcription."""
    job = pretranscribe.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown pretranscribe id.")
    return job.snapshot()


@app.get("/api/download/{download_id}/video")
def download_file(download_id: str) -> FileResponse:
    """Stream a prefetched video file so the Step-2 preview can swap from the
    embeddable player to the real downloaded file once it's ready.

    The id is resolved via the same ``downloads/<id>.*`` glob used for uploads,
    so it can never reach a file outside the downloads directory. FileResponse
    serves Range requests, so the ``<video>`` element can seek/stream normally.
    """
    try:
        path = uploads.resolve_upload(download_id)
    except InvalidVideoURLError:
        raise HTTPException(status_code=404, detail="Downloaded video not found.")
    return FileResponse(str(path))


class ClipRef(BaseModel):
    """Reference to one generated clip."""

    clip_id: str
    index: int


@app.get("/api/history")
def get_history() -> list:
    """All past generations and their clips, newest first (for the Clips panel)."""
    return history.list_entries()


@app.delete("/api/clip/{clip_id}/{index}")
def delete_clip(clip_id: str, index: int) -> dict:
    """Remove one generated clip (deletes the file and drops it from history)."""
    if history.clip_path(clip_id, index) is None:
        raise HTTPException(status_code=400, detail="Invalid clip reference.")
    deleted = history.remove_clip(clip_id, index)
    return {"status": "ok", "deleted": deleted}


class ReframeRequest(BaseModel):
    """Body for POST /api/clip/{clip_id}/{index}/reframe."""

    keyframes: list[dict] = Field(
        default_factory=list,
        description="Manual crop keyframes: [{time, pos_x, pos_y}, ...]. Empty "
        "list resets to the default centred crop.",
    )


@app.get("/api/clip/{clip_id}/{index}/source")
def clip_source(clip_id: str, index: int) -> FileResponse:
    """Stream the ORIGINAL (uncropped) source segment behind one clip, for the
    Reframe Editor — it needs the full frame to let the user reposition the
    crop, not the already-cropped output."""
    recipe = reframe.get_recipe(clip_id, index)
    if recipe is None:
        raise HTTPException(
            status_code=404,
            detail="No render recipe for this clip (the server may have restarted since it was generated).",
        )
    return FileResponse(recipe["source_mp4"])


@app.get("/api/clip/{clip_id}/{index}/reframe")
def get_reframe_info(clip_id: str, index: int) -> dict:
    """The clip's trim range (start/end, seconds into the source) — the
    Reframe Editor needs this to know what span of the source video to show."""
    recipe = reframe.get_recipe(clip_id, index)
    if recipe is None:
        raise HTTPException(status_code=404, detail="No render recipe for this clip.")
    return {"start": recipe["start"], "end": recipe["end"]}


@app.post("/api/clip/{clip_id}/{index}/reframe")
def reframe_clip(clip_id: str, index: int, req: ReframeRequest) -> dict:
    """Re-render ONE clip with a manual crop-position path, in place.

    Reuses the exact recipe (source file, trim range, captions, effects,
    music, watermark) saved when the clip was first generated — only the crop
    keyframes change, and only this one file is touched.
    """
    if history.clip_path(clip_id, index) is None:
        raise HTTPException(status_code=400, detail="Invalid clip reference.")
    recipe = reframe.get_recipe(clip_id, index)
    if recipe is None:
        raise HTTPException(
            status_code=404,
            detail="No render recipe for this clip (the server may have restarted since it was generated).",
        )
    opts = ClipOptions(
        clip_id=clip_id,
        index=index,
        reframe=req.keyframes or None,
        **recipe["opts_kwargs"],
    )
    try:
        generate_clip(Path(recipe["source_mp4"]), recipe["start"], recipe["end"], opts)
    except ClipGenerationError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"status": "ok", "url": f"/clips/{clip_id}/{index}.mp4?v={uuid.uuid4().hex[:8]}"}


@app.post("/api/reveal")
def reveal_clip(ref: ClipRef) -> dict:
    """Open the clip's folder in the OS file manager with the file selected.

    Local-only convenience (this app runs on the user's own machine). The path is
    validated to live under the clips directory before anything is launched.
    """
    path = history.clip_path(ref.clip_id, ref.index)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="Clip not found on disk.")
    try:
        if sys.platform.startswith("win"):
            # explorer returns a non-zero exit code even on success — ignore it.
            subprocess.run(["explorer", "/select,", str(path)], check=False)
        elif sys.platform == "darwin":
            subprocess.run(["open", "-R", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path.parent)], check=False)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Could not open the folder: {exc}")
    return {"status": "ok"}


@app.get("/")
def index() -> FileResponse:
    """Serve the frontend.

    Prefer the built React dashboard (web/dist) so the backend and the dev server
    show the SAME app; fall back to the legacy vanilla page only if no build exists.
    ``no-store`` keeps the browser from pinning a stale index that points at old,
    since-rebuilt asset hashes (the "old UI until hard refresh" bug).
    """
    react_index = WEB_DIST_DIR / "index.html"
    target = react_index if react_index.is_file() else (STATIC_DIR / "index.html")
    return FileResponse(str(target), headers={"Cache-Control": "no-store"})


@app.post("/api/generate")
def generate(req: GenerateRequest) -> dict:
    """Start the pipeline on a background thread and return a job id.

    The actual work (download/transcribe/select/render) runs asynchronously; the
    client subscribes to ``/api/progress/{job_id}`` for live progress and the
    final clips.
    """
    job = jobs.create_job(req)
    jobs.start_job(job)
    logger.info("[%s] job accepted", job.id)
    return {"job_id": job.id}


@app.get("/api/transcript/{source_id}")
def get_transcript(source_id: str, language: Optional[str] = None) -> dict:
    """Return the cached transcript's segments (timestamp + text) for the sidebar.

    Mirrors ``/api/music-suggest``: reads whatever pretranscribe already cached,
    falling back to the auto-detected-language transcript if a forced language
    hasn't been (re)transcribed yet.
    """
    tr = pretranscribe.cached(source_id, language) or pretranscribe.cached(source_id, None)
    if not tr:
        return {"ready": False}
    return {
        "ready": True,
        "language": tr.get("language"),
        "duration": tr.get("duration"),
        "segments": tr.get("segments") or [],
    }


@app.get("/api/music-suggest/{source_id}")
def music_suggest(source_id: str, language: Optional[str] = None) -> dict:
    """Suggest a music mood (sad/happy/romantic/…) from the prepared transcript."""
    tr = pretranscribe.cached(source_id, language) or pretranscribe.cached(source_id, None)
    if not tr:
        return {"ready": False}
    segs = tr.get("segments") or []
    text = " ".join((s.get("text") or "") for s in segs)
    return {"ready": True, **mood.suggest_mood(text)}


@app.post("/api/cancel/{job_id}")
def cancel(job_id: str) -> dict:
    """Flag a running job for cancellation; it stops at the next clip boundary."""
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job id.")
    job.cancel()
    logger.info("[%s] cancel requested", job_id)
    return {"status": "cancelled"}


@app.get("/api/progress/{job_id}")
async def progress(job_id: str) -> StreamingResponse:
    """Stream a job's progress as Server-Sent Events until it finishes."""
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job id.")

    async def event_stream():
        last_rev = -1
        while True:
            snap = job.snapshot()
            if snap["rev"] != last_rev:
                last_rev = snap["rev"]
                yield f"data: {json.dumps(snap)}\n\n"
            if snap["status"] in ("done", "error"):
                break
            await asyncio.sleep(0.3)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/result/{job_id}")
def result(job_id: str) -> dict:
    """Return the current snapshot of a job (useful after a stream reconnect)."""
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job id.")
    return job.snapshot()


# Catch-all guard: turn any unexpected error into a clean 500 (no crash).
@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):  # noqa: ANN001
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Unexpected server error: {exc}"},
    )
