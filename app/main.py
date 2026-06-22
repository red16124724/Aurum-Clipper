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
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import captions, history, jobs, transcriber, uploads
from .models import Device, GenerateRequest, InvalidVideoURLError, TranscriptionError
from .fonts import ensure_fonts
from .paths import CLIPS_DIR, STATIC_DIR, ensure_dirs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("ai_video_clipper")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create dirs, ensure the font, and load whisper ONCE before serving."""
    ensure_dirs()
    ensure_fonts()
    transcriber.load_model()
    logger.info(
        "Startup complete. Whisper '%s' on %s. No external AI APIs are used.",
        transcriber.MODEL_SIZE,
        transcriber.get_device(),
    )
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


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "device": transcriber.get_device()}


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
    """Serve the single-page frontend."""
    return FileResponse(str(STATIC_DIR / "index.html"))


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
