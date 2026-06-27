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
# Every preset shares this shape; a preset only lists what differs. This keeps
# the (long) list readable AND guarantees every key exists for both the renderer
# and the API/preview, so neither can KeyError on a new field.
#   animation: "none" | "karaoke" (via karaoke flag) | "word_reveal" | "one_word"
#              | "highlight" (whole phrase shown, active word recolours — the
#              Hormozi/creator look).
_BASE_PRESET = {
    "font_family": "Roboto",
    "bold": True,
    "font_size": 90,
    "primary_color": "#FFFFFF",
    "highlight_color": "#FFD400",
    "outline_color": "#000000",
    "outline": 5,
    "shadow": 1,
    "position": "bottom",
    "karaoke": False,
    "uppercase": True,
    "animation": "none",
    "tracking": 0,
    "underline": False,
    "strikethrough": False,
    "max_lines": 2,
    "max_chars": 22,
    "background_enabled": False,
    "background_color": "#000000",
    "trending": False,
}


def _P(label: str, **kw) -> dict:
    """Build a preset from the base template, overriding only what differs."""
    d = dict(_BASE_PRESET)
    d["label"] = label
    d.update(kw)
    return d


STYLE_PRESETS: dict[str, dict] = {
    # --- Originals ---
    "bold_white": _P("Bold White", highlight_color="#FFFFFF", font_size=96, max_chars=20),
    "karaoke_yellow": _P("Karaoke Yellow", karaoke=True, font_size=92, highlight_color="#FFE600"),
    "minimal": _P("Minimal", bold=False, uppercase=False, font_size=64, outline=1, shadow=2,
                  highlight_color="#FFFFFF", max_chars=28),

    # --- Creator / trending styles ---
    "hormozi_green": _P("Hormozi Green", trending=True, font_family="Montserrat",
                        animation="highlight", highlight_color="#27E36B", font_size=94,
                        outline=6, position="center", max_lines=2, max_chars=16),
    "hormozi_yellow": _P("Hormozi Yellow", trending=True, font_family="Montserrat",
                         animation="highlight", highlight_color="#FFD400", font_size=94,
                         outline=6, position="center", max_lines=2, max_chars=16),
    "beast_red": _P("Beast Pop", trending=True, font_family="Anton", bold=False,
                    animation="highlight", highlight_color="#FF3B30", font_size=108,
                    outline=7, position="center", max_lines=2, max_chars=15),
    "raj_clean": _P("Raj Shamani Clean", trending=True, font_family="Poppins",
                    animation="highlight", uppercase=False, highlight_color="#FFC400",
                    font_size=78, outline=4, max_chars=26),
    "alex_caps": _P("Alex Bold Caps", trending=True, font_family="Montserrat",
                    animation="highlight", highlight_color="#22D3EE", font_size=92,
                    outline=6, position="center", max_chars=17),
    "one_word_punch": _P("One-Word Punch", trending=True, font_family="Anton", bold=False,
                         animation="one_word", font_size=132, outline=8, position="center"),
    "word_reveal": _P("Word Reveal", trending=True, font_family="Montserrat",
                      animation="word_reveal", highlight_color="#FFFFFF", font_size=90, outline=5),
    "bebas_clean": _P("Bebas Clean", trending=True, font_family="Bebas Neue", bold=False,
                      font_size=110, outline=4, highlight_color="#FFFFFF", tracking=2, max_chars=22),
    "comic_bangers": _P("Comic Punch", trending=True, font_family="Bangers", bold=False,
                        primary_color="#FFE600", highlight_color="#FFFFFF", font_size=104,
                        outline=6, max_chars=20),
    "slab_impact": _P("Slab Impact", trending=True, font_family="Alfa Slab One", bold=False,
                      animation="highlight", highlight_color="#FFD400", font_size=84, outline=6),
    "marker_note": _P("Marker", trending=True, font_family="Permanent Marker", bold=False,
                      uppercase=False, highlight_color="#FFD400", font_size=82, outline=5),
    "serif_elegant": _P("Serif Elegant", trending=True, font_family="DM Serif Display", bold=False,
                        uppercase=False, highlight_color="#FFD400", font_size=88, outline=2, shadow=3,
                        max_chars=30),
    "neon_pop": _P("Neon Pop", trending=True, font_family="Luckiest Guy", bold=False,
                   animation="highlight", highlight_color="#22D3EE", outline_color="#101018",
                   font_size=92, outline=6, position="center"),
    "boxed_tiktok": _P("Boxed", trending=True, font_family="Roboto", background_enabled=True,
                       background_color="#000000", highlight_color="#FFFFFF", font_size=78,
                       outline=6, shadow=0, max_chars=24),
    "oswald_news": _P("Oswald News", trending=True, font_family="Oswald",
                      animation="highlight", highlight_color="#FFD400", font_size=86, outline=4),
    "green_word": _P("Green Word", trending=True, font_family="Poppins",
                     animation="highlight", highlight_color="#27E36B", font_size=84, outline=5),
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
                "shadow": p["shadow"],
                "position": p["position"],
                "karaoke": p["karaoke"],
                "uppercase": p["uppercase"],
                "animation": p.get("animation", "none"),
                "tracking": p.get("tracking", 0),
                "underline": p.get("underline", False),
                "strikethrough": p.get("strikethrough", False),
                "max_lines": p.get("max_lines", 2),
                "max_chars": p.get("max_chars", 22),
                "background_enabled": p.get("background_enabled", False),
                "background_color": p.get("background_color", "#000000"),
                "trending": p.get("trending", False),
            }
        )
    return out


def get_preset(preset_id: str) -> dict:
    """Return a preset dict, defaulting to bold_white for unknown ids."""
    return STYLE_PRESETS.get(preset_id, STYLE_PRESETS[DEFAULT_PRESET])


# --------------------------------------------------------------------------- #
# Colour + time conversion
# --------------------------------------------------------------------------- #
def _hex_to_ass(hex_color: str, alpha: int = 0) -> str:
    """Convert '#RRGGBB' to ASS '&HAABBGGRR'.

    ``alpha`` is ASS alpha (0 = fully opaque, 255 = fully transparent).
    """
    h = (hex_color or "").lstrip("#")
    if len(h) != 6:
        h = "FFFFFF"
    r, g, b = h[0:2], h[2:4], h[4:6]
    a = max(0, min(255, int(alpha)))
    return f"&H{a:02X}{b}{g}{r}".upper()


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
def _line_len(line: List[dict]) -> int:
    """Rendered character length of a line (words + the single spaces between)."""
    if not line:
        return 0
    return sum(len(w["word"]) for w in line) + (len(line) - 1)


def _group_events(
    words: List[dict],
    max_chars: int,
    max_lines: int,
    max_span: float = 2.5,
) -> List[dict]:
    """Pack words into caption events of up to ``max_lines`` lines.

    A word joins the current line while it fits within ``max_chars``; otherwise it
    starts a new line, or — when the event is already ``max_lines`` tall — a new
    event. ``max_span`` caps how long one event lasts so captions keep pace with
    speech. Each event: {"start", "end", "lines": [[word, ...], ...]}.
    """
    events: List[dict] = []
    cur_lines: List[List[dict]] = [[]]

    def event_start() -> float | None:
        for ln in cur_lines:
            if ln:
                return ln[0]["start"]
        return None

    def flush() -> None:
        nonlocal cur_lines
        filled = [ln for ln in cur_lines if ln]
        if filled:
            flat = [w for ln in filled for w in ln]
            events.append(
                {"start": flat[0]["start"], "end": flat[-1]["end"], "lines": filled}
            )
        cur_lines = [[]]

    for w in words:
        start = event_start()
        # Time cap: a long-running event is closed before this word extends it.
        if start is not None and (w["end"] - start) > max_span:
            flush()

        cur_line = cur_lines[-1]
        tentative = _line_len(cur_line) + (1 if cur_line else 0) + len(w["word"])
        if cur_line and tentative > max_chars:
            if len(cur_lines) < max_lines:
                cur_lines.append([w])      # wrap onto a second line
            else:
                flush()
                cur_lines = [[w]]          # start a fresh event
        else:
            cur_line.append(w)

    flush()
    return events


def _word_hold_events(words: List[dict], max_gap: float = 0.7) -> List[dict]:
    """One event per word (the 'one word at a time' style).

    Each word holds the screen until the next word begins, so there is no flicker
    between words — except across a real pause (> ``max_gap`` s), where the word
    is held only briefly so it doesn't linger through silence.
    """
    events: List[dict] = []
    n = len(words)
    for i, w in enumerate(words):
        if i + 1 < n:
            nxt = words[i + 1]["start"]
            end = nxt if (nxt - w["end"]) <= max_gap else w["end"] + 0.3
        else:
            end = w["end"]
        events.append({"start": w["start"], "end": max(end, w["end"]), "lines": [[w]]})
    return events


# --------------------------------------------------------------------------- #
# ASS builder
# --------------------------------------------------------------------------- #
def _merge_overrides(preset: dict, overrides: dict | None) -> dict:
    """Layer user `overrides` (any subset, None values ignored) onto `preset`."""
    merged = dict(preset)
    if overrides:
        for key, value in overrides.items():
            if value is not None:
                merged[key] = value
    return merged


def build_ass(
    words: List[dict],
    style_preset: str,
    video_w: int,
    video_h: int,
    out_path: Path,
    clip_start: float = 0.0,
    overrides: dict | None = None,
    fit_mode: str | None = None,
) -> Path:
    """Build an .ass subtitle file at `out_path` and return it.

    Args:
        words: list of {word, start, end} with timings in the SOURCE timeline.
        style_preset: preset id from STYLE_PRESETS.
        video_w/video_h: target frame size (sets PlayResX/Y so font px map 1:1).
        out_path: where to write the .ass file.
        clip_start: subtract this from word timings so captions align to the cut.
        overrides: optional per-render tweaks (position, rotation, stroke, shadow,
            background) that layer over the preset. See ``models.CaptionOverrides``.
        fit_mode: "square" pulls the default caption margin up so captions sit
            inside the centered square instead of in the black band below it.
            Any other value keeps the normal full-frame placement.
    """
    preset = get_preset(style_preset)
    cfg = _merge_overrides(preset, overrides)

    # Scale font/outline so presets (tuned for 1920 tall) look right at any height.
    scale = video_h / 1920.0
    font_scale = float(cfg.get("font_scale", 1.0) or 1.0)
    font_size = max(12, int(round(cfg["font_size"] * font_scale * scale)))

    # Stroke / outline width: from overrides ("outline_width") or the preset ("outline").
    outline_px = cfg.get("outline_width", cfg["outline"])
    outline = max(0, int(round(outline_px * scale)))

    # Drop shadow: an explicit toggle wins; otherwise fall back to the preset depth.
    shadow_on = cfg.get("shadow_enabled")
    if shadow_on is None:
        shadow_on = cfg["shadow"] > 0
    shadow_px = cfg.get("shadow_distance", cfg["shadow"])
    shadow = max(0, int(round(shadow_px * scale))) if shadow_on else 0
    shadow_color = cfg.get("shadow_color", "#000000")

    # Background box behind the words (BorderStyle 3) vs a per-glyph outline (1).
    bg_on = bool(cfg.get("background_enabled"))
    border_style = 3 if bg_on else 1
    # Vertical margin for top/bottom-anchored captions. In square mode the footage
    # fills a centered 1:1 square; captions sit in the black band JUST BELOW the
    # square (top-anchored there), so the title sits above the square and the
    # caption hugs it from below — both attached, outside the square. ``square_align``
    # forces that top anchor regardless of the preset's position.
    square_align = None
    if fit_mode == "square":
        inner = max(0, video_w - 60)              # square side (matches clipper geometry)
        band = max(0, (video_h - inner) // 2)     # black band above & below the square
        square_align = 8                          # top-anchored, in the band below the square
        margin_v = band + inner + int(round(inner * 0.03))   # just below the square's bottom edge
    else:
        margin_v = int(round(video_h * 0.08))

    primary = _hex_to_ass(cfg["primary_color"])
    highlight = _hex_to_ass(cfg["highlight_color"])
    # In box mode the OutlineColour slot fills the box; otherwise it strokes glyphs.
    if bg_on:
        bg_alpha = int(round((100 - float(cfg.get("background_opacity", 100) or 100)) / 100 * 255))
        outline_col = _hex_to_ass(cfg.get("background_color", "#000000"), alpha=bg_alpha)
    else:
        outline_col = _hex_to_ass(cfg["outline_color"])
    # Drop-shadow colour + opacity (BackColour slot, offset by Shadow px).
    sh_alpha = int(round((100 - float(cfg.get("shadow_opacity", 75) or 75)) / 100 * 255))
    back_col = _hex_to_ass(shadow_color, alpha=sh_alpha)
    bold_flag = -1 if cfg["bold"] else 0  # ASS: -1 = true, 0 = false
    underline_flag = -1 if cfg.get("underline") else 0
    strike_flag = -1 if cfg.get("strikethrough") else 0
    spacing = max(0, int(round(float(cfg.get("tracking", 0) or 0) * scale)))
    # Vertical placement -> ASS alignment (numpad). A pos_x/pos_y override still
    # wins, because an \an5\pos prefix is emitted per line when those are set.
    alignment = {"top": 8, "center": 5, "bottom": 2}.get(cfg.get("position", "bottom"), 2)
    if square_align is not None:
        alignment = square_align  # square mode anchors the caption just below the box

    # For karaoke, libass fills each syllable from SecondaryColour -> PrimaryColour.
    # So PrimaryColour must be the highlight colour and Secondary the base colour.
    if cfg["karaoke"]:
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
Style: Default,{cfg['font_family']},{font_size},{style_primary},{style_secondary},{outline_col},{back_col},{bold_flag},0,{underline_flag},{strike_flag},100,100,{spacing},0,{border_style},{outline},{shadow},{alignment},60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    pos_inner = _override_inner(cfg, video_w, video_h, fit_mode)
    prefix = ("{" + pos_inner + "}") if pos_inner else ""
    uppercase = cfg["uppercase"]

    # Optional soft glow: a blurred, glow-coloured copy of the words drawn on a
    # lower layer behind the sharp text (libass \\blur). Off by default.
    glow_on = bool(cfg.get("glow_enabled"))
    glow_px = max(1, int(round(float(cfg.get("glow_intensity", 10) or 10) * scale))) if glow_on else 0
    glow_col = _hex_to_ass(cfg.get("glow_color", "#7C4DFF"))
    glow_prefix = "{" + pos_inner + f"\\1c{glow_col}\\3c{glow_col}\\bord{glow_px}\\shad0\\blur{glow_px}" + "}"
    main_layer = 1 if glow_on else 0

    # Layout + animation settings (overridable; defaults match the classic look).
    animation = cfg.get("animation") or "none"
    max_lines = int(cfg.get("max_lines") or 1)
    max_chars = int(cfg.get("max_chars") or 22)

    if animation == "one_word":
        events = _word_hold_events(words)
    else:
        events = _group_events(words, max_chars=max_chars, max_lines=max_lines)

    dialogue_rows: List[str] = []
    for ev in events:
        start = ev["start"] - clip_start
        end = ev["end"] - clip_start
        if end <= 0:
            continue
        start = max(0.0, start)

        if animation == "one_word":
            text = _build_one_word_text(ev["lines"][0][0], uppercase)
        elif animation == "word_reveal":
            text = _build_reveal_text(ev, uppercase)
        elif animation == "highlight":
            text = _build_active_word_text(ev, cfg, uppercase)
        elif cfg["karaoke"]:
            text = _build_karaoke_text(ev["lines"], uppercase)
        else:
            text = _build_plain_text(ev["lines"], uppercase)

        if glow_on:
            glow_text = _build_plain_text(ev["lines"], uppercase)
            dialogue_rows.append(
                f"Dialogue: 0,{_fmt_time(start)},{_fmt_time(end)},Default,,0,0,0,,{glow_prefix}{glow_text}"
            )
        dialogue_rows.append(
            f"Dialogue: {main_layer},{_fmt_time(start)},{_fmt_time(end)},Default,,0,0,0,,{prefix}{text}"
        )

    out_path.write_text(header + "\n".join(dialogue_rows) + "\n", encoding="utf-8")
    return out_path


def _override_inner(cfg: dict, video_w: int, video_h: int, fit_mode: str | None = None) -> str:
    """Build the inline ASS tags (no braces) for position + rotation overrides.

    Position uses ``\\an5`` (centre anchor) + ``\\pos`` so the X/Y sliders place
    the caption block's centre anywhere in the frame; rotation uses ``\\frz``.
    Returns "" when neither is set, leaving the style's default bottom-centre.
    Callers wrap the result in ``{...}`` (and may append further tags, e.g. glow).

    In square mode ``pos_y`` is a % of the SQUARE (not the full canvas), matching
    the live preview — otherwise a dragged caption lands in the black band below
    the square instead of where the preview showed it.
    """
    tags: List[str] = []

    pos_x = cfg.get("pos_x")
    pos_y = cfg.get("pos_y")
    if pos_x is not None and pos_y is not None:
        x = int(round(pos_x / 100.0 * video_w))
        if fit_mode == "square":
            inner = max(0, video_w - 60)              # square side (matches clipper)
            band = max(0, (video_h - inner) // 2)     # black band above the square
            y = int(round(band + pos_y / 100.0 * inner))
        else:
            y = int(round(pos_y / 100.0 * video_h))
        tags.append(f"\\an5\\pos({x},{y})")

    rotation = cfg.get("rotation")
    if rotation:  # non-zero
        tags.append(f"\\frz{rotation:g}")

    return "".join(tags)


def _tok(word: str, uppercase: bool) -> str:
    t = _ass_escape(word)
    return t.upper() if uppercase else t


def _build_plain_text(lines: List[List[dict]], uppercase: bool) -> str:
    """Static caption: words joined by spaces, lines joined by an ASS line break."""
    rendered = []
    for line in lines:
        rendered.append(" ".join(_tok(w["word"], uppercase) for w in line if w["word"]))
    return "\\N".join(r for r in rendered if r)


def _build_karaoke_text(lines: List[List[dict]], uppercase: bool) -> str:
    """Karaoke: each word timed with {\\k<centiseconds>}; lines split by \\N."""
    line_strs: List[str] = []
    for line in lines:
        parts: List[str] = []
        prev_end = line[0]["start"]
        for w in line:
            # Gap before the word (if any) consumes time at the base colour.
            gap_cs = max(0, int(round((w["start"] - prev_end) * 100)))
            dur_cs = max(1, int(round((w["end"] - w["start"]) * 100)))
            if gap_cs > 0:
                parts.append(f"{{\\k{gap_cs}}}")
            parts.append(f"{{\\k{dur_cs}}}{_tok(w['word'], uppercase)} ")
            prev_end = w["end"]
        line_strs.append("".join(parts).strip())
    return "\\N".join(line_strs)


def _build_reveal_text(ev: dict, uppercase: bool) -> str:
    """Word-by-word reveal: each word fades + pops in at its own start time.

    Words begin invisible and small, then animate to opaque, full-size via ``\\t``
    timed (in ms) from the event's display start — so the whole phrase stays on
    screen, revealed one word at a time as it is spoken.
    """
    ev_start = ev["start"]
    line_strs: List[str] = []
    for line in ev["lines"]:
        toks: List[str] = []
        for w in line:
            t = max(0, int(round((w["start"] - ev_start) * 1000)))
            toks.append(
                f"{{\\alpha&HFF&\\fscx70\\fscy70"
                f"\\t({t},{t + 130},\\alpha&H00&\\fscx100\\fscy100)}}"
                f"{_tok(w['word'], uppercase)}"
            )
        line_strs.append(" ".join(toks))
    return "\\N".join(line_strs)


def _build_active_word_text(ev: dict, cfg: dict, uppercase: bool) -> str:
    """Whole phrase visible; the word being spoken recolours to the highlight.

    This is the signature creator / "Hormozi" look. Each word starts at the base
    (primary) colour, instantly switches to ``highlight_color`` at its own start
    time, and snaps back at its end — via zero-length ``\\t`` transforms timed (ms)
    from the event's display start. The full phrase stays on screen throughout.
    """
    base = _hex_to_ass(cfg["primary_color"])
    hi = _hex_to_ass(cfg["highlight_color"])
    ev_start = ev["start"]
    line_strs: List[str] = []
    for line in ev["lines"]:
        toks: List[str] = []
        for w in line:
            t0 = max(0, int(round((w["start"] - ev_start) * 1000)))
            t1 = max(t0 + 1, int(round((w["end"] - ev_start) * 1000)))
            toks.append(
                f"{{\\1c{base}\\t({t0},{t0},\\1c{hi})\\t({t1},{t1},\\1c{base})}}"
                f"{_tok(w['word'], uppercase)}"
            )
        line_strs.append(" ".join(toks))
    return "\\N".join(line_strs)


def _build_one_word_text(word: dict, uppercase: bool) -> str:
    """Single word with a quick fade + pop-in (the 'one word at a time' style)."""
    return (
        "{\\fad(60,0)\\fscx82\\fscy82\\t(0,130,\\fscx100\\fscy100)}"
        f"{_tok(word['word'], uppercase)}"
    )
