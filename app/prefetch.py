"""Background pre-download of URL videos so the file is ready before Generate.

When the user moves to the configuration step (Step 2) with a pasted link, the
frontend asks us to start fetching the video immediately. The download then runs
on a daemon thread while the user adjusts settings, and its progress is polled
over ``GET /api/prefetch/{id}``. When it finishes we expose a ``download_id`` —
the stem of ``downloads/<id>.mp4`` — which the pipeline reuses (via the same
``uploads.resolve_upload`` glob) so ``POST /api/generate`` skips the download
entirely instead of fetching the same video twice.

Everything is in-memory and single-process, matching ``jobs.py``. A prefetch
that the user never generates from simply leaves its file in ``downloads/`` —
the same as a normal pipeline download today.
"""

from __future__ import annotations

import logging
import threading
import uuid
from typing import Dict, Optional

from . import downloader
from .models import InvalidVideoURLError

logger = logging.getLogger("ai_video_clipper.prefetch")


class Prefetch:
    """A single background download with thread-safe progress state."""

    def __init__(self, url: str) -> None:
        self.id = uuid.uuid4().hex
        self.url = url
        self.status = "running"  # running | done | error
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.progress = 0.0  # 0..1
        self.message = "Starting download..."
        self.download_id: Optional[str] = None  # set when done (reuse handle)
        self.error: Optional[str] = None
        self._lock = threading.Lock()
        self._rev = 0  # bumped on every change (lets the UI detect updates)

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
                "downloaded_bytes": self.downloaded_bytes,
                "total_bytes": self.total_bytes,
                "message": self.message,
                "download_id": self.download_id,
                "error": self.error,
                "rev": self._rev,
            }


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
_PREFETCHES: Dict[str, Prefetch] = {}
_LOCK = threading.Lock()


def get(prefetch_id: str) -> Optional[Prefetch]:
    with _LOCK:
        return _PREFETCHES.get(prefetch_id)


def start(url: str) -> Prefetch:
    """Create a prefetch and begin downloading `url` on a daemon thread."""
    pf = Prefetch(url)
    with _LOCK:
        _PREFETCHES[pf.id] = pf
    threading.Thread(target=_run, args=(pf,), daemon=True).start()
    logger.info("[%s] prefetch started: %s", pf.id, url)
    return pf


# --------------------------------------------------------------------------- #
# Downloader thread
# --------------------------------------------------------------------------- #
def _run(pf: Prefetch) -> None:
    def hook(d: dict) -> None:
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            if total:
                pf.update(
                    downloaded_bytes=done,
                    total_bytes=total,
                    progress=min(0.99, done / total),
                    message=f"Downloading video... {int(done * 100 / total)}%",
                )
            else:
                pf.update(
                    downloaded_bytes=done,
                    message=f"Downloading video... {done / 1_048_576:.1f} MB",
                )
        elif status == "finished":
            pf.update(progress=0.99, message="Finalizing download...")

    try:
        path = downloader.download_video(pf.url, progress_hook=hook)
        # The file lives at downloads/<id>.<ext>; its stem is a 32-char hex id the
        # pipeline can resolve exactly like an upload reference.
        pf.update(
            status="done",
            progress=1.0,
            download_id=path.stem,
            message="Video download completed",
        )
        logger.info("[%s] prefetch done -> %s", pf.id, path.name)
    except InvalidVideoURLError as exc:
        logger.warning("[%s] prefetch failed: %s", pf.id, exc)
        pf.update(status="error", error=str(exc), message=str(exc))
    except Exception as exc:  # noqa: BLE001 - never let the thread die silently
        logger.exception("[%s] unexpected prefetch failure", pf.id)
        pf.update(
            status="error",
            error=f"Unexpected error while downloading: {exc}",
            message="Download failed.",
        )
