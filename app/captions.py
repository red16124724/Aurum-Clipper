"""Styled caption (ASS subtitle) generation — the single source of truth for
caption styles.

`STYLE_PRESETS` is consumed by TWO places so the on-screen burned-in result and
the live UI preview stay in sync:
  1. `build_ass(...)` maps a preset to ASS style fields for ffmpeg/libass.
  2. `get_presets_for_api()` exposes the same fields (font, sizes, colours,
     highlight, position) so the frontend can render an accurate CSS preview.

All colours are stored as CSS hex (#RRGGBB) and converted to ASS's
&HAABBGGRR form at render time.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

# --------------------------------------------------------------------------- #
# Style presets — defined ONCE, used for both ASS rendering and the UI preview.
# font_size values are tuned for a 1080x1920 (9:16) frame and scaled to other
# resolutions at render time.
# --------------------------------------------------------------------------- #
STYLE_PRESETS: dict[str, dict] = {
    "bold_white": {
        "label": "Bold White",
        "font_family": "Roboto",
        "bold": True,
        "font_size": 96,
        "primary_color": "#FFFFFF",
        "highlight_color": "#FFFFFF",  # no per-word highlight
        "outline_color": "#000000",
        "outline": 5,
        "shadow": 1,
        "position": "bottom",
        "karaoke": False,
        "uppercase": True,
    },
    "karaoke_yellow": {
        "label": "Karaoke Yellow",
        "font_family": "Roboto",
        "bold": True,
        "font_size": 92,
        "primary_color": "#FFFFFF",   # word colour before it is reached
        "highlight_color": "#FFE600",  # word colour once it is "sung"
        "outline_color": "#000000",
        "outline": 5,
        "shadow": 1,
        "position": "bottom",
        "karaoke": True,
        "uppercase": True,
    },
    "minimal": {
        "label": "Minimal",
        "font_family": "Roboto",
        "bold": False,
        "font_size": 64,
        "primary_color": "#FFFFFF",
        "highlight_color": "#FFFFFF",
        "outline_color": "#000000",
        "outline": 1,
        "shadow": 2,  # subtle drop shadow rather than a thick outline
        "position": "bottom",
        "karaoke": False,
        "uppercase": False,
    },
}

DEFAULT_PRESET = "bold_white"


# --------------------------------------------------------------------------- #
# API helper
# --------------------------------------------------------------------------- #
def get_presets_for_api() -> List[dict]:
    """Return presets in the shape the frontend needs to render previews."""
    out: List[dict] = []
    for preset_id, p in STYLE_PRESETS.items():
        out.append(
            {
                "id": preset_id,
                "label": p["label"],
                "font_family": p["font_family"],
                "font_size": p["font_size"],
                "bold": p["bold"],
                "primary_color": p["primary_color"],
                "highlight_color": p["highlight_color"],
                "outline_color": p["outline_color"],
                "outline": p["outline"],
                "position": p["position"],
                "karaoke": p["karaoke"],
                "uppercase": p["uppercase"],
            }
        )
    return out


def get_preset(preset_id: str) -> dict:
    """Return a preset dict, defaulting to bold_white for unknown ids."""
    return STYLE_PRESETS.get(preset_id, STYLE_PRESETS[DEFAULT_PRESET])


# --------------------------------------------------------------------------- #
# Colour + time conversion
# --------------------------------------------------------------------------- #
def _hex_to_ass(hex_color: str) -> str:
    """Convert '#RRGGBB' to ASS '&H00BBGGRR' (00 alpha = fully opaque)."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        h = "FFFFFF"
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H00{b}{g}{r}".upper()


def _fmt_time(seconds: float) -> str:
    """Format seconds as ASS time H:MM:SS.cs (centiseconds)."""
    if seconds < 0:
        seconds = 0.0
    cs_total = int(round(seconds * 100))
    cs = cs_total % 100
    s_total = cs_total // 100
    s = s_total % 60
    m = (s_total // 60) % 60
    h = s_total // 3600
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _ass_escape(text: str) -> str:
    """Escape characters that are special inside an ASS Dialogue field."""
    return (
        text.replace("\\", "\\\\")
        .replace("{", "(")
        .replace("}", ")")
        .replace("\n", " ")
        .strip()
    )


# --------------------------------------------------------------------------- #
# Word grouping
# --------------------------------------------------------------------------- #
def _group_words(words: List[dict], max_words: int = 4, max_span: float = 1.5) -> List[dict]:
    """Group words into short caption lines (<=max_words OR <=max_span seconds).

    Each returned line: {"start", "end", "words": [{word,start,end}, ...]}.
    """
    lines: List[dict] = []
    current: List[dict] = []

    for w in words:
        if not current:
            current = [w]
            continue

        span = w["end"] - current[0]["start"]
        if len(current) >= max_words or span > max_span:
            lines.append(
                {
                    "start": current[0]["start"],
                    "end": current[-1]["end"],
                    "words": current,
                }
            )
            current = [w]
        else:
            current.append(w)

    if current:
        lines.append(
            {
                "start": current[0]["start"],
                "end": current[-1]["end"],
                "words": current,
            }
        )
    return lines


# --------------------------------------------------------------------------- #
# ASS builder
# --------------------------------------------------------------------------- #
def build_ass(
    words: List[dict],
    style_preset: str,
    video_w: int,
    video_h: int,
    out_path: Path,
    clip_start: float = 0.0,
) -> Path:
    """Build an .ass subtitle file at `out_path` and return it.

    Args:
        words: list of {word, start, end} with timings in the SOURCE timeline.
        style_preset: preset id from STYLE_PRESETS.
        video_w/video_h: target frame size (sets PlayResX/Y so font px map 1:1).
        out_path: where to write the .ass file.
        clip_start: subtract this from word timings so captions align to the cut.
    """
    preset = get_preset(style_preset)

    # Scale font/outline so presets (tuned for 1920 tall) look right at any height.
    scale = video_h / 1920.0
    font_size = max(12, int(round(preset["font_size"] * scale)))
    outline = max(0, int(round(preset["outline"] * scale)))
    shadow = max(0, int(round(preset["shadow"] * scale)))
    margin_v = int(round(video_h * 0.08))

    primary = _hex_to_ass(preset["primary_color"])
    highlight = _hex_to_ass(preset["highlight_color"])
    outline_col = _hex_to_ass(preset["outline_color"])
    bold_flag = -1 if preset["bold"] else 0  # ASS: -1 = true, 0 = false
    alignment = 2  # bottom-center (numpad layout)

    # For karaoke, libass fills each syllable from SecondaryColour -> PrimaryColour.
    # So PrimaryColour must be the highlight colour and Secondary the base colour.
    if preset["karaoke"]:
        style_primary = highlight
        style_secondary = primary
    else:
        style_primary = primary
        style_secondary = primary

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_w}
PlayResY: {video_h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{preset['font_family']},{font_size},{style_primary},{style_secondary},{outline_col},&H64000000,{bold_flag},0,0,0,100,100,0,0,1,{outline},{shadow},{alignment},60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lines = _group_words(words, max_words=4, max_span=1.5)
    dialogue_rows: List[str] = []

    for line in lines:
        start = line["start"] - clip_start
        end = line["end"] - clip_start
        if end <= 0:
            continue
        start = max(0.0, start)

        if preset["karaoke"]:
            text = _build_karaoke_text(line["words"], clip_start, preset["uppercase"])
        else:
            text = _build_plain_text(line["words"], preset["uppercase"])

        dialogue_rows.append(
            f"Dialogue: 0,{_fmt_time(start)},{_fmt_time(end)},Default,,0,0,0,,{text}"
        )

    out_path.write_text(header + "\n".join(dialogue_rows) + "\n", encoding="utf-8")
    return out_path


def _build_plain_text(line_words: List[dict], uppercase: bool) -> str:
    tokens = [_ass_escape(w["word"]) for w in line_words]
    text = " ".join(t for t in tokens if t)
    return text.upper() if uppercase else text


def _build_karaoke_text(line_words: List[dict], clip_start: float, uppercase: bool) -> str:
    """Build a karaoke line where each word is timed with {\\k<centiseconds>}."""
    parts: List[str] = []
    prev_end = line_words[0]["start"]

    for w in line_words:
        # Gap before the word (if any) consumes time at the base colour.
        gap_cs = max(0, int(round((w["start"] - prev_end) * 100)))
        dur_cs = max(1, int(round((w["end"] - w["start"]) * 100)))
        token = _ass_escape(w["word"])
        if uppercase:
            token = token.upper()
        if gap_cs > 0:
            parts.append(f"{{\\k{gap_cs}}}")
        parts.append(f"{{\\k{dur_cs}}}{token} ")
        prev_end = w["end"]

    return "".join(parts).strip()
