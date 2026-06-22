"""Download the source video with yt-dlp (the only video-fetch network call).

We use the yt-dlp *Python API* rather than shelling out so failures surface as
exceptions we can translate into a clean 400. The server must never crash on a
bad or blocked URL.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Callable, Optional

import yt_dlp

from .models import InvalidVideoURLError
from .paths import DOWNLOADS_DIR

logger = logging.getLogger(__name__)


def download_video(
    url: str, progress_hook: Optional[Callable[[dict], None]] = None
) -> Path:
    """Download `url` to downloads/<uuid>.mp4 and return the file path.

    Args:
        url: source video URL.
        progress_hook: optional yt-dlp progress callback (receives the raw
            progress dict with ``status``/``downloaded_bytes``/``total_bytes``)
            so callers can surface live download progress.

    Raises:
        InvalidVideoURLError: on any download failure, with a readable message.
    """
    if not url or not url.strip():
        raise InvalidVideoURLError("No video URL was provided.")

    clip_uuid = uuid.uuid4().hex
    # yt-dlp fills in the real extension; we force a merge to mp4 below so the
    # final file is downloads/<uuid>.mp4.
    out_template = str(DOWNLOADS_DIR / f"{clip_uuid}.%(ext)s")
    expected_path = DOWNLOADS_DIR / f"{clip_uuid}.mp4"

    ydl_opts = {
        # Prefer the best stream up to 1080p (plenty for shorts, avoids slow 4K
        # downloads). Container is normalised to mp4 by merge_output_format, so
        # we don't restrict by extension - that was too strict and could fall
        # back to a tiny stream when no progressive mp4 existed.
        "format": (
            "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
        ),
        "merge_output_format": "mp4",
        "outtmpl": out_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        # Be resilient: keep going if a single fragment hiccups.
        "ignoreerrors": False,
    }
    if progress_hook is not None:
        ydl_opts["progress_hooks"] = [progress_hook]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url.strip()])
    except yt_dlp.utils.DownloadError as exc:
        logger.warning("yt-dlp DownloadError for %s: %s", url, exc)
        raise InvalidVideoURLError(
            "Could not download that video. Check the URL is correct, public, "
            "and reachable from this machine."
        ) from exc
    except Exception as exc:  # noqa: BLE001 - never let the server crash here
        logger.exception("Unexpected download failure for %s", url)
        raise InvalidVideoURLError(
            f"Unexpected error while downloading the video: {exc}"
        ) from exc

    if expected_path.exists():
        return expected_path

    # Some sources may not produce exactly <uuid>.mp4 (e.g. a different
    # container survived the merge). Fall back to any file with our uuid prefix.
    candidates = sorted(DOWNLOADS_DIR.glob(f"{clip_uuid}.*"))
    if candidates:
        return candidates[0]

    raise InvalidVideoURLError(
        "The download completed but no output file was produced. The video may "
        "be unavailable or region-locked."
    )
