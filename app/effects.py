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

import json
import logging
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .config import get_gemini_api_key

logger = logging.getLogger(__name__)

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
    "high_contrast": "eq=contrast=1.35:saturation=1.15",
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
        y = base + int(round(k * step))
        h = base + int(round((k + 1) * step)) - y
        if h <= 0:
            continue
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
    #    keep the bloom COLOUR-NEUTRAL.
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


def _local_analyze_effects(words: List[Dict[str, Any]], clip_start: float) -> List[Dict[str, Any]]:
    """Local offline heuristic for automatic sound and visual effects."""
    if not words:
        return []

    effects: List[Dict[str, Any]] = []
    
    # Keyword sets for sound triggers
    ding_words = {"how", "why", "what", "secret", "tip", "key", "idea", "remember", "rule", "learn", "truth", "important", "actually", "first", "million", "billion"}
    boom_words = {"never", "always", "stop", "biggest", "worst", "best", "money", "free", "shocking", "danger", "destroy", "crazy", "boom", "insane", "dead", "zero", "hate", "love", "must"}
    transition_words = {"but", "however", "suddenly", "then", "next", "finally", "instead", "meanwhile"}

    used_times: List[float] = []
    def can_add_at(t: float, min_gap: float = 3.0) -> bool:
        return all(abs(t - u) >= min_gap for u in used_times)

    for w in words:
        token = re.sub(r"[^\w]", "", w.get("word", "").lower())
        raw = w.get("word", "")
        t_rel = round(max(0.0, float(w.get("start", 0.0)) - clip_start), 2)

        # 1. Question / Key insight -> Ding
        if (token in ding_words or raw.endswith("?")) and can_add_at(t_rel, min_gap=3.5):
            effects.append({"time": t_rel, "effect": "sfx_ding"})
            used_times.append(t_rel)
        # 2. Strong shock / impact / exclamation -> Boom
        elif (token in boom_words or raw.endswith("!")) and can_add_at(t_rel, min_gap=3.5):
            effects.append({"time": t_rel, "effect": "sfx_boom"})
            used_times.append(t_rel)
        # 3. Transition words or sentence switch -> Whoosh
        elif token in transition_words and can_add_at(t_rel, min_gap=4.0):
            effects.append({"time": t_rel, "effect": "sfx_whoosh"})
            used_times.append(t_rel)

        if len(effects) >= 3:
            break

    # If transcript had few keywords, add sound effects at natural pacing
    if not effects and len(words) >= 4:
        first_t = round(max(0.1, float(words[0].get("start", 0.0)) - clip_start), 2)
        mid_idx = len(words) // 2
        mid_t = round(max(first_t + 2.0, float(words[mid_idx].get("start", 0.0)) - clip_start), 2)
        effects.append({"time": first_t, "effect": "sfx_whoosh"})
        effects.append({"time": mid_t, "effect": "sfx_ding"})

    return effects


def _local_analyze_template(words: List[Dict[str, Any]]) -> str:
    """Local offline heuristic for video templates."""
    if not words:
        return "podcast_classic"
    
    text = " ".join(w.get("word", "").lower() for w in words)
    if any(k in text for k in ["grind", "money", "hustle", "success", "discipline", "win", "focus", "work"]):
        return "sigma_grindset"
    if any(k in text for k in ["game", "gaming", "play", "kill", "insane", "crazy", "reaction", "hype", "lol"]):
        return "hype_beast"
    if any(k in text for k in ["story", "friend", "life", "remember", "day", "feel", "love", "home", "thought"]):
        return "storytime_chill"
    return "podcast_classic"


def analyze_effects_with_gemini(words: List[Dict[str, Any]], clip_start: float) -> List[Dict[str, Any]]:
    """
    Uses Gemini to analyze the transcript and suggest SFX and VFX.
    Falls back to a local heuristic if Gemini API key is not configured or fails.
    """
    if not words:
        return []

    gemini_key = get_gemini_api_key()
    if not gemini_key:
        return _local_analyze_effects(words, clip_start)

    try:
        from google import genai
        from google.genai import types

        lines = []
        current_line = []
        line_start = None

        for w in words:
            rel_start = w['start'] - clip_start
            if line_start is None:
                line_start = rel_start

            current_line.append(w['word'])
            if len(current_line) >= 5 or w['word'].endswith(('.', '?', '!', ',')):
                lines.append(f"[{line_start:.1f}s] {' '.join(current_line)}")
                current_line = []
                line_start = None

        if current_line and line_start is not None:
            lines.append(f"[{line_start:.1f}s] {' '.join(current_line)}")

        transcript_text = "\n".join(lines)

        prompt = f"""You are a video editor adding sound effects (SFX) and visual effects (VFX) to a short-form vertical video (like a TikTok or Reel).
Here is the transcript with timestamps:
{transcript_text}

Choose from these exact effects:
- sfx_ding (for a realization, idea, or positive point)
- sfx_boom (for impact, shock, or a heavy statement)
- sfx_whoosh (for a quick transition or gesture)
- vfx_bw (flashes the screen black and white briefly for dramatic effect)

Return a JSON array of objects, where each object has 'time' (float, matching the timestamp near where the effect should happen) and 'effect' (string, the exact name of the effect).
Do not overuse them! 1 to 3 effects per clip is plenty.
"""

        client = genai.Client(api_key=gemini_key)
        try:
            response = client.models.generate_content(
                model='gemini-3.8-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    thinking_config=types.ThinkingConfig(thinking_budget=4096)
                )
            )
        except Exception as err:
            logger.debug("gemini-3.8-flash failed in effects analysis, falling back to gemini-2.5-flash: %s", err)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    thinking_config=types.ThinkingConfig(thinking_budget=4096)
                )
            )
        text = response.text.strip() if response and response.text else ""
        match = re.search(r"\[.*\]", text, re.DOTALL)
        raw_effects = None
        if match:
            try:
                raw_effects = json.loads(match.group(0))
            except Exception:
                pass
        if raw_effects is None and text:
            try:
                raw_effects = json.loads(text)
            except Exception:
                pass

        if isinstance(raw_effects, list) and raw_effects:
            sanitized: List[Dict[str, Any]] = []
            for item in raw_effects:
                if isinstance(item, dict) and "effect" in item:
                    try:
                        t = float(item.get("time", 0.0))
                        if not math.isnan(t) and not math.isinf(t):
                            sanitized.append({
                                "time": round(max(0.0, t), 2),
                                "effect": str(item["effect"]),
                            })
                    except (ValueError, TypeError):
                        continue
            if sanitized:
                return sanitized
        return _local_analyze_effects(words, clip_start)
    except Exception as e:
        logger.warning("Gemini effects analysis fallback to local: %s", e)
        return _local_analyze_effects(words, clip_start)


def analyze_template_with_gemini(words: List[Dict[str, Any]]) -> str:
    """
    Analyzes the transcript and selects the best matching video template.
    Falls back to a local heuristic if Gemini API key is not configured or fails.
    """
    if not words:
        return "podcast_classic"

    gemini_key = get_gemini_api_key()
    if not gemini_key:
        return _local_analyze_template(words)

    try:
        from google import genai
        from google.genai import types

        lines = []
        current_line = []

        for w in words:
            current_line.append(w['word'])
            if len(current_line) >= 8 or w['word'].endswith(('.', '?', '!', ',')):
                lines.append(' '.join(current_line))
                current_line = []

        if current_line:
            lines.append(' '.join(current_line))

        transcript_text = "\n".join(lines)

        prompt = f"""You are an expert short-form video editor for TikTok/Reels. 
Analyze the following transcript and choose the BEST editing template to match the vibe.

Transcript:
{transcript_text}

Available templates:
- sigma_grindset: High contrast, dramatic. Best for motivational speeches, tough talk, intense moments.
- storytime_chill: Soft, engaging, friendly. Best for personal stories, casual talks, vlogs.
- podcast_classic: Clean, standard, professional. Best for educational content, interviews, news.
- hype_beast: Loud, colorful. Best for high-energy reactions, gaming, pranks.

Return ONLY the exact template ID string (e.g. sigma_grindset) and nothing else.
"""

        client = genai.Client(api_key=gemini_key)
        try:
            response = client.models.generate_content(
                model='gemini-3.8-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_budget=4096)
                )
            )
        except Exception as err:
            logger.debug("gemini-3.8-flash failed in template analysis, falling back to gemini-2.5-flash: %s", err)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_budget=4096)
                )
            )
        text = response.text.strip().lower() if response and response.text else ""
        for tid in ["sigma_grindset", "storytime_chill", "podcast_classic", "hype_beast"]:
            if tid in text:
                return tid
        return _local_analyze_template(words)
    except Exception as e:
        logger.warning("Gemini template analysis fallback to local: %s", e)
        return _local_analyze_template(words)

def spell_check_with_gemini(words: List[Dict[str, Any]], target_language: Optional[str] = None) -> List[Dict[str, Any]]:
    """Uses Gemini to correct spelling mistakes while preserving timestamps, and optionally filters out words not in the target language."""
    if not words:
        return words

    gemini_key = get_gemini_api_key()
    if not gemini_key:
        return words

    try:
        from google import genai
        from google.genai import types

        if target_language:
            prompt = f"Fix ONLY spelling and grammatical mistakes in the 'word' fields of this JSON array. DO NOT TRANSLATE THE TEXT. You must maintain the original language. DO NOT change start/end timestamps. You MUST strictly REMOVE any objects/words that are NOT in the {target_language} language (drop words that belong to other languages). Return ONLY the corrected JSON array.\n\n" + json.dumps(words, ensure_ascii=False)
        else:
            prompt = "Fix ONLY spelling and grammatical mistakes in the 'word' fields of this JSON array. DO NOT TRANSLATE THE TEXT. You must maintain the original language. If the text is in Hinglish or a non-English language, leave it in that language. DO NOT change start/end timestamps. DO NOT add or remove any elements. Return ONLY the corrected JSON array.\n\n" + json.dumps(words, ensure_ascii=False)

        client = genai.Client(api_key=gemini_key)
        try:
            response = client.models.generate_content(
                model='gemini-3.8-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    thinking_config=types.ThinkingConfig(thinking_budget=4096)
                )
            )
        except Exception as err:
            logger.debug("gemini-3.8-flash failed in spell check, falling back to gemini-2.5-flash: %s", err)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    thinking_config=types.ThinkingConfig(thinking_budget=4096)
                )
            )
        text = response.text.strip() if response and response.text else ""
        match = re.search(r"\[.*\]", text, re.DOTALL)
        
        parsed = []
        if match:
            try:
                parsed = json.loads(match.group(0))
            except Exception:
                pass
        elif text:
            try:
                parsed = json.loads(text)
            except Exception:
                pass
            
        if isinstance(parsed, list) and parsed:
            sanitized_words = []
            for item in parsed:
                if isinstance(item, dict) and "word" in item and "start" in item and "end" in item:
                    sanitized_words.append(item)
            if target_language and sanitized_words:
                return sanitized_words
            elif len(sanitized_words) == len(words):
                return sanitized_words
            
        return words
    except Exception as e:
        logger.warning("Gemini spell check failed: %s", e)
        return words
