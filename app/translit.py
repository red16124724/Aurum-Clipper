"""Hinglish romanisation — turn Devanagari (Hindi/Urdu speech) into readable
Roman ("Hinglish", the way people actually type Urdu/Hindi in English letters).

Whisper transcribes Hindustani in Devanagari; this module converts each word
into Latin script so captions read like "aap kaise hain" instead of the native
script. It is intentionally a *readable approximation*, not a strict academic
transliteration:

  1. Devanagari -> IAST (via indic-transliteration) gives a clean, reversible
     base where the inherent schwa is a short ``a`` and long vowels carry
     diacritics (``ā`` etc).
  2. The trailing inherent schwa is dropped (``ghara`` -> ``ghar``,
     ``dosta`` -> ``dost``) — Hindi deletes it in speech, and keeping it is the
     #1 thing that makes naive transliteration look wrong.
  3. ``c`` -> ``ch`` and a few sounds (``ś/ṣ`` -> ``sh``) are spelled the way
     people type them.
  4. Remaining diacritics are folded to plain ASCII (``ā`` -> ``a``).

Word-level so caption timings are preserved: each timed token is romanised on
its own. If the library is unavailable the text is returned unchanged (captions
still render, just in the native script) so this never breaks a render.
"""

from __future__ import annotations

import logging
import re
import unicodedata

logger = logging.getLogger(__name__)

try:
    from indic_transliteration import sanscript
    from indic_transliteration.sanscript import transliterate

    _AVAILABLE = True
except Exception:  # noqa: BLE001 - degrade to a no-op if the dep is missing
    _AVAILABLE = False
    logger.warning("indic-transliteration not installed; Hinglish output disabled.")

# Any Devanagari codepoint — used to skip romanising pure-ASCII/number tokens.
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")

# Sounds spelled for readability BEFORE folding the rest to ASCII. Applied to the
# IAST string, so e.g. ``ś``/``ṣ`` become ``sh`` rather than a bare ``s``.
_PRE_FOLD = {
    "ṛ": "ri", "ṝ": "ri",
    "ṅ": "ng", "ñ": "n",
    "ś": "sh", "ṣ": "sh",
    "ṁ": "n", "ṃ": "n",   # anusvara -> n (hain, main, …)
    "~": "n", "m̐": "n",   # chandrabindu nasalisation (hūṁ -> hun)
}


def available() -> bool:
    """True if the transliteration backend is importable."""
    return _AVAILABLE


def _romanize_word(word: str) -> str:
    """Romanise a single Devanagari token to readable Hinglish."""
    if not _DEVANAGARI.search(word):
        return word  # numbers / Latin / punctuation pass straight through

    iast = transliterate(word, sanscript.DEVANAGARI, sanscript.IAST)

    for src, dst in _PRE_FOLD.items():
        iast = iast.replace(src, dst)

    # च = "c" -> "ch", छ = "ch" -> "chh", without the second pass clobbering the
    # first: park छ on a placeholder, expand च, then restore.
    iast = iast.replace("ch", "\x01").replace("c", "ch").replace("\x01", "chh")

    # Drop the trailing inherent schwa (short 'a'): ghara -> ghar, dosta -> dost.
    # Done while long 'ā' is still a distinct character, so a genuine long-vowel
    # ending isn't trimmed. Guarded so tiny words (na, ja) keep a vowel.
    if len(iast) >= 3 and iast.endswith("a"):
        iast = iast[:-1]

    # Long 'ā' -> 'aa' the way Hinglish is typed (aap, kaam, yaar) — after schwa
    # deletion so it only doubles real long vowels.
    iast = iast.replace("ā", "aa")

    # Fold any remaining diacritics to plain ASCII (ī -> i, ū -> u, …).
    folded = "".join(
        c for c in unicodedata.normalize("NFKD", iast) if not unicodedata.combining(c)
    )
    return folded.lower()


def to_roman(text: str) -> str:
    """Romanise a run of text token-by-token (whitespace preserved)."""
    if not text or not _AVAILABLE or not _DEVANAGARI.search(text):
        return text
    # Split on whitespace but keep the separators so spacing is preserved.
    parts = re.split(r"(\s+)", text)
    return "".join(p if p.isspace() else _romanize_word(p) for p in parts)


def romanize_transcript(transcript: dict) -> dict:
    """Return a copy of a Whisper transcript with all text fields romanised.

    Romanises the word tokens (keeping their timings), the segment texts, and the
    full text. The ``language`` is tagged ``"hinglish"`` so downstream naming and
    the UI know the captions are Roman Urdu/Hindi. A no-op (returns the input) if
    the backend is unavailable.
    """
    if not _AVAILABLE:
        return transcript

    out = dict(transcript)
    out["language"] = "hinglish"
    out["words"] = [
        {**w, "word": to_roman(w.get("word", ""))} for w in transcript.get("words", [])
    ]
    out["segments"] = [
        {**s, "text": to_roman(s.get("text", ""))}
        for s in transcript.get("segments", [])
    ]
    if transcript.get("text"):
        out["text"] = to_roman(transcript["text"])
    return out
