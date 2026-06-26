"""Background-music library.

Tracks come from two places, both inside ``assets/music/``:
  1. files the user drops into the folder by hand (a quick "paste and go"), and
  2. files uploaded through the UI.

Either way they're listed by ``list_tracks`` and selectable per render. The
mixing itself (ducking the music under the voice, reels-style) lives in
``clipper`` — this module only manages the files.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import BinaryIO

from .models import InvalidVideoURLError
from .paths import MUSIC_DIR

logger = logging.getLogger(__name__)

ALLOWED_MUSIC_EXTS = {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac"}


def _pretty(name: str) -> str:
    """A human label from a filename: drop the extension, tidy separators."""
    stem = Path(name).stem
    return re.sub(r"[_\-]+", " ", stem).strip() or stem


def list_tracks() -> list[dict]:
    """Return the available music tracks as ``{name, file}``, sorted by name.

    Scans ``assets/music/`` so anything pasted into the folder shows up too.
    """
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    tracks = []
    for p in sorted(MUSIC_DIR.iterdir(), key=lambda x: x.name.lower()):
        if p.is_file() and p.suffix.lower() in ALLOWED_MUSIC_EXTS:
            tracks.append({"name": _pretty(p.name), "file": p.name})
    return tracks


def save_track(filename: str, fileobj: BinaryIO) -> dict:
    """Save an uploaded audio file into the music library. Returns ``{name, file}``.

    Raises:
        InvalidVideoURLError: unsupported extension or empty file.
    """
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_MUSIC_EXTS:
        raise InvalidVideoURLError(
            f"Unsupported audio type '{ext or 'unknown'}'. Upload mp3, m4a, wav, aac, ogg or flac."
        )
    data = fileobj.read()
    if not data:
        raise InvalidVideoURLError("The uploaded music file was empty.")

    safe = re.sub(r"[^A-Za-z0-9._ -]", "_", Path(filename).name) or f"track{ext}"
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    dest = MUSIC_DIR / safe
    try:
        dest.write_bytes(data)
    except OSError as exc:
        raise InvalidVideoURLError(f"Could not save the music: {exc}") from exc
    logger.info("Saved music track %s", safe)
    return {"name": _pretty(safe), "file": safe}


def resolve_track(track: str) -> Path:
    """Resolve a track filename to a real path inside the music dir (path-safe).

    Raises:
        InvalidVideoURLError: if the file is missing or escapes the music dir.
    """
    if not track:
        raise InvalidVideoURLError("No music track was given.")
    # Only ever trust the bare filename — never a path.
    candidate = (MUSIC_DIR / Path(track).name).resolve()
    if MUSIC_DIR.resolve() not in candidate.parents or not candidate.is_file():
        raise InvalidVideoURLError("That music track was not found.")
    return candidate
