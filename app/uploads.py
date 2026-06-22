"""Local file uploads as an alternative video source to a URL.

A user can upload a video straight from their machine instead of providing a URL.
We stream the file to ``downloads/<uuid><ext>`` (the same place yt-dlp writes to)
and hand the pipeline a reference (``upload_id``) it can resolve back to a path.

The id is a 32-char hex uuid we generate ourselves, and resolution only ever
globs ``downloads/<id>.*`` - so a caller can never use the id to reach a file
outside the downloads directory (no path traversal).
"""

from __future__ import annotations

import logging
import re
import shutil
import uuid
from pathlib import Path
from typing import BinaryIO

from .models import InvalidVideoURLError
from .paths import DOWNLOADS_DIR

logger = logging.getLogger(__name__)

# Container formats ffmpeg/whisper can handle. Extension is a cheap first gate;
# ffmpeg is the real validator when it tries to read the file.
ALLOWED_EXTS = {
    ".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v",
    ".flv", ".wmv", ".mpeg", ".mpg", ".ts", ".m2ts",
}

_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def save_upload(filename: str, fileobj: BinaryIO) -> dict:
    """Stream an uploaded file to downloads/ and return its reference.

    Args:
        filename: the client-supplied name (used only for its extension/label).
        fileobj: a binary file-like object to copy from.

    Returns:
        ``{"upload_id": <hex>, "filename": <name>, "ext": <ext>}``.

    Raises:
        InvalidVideoURLError: unsupported extension or empty file.
    """
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise InvalidVideoURLError(
            f"Unsupported file type '{ext or 'unknown'}'. Please upload a video "
            f"file ({', '.join(sorted(ALLOWED_EXTS))})."
        )

    upload_id = uuid.uuid4().hex
    dest = DOWNLOADS_DIR / f"{upload_id}{ext}"
    try:
        with dest.open("wb") as out:
            shutil.copyfileobj(fileobj, out, length=1024 * 1024)
    except OSError as exc:
        logger.exception("Failed to save upload %s", filename)
        raise InvalidVideoURLError(f"Could not save the uploaded file: {exc}") from exc

    if not dest.exists() or dest.stat().st_size == 0:
        dest.unlink(missing_ok=True)
        raise InvalidVideoURLError("The uploaded file was empty.")

    logger.info("Saved upload %s -> %s (%d bytes)", filename, dest.name, dest.stat().st_size)
    return {"upload_id": upload_id, "filename": Path(filename or "video").name, "ext": ext}


def resolve_upload(upload_id: str) -> Path:
    """Map an ``upload_id`` back to the saved file path.

    Raises:
        InvalidVideoURLError: malformed id or file no longer present.
    """
    if not upload_id or not _ID_RE.match(upload_id):
        raise InvalidVideoURLError("Invalid upload reference.")
    matches = sorted(DOWNLOADS_DIR.glob(f"{upload_id}.*"))
    if not matches:
        raise InvalidVideoURLError(
            "The uploaded file could not be found. Please upload it again."
        )
    return matches[0]
