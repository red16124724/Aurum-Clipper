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
import subprocess
import tempfile
from pathlib import Path
from typing import BinaryIO

from .models import InvalidVideoURLError
from .paths import MUSIC_DIR

logger = logging.getLogger(__name__)

ALLOWED_MUSIC_EXTS = {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac"}
# Video containers we accept too — we don't keep the video, just rip its audio
# track into an .m4a so it can be used as background music.
ALLOWED_VIDEO_EXTS = {
    ".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v",
    ".flv", ".wmv", ".mpeg", ".mpg", ".ts", ".m2ts",
}


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
    """Save an uploaded track into the music library. Returns ``{name, file}``.

    Audio files are stored as-is. Video files (mp4, mov, …) are accepted too —
    we keep only their audio track, ripped to an ``.m4a`` so the video itself is
    never stored.

    Raises:
        InvalidVideoURLError: unsupported extension, empty file, or no audio.
    """
    ext = Path(filename or "").suffix.lower()
    is_video = ext in ALLOWED_VIDEO_EXTS
    if ext not in ALLOWED_MUSIC_EXTS and not is_video:
        raise InvalidVideoURLError(
            f"Unsupported file type '{ext or 'unknown'}'. Upload audio "
            "(mp3, m4a, wav, aac, ogg, flac) or a video (mp4, mov, mkv, webm…) "
            "to use its sound."
        )
    data = fileobj.read()
    if not data:
        raise InvalidVideoURLError("The uploaded music file was empty.")

    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    if is_video:
        return _save_audio_from_video(filename, data)

    safe = re.sub(r"[^A-Za-z0-9._ -]", "_", Path(filename).name) or f"track{ext}"
    dest = MUSIC_DIR / safe
    try:
        dest.write_bytes(data)
    except OSError as exc:
        raise InvalidVideoURLError(f"Could not save the music: {exc}") from exc
    logger.info("Saved music track %s", safe)
    return {"name": _pretty(safe), "file": safe}


def _save_audio_from_video(filename: str, data: bytes) -> dict:
    """Rip the audio track out of an uploaded video and save it as ``.m4a``.

    The video bytes go to a temp file, ffmpeg extracts the audio (re-encoded to
    AAC so any source codec works), and only the resulting ``.m4a`` is kept in
    the music library.

    Raises:
        InvalidVideoURLError: ffmpeg missing, the file has no audio, or it fails.
    """
    src_ext = Path(filename).suffix.lower() or ".mp4"
    stem = re.sub(r"[^A-Za-z0-9._ -]", "_", Path(filename).stem) or "track"
    out_name = _unique_name(f"{stem}.m4a")
    dest = MUSIC_DIR / out_name

    with tempfile.NamedTemporaryFile(suffix=src_ext, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)

    cmd = [
        "ffmpeg", "-y", "-i", str(tmp_path),
        "-vn",  # drop the video — audio only
        "-c:a", "aac", "-b:a", "192k",
        str(dest),
    ]
    try:
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
        )
    except FileNotFoundError as exc:
        raise InvalidVideoURLError(
            "ffmpeg was not found on PATH — it's needed to pull the audio out of a video."
        ) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    if proc.returncode != 0 or not dest.exists() or dest.stat().st_size == 0:
        dest.unlink(missing_ok=True)
        tail = (proc.stderr or "").strip().splitlines()[-6:]
        hint = "\n".join(tail)
        raise InvalidVideoURLError(
            "Couldn't get any audio out of that video (it may be silent or "
            "unreadable).\n" + hint
        )
    logger.info("Extracted music track %s from uploaded video %s", out_name, filename)
    return {"name": _pretty(out_name), "file": out_name}


def _unique_name(name: str) -> str:
    """Return ``name``, or ``name (2).ext`` etc. if it already exists in the library."""
    dest = MUSIC_DIR / name
    if not dest.exists():
        return name
    stem, ext = Path(name).stem, Path(name).suffix
    i = 2
    while (MUSIC_DIR / f"{stem} ({i}){ext}").exists():
        i += 1
    return f"{stem} ({i}){ext}"


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
