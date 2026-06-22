"""Ensure the bundled caption font exists (download once, then fully offline).

A binary .ttf can't ship as copy-paste source, so on first startup we fetch
Roboto (Regular + Bold, Apache-2.0) into assets/fonts/ and pass that directory
to ffmpeg via `fontsdir` for deterministic caption rendering. This is a one-time
download; afterwards everything works offline. If the download fails, we log a
warning and continue — libass will fall back to a system font.
"""

from __future__ import annotations

import logging

from .paths import FONTS_DIR

logger = logging.getLogger(__name__)

# Stable Apache-2.0 sources (hinted static TTFs from the Roboto upstream repo).
# Downloaded at most once; afterwards everything works offline.
_FONT_FILES = {
    "Roboto-Regular.ttf": (
        "https://github.com/googlefonts/roboto-2/raw/main/src/hinted/Roboto-Regular.ttf"
    ),
    "Roboto-Bold.ttf": (
        "https://github.com/googlefonts/roboto-2/raw/main/src/hinted/Roboto-Bold.ttf"
    ),
}


def ensure_fonts() -> None:
    """Download missing bundled fonts. Best-effort; never raises."""
    FONTS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        import requests
    except Exception:  # noqa: BLE001
        logger.warning("`requests` unavailable; skipping font download.")
        return

    for filename, url in _FONT_FILES.items():
        target = FONTS_DIR / filename
        if target.exists() and target.stat().st_size > 0:
            continue
        try:
            logger.info("Downloading bundled font %s ...", filename)
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            target.write_bytes(resp.content)
            logger.info("Saved %s (%d bytes).", filename, len(resp.content))
        except Exception as exc:  # noqa: BLE001 - degrade gracefully to system fonts
            logger.warning(
                "Could not download font %s (%s). Captions will use a system "
                "font fallback.",
                filename,
                exc,
            )
