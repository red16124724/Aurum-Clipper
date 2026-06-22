"""Clip selection — fully LOCAL.

This is NOT cloud "AI virality" detection. It is a transparent local heuristic:
we build candidate windows aligned to transcript segment boundaries and score
them with simple, explainable signals (word density, sentence completeness, the
presence of questions / strong statements, and how close the window length is to
an ideal short length). The top non-overlapping windows are returned.

An OPTIONAL, OFF-by-default scaffold can score/title windows with a *local*
Ollama model if one is detected on this machine. It still makes zero external
API calls — Ollama runs on localhost. Enable it by setting USE_OLLAMA=1.
"""

from __future__ import annotations

import logging
import os
import re
from typing import List

logger = logging.getLogger(__name__)

# Candidate window length bounds (seconds) and the "ideal" length we score toward.
MIN_CLIP_LEN = 20.0
MAX_CLIP_LEN = 45.0
IDEAL_CLIP_LEN = 30.0

# Words that often mark hooks / strong or curiosity-driving statements.
STRONG_WORDS = {
    "how", "why", "what", "when", "who", "where", "best", "worst", "never",
    "always", "secret", "mistake", "biggest", "important", "actually", "truth",
    "realize", "realise", "amazing", "incredible", "stop", "avoid", "must",
    "everyone", "nobody", "money", "free", "new", "first", "tip", "tips",
}

_OLLAMA_URL = "http://localhost:11434"
_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def select_clips(transcript: dict, num_clips: int) -> List[dict]:
    """Return up to `num_clips` non-overlapping {start, end, title} windows."""
    segments = transcript.get("segments") or []
    if not segments:
        return _fallback_even_split(transcript, num_clips)

    candidates = _build_candidate_windows(segments)
    if not candidates:
        return _fallback_even_split(transcript, num_clips)

    # Optional local Ollama scoring (off unless explicitly enabled and available).
    if os.environ.get("USE_OLLAMA") == "1" and _ollama_available():
        try:
            return _select_with_ollama(candidates, num_clips)
        except Exception as exc:  # noqa: BLE001 - always degrade to heuristic
            logger.warning("Ollama selection failed, using heuristic: %s", exc)

    return _select_heuristic(candidates, num_clips)


# --------------------------------------------------------------------------- #
# Heuristic selection
# --------------------------------------------------------------------------- #
def _build_candidate_windows(segments: List[dict]) -> List[dict]:
    """Build candidate windows by greedily grouping consecutive segments.

    Each window starts at a segment boundary and extends until it reaches the
    ideal length, keeping the result inside [MIN_CLIP_LEN, MAX_CLIP_LEN].
    """
    candidates: List[dict] = []
    n = len(segments)

    for i in range(n):
        start = float(segments[i]["start"])
        end = start
        text_parts: List[str] = []

        for j in range(i, n):
            seg = segments[j]
            end = float(seg["end"])
            text_parts.append((seg["text"] or "").strip())
            length = end - start

            if length >= IDEAL_CLIP_LEN:
                break

        length = end - start
        if length < MIN_CLIP_LEN or length > MAX_CLIP_LEN:
            continue

        text = " ".join(p for p in text_parts if p).strip()
        if not text:
            continue

        candidates.append(
            {
                "start": round(start, 2),
                "end": round(end, 2),
                "text": text,
                "score": _score_window(text, length),
            }
        )

    return candidates


def _score_window(text: str, length: float) -> float:
    """Score a window from simple, explainable local signals (higher = better)."""
    words = re.findall(r"\b\w+\b", text.lower())
    word_count = len(words)
    if word_count == 0:
        return 0.0

    # 1) Word density: spoken-heavy windows make better clips than near-silence.
    density = word_count / max(length, 1.0)
    density_score = min(density / 3.0, 1.0)  # ~3 words/sec saturates

    # 2) Sentence completeness: rewards windows that end on a full stop.
    completeness = 1.0 if text.rstrip().endswith((".", "!", "?")) else 0.4

    # 3) Hook signals: questions and strong/curiosity words.
    strong_hits = sum(1 for w in words if w in STRONG_WORDS)
    question_bonus = 0.3 if "?" in text else 0.0
    hook_score = min(strong_hits / 5.0, 1.0) + question_bonus

    # 4) Length fit: prefer windows close to the ideal length.
    length_fit = 1.0 - min(abs(length - IDEAL_CLIP_LEN) / IDEAL_CLIP_LEN, 1.0)

    return (
        2.0 * density_score
        + 1.5 * completeness
        + 1.5 * hook_score
        + 1.0 * length_fit
    )


def _select_heuristic(candidates: List[dict], num_clips: int) -> List[dict]:
    """Greedily pick the highest-scoring non-overlapping windows."""
    ranked = sorted(candidates, key=lambda c: c["score"], reverse=True)
    chosen: List[dict] = []

    for cand in ranked:
        if len(chosen) >= num_clips:
            break
        if any(_overlaps(cand, c) for c in chosen):
            continue
        chosen.append(cand)

    # Present clips in chronological order.
    chosen.sort(key=lambda c: c["start"])
    return [
        {
            "start": c["start"],
            "end": c["end"],
            "title": _derive_title(c["text"]),
        }
        for c in chosen
    ]


def _overlaps(a: dict, b: dict) -> bool:
    return a["start"] < b["end"] and b["start"] < a["end"]


def _derive_title(text: str, max_words: int = 7) -> str:
    """Build a short, human-readable title from the window's leading words."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    words = cleaned.split(" ")
    title = " ".join(words[:max_words]).strip(" ,.;:-")
    if not title:
        return "Clip"
    # Title-case only if it looks like all-lower/all-upper noise.
    if title.islower() or title.isupper():
        title = title.capitalize()
    return title


def _fallback_even_split(transcript: dict, num_clips: int) -> List[dict]:
    """Last resort: split the duration into even windows (no segments available)."""
    duration = float(transcript.get("duration") or 0.0)
    if duration <= 0:
        return []

    n = max(1, min(num_clips, 10))
    clip_len = min(MAX_CLIP_LEN, max(MIN_CLIP_LEN, duration / n))
    clips: List[dict] = []
    cursor = 0.0
    idx = 1
    while cursor < duration and len(clips) < n:
        end = min(cursor + clip_len, duration)
        if end - cursor < 3.0:  # skip a tiny tail
            break
        clips.append(
            {"start": round(cursor, 2), "end": round(end, 2), "title": f"Clip {idx}"}
        )
        cursor = end
        idx += 1
    return clips


# --------------------------------------------------------------------------- #
# Optional LOCAL Ollama scaffold (OFF by default; localhost only)
# --------------------------------------------------------------------------- #
def _ollama_available() -> bool:
    """Return True if a local Ollama server answers on localhost."""
    try:
        import requests

        resp = requests.get(f"{_OLLAMA_URL}/api/tags", timeout=1.5)
        return resp.status_code == 200
    except Exception:  # noqa: BLE001
        return False


def _select_with_ollama(candidates: List[dict], num_clips: int) -> List[dict]:
    """Score the top candidates with a local Ollama model and title them.

    This still makes NO external API calls — Ollama runs on this machine. We ask
    the model for a 0-100 interest score and a short title per window, then pick
    the best non-overlapping ones. Any failure raises so the caller can fall
    back to the pure heuristic.
    """
    import json

    import requests

    # Pre-rank with the heuristic so we only ask the local model about the best
    # ~3x candidates (keeps it fast on modest hardware).
    pre = sorted(candidates, key=lambda c: c["score"], reverse=True)[: num_clips * 3]

    scored: List[dict] = []
    for cand in pre:
        prompt = (
            "You are scoring short-video clip candidates. Given the transcript "
            "snippet, reply with ONLY compact JSON: "
            '{"score": <0-100 integer>, "title": "<<=8 word hook title>"}.\n\n'
            f"Transcript:\n{cand['text'][:1200]}"
        )
        resp = requests.post(
            f"{_OLLAMA_URL}/api/generate",
            json={"model": _OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=60,
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "")
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            continue
        data = json.loads(match.group(0))
        scored.append(
            {
                "start": cand["start"],
                "end": cand["end"],
                "score": float(data.get("score", cand["score"])),
                "title": _derive_title(str(data.get("title") or cand["text"])),
            }
        )

    if not scored:
        raise RuntimeError("Ollama returned no usable scores")

    scored.sort(key=lambda c: c["score"], reverse=True)
    chosen: List[dict] = []
    for cand in scored:
        if len(chosen) >= num_clips:
            break
        if any(_overlaps(cand, c) for c in chosen):
            continue
        chosen.append(cand)

    chosen.sort(key=lambda c: c["start"])
    return [
        {"start": c["start"], "end": c["end"], "title": c["title"]} for c in chosen
    ]
