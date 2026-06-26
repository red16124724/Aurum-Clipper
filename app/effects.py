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

# Bands used to fake a smooth gradient from stacked semi-transparent boxes.
_GRAD_BANDS = 14


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
    """A comma-chain of drawbox bands approximating a dark gradient.

    ``top=False`` darkens the bottom (fading up); ``top=True`` darkens the top.
    The bands all share one edge (bottom or top) so overlaps accumulate there,
    landing at ~``strength`` opacity at the darkest edge and fading to ~0.
    """
    h_grad = max(1, int(vh * max(0.0, min(0.8, height_pct / 100.0))))
    n = _GRAD_BANDS
    step = h_grad / n
    m = max(0.0, min(0.96, strength / 100.0))
    # Per-band alpha so n overlapping layers reach max opacity m: 1-(1-a)^n = m.
    a = 1.0 - (1.0 - m) ** (1.0 / n)
    boxes: List[str] = []
    for k in range(n):
        if top:
            y, h = 0, int(round(h_grad - k * step))
        else:
            y = int(round(vh - h_grad + k * step))
            h = vh - y
        if h <= 0:
            continue
        boxes.append(f"drawbox=x=0:y={y}:w=iw:h={h}:color=black@{a:.3f}:t=fill")
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

    # 2) Glow / bloom — split, blur one copy, screen-blend it back.
    if _on(cfg, "glow"):
        s = _f(_num(cfg, "glow_strength", 50), 4.0, 18.0)       # blur sigma
        o = _f(_num(cfg, "glow_strength", 50), 0.15, 0.5)       # blend opacity
        nxt = f"cine{idx}"
        stages.append(
            f"[{cur}]split=2[{nxt}a][{nxt}b];"
            f"[{nxt}b]gblur=sigma={s:.1f}[{nxt}c];"
            f"[{nxt}a][{nxt}c]blend=all_mode=screen:all_opacity={o:.3f}[{nxt}]"
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

    return stages, cur
