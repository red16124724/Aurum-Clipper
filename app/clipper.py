"""Cut, reframe, and burn captions with ffmpeg.

Each clip is re-encoded (libx264 + aac) so cuts are frame-accurate and the ASS
captions are burned into the pixels. Reframing either fills the target frame
(crop) or fits with black bars (pad); in pad mode an optional top-bar text can
be drawn on the top band.
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .models import AspectRatio, ClipGenerationError, FitMode
from .paths import CLIPS_DIR, FONTS_DIR

logger = logging.getLogger(__name__)

# Target frame sizes per aspect ratio.
_TARGETS = {
    AspectRatio.NINE_16: (1080, 1920),
    AspectRatio.SIXTEEN_9: (1920, 1080),
}

_BAR_FONT = FONTS_DIR / "Roboto-Bold.ttf"


@dataclass
class ClipOptions:
    """Everything generate_clip needs beyond the time range."""

    aspect_ratio: AspectRatio
    fit_mode: FitMode
    ass_path: Path
    clip_id: str
    index: int
    bar_text: Optional[str] = None


def _rel_for_filter(target: Path, start_dir: Path) -> str:
    """Return `target` relative to `start_dir` with forward slashes.

    ffmpeg's filtergraph parser treats ':' as an option separator and is fussy
    about Windows drive letters and spaces inside filter VALUES (the `ass`,
    `fontsdir`, and drawtext `fontfile` options). By running ffmpeg with its cwd
    set to the clip folder and passing these as *relative* paths (e.g. `0.ass`,
    `../../assets/fonts`) we avoid the drive colon and spaces entirely, so no
    fragile two-level escaping is needed. All paths live under the project root
    on the same drive, so relpath is always valid.
    """
    return os.path.relpath(str(target), str(start_dir)).replace("\\", "/")


def _escape_drawtext(text: str) -> str:
    """Escape user text for ffmpeg drawtext (the value is wrapped in quotes)."""
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "’")  # swap apostrophe for a typographic one to avoid quoting hell
        .replace("%", "\\%")
    )


def _build_filter(opts: ClipOptions, width: int, height: int, work_dir: Path) -> str:
    """Construct the full -vf filtergraph: reframe -> (bar text) -> captions.

    `work_dir` is the ffmpeg cwd; in-filtergraph paths are made relative to it.
    """
    if opts.fit_mode == FitMode.CROP:
        # Scale to cover the target, then center-crop to exactly WxH.
        reframe = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}"
        )
    else:
        # Scale to fit inside the target, then pad with black bars to WxH.
        reframe = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black"
        )

    parts = [reframe]

    # Top-bar text only makes sense with pad (there is a real top bar there).
    if opts.fit_mode == FitMode.PAD and opts.bar_text and opts.bar_text.strip():
        font_size = max(18, int(round(height * 0.035)))
        y = int(round(height * 0.04))
        drawtext = (
            f"drawtext=fontfile={_rel_for_filter(_BAR_FONT, work_dir)}:"
            f"text='{_escape_drawtext(opts.bar_text.strip())}':"
            f"fontcolor=white:fontsize={font_size}:"
            f"x=(w-text_w)/2:y={y}:"
            f"box=1:boxcolor=black@0.5:boxborderw=20"
        )
        parts.append(drawtext)

    # Burn the styled captions last so they sit on top of everything. Relative
    # paths (cwd = work_dir) keep the drive colon and spaces out of the graph.
    ass = (
        f"ass={_rel_for_filter(opts.ass_path, work_dir)}:"
        f"fontsdir={_rel_for_filter(FONTS_DIR, work_dir)}"
    )
    parts.append(ass)

    return ",".join(parts)


def generate_clip(source_mp4: Path, start: float, end: float, opts: ClipOptions) -> Path:
    """Cut [start, end] from `source_mp4`, reframe + caption it, return the mp4.

    Raises:
        ClipGenerationError: if ffmpeg is missing or fails.
    """
    width, height = _TARGETS[opts.aspect_ratio]
    duration = max(0.1, end - start)

    out_dir = (CLIPS_DIR / opts.clip_id).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{opts.index}.mp4"

    # ffmpeg runs with cwd = out_dir so the in-filtergraph paths can be relative
    # (no Windows drive colon / spaces to escape). Input and output are passed as
    # absolute paths since they are plain argv, not part of the filtergraph.
    vf = _build_filter(opts, width, height, out_dir)

    cmd = [
        "ffmpeg",
        "-y",
        "-ss", f"{start:.3f}",
        "-i", str(Path(source_mp4).resolve()),
        "-t", f"{duration:.3f}",
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        str(out_path),
    ]

    logger.info("Rendering clip %d (cwd=%s): %s", opts.index, out_dir, " ".join(cmd))

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(out_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise ClipGenerationError(
            "ffmpeg was not found on PATH. Install it (winget/brew/apt) — it "
            "does the cutting, reframing, and caption burning."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise ClipGenerationError(f"Failed to run ffmpeg: {exc}") from exc

    if proc.returncode != 0 or not out_path.exists():
        # Surface the tail of ffmpeg's stderr — it usually pinpoints the problem.
        tail = (proc.stderr or "").strip().splitlines()[-12:]
        raise ClipGenerationError(
            "ffmpeg failed to render the clip:\n" + "\n".join(tail)
        )

    return out_path
