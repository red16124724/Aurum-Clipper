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

from .config import get_gemini_api_key

logger = logging.getLogger(__name__)

# Candidate window length bounds (seconds) and the "ideal" length we score toward.
# A clip must run at least MIN, then keeps going until the sentence finishes — it is
# never cut mid-thought. MAX is a hard safety cap (≈ for runaway monologues).
MIN_CLIP_LEN = 30.0
MAX_CLIP_LEN = 90.0
IDEAL_CLIP_LEN = 40.0
_SENT_END = (".", "!", "?", "।", "…")  # incl. Urdu/Hindi danda

# A clip can be a grammatically complete sentence and still end mid-THOUGHT —
# "and that's when I realized..." is a full stop but leaves the story hanging.
# These two signals (a real pause, or the next line sharing almost no
# vocabulary with this one) are a local, no-model stand-in for "the topic
# actually moved on" — used to prefer ending clips on a genuine story
# boundary instead of just the first sentence-end past the target length.
TOPIC_PAUSE_GAP = 0.6       # seconds of silence that reads as a natural beat
TOPIC_OVERLAP_MAX = 0.25    # word-overlap with the next line below this -> topic shifted
TOPIC_SLACK_FRAC = 0.35     # how much further past target_len to keep looking

# Words that often mark hooks / strong or curiosity-driving statements.
STRONG_WORDS = {
    "how", "why", "what", "when", "who", "where", "best", "worst", "never",
    "always", "secret", "mistake", "biggest", "important", "actually", "truth",
    "realize", "realise", "amazing", "incredible", "stop", "avoid", "must",
    "everyone", "nobody", "money", "free", "new", "first", "tip", "tips",
}

# High-energy Action, Explosions, Gunshots, Combat, Thrill
ACTION_WORDS = {
    "boom", "bang", "gun", "guns", "gunshot", "gunshots", "shoot", "shooting",
    "shot", "fire", "firing", "blast", "blasting", "explosion", "explosions",
    "explode", "exploded", "bomb", "bombs", "grenade", "missile", "tank", "bullet",
    "bullets", "sniper", "fight", "fighting", "combat", "attack", "attacking",
    "punch", "punching", "strike", "hit", "hitting", "kill", "killing", "die",
    "dying", "death", "dead", "destroy", "destroying", "danger", "dangerous",
    "run", "running", "fast", "escape", "escaping", "chase", "chasing", "crash",
    "smash", "blood", "bloody", "war", "battle", "threat", "knife", "weapon",
    "weapons", "screaming", "scream", "yelling", "shout", "shouting", "crazy",
    "insane", "omg", "wtf", "stunt", "intense", "clash", "brawl", "ambush",
    "survive", "survival", "emergency", "fatal", "lethal"
}

# Viral Comedy, Laughing, Gen-Z / Meme Relevance
COMEDY_WORDS = {
    "laugh", "laughing", "laughter", "hilarious", "joke", "jokes", "joking",
    "funny", "haha", "hahaha", "lmao", "lol", "roast", "roasting", "prank",
    "pranks", "humor", "comedy", "clown", "embarrassing", "cringe", "ridiculous",
    "stupid", "dumb", "idiot", "mess", "nah", "bruh", "bro", "dead", "funniest",
    "ironic", "sarcasm", "comedian", "meme", "wild", "awkward", "goofy",
    "hysterical", "snicker", "giggle", "giggling", "chuckle", "parody"
}

# Sadness, Crying, Grief, Tragedy, Emotional Pain
SAD_WORDS = {
    "cry", "crying", "tears", "sad", "sadness", "depressed", "depression", "grief",
    "grieving", "sorrow", "heartbroken", "heartbreak", "pain", "painful", "loss",
    "lost", "alone", "lonely", "goodbye", "farewell", "miss", "missing", "suffer",
    "suffering", "hurts", "hurt", "teardrop", "weep", "weeping", "tragic", "tragedy",
    "hopeless", "broken", "funeral", "mourn", "mourning", "regret", "apologize",
    "sorry", "forgive", "teary"
}

# Romance, Passion, Love, Intimacy
ROMANTIC_WORDS = {
    "love", "loved", "loving", "lover", "kiss", "kissing", "kisses", "marry",
    "marriage", "heart", "hearts", "romantic", "romance", "passion", "passionate",
    "forever", "beautiful", "gorgeous", "attractive", "crush", "date", "dating",
    "feelings", "together", "hug", "hugging", "adore", "beloved", "sweetheart",
    "darling", "soulmate", "couple", "intimate", "embrace", "holding", "cherish",
    "proposal"
}

# Unemotional / Dry / Boring Conversation Filter (Penalty signals)
DRY_CONVERSATION_WORDS = {
    "agenda", "slide", "slides", "table", "column", "row", "item", "procedural",
    "technically", "furthermore", "moreover", "essentially", "basically", "regarding",
    "as i said", "moving on", "next point", "clicking", "click", "spreadsheet",
    "interface", "settings", "documentation", "monotone", "so yeah", "anyway",
    "um", "uh", "like i said", "just saying", "bullet point", "bullet points"
}

_OLLAMA_URL = "http://localhost:11434"
_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def select_clips(
    transcript: dict, num_clips: int, clip_length: float | None = None
) -> List[dict]:
    """Return up to `num_clips` non-overlapping {start, end, title} windows.

    If ``clip_length`` is given (seconds — e.g. 30 / 45 / 60 / custom), each window
    is cut to EXACTLY that duration (30s means 30s, not "≈38s to finish a
    sentence"); ``num_clips`` only caps the count.

    Otherwise the clip length ADAPTS to how many clips were asked for: a few clips
    → longer (~ideal) windows; many clips → shorter windows so the video can
    actually yield that many. (You can only fit ~duration / clip-length clips.)
    """
    segments = transcript.get("segments") or []
    if not segments:
        return _fallback_even_split(transcript, num_clips, clip_length)

    duration = float(transcript.get("duration") or (segments[-1].get("end") or 0.0))

    if clip_length and clip_length > 0:
        # Explicit length requested: cut each window to EXACTLY this many seconds so
        # the clip is the duration the user asked for (no sentence-boundary overshoot).
        candidates = _build_candidate_windows(segments, float(clip_length),
                                              exact_len=float(clip_length))
    else:
        # Target window length so `num_clips` can fit the video. The ×0.85
        # compensates for windows overshooting the target while finishing a
        # sentence, keeping the final count close to what was requested.
        target = (duration / num_clips) if (num_clips and duration) else IDEAL_CLIP_LEN
        target = max(10.0, min(MAX_CLIP_LEN, target * 0.85))
        candidates = _build_candidate_windows(segments, target)

    if not candidates:
        return _fallback_even_split(transcript, num_clips, clip_length)

    # Optional Gemini scoring (takes precedence if API key is present).
    gemini_key = get_gemini_api_key()
    if gemini_key:
        try:
            return _select_with_gemini(candidates, num_clips)
        except Exception as exc:
            logger.warning("Gemini selection failed, falling back to next available option: %s", exc)

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
def _build_candidate_windows(
    segments: List[dict],
    target_len: float = IDEAL_CLIP_LEN,
    max_len: float | None = None,
    exact_len: float | None = None,
) -> List[dict]:
    """Tile the transcript into CONTIGUOUS, non-overlapping windows ~``target_len``.

    Walking start→end and jumping to each window's end (rather than one window per
    segment) packs the video tightly, so the timeline yields about
    ``duration / target_len`` windows — i.e. asking for many clips actually gives
    many. Each window still ends on a sentence boundary when possible (capped at
    ~1.2× target so the count stays close to what was requested).

    ``max_len`` overrides the hard upper cap — passed when the user picks an
    explicit clip length so a long custom length isn't clamped to ``MAX_CLIP_LEN``.

    ``exact_len`` (when set) makes every window EXACTLY that many seconds long,
    starting at a segment boundary — used when the user picks a fixed clip length
    so a "30s" clip is 30s, not ~38s snapping to the next sentence end.
    """
    if exact_len is not None and exact_len > 0:
        return _build_exact_windows(segments, exact_len)

    candidates: List[dict] = []
    n = len(segments)
    min_len = max(6.0, min(MIN_CLIP_LEN, target_len * 0.6))
    # Must comfortably exceed target_len * (1 + TOPIC_SLACK_FRAC): that's how far
    # the topic-boundary search below is allowed to look past the first
    # sentence-end, and a tighter cap here would cut it off before it gets the
    # chance (silently making the boundary search a no-op).
    if max_len is None:
        max_len = min(MAX_CLIP_LEN, max(target_len * (1.2 + TOPIC_SLACK_FRAC), min_len + 6))
    else:
        max_len = max(max_len, min_len + 6)

    i = 0
    while i < n:
        start = float(segments[i]["start"])
        end = start
        text_parts: List[str] = []
        j = i
        fallback_j: int | None = None  # first sentence-end past target_len, just in case
        while j < n:
            seg = segments[j]
            end = float(seg["end"])
            seg_text = (seg["text"] or "").strip()
            text_parts.append(seg_text)
            j += 1
            length = end - start
            if length >= target_len and seg_text.endswith(_SENT_END):
                if fallback_j is None:
                    fallback_j = j
                if _is_topic_boundary(segments, j, text_parts):
                    break  # a real story boundary, not just a complete sentence
                if length >= target_len * (1 + TOPIC_SLACK_FRAC):
                    # Kept looking for a cleaner boundary long enough — take the
                    # first acceptable sentence-end rather than run further.
                    j, end = fallback_j, float(segments[fallback_j - 1]["end"])
                    text_parts = text_parts[: fallback_j - i]
                    break
            if length >= max_len:
                if fallback_j is not None:
                    j, end = fallback_j, float(segments[fallback_j - 1]["end"])
                    text_parts = text_parts[: fallback_j - i]
                break

        i = j  # next window starts right after this one (contiguous, non-overlapping)

        length = end - start
        if length < min_len:   # the inner loop already caps the upper end near max_len
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


def _is_topic_boundary(segments: List[dict], j: int, window_text_parts: List[str]) -> bool:
    """Local heuristic: is the cut at ``segments[j]`` a genuine story boundary?

    True at the end of the transcript, across a real pause, or when the next
    line's vocabulary is mostly NEW relative to everything said in the window
    so far (the topic likely moved on) — as opposed to a sentence that's
    merely grammatically complete but still mid-thought (e.g. "...and that's
    when I realized"). Comparing against the WHOLE window (not just the one
    adjacent line) avoids false positives from short lines that just happen
    to phrase the same idea differently.
    """
    if j >= len(segments):
        return True
    prev_end = float(segments[j - 1]["end"])
    nxt = segments[j]
    if float(nxt["start"]) - prev_end >= TOPIC_PAUSE_GAP:
        return True
    window_words = set(re.findall(r"\b\w+\b", " ".join(window_text_parts).lower()))
    next_words = set(re.findall(r"\b\w+\b", (nxt["text"] or "").lower()))
    if not window_words or not next_words:
        return False
    # What fraction of the NEXT line's words are already-familiar (heard in
    # this window)? Low -> mostly new vocabulary -> topic likely shifted.
    familiar = len(window_words & next_words) / max(1, len(next_words))
    return familiar < TOPIC_OVERLAP_MAX


def _build_exact_windows(segments: List[dict], exact_len: float) -> List[dict]:
    """Tile the timeline into fixed ``exact_len``-second windows.

    Each window begins at a segment boundary (a natural point in the speech) and is
    cut to EXACTLY ``exact_len`` seconds, so the rendered clip is the duration the
    user asked for. Text from every segment overlapping the window is gathered for
    scoring/titling. The final window is trimmed to the media end and dropped if it
    is only a short tail.
    """
    n = len(segments)
    total_end = float(segments[-1]["end"])
    candidates: List[dict] = []

    i = 0
    while i < n:
        start = float(segments[i]["start"])
        end = min(start + exact_len, total_end)
        length = end - start

        # Gather text from every segment that overlaps [start, end).
        text_parts: List[str] = []
        j = i
        while j < n and float(segments[j]["start"]) < end:
            text_parts.append((segments[j]["text"] or "").strip())
            j += 1

        # Next window starts at the first segment beginning at/after this window's end.
        nxt = i + 1
        while nxt < n and float(segments[nxt]["start"]) < end:
            nxt += 1
        i = nxt

        # Drop a short final tail that can't make a real clip.
        if length < max(6.0, exact_len * 0.5):
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
    """Score a window prioritizing high-action, comedy, sadness/crying, and romance over dry conversations."""
    words = re.findall(r"\b\w+\b", text.lower())
    word_count = len(words)
    if word_count == 0:
        return 0.0

    # 1) Spoken word density & pacing
    density = word_count / max(length, 1.0)
    density_score = min(density / 3.0, 1.0)

    # 2) Sentence completeness: rewards windows that end on a full stop
    completeness = 1.0 if text.rstrip().endswith((".", "!", "?")) else 0.4

    # 3) Hook signals: questions and curiosity words
    strong_hits = sum(1 for w in words if w in STRONG_WORDS)
    question_bonus = 0.5 if "?" in text else 0.0
    hook_score = min(strong_hits / 4.0, 1.5) + question_bonus

    # 4) High-intensity Action (explosions, gunshots, combat, adrenaline, danger)
    action_hits = sum(1 for w in words if w in ACTION_WORDS)
    action_score = min(action_hits * 1.5, 6.0)

    # 5) Comedy & Laughter (jokes, hilarious punchlines, memes, laughing)
    comedy_hits = sum(1 for w in words if w in COMEDY_WORDS)
    comedy_score = min(comedy_hits * 1.5, 6.0)

    # 6) Sadness, Crying, Grief (tears, heartbreak, mourning, tragic scenes)
    sad_hits = sum(1 for w in words if w in SAD_WORDS)
    sad_score = min(sad_hits * 1.5, 6.0)

    # 7) Romance, Passion, Love (confessions, intimacy, romance, kissing)
    romantic_hits = sum(1 for w in words if w in ROMANTIC_WORDS)
    romantic_score = min(romantic_hits * 1.5, 5.0)

    # Emotional & Action peaks: the strongest dramatic/action/humor/grief hook
    emotional_peaks = [action_score, comedy_score, sad_score, romantic_score]
    max_emotion = max(emotional_peaks)
    total_emotion_sum = sum(emotional_peaks)

    # Exclamations & shouting (screaming, high energy, laughing, loud action)
    exclamation_count = text.count("!")
    exclamation_bonus = min(exclamation_count * 0.5, 2.5)

    uppercase_words = [
        w for w in re.findall(r"\b[A-Z]{2,}\b", text)
        if len(w) > 1 and w.lower() not in ("ok", "tv", "id", "ai", "us", "uk", "am", "pm")
    ]
    shout_bonus = min(len(uppercase_words) * 0.5, 2.0)

    # 8) Length fit
    length_fit = 1.0 - min(abs(length - IDEAL_CLIP_LEN) / IDEAL_CLIP_LEN, 1.0)

    # 9) Dry, Emotionless Small-Talk Penalty
    dry_hits = sum(1 for w in words if w in DRY_CONVERSATION_WORDS)
    dry_penalty = min(dry_hits * 1.0, 5.0)

    # If the window has ZERO intense action, comedy, sadness, or romance markers,
    # apply a severe penalty so dry conversations are demoted
    if max_emotion == 0.0 and exclamation_count == 0 and len(uppercase_words) == 0:
        emotionless_penalty = 3.0
    else:
        emotionless_penalty = 0.0

    raw_score = (
        (max_emotion * 2.5)
        + (total_emotion_sum * 0.5)
        + (2.0 * density_score)
        + (1.5 * completeness)
        + (1.2 * hook_score)
        + exclamation_bonus
        + shout_bonus
        + (1.0 * length_fit)
        - dry_penalty
        - emotionless_penalty
    )

    return max(0.0, raw_score)


def _select_heuristic(candidates: List[dict], num_clips: int) -> List[dict]:
    """Pick the best non-overlapping windows, then FILL to reach `num_clips`."""
    ranked = sorted(candidates, key=lambda c: c["score"], reverse=True)
    chosen: List[dict] = []

    # Pass 1 — quality: highest-scoring non-overlapping windows.
    for cand in ranked:
        if len(chosen) >= num_clips:
            break
        if any(_overlaps(cand, c) for c in chosen):
            continue
        chosen.append(cand)

    # Pass 2 — fill: if we still need more, add remaining non-overlapping
    # candidates prioritizing higher scores
    if len(chosen) < num_clips:
        remaining = [c for c in ranked if c not in chosen]
        for cand in remaining:
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


def _fallback_even_split(
    transcript: dict, num_clips: int, clip_length: float | None = None
) -> List[dict]:
    """Last resort: split the duration into even windows (no segments available)."""
    import math
    duration = float(transcript.get("duration") or 0.0)
    if duration <= 0 or math.isnan(duration) or math.isinf(duration):
        return []

    if clip_length and clip_length > 0:
        # Honour the requested clip length; fit as many as asked for into the video.
        clip_len = float(clip_length)
        n = max(1, min(num_clips, int(duration // clip_len) or 1))
    else:
        n = max(1, min(num_clips, 10))
        clip_len = min(MAX_CLIP_LEN, max(MIN_CLIP_LEN, duration / n))
    clips: List[dict] = []
    cursor = 0.0
    idx = 1
    while cursor < duration and len(clips) < n:
        end = min(cursor + clip_len, duration)
        if end - cursor < 3.0 and len(clips) > 0:  # skip a tiny trailing remainder only if we already have clips
            break
        if end - cursor < 0.2:  # empty or negligible duration
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
            "You are an elite short-form video clip curator. Score this candidate for viral clip generation.\n"
            "Give high scores (85-100) to: intense action (explosions, gunshots, screams, fights), viral comedy & laughter, deep sadness/crying, or passionate romance.\n"
            "Give very low scores (0-20) to: random unemotional conversations, dry small talk, monotone chatter.\n"
            "Reply with ONLY compact JSON: "
            '{"score": <0-100 integer>, "title": "<short hook title <= 8 words>"}.\n\n'
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


# --------------------------------------------------------------------------- #
# Optional Gemini Integration
# --------------------------------------------------------------------------- #
def _select_with_gemini(candidates: List[dict], num_clips: int) -> List[dict]:
    """Score the top candidates with Google Gemini and title them."""
    import json
    from google import genai
    from google.genai import types

    # Pre-rank with the heuristic so we only ask the model about the best candidates
    pre = sorted(candidates, key=lambda c: c["score"], reverse=True)[: num_clips * 3]

    import concurrent.futures

    client = genai.Client(api_key=get_gemini_api_key())
    scored: List[dict] = []

    def _score_cand(cand):
        prompt = (
            "You are an elite short-form video editor and virality curator. Your task is to select ONLY the most gripping, high-intensity, and emotionally engaging moments for viral short-form clips (Shorts, Reels, TikTok) from the transcript.\n\n"
            "SCORING GUIDELINES (0 to 100):\n"
            "- HIGH INTENSITY & ACTION (90-100): Explosions, gunshots, combat, intense arguments, screams, life-or-death drama, chases, extreme stunts, high adrenaline.\n"
            "- COMEDIC & VIRAL GEN-Z HUMOR (85-100): Laugh-out-loud moments, hilarious punchlines, witty roasts, relatable meme-worthy reactions, infectious laughter.\n"
            "- DEEP EMOTIONAL & ROMANTIC PEAKS (85-100): Heartbreaking sad scenes, genuine crying, grief, deep romantic confessions, passionate emotional encounters.\n"
            "- STRICT REJECTION (0-20): Random monotone conversations, dry small talk, procedural or technical explanations, uninteresting conversational filler with no emotion.\n\n"
            "STRICT REQUIREMENT: Do NOT select or give high scores to unemotional, mundane, or flat conversational filler.\n\n"
            "Reply with ONLY compact JSON: "
            '{"score": <0-100 integer>, "title": "<short viral hook title <= 8 words>"}.\n\n'
            f"Transcript Snippet:\n{cand['text'][:1500]}"
        )
        try:
            try:
                resp = client.models.generate_content(
                    model='gemini-3.8-flash',
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        thinking_config=types.ThinkingConfig(thinking_budget=4096)
                    )
                )
            except Exception as err:
                logger.debug("gemini-3.8-flash scoring failed, falling back to gemini-2.5-flash: %s", err)
                resp = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        thinking_config=types.ThinkingConfig(thinking_budget=4096)
                    )
                )
            match = re.search(r"\{.*\}", resp.text, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                score_val = cand["score"]
                if "score" in data:
                    try:
                        import math
                        s = float(data["score"])
                        if not math.isnan(s) and not math.isinf(s):
                            score_val = max(0.0, min(100.0, s))
                    except (ValueError, TypeError):
                        pass
                title_val = _derive_title(str(data.get("title") or cand["text"]))
                return {
                    "start": cand["start"],
                    "end": cand["end"],
                    "score": score_val,
                    "title": title_val,
                }
        except Exception:
            pass
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        for res in executor.map(_score_cand, pre):
            if res:
                scored.append(res)


    if not scored:
        raise RuntimeError("Gemini returned no usable scores")

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
