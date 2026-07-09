"""Tiny LOCAL mood detector for music suggestions.

Counts simple keyword hits (English + Roman Urdu/Hindi) in the transcript and maps
the strongest signal to a music mood. No model, no network — fully transparent.
"""

from __future__ import annotations

KEYWORDS: dict[str, list[str]] = {
    "romantic": ["love", "heart", "pyar", "pyaar", "ishq", "mohabbat", "romance", "dil",
                 "beloved", "kiss", "crush", "relationship", "feelings", "mohabat", "chahat"],
    "sad": ["sad", "cry", "alone", "tears", "pain", "dard", "udaas", "rona", "lonely",
            "broken", "miss", "death", "loss", "hurt", "depress", "gham", "tanha", "akela"],
    "happy": ["happy", "joy", "fun", "laugh", "celebrate", "khushi", "maza", "mazaa",
              "smile", "excited", "amazing", "great", "awesome", "enjoy", "khush", "hassi"],
    "energetic": ["money", "hustle", "grind", "power", "win", "energy", "party", "dance",
                  "success", "goal", "beast", "fire", "boss", "gym", "paisa", "mehnat",
                  "kamyabi", "jeet", "power", "speed"],
    "calm": ["calm", "peace", "relax", "slow", "quiet", "meditate", "sukoon", "breath",
             "gentle", "soft", "shanti", "aaram"],
}

LABELS: dict[str, tuple[str, str, str]] = {
    "romantic": ("Romantic", "💜", "soft, emotional track"),
    "sad": ("Sad / Emotional", "🖤", "slow, emotional track"),
    "happy": ("Happy / Upbeat", "☀️", "cheerful, upbeat track"),
    "energetic": ("Energetic / Hype", "🔥", "high-energy trap / hype beat"),
    "calm": ("Calm / Chill", "🌙", "chill lo-fi track"),
    "neutral": ("Neutral", "🎵", "any subtle background track"),
}


def suggest_mood(text: str) -> dict:
    """Return {mood,label,emoji,hint,scores} for the transcript text."""
    t = (text or "").lower()
    scores = {m: sum(t.count(k) for k in kws) for m, kws in KEYWORDS.items()}
    best = max(scores, key=lambda m: scores[m]) if any(scores.values()) else "neutral"
    if scores.get(best, 0) == 0:
        best = "neutral"
    label, emoji, hint = LABELS[best]
    return {"mood": best, "label": label, "emoji": emoji, "hint": hint, "scores": scores}
