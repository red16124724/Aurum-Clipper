"""Pydantic schemas, enums, and custom exceptions for the API.

These are the contract between the frontend and the pipeline. Keeping them in
one module means the request/response shapes and the domain errors live in a
single, easy-to-audit place.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


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
    bar_text: Optional[str] = Field(
        default=None,
        description="Title text drawn over the top of the frame (square mode).",
    )
    num_clips: int = Field(
        default=3, ge=1, le=10, description="How many clips to generate (1-10)."
    )
    caption_style: str = Field(
        default="bold_white", description="Caption style preset id."
    )
    caption_overrides: Optional[CaptionOverrides] = Field(
        default=None,
        description="Per-render tweaks (position, rotation, stroke, shadow, "
        "background) layered over the chosen preset.",
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
