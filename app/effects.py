"""Cinematic video effects — ffmpeg filter stages for the "reel" look.

Builds a list of labelled filtergraph stages that sit between the reframed video
and the burned-in captions, so colour grades, glows, gradients, etc. affect the
footage but never the (sharp, on-top) captions. Everything is expressed as
``[in]…[out]`` segments joined with ``;`` so it drops straight into the same
``-filter_complex`` both crop and square modes use.

Each effect is input-less (no extra ffmpeg inputs): gradients are stacked
semi-transparent ``drawbox`` bands, glow is a ``split``→``gblur``→``blend=screen``
bloom, and grades are ``curves``/``eq``/``colorbalance`` chains. The single source
of truth for what's available is ``COLOR_GRADES`` + the keys read in
``cinematic_stages`` — the frontend mirrors these for its live preview.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

# Colour-grade presets -> the ffmpeg filter chain that produces the look.
COLOR_GRADES: dict[str, str] = {
    "none": "",
    "warm": "eq=saturation=1.10,colorbalance=rm=0.06:gm=0.02:bm=-0.06:rh=0.05:bh=-0.06",
    "cool": "eq=saturation=1.05,colorbalance=rm=-0.05:bm=0.06:bh=0.06",
    "teal_orange": (
        "colorbalance=rh=0.08:gh=0.02:bh=-0.05:bs=0.06:gs=0.02:rs=-0.05,"
        "eq=saturation=1.12:contrast=1.05"
    ),
    "vintage": "curves=preset=vintage",
    "vibrant": "eq=saturation=1.35:contrast=1.08:brightness=0.01",
    "bw": "hue=s=0,eq=contrast=1.10",
}

# Strips used to fake a smooth gradient. Each is a thin, non-overlapping band
# whose opacity follows an eased (smoothstep) ramp toward the dark edge — enough
# of them (and small enough steps) that it reads as a soft, photographic falloff
# rather than a visible bar.
_GRAD_BANDS = 64


def _f(x: float, lo: float, hi: float) -> float:
    """Clamp a 0..100 'strength' style value to a 0..1 fraction, then to [lo,hi]."""
    frac = max(0.0, min(100.0, float(x))) / 100.0
    return lo + frac * (hi - lo)


def _on(cfg: dict, key: str) -> bool:
    return bool(cfg.get(key))


def _num(cfg: dict, key: str, default: float) -> float:
    v = cfg.get(key)
    try:
        return float(v) if v is not None else float(default)
    except (TypeError, ValueError):
        return float(default)


def _gradient_bands(vw: int, vh: int, height_pct: float, strength: float, top: bool) -> str:
    """A comma-chain of drawbox strips approximating a *smooth* dark gradient.

    The region is sliced into ``_GRAD_BANDS`` thin, non-overlapping strips, each a
    solid box whose opacity follows a linear ramp: ~0 at the soft (faded) edge up
    to ``strength`` at the dark edge. Because the strips don't stack, the opacity
    step between neighbours is just ``strength / n`` (≈2%), so there's no hard
    accumulation edge — it reads as a smooth fade instead of visible bands.

    ``top=False`` darkens the bottom (fading up); ``top=True`` darkens the top.
    """
    h_grad = max(1, int(vh * max(0.0, min(0.8, height_pct / 100.0))))
    n = _GRAD_BANDS
    step = h_grad / n
    m = max(0.0, min(0.96, strength / 100.0))
    base = 0 if top else (vh - h_grad)  # top of the gradient region

    boxes: List[str] = []
    for k in range(n):
        # Strips tile the region EXACTLY: each one runs from one rounded boundary
        # to the next, so there's no gap (a bright seam) and — crucially — no
        # overlap (where two semi-transparent blacks would stack into a dark line
        # and re-introduce banding). k counts strips from the top of the region.
        y = base + int(round(k * step))
        h = base + int(round((k + 1) * step)) - y
        if h <= 0:
            continue
        # Opacity ramps toward the dark edge: bottom-gradient darkens downward,
        # top-gradient darkens upward. Smoothstep (not linear) so both ends of
        # the ramp ease in/out — no perceptible seam where the effect "starts",
        # and no hard edge at the peak. This is the fix for the reported
        # "visible black bar" look: a linear ramp reads as flat-then-a-wall;
        # smoothstep reads as a continuous, photographic falloff.
        frac = (k + 0.5) / n
        eased = frac * frac * (3.0 - 2.0 * frac)
        alpha = m * eased if not top else m * (1.0 - eased)
        if alpha <= 0.002:
            continue
        boxes.append(f"drawbox=x=0:y={y}:w=iw:h={h}:color=black@{alpha:.4f}:t=fill")
    return ",".join(boxes)


def cinematic_stages(
    cfg: Optional[dict], in_label: str, vw: int, vh: int
) -> Tuple[List[str], str]:
    """Build the cinematic filtergraph stages.

    Returns ``(stages, out_label)`` where ``stages`` is a list of ``[a]…[b]``
    segments and ``out_label`` is the label the captions should consume. When no
    effects are enabled it returns ``([], in_label)`` so the caller burns
    captions straight onto the input — zero overhead for the default path.
    """
    if not cfg:
        return [], in_label

    stages: List[str] = []
    cur = in_label
    idx = 0

    def push(filters: str) -> None:
        """Append a single linear filter segment cur -> cine{idx}."""
        nonlocal cur, idx
        nxt = f"cine{idx}"
        stages.append(f"[{cur}]{filters}[{nxt}]")
        cur, idx = nxt, idx + 1

    # 1) Colour grade (whole image).
    grade = COLOR_GRADES.get(str(cfg.get("color_grade") or "none"))
    if grade:
        push(grade)

    # 2) Glow / bloom — isolate the HIGHLIGHTS, blur those, screen-blend back, and
    #    keep the bloom COLOUR-NEUTRAL. Three things have to be true or it looks
    #    wrong:
    #      a) threshold first (curves crush mids/shadows to black) so only bright
    #         areas bloom — without it the whole frame lifts into a milky haze;
    #      b) desaturate the bloom to grey (format=gray) so the glow adds soft
    #         *light*, never colour — without it a magenta/purple-lit scene blooms
    #         its own colour and washes the entire frame purple (the reported bug);
    #      c) blend in RGB (gbrp) — on YUV the screen hits the chroma planes and
    #         tints the frame purple no matter what. Back to yuv420p afterwards.
    if _on(cfg, "glow"):
        s = _f(_num(cfg, "glow_strength", 50), 6.0, 22.0)       # blur sigma
        o = _f(_num(cfg, "glow_strength", 50), 0.35, 0.85)      # bloom opacity
        nxt = f"cine{idx}"
        stages.append(
            f"[{cur}]format=gbrp,split=2[{nxt}a][{nxt}b];"
            f"[{nxt}b]curves=all='0/0 0.55/0 0.8/0.55 1/1',format=gray,format=gbrp,"
            f"gblur=sigma={s:.1f}[{nxt}c];"
            f"[{nxt}a][{nxt}c]blend=all_mode=screen:all_opacity={o:.3f},"
            f"format=yuv420p[{nxt}]"
        )
        cur, idx = nxt, idx + 1

    # 3) Film grain.
    if _on(cfg, "grain"):
        n = int(round(_f(_num(cfg, "grain_strength", 40), 4.0, 32.0)))
        push(f"noise=alls={n}:allf=t+u")

    # 4) Vignette (darkened corners).
    if _on(cfg, "vignette"):
        ang = _f(_num(cfg, "vignette_strength", 50), 0.45, 1.25)
        push(f"vignette=angle={ang:.3f}")

    # 5) Bottom gradient (the classic reel scrim under captions).
    if _on(cfg, "bottom_gradient"):
        bands = _gradient_bands(
            vw, vh, _num(cfg, "bottom_gradient_height", 25),
            _num(cfg, "bottom_gradient_strength", 70), top=False,
        )
        if bands:
            push(bands)

    # 6) Top gradient.
    if _on(cfg, "top_gradient"):
        bands = _gradient_bands(
            vw, vh, _num(cfg, "top_gradient_height", 20),
            _num(cfg, "top_gradient_strength", 60), top=True,
        )
        if bands:
            push(bands)

    # 7) Cinematic letterbox bars (top + bottom).
    if _on(cfg, "letterbox"):
        bh = max(1, int(vh * _f(_num(cfg, "letterbox_size", 50), 0.05, 0.14)))
        push(
            f"drawbox=x=0:y=0:w=iw:h={bh}:color=black:t=fill,"
            f"drawbox=x=0:y=ih-{bh}:w=iw:h={bh}:color=black:t=fill"
        )

    # 8) Sharpen / clarity (unsharp mask on the luma plane).
    if _on(cfg, "sharpen"):
        amt = _f(_num(cfg, "sharpen_strength", 40), 0.2, 1.6)
        push(f"unsharp=luma_msize_x=5:luma_msize_y=5:luma_amount={amt:.2f}")

    # 9) Chromatic aberration — subtle RGB channel split for a lens/glitch look.
    if _on(cfg, "chroma_shift"):
        px = max(1, int(round(_f(_num(cfg, "chroma_shift_strength", 40), 1.0, 6.0))))
        push(f"rgbashift=rh=-{px}:bh={px}:edge=smear")

    return stages, cur
