"""Persistent history of generated clips.

Jobs live only in memory (cleared on restart), but the rendered clips survive on
disk. This module records a small JSON manifest next to them so the UI can show a
"Video clips" history that persists across restarts, and can remove clips or
reveal them in the OS file manager.

Every generation appends one entry (a job and its clips). The store is a single
JSON file guarded by a lock; this is a local, single-user tool so that is plenty.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .paths import CLIPS_DIR

logger = logging.getLogger(__name__)

HISTORY_FILE = CLIPS_DIR / "history.json"
_LOCK = threading.Lock()

# clip_id is a 32-char hex uuid; index is a small non-negative int. Validating
# both means a request can never reach a path outside the clips directory.
_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def clip_path(clip_id: str, index: int) -> Optional[Path]:
    """Resolve clips/<clip_id>/<index>.mp4, or None if the reference is invalid."""
    if not _ID_RE.match(clip_id or "") or not isinstance(index, int) or index < 0:
        return None
    path = (CLIPS_DIR / clip_id / f"{index}.mp4").resolve()
    # Defence in depth: the resolved path must stay under clips/.
    if CLIPS_DIR.resolve() not in path.parents:
        return None
    return path


def _load() -> list:
    if not HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        logger.warning("history.json was unreadable; starting a fresh history.")
        return []


def _save(entries: list) -> None:
    try:
        HISTORY_FILE.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as exc:
        logger.warning("Could not write history.json: %s", exc)


def add_entry(
    clip_id: str,
    source: str,
    settings: dict,
    clips: List[dict],
    source_type: str = "url",
) -> None:
    """Record one finished generation (a job and the clips it produced).

    ``source`` is a human label (the URL, or an uploaded file's name) and
    ``source_type`` is "url" or "upload" so the UI can show the right icon.
    """
    entry = {
        "clip_id": clip_id,
        "created": datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "source_type": source_type,
        "settings": settings,
        "clips": clips,
    }
    with _LOCK:
        entries = _load()
        entries.append(entry)
        _save(entries)


def list_entries() -> list:
    """All entries, newest first, each clip annotated with whether it still exists."""
    with _LOCK:
        entries = _load()
    for e in entries:
        for c in e.get("clips", []):
            p = clip_path(e.get("clip_id", ""), c.get("index", -1))
            c["exists"] = bool(p and p.exists())
    entries.sort(key=lambda e: e.get("created", ""), reverse=True)
    return entries


def remove_clip(clip_id: str, index: int) -> bool:
    """Delete one clip file and drop it from history. Returns True if a file went."""
    path = clip_path(clip_id, index)
    deleted = False
    if path and path.exists():
        try:
            path.unlink()
            deleted = True
        except OSError as exc:
            logger.warning("Could not delete clip %s/%s: %s", clip_id, index, exc)

    with _LOCK:
        entries = _load()
        for e in entries:
            if e.get("clip_id") == clip_id:
                e["clips"] = [c for c in e.get("clips", []) if c.get("index") != index]
        # Drop entries that have no clips left, and clean their (now empty) folder.
        kept = []
        for e in entries:
            if e.get("clips"):
                kept.append(e)
            else:
                folder = CLIPS_DIR / e.get("clip_id", "")
                if _ID_RE.match(e.get("clip_id", "")) and folder.exists():
                    shutil.rmtree(folder, ignore_errors=True)
        _save(kept)
    return deleted
