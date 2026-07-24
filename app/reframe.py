"""Per-clip render recipes, so "Reframe" can re-render ONE clip.

Every clip already goes through ``clipper.generate_clip(source_mp4, start,
end, opts)`` inside the batch pipeline (see ``jobs.py``). To let a user
manually reposition the crop later without re-running the whole
download -> transcribe -> select -> render pipeline for every other clip,
jobs.py saves the exact arguments that produced each clip here, keyed by
``clip_id`` + ``index``. The reframe endpoint (main.py) looks the recipe back
up, swaps in new crop keyframes, and re-renders just that one file in place.

In-memory only (like ``jobs.py``'s job registry) — recipes don't need to
survive a server restart; the clip files on disk already reflect the last
render either way.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

_RECIPES: dict[str, dict] = {}
_LOCK = threading.Lock()


def _key(clip_id: str, index: int) -> str:
    return f"{clip_id}:{index}"


def save_recipe(clip_id: str, index: int, *, source_mp4: Path, start: float, end: float, opts_kwargs: dict) -> None:
    """Record what produced ``clips/<clip_id>/<index>.mp4`` for later reframing."""
    with _LOCK:
        _RECIPES[_key(clip_id, index)] = {
            "source_mp4": str(source_mp4),
            "start": start,
            "end": end,
            "opts_kwargs": opts_kwargs,
        }


def get_recipe(clip_id: str, index: int) -> Optional[dict]:
    with _LOCK:
        recipe = _RECIPES.get(_key(clip_id, index))
        return dict(recipe) if recipe else None
