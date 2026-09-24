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
import math
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import effects
from .models import AspectRatio, ClipGenerationError, FitMode
from .paths import CLIPS_DIR, FONTS_DIR, MASKS_DIR, SFX_DIR, BUNDLED_SFX_DIR

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

    if radius <= 0:
        # Sharp corners: a fully opaque square needs no SDF ramp — solid white.
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=white:s={size}x{size}:d=0.1",
            "-frames:v", "1", str(path),
        ]
    else:
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
_SIGNATURE_FONT = FONTS_DIR / "Roboto-Bold.ttf"


@dataclass
class ClipOptions:
    """Everything generate_clip needs beyond the time range."""

    aspect_ratio: AspectRatio
    fit_mode: FitMode
    ass_path: Optional[Path]
    clip_id: str
    index: int
    square_corners: str = "round"      # "round" | "square" — square fit mode only
    face_zone: int = 4                 # 0-8 for static split facecam region
    bar_text: Optional[str] = None
    bar_text_color: str = "#FFFFFF"     # square title colour
    bar_text_anim: str = "none"         # square title entrance: none | fade | slide
    cinematic: Optional[dict] = None  # cinematic effects config (see app.effects)
    music_path: Optional[Path] = None  # background-music track to mix under the audio
    music_volume: float = 35.0         # 0-100, reels-style (ducked under speech)
    music_duck: float = 70.0           # 0-100, how hard music dips under the voice
    music_start: float = 0.0           # seconds into the track to start from (beat-aligned)
    signature: Optional[dict] = None   # burned-in watermark (see app.models.Signature)
    reframe: Optional[list[dict]] = None  # manual crop keyframes (see app.models.ReframeKeyframe)
    keep_segments: Optional[list[tuple[float, float]]] = None  # (start, end) pairs for jump cuts
    effects: Optional[list[dict]] = None  # auto SFX/VFX from Gemini
    hevc: bool = False                 # use H.265 instead of H.264
    use_igpu: bool = False             # prioritize iGPU over dGPU


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
        text.replace("\r", "")
        .replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("'", "’")  # swap apostrophe for a typographic one to avoid quoting hell
        .replace("%", "\\%")
    )


def _ass_filter(opts: ClipOptions, work_dir: Path) -> str:
    """The caption-burn filter. Relative paths keep the drive colon/spaces out."""
    return (
        f"ass={_rel_for_filter(opts.ass_path, work_dir)}:"
        f"fontsdir={_rel_for_filter(FONTS_DIR, work_dir)}"
    )


def _caption_stage(in_label: str, opts: ClipOptions, work_dir: Path, out_label: str = "outv") -> str:
    """The final stage that burns the captions onto ``in_label`` -> ``[out_label]``."""
    if not opts.ass_path:
        return f"[{in_label}]copy[{out_label}]"
    return f"[{in_label}]{_ass_filter(opts, work_dir)}[{out_label}]"


def _signature_stages(in_label: str, sig: Optional[dict], w: int, h: int, work_dir: Path) -> tuple[list[str], str]:
    """Burn the signature/watermark text. Returns (stages, out_label).

    pos_x/pos_y are the text centre as a % of the frame; size is at 1080-wide and
    scales to the real width; opacity 0-100. No-op when disabled/empty.
    """
    if not sig or not str(sig.get("text", "")).strip() or not sig.get("enabled"):
        return [], in_label

    t = str(sig.get("text", "")).strip()
    c = str(sig.get("color", "#FFFFFF")).replace("#", "0x")
    s = int(sig.get("size", 28)) * (w / 1080.0)
    o = max(0.0, min(1.0, float(sig.get("opacity", 75)) / 100.0))
    x = float(sig.get("pos_x", 50)) / 100.0
    y = float(sig.get("pos_y", 50)) / 100.0

    font_path = _rel_for_filter(_SIGNATURE_FONT, work_dir)
    shadow = f"shadowcolor=black@{(o * 0.8):.2f}:shadowx=2:shadowy=2"
    f = f"drawtext=fontfile={font_path}:text='{_escape_drawtext(t)}':fontcolor={c}@{o:.2f}:fontsize={s:.1f}:x={x:.3f}*w-text_w/2:y={y:.3f}*h-text_h/2:{shadow}"
    return [f"[{in_label}]{f}[sig]"], "sig"


def _finish_stages(in_label: str, vw: int, vh: int, opts: ClipOptions, work_dir: Path) -> list[str]:
    """Append the cinematic stages (under the captions) then the caption burn.

    Returns the stages that take ``in_label`` -> cinematic effects -> ``[outv]``.
    With no effects this is just the single caption-burn stage, so the default
    render is unchanged. Used by crop mode, where the footage fills the whole
    frame so the effects land on the video. (Square mode applies the effects to
    the square itself — see ``_build_square_filter_complex``.)
    """
    cine_stages, cap_in = effects.cinematic_stages(opts.cinematic, in_label, vw, vh)
    sig_stages, sig_in = _signature_stages(cap_in, opts.signature, vw, vh, work_dir)
    
    stages = cine_stages + sig_stages
    
    if opts.effects:
        vfx = [e for e in opts.effects if e.get("effect", "").startswith("vfx_")]
        if vfx:
            stages.append(_caption_stage(sig_in, opts, work_dir, out_label="pre_vfx"))
            last_lbl = "pre_vfx"
            
            for i, fx in enumerate(vfx):
                fx_type = fx.get("effect")
                t = float(fx.get("time", 0.0))
                out_lbl = f"vfx{i}" if i < len(vfx) - 1 else "outv"
                
                if fx_type == "vfx_bw":
                    # flash black and white for 0.4 seconds
                    stages.append(f"[{last_lbl}]hue=s=0:enable='between(t,{t:.3f},{t+0.4:.3f})'[{out_lbl}]")
                else:
                    stages.append(f"[{last_lbl}]copy[{out_lbl}]") # fallback
                
                last_lbl = out_lbl
            return stages

    stages.append(_caption_stage(sig_in, opts, work_dir))
    return stages


def _piecewise_linear(pts: list[tuple[float, float]]) -> str:
    """Build an ffmpeg ``if(lt(t,...),...)`` expression that linearly
    interpolates between ``(time, value)`` points, holding the first/last
    value outside their range. Shared by the pan and zoom expressions below."""
    expr = f"{pts[-1][1]:.6f}"
    for i in range(len(pts) - 2, -1, -1):
        t0, v0 = pts[i]
        t1, v1 = pts[i + 1]
        seg = f"{v1:.6f}" if t1 <= t0 else f"({v0:.6f}+({v1:.6f}-{v0:.6f})*(t-{t0:.3f})/{(t1 - t0):.6f})"
        expr = f"if(lt(t\\,{t1:.3f})\\,{seg}\\,{expr})"
    if len(pts) > 1:
        expr = f"if(lt(t\\,{pts[0][0]:.3f})\\,{pts[0][1]:.6f}\\,{expr})"
    return expr


def _pos_frac_expr(keyframes: list[dict], key: str) -> Optional[str]:
    """ffmpeg eval expression for one pan axis's 0..1 fraction, or None if
    there are no keyframes at all.

    ``keyframes`` are ``{"time", "pos_x", "pos_y", "zoom"}`` dicts (see
    ``app.models.ReframeKeyframe``); ``key`` picks ``pos_x``/``pos_y``.
    Between keyframes the position is linearly interpolated (a smooth pan);
    before the first / after the last, it holds.
    """
    if not keyframes:
        return None
    raw_pts = []
    for k in keyframes:
        try:
            t = float(k.get("time", 0.0))
            v = float(k.get(key, 50.0))
            if not math.isnan(t) and not math.isinf(t) and not math.isnan(v) and not math.isinf(v):
                raw_pts.append((max(0.0, t), max(0.0, min(100.0, v)) / 100.0))
        except (TypeError, ValueError):
            continue
    pts = sorted(raw_pts, key=lambda p: p[0])
    if not pts:
        return None
    return _piecewise_linear(pts)


def _zoom_expr(keyframes: list[dict]) -> Optional[str]:
    """ffmpeg eval expression for the crop's zoom FACTOR (>=1), or None if every
    keyframe is zoom=100 (or there are none) — the common case, where skipping
    this stage keeps the render identical to a build with no zoom support.

    ``zoom`` (see ``app.models.ReframeKeyframe``) is 10-100, the crop box's size
    as a % of the default max-coverage box. This interpolates that percentage
    the same piecewise-linear way as pan, then converts it to a scale factor
    (100/zoom) applied to the pre-crop canvas: 100 -> 1x (no-op), 50 -> 2x
    (scale the canvas up twice as much before cropping the same fixed WxH
    window out of it — i.e. a tighter, more zoomed-in crop).
    """
    if not keyframes:
        return None
    raw_pts = []
    for k in keyframes:
        try:
            t = float(k.get("time", 0.0))
            z = float(k.get("zoom", 100.0))
            if not math.isnan(t) and not math.isinf(t) and not math.isnan(z) and not math.isinf(z):
                raw_pts.append((max(0.0, t), max(10.0, min(100.0, z))))
        except (TypeError, ValueError):
            continue
    pts = sorted(raw_pts, key=lambda p: p[0])
    if not pts or all(abs(z - 100.0) < 0.05 for _, z in pts):
        return None
    return f"(100/({_piecewise_linear(pts)}))"


def _crop_filter(width: int, height: int, reframe: Optional[list[dict]]) -> str:
    """The reframe filter fragment for a cover-scaled frame: an optional zoom
    pre-scale (only emitted when a keyframe actually zooms in) feeding a
    ``crop=...`` that's keyframed if ``reframe`` is set, else ffmpeg's plain
    centred crop (unchanged default behaviour)."""
    kfs = reframe or []
    xf = _pos_frac_expr(kfs, "pos_x")
    yf = _pos_frac_expr(kfs, "pos_y")
    zoom = _zoom_expr(kfs)

    if xf is None and yf is None:
        return f"crop={width}:{height}"
    xf = xf or "0.5"
    yf = yf or "0.5"

    if zoom is not None:
        prefix = f"scale=w='round(iw*{zoom})':h='round(ih*{zoom})':flags=lanczos:eval=frame,"
        x_part = f"clip(in_w*({xf})-(out_w/2),0,in_w-out_w)"
        y_part = f"clip(in_h*({yf})-(out_h/2),0,in_h-out_h)"
    else:
        prefix = ""
        x_part = f"clip(in_w*({xf})-(out_w/2),0,in_w-out_w)"
        y_part = f"clip(in_h*({yf})-(out_h/2),0,in_h-out_h)"

    # crop's x/y expressions are re-evaluated every frame automatically when
    # they reference time-varying variables like `t` — unlike drawbox/overlay,
    # this filter has no separate `eval` option (passing one is a hard error).
    return f"{prefix}crop={width}:{height}:x='{x_part}':y='{y_part}'"


def _build_crop_filter_complex(width: int, height: int, opts: ClipOptions, work_dir: Path, in_v: str = "0:v") -> str:
    """-filter_complex graph for crop mode: cover+crop, cinematic FX, then captions."""
    stages = [
        f"[{in_v}]scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"{_crop_filter(width, height, opts.reframe)}[v0]"
    ]
    stages += _finish_stages("v0", width, height, opts, work_dir)
    return ";".join(stages)


def _build_square_filter_complex(opts: ClipOptions, work_dir: Path, in_v: str = "0:v", mask_idx: int = 1) -> str:
    """-filter_complex graph for square mode.

    Input 0 = source video, mask_idx = the rounded mask. We split the source: one
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
        f"[{in_v}]split[base][fg]",
        f"[base]scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={w}:{h},drawbox=0:0:iw:ih:black:t=fill[bg]",
        f"[fg]scale={s}:{s}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"{_crop_filter(s, s, opts.reframe)}[fgsq]",
    ]

    # Cinematic FX go on the SQUARE itself (vw=vh=s) — exactly the region the live
    # preview grades — so gradients/vignette/grade land on the footage, not on the
    # black canvas around it. (Crop mode applies them to the full frame instead.)
    cine_stages, sq_cine = effects.cinematic_stages(opts.cinematic, "fgsq", s, s)
    stages += cine_stages

    stages += [
        f"[{sq_cine}]format=yuva420p[sq]",
        f"[{mask_idx}:v]format=gray,scale={s}:{s}[m]",
        "[sq][m]alphamerge[r]",
        f"[bg][r]overlay={mx}:{my}[ov]",
    ]
    last = "ov"

    if opts.bar_text and opts.bar_text.strip():
        # Title can be MULTI-LINE (the UI sends \n for Shift+Enter). Each line is a
        # separate drawtext, stacked, so the whole block sits in the top black band
        # just above the square.
        lines = [ln.strip() for ln in opts.bar_text.split("\n") if ln.strip()][:3]
        font_size = max(28, int(round(h * 0.040)))
        line_h = int(round(font_size * 1.3))
        block_h = line_h * len(lines)
        start_y = max(16, my - block_h - 22)  # bottom of block ~22px above the square
        col = (opts.bar_text_color or "#FFFFFF").replace("#", "0x")
        anim = (opts.bar_text_anim or "none").lower()
        # Entrance animation (commas escaped for the filtergraph expression parser):
        #   fade  → alpha ramps 0→1 over 0.5s; slide → drops in from ~40px below.
        alpha_expr = ":alpha='if(lt(t\\,0.5)\\,t/0.5\\,1)'" if anim == "fade" else ""
        for li, ln in enumerate(lines):
            base_y = start_y + li * line_h
            y = (f"'{base_y}+40*(1-min(t/0.45\\,1))'" if anim == "slide" else str(base_y))
            stages.append(
                f"[{last}]drawtext=fontfile={_rel_for_filter(_BAR_FONT, work_dir)}:"
                f"text='{_escape_drawtext(ln)}':"
                f"fontcolor={col}:fontsize={font_size}:x=(w-text_w)/2:y={y}{alpha_expr}:"
                f"borderw=3:bordercolor=black@0.85[ttl{li}]"
            )
            last = f"ttl{li}"

    # Signature/watermark, then captions, on the composited canvas.
    sig_stages, last = _signature_stages(last, opts.signature, w, h, work_dir)
    stages += sig_stages
    stages.append(_caption_stage(last, opts, work_dir))
    return ";".join(stages)


def _build_split_filter_complex(width: int, height: int, opts: ClipOptions, work_dir: Path, is_dynamic: bool, in_v: str = "0:v") -> str:
    """-filter_complex graph for split screen mode (facecam top, gameplay bottom)."""
    # Each half takes up exactly half the height
    half_h = height // 2
    
    stages = [f"[{in_v}]split[top_src][bottom_src]"]
    
    # 1. Top half (Facecam)
    if is_dynamic and opts.reframe:
        top_kfs = [
            {**kf, "zoom": 33.3 if (kf.get("zoom") is None or kf.get("zoom") >= 100) else kf["zoom"]}
            for kf in opts.reframe
        ]
    else:
        # Static facecam (0=top-left, 4=center, 8=bottom-right)
        zone = opts.face_zone if hasattr(opts, 'face_zone') else 4
        px = (zone % 3) * 50.0
        py = (zone // 3) * 50.0
        top_kfs = [{"time": 0.0, "pos_x": px, "pos_y": py, "zoom": 33.3}]
        
    top_crop = _crop_filter(width, half_h, top_kfs)
    stages.append(f"[top_src]scale={width}:{half_h}:force_original_aspect_ratio=increase:flags=lanczos,{top_crop}[top_raw]")
    
    # 2. Bottom half (Gameplay)
    # Static gameplay (assume center-bottom)
    bottom_kfs = [{"time": 0.0, "pos_x": 50.0, "pos_y": 75.0, "zoom": 100}]
    bottom_crop = _crop_filter(width, half_h, bottom_kfs)
    stages.append(f"[bottom_src]scale={width}:{half_h}:force_original_aspect_ratio=increase:flags=lanczos,{bottom_crop}[bottom_raw]")
    
    # Stack them
    stages.append("[top_raw][bottom_raw]vstack[stacked]")
    
    # Finish stages (cinematic, watermark, captions)
    stages += _finish_stages("stacked", width, height, opts, work_dir)
    
    return ";".join(stages)


def _music_audio_graph(mus_idx: int, volume: float, duck: float = 70.0, in_a: str = "0:a") -> str:
    """Filtergraph that mixes a background track UNDER the original audio, reels-style.

    The voice is split: one copy is the sidechain key for ``sidechaincompress``,
    which automatically ducks the music whenever the speaker is talking, and one
    copy is mixed back at full level. So you hear the voice clearly with music
    filling the gaps — never a wall of loud music. ``normalize=0`` keeps the voice
    at unity gain instead of amix halving everything.

    ``volume`` (0-100) sets the music's resting loudness; ``duck`` (0-100) sets how
    hard the music dips while someone is talking, by scaling the sidechain
    compression ratio: 0 leaves the music steady (ratio ≈ 1), 100 pulls it down
    aggressively (ratio ≈ 20) so the voice always cuts through.

    Input 0's audio is the source voice; ``mus_idx`` is the music input's index.
    Produces the ``[aout]`` label the caller maps as the output audio.
    """
    try:
        vol_f = float(volume) if volume is not None else 35.0
    except (TypeError, ValueError):
        vol_f = 35.0
    try:
        duck_f = float(duck) if duck is not None else 70.0
    except (TypeError, ValueError):
        duck_f = 70.0
    base = max(0.0, min(1.0, vol_f / 100.0 * 0.7))
    d = max(0.0, min(1.0, duck_f / 100.0))
    ratio = 1.0 + d * 19.0  # 0 → 1 (no ducking), 100 → 20 (hard ducking)
    return (
        f"[{in_a}]asplit=2[__v1][__v2];"
        f"[{mus_idx}:a]volume={base:.3f},aresample=async=1[__m];"
        f"[__m][__v2]sidechaincompress=threshold=0.02:ratio={ratio:.2f}:attack=15:release=300[__md];"
        f"[__v1][__md]amix=inputs=2:duration=first:normalize=0[aout]"
    )


# Shared output-encoding args (everything after the filter graph).
_HW_ENCODER_CACHE = {}
_HW_ENCODER_LOCK = threading.Lock()

def get_encode_args(hevc: bool = False, use_igpu: bool = False) -> list[str]:
    cache_key = (hevc, use_igpu)
    with _HW_ENCODER_LOCK:
        if cache_key in _HW_ENCODER_CACHE:
            return _HW_ENCODER_CACHE[cache_key]

        logger.info(f"Detecting hardware acceleration support for {'HEVC' if hevc else 'H.264'} encoding...")

        args = []

        # We define checking functions to keep it clean
        def _check_encoder(codec: str) -> bool:
            try:
                proc = subprocess.run(
                    ["ffmpeg", "-y", "-f", "lavfi", "-i", "nullsrc=s=128x128:d=0.1:r=30",
                     "-pix_fmt", "yuv420p", "-c:v", codec, "-f", "null", "-"],
                    capture_output=True, timeout=10, text=True,
                )
                return proc.returncode == 0
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                return False

        def check_nvenc():
            return _check_encoder("hevc_nvenc" if hevc else "h264_nvenc")

        def check_amf():
            return _check_encoder("hevc_amf" if hevc else "h264_amf")

        def check_qsv():
            return _check_encoder("hevc_qsv" if hevc else "h264_qsv")

        # Determine priority order based on user preference
        # Usually: NVENC/AMF = dGPU (NVIDIA / AMD), QSV = iGPU (Intel)
        check_order = [("qsv", check_qsv), ("nvenc", check_nvenc), ("amf", check_amf)] if use_igpu else [("nvenc", check_nvenc), ("amf", check_amf), ("qsv", check_qsv)]

        encoder_found = None
        for enc_name, check_fn in check_order:
            if check_fn():
                encoder_found = enc_name
                break

        if encoder_found == "nvenc":
            logger.info(f"Hardware Acceleration Enabled: NVIDIA NVENC {'(HEVC)' if hevc else ''} (10,000 kbps CBR)")
            args = [
                "-c:v", "hevc_nvenc" if hevc else "h264_nvenc",
                "-preset", "p7",
                "-b:v", "10000k",
                "-minrate", "10000k",
                "-maxrate", "10000k",
                "-bufsize", "20000k",
                "-rc", "cbr",
                "-spatial-aq", "1",
                "-temporal-aq", "1",
                "-rc-lookahead", "32",
                "-pix_fmt", "yuv420p"
            ]
        elif encoder_found == "amf":
            logger.info(f"Hardware Acceleration Enabled: AMD AMF {'(HEVC)' if hevc else ''} (10,000 kbps CBR)")
            args = [
                "-c:v", "hevc_amf" if hevc else "h264_amf",
                "-quality", "quality",
                "-b:v", "10000k",
                "-minrate", "10000k",
                "-maxrate", "10000k",
                "-bufsize", "20000k",
                "-rc", "cbr",
                "-pix_fmt", "yuv420p"
            ]
        elif encoder_found == "qsv":
            logger.info(f"Hardware Acceleration Enabled: Intel QSV {'(HEVC)' if hevc else ''} (10,000 kbps CBR)")
            args = [
                "-c:v", "hevc_qsv" if hevc else "h264_qsv",
                "-preset", "veryslow",
                "-b:v", "10000k",
                "-minrate", "10000k",
                "-maxrate", "10000k",
                "-bufsize", "20000k",
                "-look_ahead", "1",
                "-pix_fmt", "yuv420p"
            ]
        else:
            logger.info(f"No hardware encoder detected. Falling back to CPU ({'libx265' if hevc else 'libx264'}) (10,000 kbps CBR).")
            args = [
                "-c:v", "libx265" if hevc else "libx264",
                "-preset", "slow",
                "-b:v", "10000k",
                "-minrate", "10000k",
                "-maxrate", "10000k",
                "-bufsize", "20000k",
                "-pix_fmt", "yuv420p"
            ]

        if hevc:
            args.extend(["-tag:v", "hvc1"])
        args.extend(["-r", "60", "-g", "120", "-keyint_min", "60", "-c:a", "aac", "-b:a", "320k", "-movflags", "+faststart"])
        _HW_ENCODER_CACHE[cache_key] = args
        return args


_RENDER_LOCK = threading.RLock()

def generate_clip(source_mp4: Path, start: float, end: float, opts: ClipOptions, cancel_check: Optional[Callable[[], bool]] = None) -> Path:
    with _RENDER_LOCK:
        return _generate_clip_impl(source_mp4, start, end, opts, cancel_check)

def _generate_clip_impl(source_mp4: Path, start: float, end: float, opts: ClipOptions, cancel_check: Optional[Callable[[], bool]] = None) -> Path:
    # Check if source has audio
    probe_cmd = ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(source_mp4)]
    try:
        has_audio = bool(subprocess.check_output(probe_cmd, text=True).strip())
    except Exception:
        has_audio = True

    in_a = "0:a" if has_audio else "dummy_a"
    """Cut [start, end] from `source_mp4`, reframe + caption it, return the mp4.

    Raises:
        ClipGenerationError: if ffmpeg is missing or fails.
    """
    duration = max(0.1, end - start)

    input_count = 1
    inputs = ["-ss", f"{start:.3f}", "-i", str(source_mp4.resolve())]
    if not has_audio:
        inputs += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono"]
        input_count += 1
        in_a = "1:a"
    else:
        in_a = "0:a"
    
    out_dir = (CLIPS_DIR / opts.clip_id).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{opts.index}.mp4"

    src = str(Path(source_mp4).resolve())

    has_music = opts.music_path is not None and Path(opts.music_path).is_file()

    concat_fc = ""
    in_v = "0:v"
    
    # Store the raw audio stream mapping for use in jump_cut
    in_a_raw = in_a
    
    if opts.keep_segments:
        segments = []
        for i, (seg_start, seg_end) in enumerate(opts.keep_segments):
            rel_start = max(0.0, seg_start - start)
            rel_end = max(0.0, seg_end - start)
            if rel_end > rel_start:
                segments.append((rel_start, rel_end, i))
                
        if segments:
            parts = []
            for (rs, re, i) in segments:
                parts.append(f"[0:v]trim=start={rs:.3f}:end={re:.3f},setpts=PTS-STARTPTS[v{i}]")
                parts.append(f"[{in_a_raw}]atrim=start={rs:.3f}:end={re:.3f},asetpts=PTS-STARTPTS[a{i}]")
                
            concat_inputs = "".join(f"[v{i}][a{i}]" for _, _, i in segments)
            parts.append(f"{concat_inputs}concat=n={len(segments)}:v=1:a=1[jump_v][jump_a]")
            
            concat_fc = ";".join(parts) + ";"
            in_v = "jump_v"
            in_a = "jump_a"
            duration = sum((re - rs) for rs, re, _ in segments)

    if opts.fit_mode == FitMode.SQUARE:
        radius = _SQUARE_RADIUS if opts.square_corners != "square" else 0
        mask = ensure_rounded_mask(radius=radius)
        mask_idx = input_count
        fc = concat_fc + _build_square_filter_complex(opts, out_dir, in_v=in_v, mask_idx=mask_idx)
        inputs += ["-loop", "1", "-i", str(mask.resolve())]
        input_count += 1
        tail = ["-shortest"]
    elif opts.fit_mode in (FitMode.STATIC_SPLIT, FitMode.DYNAMIC_SPLIT):
        # Split mode treats the canvas size the same as CROP
        width, height = target_size(opts.aspect_ratio, FitMode.CROP)
        is_dynamic = (opts.fit_mode == FitMode.DYNAMIC_SPLIT)
        fc = concat_fc + _build_split_filter_complex(width, height, opts, out_dir, is_dynamic, in_v=in_v)
        tail = []
    else:
        width, height = target_size(opts.aspect_ratio, opts.fit_mode)
        fc = concat_fc + _build_crop_filter_complex(width, height, opts, out_dir, in_v=in_v)
        tail = []

    # Handle SFX
    sfx_list = [e for e in (opts.effects or []) if e.get("effect", "").startswith("sfx_")]
    final_voice_a = in_a
    
    if sfx_list:
        sfx_parts = []
        amix_inputs = f"[{in_a}]"
        num_mix = 1
        
        for e in sfx_list:
            eff_name = e.get("effect").replace("sfx_", "")
            sfx_file = SFX_DIR / f"{eff_name}.mp3"
            if not sfx_file.exists():
                sfx_file = BUNDLED_SFX_DIR / f"{eff_name}.mp3"
            if sfx_file.exists():
                inputs += ["-i", str(sfx_file.resolve())]
                s_idx = input_count
                input_count += 1
                
                delay_ms = int(float(e.get("time", 0.0)) * 1000)
                # adelay=1000|1000 delays all channels
                sfx_parts.append(f"[{s_idx}:a]adelay={delay_ms}|{delay_ms}[sfx{s_idx}]")
                amix_inputs += f"[sfx{s_idx}]"
                num_mix += 1
                
        if num_mix > 1:
            # mix them together
            sfx_parts.append(f"{amix_inputs}amix=inputs={num_mix}:duration=first:dropout_transition=0:normalize=0[voice_with_sfx]")
            fc += ";" + ";".join(sfx_parts)
            final_voice_a = "voice_with_sfx"

    # Background music
    if has_music:
        seek = ["-ss", f"{max(0.0, opts.music_start):.2f}"] if opts.music_start and opts.music_start > 0 else []
        inputs += ["-stream_loop", "-1", *seek, "-i", str(Path(opts.music_path).resolve())]
        music_idx = input_count
        input_count += 1
        
        fc = fc + ";" + _music_audio_graph(music_idx, opts.music_volume, opts.music_duck, in_a=final_voice_a)
        audio_map = ["-map", "[aout]"]
    else:
        audio_map = ["-map", f"[{final_voice_a}]"] if (opts.keep_segments or sfx_list) else (["-map", "1:a"] if not has_audio else ["-map", "0:a?"])

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-t", f"{duration:.3f}",
        "-filter_complex", fc,
        "-map", "[outv]", *audio_map,
        *get_encode_args(opts.hevc, opts.use_igpu),
        *tail,
        str(out_path),
    ]

    logger.info("Rendering clip %d (cwd=%s): %s", opts.index, out_dir, " ".join(cmd))

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(out_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        
        while True:
            try:
                stdout, stderr = proc.communicate(timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                if cancel_check and cancel_check():
                    proc.terminate()
                    try:
                        proc.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    if out_path.exists():
                        try:
                            out_path.unlink(missing_ok=True)
                        except Exception:
                            pass
                    raise ClipGenerationError("Job cancelled during ffmpeg rendering")
    except FileNotFoundError as exc:
        raise ClipGenerationError(
            "ffmpeg was not found on PATH. Install it (winget/brew/apt) — it "
            "does the cutting, reframing, and caption burning."
        ) from exc
    except ClipGenerationError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ClipGenerationError(f"Failed to run ffmpeg: {exc}") from exc

    if proc.returncode != 0 or not out_path.exists():
        # Surface the tail of ffmpeg's stderr — it usually pinpoints the problem.
        tail_lines = (stderr or "").strip().splitlines()[-12:]
        raise ClipGenerationError(
            "ffmpeg failed to render the clip:\n" + "\n".join(tail_lines)
        )

    return out_path

