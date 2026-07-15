"""Pydantic schemas, enums, and custom exceptions for the API.

These are the contract between the frontend and the pipeline. Keeping them in
one module means the request/response shapes and the domain errors live in a
single, easy-to-audit place.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

# ISO language code -> native display name, used to name downloaded clip files in
# the caption's own language (e.g. an Urdu clip downloads as "اردو - ….mp4").
# Codes match what faster-whisper reports in `info.language`.
LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "hinglish": "Hinglish",
    "ur": "اردو",
    "hi": "हिन्दी",
    "ar": "العربية",
    "fa": "فارسی",
    "pa": "ਪੰਜਾਬੀ",
    "bn": "বাংলা",
    "mr": "मराठी",
    "ne": "नेपाली",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
    "pt": "Português",
    "ru": "Русский",
    "tr": "Türkçe",
    "id": "Bahasa",
    "ja": "日本語",
    "ko": "한국어",
    "zh": "中文",
}


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class AspectRatio(str, Enum):
    """Output aspect ratio. Vertical (9:16) is the default for shorts."""

    NINE_16 = "9:16"
    SIXTEEN_9 = "16:9"


class FitMode(str, Enum):
    """How the source is fitted into the target frame.

    - crop:   scale to *cover* the chosen aspect ratio, then center-crop (fills it).
    - square: force a 1:1 square frame and center-crop to fill it. The chosen
              aspect_ratio is IGNORED in this mode.
    """

    CROP = "crop"
    SQUARE = "square"


class SquareCorners(str, Enum):
    """Corner style of the centered square in ``square`` fit mode."""

    ROUND = "round"
    SQUARE = "square"


class Device(str, Enum):
    """Which compute device runs the local Whisper transcription.

    - auto: prefer the GPU (CUDA) when available, otherwise the CPU.
    - cuda: force the NVIDIA GPU (errors clearly if it cannot be used).
    - cpu:  force the CPU (slower on 'medium' but works everywhere).
    """

    AUTO = "auto"
    CUDA = "cuda"
    CPU = "cpu"


# --------------------------------------------------------------------------- #
# Request / response schemas
# --------------------------------------------------------------------------- #
class CaptionOverrides(BaseModel):
    """User tweaks layered on top of the chosen caption preset.

    Every field is optional: an unset field falls back to the preset's value in
    ``captions.build_ass``. Values are expressed in the same 1080x1920-tuned
    space the presets use, so they scale to any output resolution at render time.
    Colours are CSS hex (#RRGGBB).
    """

    pos_x: Optional[float] = Field(
        default=None, ge=0, le=100,
        description="Horizontal centre of the caption, as % of frame width.",
    )
    pos_y: Optional[float] = Field(
        default=None, ge=0, le=100,
        description="Vertical centre of the caption, as % of frame height.",
    )
    rotation: Optional[float] = Field(
        default=None, ge=-180, le=180,
        description="Caption rotation in degrees (counter-clockwise positive).",
    )
    outline_width: Optional[float] = Field(
        default=None, ge=0, le=40,
        description="Stroke/outline thickness in px (at 1080-wide scale).",
    )
    outline_color: Optional[str] = Field(
        default=None, description="Stroke/outline colour (#RRGGBB)."
    )
    shadow_enabled: Optional[bool] = Field(
        default=None, description="Whether to draw a drop shadow."
    )
    shadow_distance: Optional[float] = Field(
        default=None, ge=0, le=40,
        description="Drop-shadow offset in px (at 1080-wide scale).",
    )
    shadow_color: Optional[str] = Field(
        default=None, description="Drop-shadow colour (#RRGGBB)."
    )
    background_enabled: Optional[bool] = Field(
        default=None, description="Whether to draw a filled box behind the words."
    )
    background_color: Optional[str] = Field(
        default=None, description="Background-box colour (#RRGGBB)."
    )
    background_opacity: Optional[float] = Field(
        default=None, ge=0, le=100, description="Box opacity in % (100 = solid)."
    )
    shadow_opacity: Optional[float] = Field(
        default=None, ge=0, le=100, description="Drop-shadow opacity in %."
    )
    glow_enabled: Optional[bool] = Field(
        default=None, description="Soft glow halo behind the text."
    )
    glow_color: Optional[str] = Field(
        default=None, description="Glow colour (#RRGGBB)."
    )
    glow_intensity: Optional[float] = Field(
        default=None, ge=0, le=30,
        description="Glow size/strength in px (at 1080-wide scale).",
    )
    # -- layout & animation ------------------------------------------------- #
    max_lines: Optional[int] = Field(
        default=None, ge=1, le=2,
        description="Maximum text lines per caption event (1 or 2).",
    )
    max_chars: Optional[int] = Field(
        default=None, ge=8, le=48,
        description="Maximum characters packed onto one caption line.",
    )
    animation: Optional[str] = Field(
        default=None,
        description="Reveal animation: 'none', 'word_reveal' (words pop in and "
        "stay), 'one_word' (one word on screen at a time), or 'highlight' (whole "
        "phrase shown, active word recolours — the creator/Hormozi look).",
    )
    # -- typeface & emphasis (advanced custom controls) --------------------- #
    font_family: Optional[str] = Field(
        default=None, description="Caption font family (must be an available font)."
    )
    bold: Optional[bool] = Field(default=None, description="Bold the caption text.")
    uppercase: Optional[bool] = Field(
        default=None, description="Force the caption text to UPPERCASE."
    )
    primary_color: Optional[str] = Field(
        default=None, description="Base text colour (#RRGGBB)."
    )
    highlight_color: Optional[str] = Field(
        default=None, description="Active/karaoke word colour (#RRGGBB)."
    )
    font_scale: Optional[float] = Field(
        default=None, ge=0.4, le=2.5,
        description="Multiplier on the preset's font size (1.0 = preset default).",
    )
    tracking: Optional[float] = Field(
        default=None, ge=0, le=40,
        description="Letter spacing in px (at 1080-wide scale).",
    )
    underline: Optional[bool] = Field(default=None, description="Underline the text.")
    strikethrough: Optional[bool] = Field(
        default=None, description="Strike through the text."
    )
    karaoke: Optional[bool] = Field(
        default=None,
        description="Fill each word left-to-right at its spoken time (karaoke).",
    )
    position: Optional[str] = Field(
        default=None,
        description="Vertical placement: 'top', 'center', or 'bottom'.",
    )


class CinematicEffects(BaseModel):
    """Reel-style cinematic effects applied to the footage (under the captions).

    All optional / off by default. Strengths are 0-100; gradient heights are a %
    of the frame height. Mirrored by the frontend so the live preview matches the
    burned-in render. See ``app.effects.cinematic_stages``.
    """

    color_grade: Optional[str] = Field(
        default="none",
        description="Colour look: none, warm, cool, teal_orange, vintage, vibrant, bw.",
    )
    glow: Optional[bool] = Field(default=False, description="Soft bloom/glow on highlights.")
    glow_strength: Optional[float] = Field(default=50, ge=0, le=100)
    grain: Optional[bool] = Field(default=False, description="Film grain.")
    grain_strength: Optional[float] = Field(default=40, ge=0, le=100)
    vignette: Optional[bool] = Field(default=False, description="Darkened corners.")
    vignette_strength: Optional[float] = Field(default=50, ge=0, le=100)
    bottom_gradient: Optional[bool] = Field(
        default=False, description="Dark scrim rising from the bottom (caption legibility)."
    )
    bottom_gradient_height: Optional[float] = Field(default=25, ge=0, le=80)
    bottom_gradient_strength: Optional[float] = Field(default=70, ge=0, le=100)
    top_gradient: Optional[bool] = Field(default=False, description="Dark scrim from the top.")
    top_gradient_height: Optional[float] = Field(default=20, ge=0, le=80)
    top_gradient_strength: Optional[float] = Field(default=60, ge=0, le=100)
    letterbox: Optional[bool] = Field(
        default=False, description="Cinematic black bars (top + bottom)."
    )
    letterbox_size: Optional[float] = Field(default=50, ge=0, le=100)


class Signature(BaseModel):
    """A burned-in signature / watermark (your handle) over the footage."""

    enabled: Optional[bool] = Field(default=False)
    text: Optional[str] = Field(default="@yourhandle")
    pos_x: Optional[float] = Field(default=50, ge=0, le=100, description="X centre as % of width.")
    pos_y: Optional[float] = Field(default=92, ge=0, le=100, description="Y centre as % of height.")
    size: Optional[float] = Field(default=34, ge=10, le=120, description="Font size in px (at 1080-wide).")
    color: Optional[str] = Field(default="#FFFFFF", description="Text colour (#RRGGBB).")
    opacity: Optional[float] = Field(default=75, ge=0, le=100, description="Opacity in %.")


class GenerateRequest(BaseModel):
    """Body for POST /api/generate.

    The source is EITHER a ``video_url`` (fetched with yt-dlp) OR an ``upload_id``
    returned by ``POST /api/upload`` (a file the user uploaded). Exactly one is
    required; ``upload_id`` takes precedence if both are somehow supplied.
    """

    video_url: Optional[str] = Field(
        default=None, description="Source video URL (e.g. YouTube)."
    )
    upload_id: Optional[str] = Field(
        default=None,
        description="Reference to a previously uploaded file (from /api/upload).",
    )
    upload_name: Optional[str] = Field(
        default=None,
        description="Original filename of the uploaded video (display label only).",
    )
    download_id: Optional[str] = Field(
        default=None,
        description="Reference to a video already fetched in the background via "
        "/api/prefetch. When present (alongside the original video_url), the "
        "pipeline reuses that file instead of downloading it again.",
    )
    aspect_ratio: AspectRatio = AspectRatio.NINE_16
    fit_mode: FitMode = FitMode.CROP
    square_corners: SquareCorners = Field(
        default=SquareCorners.ROUND,
        description="Corner style of the centered square (square fit mode only).",
    )
    bar_text: Optional[str] = Field(
        default=None,
        description="Title text drawn over the top of the frame (square mode).",
    )
    bar_text_color: Optional[str] = Field(
        default="#FFFFFF", description="Square title colour (#RRGGBB)."
    )
    bar_text_anim: Optional[str] = Field(
        default="none", description="Square title entrance: 'none', 'fade', or 'slide'.",
    )
    num_clips: int = Field(
        default=3, ge=1, le=100,
        description="How many clips to generate. The selector returns at most as "
        "many non-overlapping windows as the transcript supports.",
    )
    clip_length: Optional[float] = Field(
        default=None, ge=5, le=600,
        description="Target length of each clip in SECONDS (e.g. 30, 45, 60, or a "
        "custom value). When set, each clip aims for this duration — finishing on "
        "a sentence boundary near it — instead of dividing the video evenly by "
        "num_clips. None keeps the adaptive length behaviour.",
    )
    caption_style: str = Field(
        default="bold_white", description="Caption style preset id."
    )
    language: Optional[str] = Field(
        default=None,
        description="Language the captions are transcribed in (ISO code, e.g. "
        "'en', 'ur', 'hi'). None / 'auto' lets Whisper auto-detect. Forcing a "
        "language helps when auto-detect confuses e.g. Urdu and Hindi, and also "
        "names the downloaded clip files in that language.",
    )
    caption_overrides: Optional[CaptionOverrides] = Field(
        default=None,
        description="Per-render tweaks (position, rotation, stroke, shadow, "
        "background) layered over the chosen preset.",
    )
    cinematic: Optional[CinematicEffects] = Field(
        default=None,
        description="Cinematic video effects (gradients, glow, vignette, grain, "
        "colour grade, letterbox) burned under the captions.",
    )
    music_track: Optional[str] = Field(
        default=None,
        description="Background-music filename from the music library (assets/music). "
        "Mixed UNDER the original audio and ducked when speech is present.",
    )
    music_volume: Optional[float] = Field(
        default=35, ge=0, le=100,
        description="Background-music loudness (0-100). Kept subtle/reels-style; "
        "ducks down further while the speaker is talking.",
    )
    music_duck: Optional[float] = Field(
        default=70, ge=0, le=100,
        description="How hard the music dips under the voice (0-100). 0 keeps the "
        "music steady; higher values pull it down further whenever someone is "
        "talking so the original voice stays clear.",
    )
    music_start: Optional[float] = Field(
        default=0, ge=0,
        description="Seconds into the music track to start from (beat-aligned in the "
        "UI), so the chosen drop/beat lands at the clip's start.",
    )
    signature: Optional[Signature] = Field(
        default=None, description="Burned-in signature / watermark over the footage.",
    )
    device: Device = Field(
        default=Device.AUTO,
        description="Compute device for transcription: auto, cuda (GPU), or cpu.",
    )

    @model_validator(mode="after")
    def _require_a_source(self) -> "GenerateRequest":
        has_url = bool(self.video_url and self.video_url.strip())
        has_upload = bool(self.upload_id and self.upload_id.strip())
        if not has_url and not has_upload:
            raise ValueError(
                "Provide either a video URL or an uploaded file."
            )
        return self


class ClipResult(BaseModel):
    """A single generated clip returned to the frontend."""

    index: int
    title: str
    start: float
    end: float
    url: str


class GenerateResponse(BaseModel):
    """Response for POST /api/generate."""

    status: str = "success"
    clip_id: str
    transcript_path: str
    clips: List[ClipResult]


# --------------------------------------------------------------------------- #
# Domain exceptions — each maps to a clean HTTP status in main.py
# --------------------------------------------------------------------------- #
class InvalidVideoURLError(Exception):
    """Raised when the source video cannot be downloaded (bad/blocked URL).

    Maps to HTTP 400.
    """


class TranscriptionError(Exception):
    """Raised when transcription fails. Maps to HTTP 500."""


class ClipGenerationError(Exception):
    """Raised when ffmpeg fails to cut/reframe/burn a clip. Maps to HTTP 500."""
