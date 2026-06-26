"""Background pre-transcription so Whisper runs while the user is still tweaking
settings — by the time they hit Generate the transcript is already cached.

Transcription depends only on the source video + compute device (NOT on caption
style, aspect ratio, clip count, etc.), so it's safe to start as soon as the
video is on disk. Results are cached per source-file id and reused by the
pipeline, which then skips the (usually slowest) transcribe stage entirely.

A single lock serialises all transcription: the local Whisper model is shared,
and running two transcriptions at once isn't worth the risk on a single-user
tool. Double-checking the cache inside that lock means a Generate run that
arrives while a pre-transcription is mid-flight simply waits for it and then
reuses the result — the same video is never transcribed twice.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from pathlib import Path
from typing import Callable, Dict, Optional

from . import transcriber, uploads
from .models import InvalidVideoURLError, TranscriptionError
from .paths import TRANSCRIPTS_DIR

logger = logging.getLogger("ai_video_clipper.pretranscribe")

# transcript identity key (source file stem + chosen language) -> transcript dict.
# Including the language means switching languages re-transcribes instead of
# reusing a transcript decoded in the wrong language.
_CACHE: Dict[str, dict] = {}
_CACHE_LOCK = threading.Lock()
# Serialises access to the shared Whisper model (and dedupes same-source work).
_TRANSCRIBE_LOCK = threading.Lock()


def _key(source_id: str, language: Optional[str]) -> str:
    """Cache / transcript-file key for a source at a given language ('auto' = detect)."""
    lang = (language or "auto").strip().lower() or "auto"
    return f"{source_id}__{lang}"


def cached(source_id: str, language: Optional[str] = None) -> Optional[dict]:
    """Return an in-memory cached transcript for this source+language, if any."""
    with _CACHE_LOCK:
        return _CACHE.get(_key(source_id, language))


def get_or_transcribe(
    source_path: Path,
    source_id: str,
    device: str,
    progress: Optional[Callable[[float, str], None]] = None,
    language: Optional[str] = None,
) -> dict:
    """Return a cached transcript for this source+language, or transcribe + cache it.

    Concurrency-safe: if another thread is already transcribing this source, this
    call blocks on the lock and then returns the freshly-cached result instead of
    transcribing again. Also reuses a transcript persisted on disk (survives
    restarts / in-memory cache misses). The chosen ``language`` is part of the
    cache identity, so the same video can hold a separate transcript per language.
    """
    key = _key(source_id, language)
    hit = cached(source_id, language)
    if hit is not None:
        return hit

    with _TRANSCRIBE_LOCK:
        # Re-check now that we hold the lock — a concurrent run may have finished.
        hit = cached(source_id, language)
        if hit is not None:
            return hit

        # Disk fallback: a previous run (or session) may have already saved it.
        tpath = TRANSCRIPTS_DIR / f"{key}.json"
        if tpath.exists():
            try:
                result = json.loads(tpath.read_text(encoding="utf-8"))
                with _CACHE_LOCK:
                    _CACHE[key] = result
                logger.info("Reusing transcript on disk for %s", key)
                return result
            except Exception:  # noqa: BLE001 - corrupt/partial json -> re-transcribe
                logger.warning("Ignoring unreadable transcript %s", tpath, exc_info=True)

        result = transcriber.transcribe_video(
            source_path, key, progress=progress, device=device, language=language
        )
        with _CACHE_LOCK:
            _CACHE[key] = result
        return result


# --------------------------------------------------------------------------- #
# Background job (so the UI can show "transcribing in the background" progress)
# --------------------------------------------------------------------------- #
class TranscriptJob:
    """A single background pre-transcription with thread-safe progress state."""

    def __init__(self, source_id: str, device: str, language: Optional[str] = None) -> None:
        self.id = uuid.uuid4().hex
        self.source_id = source_id
        self.device = device
        self.language = language
        self.status = "running"  # running | done | error
        self.progress = 0.0
        self.message = "Preparing transcription..."
        self.error: Optional[str] = None
        self._lock = threading.Lock()
        self._rev = 0

    def update(self, **fields) -> None:
        with self._lock:
            for key, value in fields.items():
                setattr(self, key, value)
            self._rev += 1

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "id": self.id,
                "status": self.status,
                "progress": round(self.progress, 4),
                "message": self.message,
                "error": self.error,
                "rev": self._rev,
            }


_JOBS: Dict[str, TranscriptJob] = {}
_JOBS_LOCK = threading.Lock()


def get(job_id: str) -> Optional[TranscriptJob]:
    with _JOBS_LOCK:
        return _JOBS.get(job_id)


def find_running(source_id: str) -> Optional[TranscriptJob]:
    """Return a still-running background transcription for this source, if any.

    Lets the Generate pipeline mirror an in-flight pre-transcription's live
    progress (instead of a frozen bar) while it waits on the shared model lock.
    """
    with _JOBS_LOCK:
        for job in _JOBS.values():
            if job.source_id == source_id and job.status == "running":
                return job
    return None


def start(source_id: str, device: str, language: Optional[str] = None) -> TranscriptJob:
    """Begin pre-transcribing `source_id` on a daemon thread."""
    job = TranscriptJob(source_id, device, language)
    with _JOBS_LOCK:
        _JOBS[job.id] = job
    threading.Thread(target=_run, args=(job,), daemon=True).start()
    logger.info(
        "[%s] pretranscribe started: source=%s device=%s language=%s",
        job.id, source_id, device, language or "auto",
    )
    return job


def _run(job: TranscriptJob) -> None:
    if cached(job.source_id, job.language) is not None:
        job.update(status="done", progress=1.0, message="Transcript ready.")
        return
    try:
        path = uploads.resolve_upload(job.source_id)
    except InvalidVideoURLError as exc:
        job.update(status="error", error=str(exc), message="Source file not found.")
        return

    def on_progress(frac: float, msg: str) -> None:
        job.update(progress=min(0.99, frac), message=msg)

    try:
        get_or_transcribe(
            path, job.source_id, job.device, progress=on_progress, language=job.language
        )
        job.update(status="done", progress=1.0, message="Transcript ready.")
        logger.info("[%s] pretranscribe done", job.id)
    except TranscriptionError as exc:
        logger.warning("[%s] pretranscribe failed: %s", job.id, exc)
        job.update(status="error", error=str(exc), message="Could not pre-transcribe.")
    except Exception as exc:  # noqa: BLE001 - never let the thread die silently
        logger.exception("[%s] unexpected pretranscribe failure", job.id)
        job.update(
            status="error",
            error=f"Unexpected error: {exc}",
            message="Could not pre-transcribe.",
        )
