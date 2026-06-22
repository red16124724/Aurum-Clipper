"""Cut, reframe, and burn captions with ffmpeg.

Each clip is re-encoded (libx264 + aac) so cuts are frame-accurate and the ASS
captions are burned into the pixels.

``crop`` scales to *cover* the chosen aspect ratio (9:16 / 16:9) and center-crops
to fill it. ``square`` renders a 9:16 canvas with the source cropped to a 1:1
square, given **soft rounded corners**, and centered on black — with an optional
title drawn above it (the "rounded square reel" look). The aspect ratio is
ignored in square mode (the canvas is always 9:16).
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .models import AspectRatio, ClipGenerationError, FitMode
from .paths import CLIPS_DIR, FONTS_DIR, MASKS_DIR

logger = logging.getLogger(__name__)

# Target frame sizes per aspect ratio.
_TARGETS = {
    AspectRatio.NINE_16: (1080, 1920),
    AspectRatio.SIXTEEN_9: (1920, 1080),
}

# Square ("rounded reel") mode: a 9:16 canvas with a centered, rounded 1:1 square.
_SQUARE_CANVAS = (1080, 1920)   # output frame (aspect ratio is ignored)
_SQUARE_INNER = 1020            # side of the centered square
_SQUARE_RADIUS = 60             # corner radius of that square (soft, anti-aliased)


def target_size(aspect_ratio: AspectRatio, fit_mode: FitMode) -> tuple[int, int]:
    """Output (width, height): 9:16 canvas for square mode, else the aspect size."""
    if fit_mode == FitMode.SQUARE:
        return _SQUARE_CANVAS
    return _TARGETS[aspect_ratio]


def ensure_rounded_mask(size: int = _SQUARE_INNER, radius: int = _SQUARE_RADIUS) -> Path:
    """Create (once) and cache a grayscale rounded-rectangle mask via ffmpeg.

    White inside the rounded square, black outside; used by ``alphamerge`` to
    give the centered square its soft corners. Generated with ffmpeg's ``geq``
    so we need no extra image library.
    """
    path = MASKS_DIR / f"rounded_{size}_{radius}.png"
    if path.exists():
        return path
    MASKS_DIR.mkdir(parents=True, exist_ok=True)

    edge = size - 1 - radius
    # Distance from each pixel to the inner rectangle's edge (the rounded-rect SDF);
    # a ~1.5px soft ramp around `radius` anti-aliases the corners (smooth, not jaggy).
    # alpha = 255 inside, 0 outside. Commas are escaped for the filtergraph.
    expr = (
        f"255*clip(0.5+({radius}-hypot("
        f"max(0\\,{radius}-X)+max(0\\,X-{edge})\\,"
        f"max(0\\,{radius}-Y)+max(0\\,Y-{edge})))/1.5\\,0\\,1)"
    )
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=black:s={size}x{size}:d=0.1",
        "-vf", f"geq=lum='{expr}':cb=128:cr=128",
        "-frames:v", "1", str(path),
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError as exc:
        raise ClipGenerationError(
            "ffmpeg was not found on PATH (needed to build the rounded mask)."
        ) from exc
    if proc.returncode != 0 or not path.exists():
        tail = (proc.stderr or "").strip().splitlines()[-8:]
        raise ClipGenerationError(
            "Could not generate the rounded-corner mask:\n" + "\n".join(tail)
        )
    return path

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


def _ass_filter(opts: ClipOptions, work_dir: Path) -> str:
    """The caption-burn filter. Relative paths keep the drive colon/spaces out."""
    return (
        f"ass={_rel_for_filter(opts.ass_path, work_dir)}:"
        f"fontsdir={_rel_for_filter(FONTS_DIR, work_dir)}"
    )


def _build_crop_filter(width: int, height: int, opts: ClipOptions, work_dir: Path) -> str:
    """-vf graph for crop mode: cover+crop to WxH, then burn captions."""
    reframe = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height}"
    )
    return f"{reframe},{_ass_filter(opts, work_dir)}"


def _build_square_filter_complex(opts: ClipOptions, work_dir: Path) -> str:
    """-filter_complex graph for square mode.

    Input 0 = source video, input 1 = the rounded mask. We split the source: one
    branch becomes a 9:16 black canvas (so the canvas shares the video's fps and
    timing), the other is cropped to a square and rounded via ``alphamerge``. The
    rounded square is then ``overlay``-composited onto the black canvas — doing
    the compositing explicitly (rather than ``pad`` + dropping the alpha at encode)
    is what makes the soft corners actually survive into the rendered pixels.
    """
    s = _SQUARE_INNER
    w, h = _SQUARE_CANVAS
    mx, my = (w - s) // 2, (h - s) // 2

    stages = [
        "[0:v]split[base][fg]",
        f"[base]scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},drawbox=0:0:iw:ih:black:t=fill[bg]",
        f"[fg]scale={s}:{s}:force_original_aspect_ratio=increase,"
        f"crop={s}:{s},format=yuva420p[sq]",
        f"[1:v]format=gray,scale={s}:{s}[m]",
        "[sq][m]alphamerge[r]",
        f"[bg][r]overlay={mx}:{my}[ov]",
    ]
    last = "ov"

    if opts.bar_text and opts.bar_text.strip():
        font_size = max(28, int(round(h * 0.040)))
        y = max(20, my - font_size - 40)  # sits in the black band just above the square
        stages.append(
            f"[{last}]drawtext=fontfile={_rel_for_filter(_BAR_FONT, work_dir)}:"
            f"text='{_escape_drawtext(opts.bar_text.strip())}':"
            f"fontcolor=white:fontsize={font_size}:x=(w-text_w)/2:y={y}:"
            f"borderw=3:bordercolor=black@0.85[titled]"
        )
        last = "titled"

    stages.append(f"[{last}]{_ass_filter(opts, work_dir)}[outv]")
    return ";".join(stages)


# Shared output-encoding args (everything after the filter graph).
_ENCODE_ARGS = [
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
]


def generate_clip(source_mp4: Path, start: float, end: float, opts: ClipOptions) -> Path:
    """Cut [start, end] from `source_mp4`, reframe + caption it, return the mp4.

    Raises:
        ClipGenerationError: if ffmpeg is missing or fails.
    """
    duration = max(0.1, end - start)

    out_dir = (CLIPS_DIR / opts.clip_id).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{opts.index}.mp4"

    src = str(Path(source_mp4).resolve())

    # ffmpeg runs with cwd = out_dir so in-filtergraph paths can be relative (no
    # Windows drive colon / spaces). Inputs/outputs are absolute argv, which is fine.
    if opts.fit_mode == FitMode.SQUARE:
        mask = ensure_rounded_mask()
        fc = _build_square_filter_complex(opts, out_dir)
        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{start:.3f}", "-i", src,
            "-loop", "1", "-i", str(mask.resolve()),
            "-t", f"{duration:.3f}",
            "-filter_complex", fc,
            "-map", "[outv]", "-map", "0:a?",
            *_ENCODE_ARGS,
            "-shortest",
            str(out_path),
        ]
    else:
        width, height = target_size(opts.aspect_ratio, opts.fit_mode)
        vf = _build_crop_filter(width, height, opts, out_dir)
        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{start:.3f}", "-i", src,
            "-t", f"{duration:.3f}",
            "-vf", vf,
            *_ENCODE_ARGS,
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
