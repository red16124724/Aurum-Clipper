"""Background job model + in-memory registry for the clip pipeline.

The full pipeline (download -> transcribe -> select -> render) can take minutes,
so running it inside the HTTP request would make the browser appear frozen. Each
request instead creates a :class:`Job`, runs the pipeline on a daemon thread, and
reports fine-grained progress that the frontend streams live (see the SSE
endpoint in ``main.py``).

Everything is in-memory and single-process - perfect for this local, single-user
tool. Restarting the server clears jobs (the rendered clips on disk survive).
"""

from __future__ import annotations

import logging
import threading
import uuid
from typing import Dict, List, Optional

from . import captions, downloader, history, selector, transcriber, uploads
from .clipper import ClipOptions, generate_clip, target_size
from .models import (
    ClipGenerationError,
    GenerateRequest,
    InvalidVideoURLError,
    TranscriptionError,
)
from .paths import CLIPS_DIR

logger = logging.getLogger("ai_video_clipper.jobs")


# Overall-progress span (0..1) owned by each stage. The per-stage fraction is
# mapped into these bands so the single top progress bar advances smoothly across
# the whole pipeline rather than jumping per stage.
_STAGE_SPANS = {
    "queued": (0.0, 0.0),
    "downloading": (0.02, 0.25),
    "transcribing": (0.25, 0.70),
    "selecting": (0.70, 0.74),
    "rendering": (0.74, 0.99),
    "done": (1.0, 1.0),
    "error": (0.0, 0.0),
}

# Human labels for the stepper in the UI.
STAGE_LABELS = {
    "downloading": "Download",
    "transcribing": "Transcribe",
    "selecting": "Analyze",
    "rendering": "Render",
}


class Job:
    """A single pipeline run with thread-safe progress + result state."""

    def __init__(self, req: GenerateRequest) -> None:
        self.id = uuid.uuid4().hex
        self.req = req
        self.status = "queued"  # queued | running | done | error
        self.stage = "queued"
        self.stage_progress = 0.0  # 0..1 within the current stage
        self.progress = 0.0  # 0..1 overall (derived from stage span)
        self.message = "Queued..."
        self.clips: List[dict] = []
        self.error: Optional[str] = None
        self.clip_id: Optional[str] = None
        self._lock = threading.Lock()
        self._rev = 0  # bumped on every change so the SSE stream only sends diffs

    # -- mutation ---------------------------------------------------------- #
    def set_stage(self, stage: str, frac: float, message: str) -> None:
        """Move to/within a stage and recompute the overall progress band."""
        frac = min(1.0, max(0.0, frac))
        lo, hi = _STAGE_SPANS.get(stage, (0.0, 0.0))
        with self._lock:
            self.status = "running"
            self.stage = stage
            self.stage_progress = frac
            self.progress = lo + frac * (hi - lo)
            self.message = message
            self._rev += 1

    def add_clip(self, clip: dict) -> None:
        """Publish a finished clip so the UI can show it before the run ends."""
        with self._lock:
            self.clips.append(clip)
            self._rev += 1

    def finish(self, clips: List[dict]) -> None:
        with self._lock:
            self.status = "done"
            self.stage = "done"
            self.stage_progress = 1.0
            self.progress = 1.0
            self.message = f"Done - {len(clips)} clip(s) ready."
            self.clips = clips
            self._rev += 1

    def fail(self, message: str) -> None:
        with self._lock:
            self.status = "error"
            self.stage = "error"
            self.error = message
            self.message = message
            self._rev += 1

    # -- read -------------------------------------------------------------- #
    def snapshot(self) -> dict:
        """Return a JSON-serialisable view of the current state."""
        with self._lock:
            return {
                "id": self.id,
                "status": self.status,
                "stage": self.stage,
                "stage_progress": round(self.stage_progress, 4),
                "progress": round(self.progress, 4),
                "message": self.message,
                "clips": list(self.clips),
                "error": self.error,
                "clip_id": self.clip_id,
                "rev": self._rev,
            }


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
_JOBS: Dict[str, Job] = {}
_JOBS_LOCK = threading.Lock()


def create_job(req: GenerateRequest) -> Job:
    job = Job(req)
    with _JOBS_LOCK:
        _JOBS[job.id] = job
    return job


def get_job(job_id: str) -> Optional[Job]:
    with _JOBS_LOCK:
        return _JOBS.get(job_id)


def start_job(job: Job) -> None:
    """Run the pipeline for `job` on a background daemon thread."""
    thread = threading.Thread(target=_run_pipeline, args=(job,), daemon=True)
    thread.start()


# --------------------------------------------------------------------------- #
# Pipeline runner
# --------------------------------------------------------------------------- #
def _run_pipeline(job: Job) -> None:
    """download -> transcribe -> select -> render, updating `job` throughout."""
    req = job.req
    logger.info("[%s] starting pipeline: %s", job.id, req.model_dump())

    try:
        # 1) Get the source video: a previously uploaded file, or a URL download.
        if req.upload_id:
            job.set_stage("downloading", 0.2, "Loading uploaded video...")
            source_mp4 = uploads.resolve_upload(req.upload_id)
            job.set_stage("downloading", 1.0, "Uploaded video ready. Preparing...")
        else:
            job.set_stage("downloading", 0.0, "Starting download...")

            def on_download(d: dict) -> None:
                status = d.get("status")
                if status == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate")
                    done = d.get("downloaded_bytes") or 0
                    if total:
                        pct = int(done * 100 / total)
                        job.set_stage("downloading", done / total, f"Downloading video... {pct}%")
                    else:
                        mb = done / 1_048_576
                        job.set_stage("downloading", 0.1, f"Downloading video... {mb:.1f} MB")
                elif status == "finished":
                    job.set_stage("downloading", 1.0, "Download complete. Preparing...")

            source_mp4 = downloader.download_video(req.video_url, progress_hook=on_download)

        # 2) Transcribe locally (word timestamps) on the requested device.
        clip_id = uuid.uuid4().hex
        job.clip_id = clip_id
        device_label = {"auto": "Auto", "cuda": "GPU", "cpu": "CPU"}.get(
            req.device.value, "Auto"
        )
        job.set_stage(
            "transcribing", 0.0, f"Transcribing audio with local Whisper ({device_label})..."
        )

        def on_transcribe(frac: float, msg: str) -> None:
            job.set_stage("transcribing", frac, msg)

        transcript = transcriber.transcribe_video(
            source_mp4, clip_id, progress=on_transcribe, device=req.device.value
        )

        # 3) Select clips (local heuristic, optional local Ollama).
        job.set_stage("selecting", 0.3, "Analyzing transcript for the best moments...")
        windows = selector.select_clips(transcript, req.num_clips)
        if not windows:
            raise ClipGenerationError(
                "Could not find any suitable clip windows in this video. "
                "Try a longer video or fewer clips."
            )
        job.set_stage("selecting", 1.0, f"Found {len(windows)} clip(s) to render.")

        # 4) Per clip: build ASS captions + render with ffmpeg. The caption canvas
        # must match the actual output frame (1:1 in square mode, aspect otherwise).
        words = transcript.get("words") or []
        width, height = target_size(req.aspect_ratio, req.fit_mode)
        clip_dir = CLIPS_DIR / clip_id
        clip_dir.mkdir(parents=True, exist_ok=True)

        results: List[dict] = []
        total = len(windows)
        for index, win in enumerate(windows):
            start, end = float(win["start"]), float(win["end"])
            job.set_stage(
                "rendering",
                index / total,
                f"Rendering clip {index + 1} of {total}...",
            )

            clip_words = [w for w in words if w["end"] > start and w["start"] < end]
            ass_path = clip_dir / f"{index}.ass"
            captions.build_ass(
                words=clip_words,
                style_preset=req.caption_style,
                video_w=width,
                video_h=height,
                out_path=ass_path,
                clip_start=start,
            )

            opts = ClipOptions(
                aspect_ratio=req.aspect_ratio,
                fit_mode=req.fit_mode,
                ass_path=ass_path,
                clip_id=clip_id,
                index=index,
                bar_text=req.bar_text,
            )
            generate_clip(source_mp4, start, end, opts)

            clip = {
                "index": index,
                "title": win.get("title") or f"Clip {index + 1}",
                "start": round(start, 2),
                "end": round(end, 2),
                "url": f"/clips/{clip_id}/{index}.mp4",
            }
            results.append(clip)
            job.add_clip(clip)  # stream the finished clip to the UI immediately

        job.finish(results)
        logger.info("[%s] pipeline complete: %d clips", job.id, len(results))

        # Persist to history so the History panel survives restarts. Use a
        # meaningful label: the uploaded file's name, or the source URL.
        if req.upload_id:
            source_label = req.upload_name or "Uploaded file"
            source_type = "upload"
        else:
            source_label = req.video_url or "Unknown source"
            source_type = "url"
        try:
            history.add_entry(
                clip_id=clip_id,
                source=source_label,
                source_type=source_type,
                settings={
                    "aspect_ratio": req.aspect_ratio.value,
                    "fit_mode": req.fit_mode.value,
                    "caption_style": req.caption_style,
                    "num_clips": req.num_clips,
                },
                clips=results,
            )
        except Exception:  # noqa: BLE001 - history is best-effort, never fail the job
            logger.warning("[%s] could not write history entry", job.id, exc_info=True)

    except InvalidVideoURLError as exc:
        logger.warning("[%s] download error: %s", job.id, exc)
        job.fail(str(exc))
    except TranscriptionError as exc:
        logger.warning("[%s] transcription error: %s", job.id, exc)
        job.fail(str(exc))
    except ClipGenerationError as exc:
        logger.warning("[%s] render error: %s", job.id, exc)
        job.fail(str(exc))
    except Exception as exc:  # noqa: BLE001 - never let a thread die silently
        logger.exception("[%s] unexpected pipeline failure", job.id)
        job.fail(f"Unexpected error: {exc}")
