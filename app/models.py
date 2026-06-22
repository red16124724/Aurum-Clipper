"""Pydantic schemas, enums, and custom exceptions for the API.

These are the contract between the frontend and the pipeline. Keeping them in
one module means the request/response shapes and the domain errors live in a
single, easy-to-audit place.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class AspectRatio(str, Enum):
    """Output aspect ratio. Vertical (9:16) is the default for shorts."""

    NINE_16 = "9:16"
    SIXTEEN_9 = "16:9"


class FitMode(str, Enum):
    """How the source is fitted into the target frame.

    - crop: scale to *cover* the target, then center-crop (fills the frame).
    - pad:  scale to *fit* inside the target, then pad with black bars.
    """

    CROP = "crop"
    PAD = "pad"


# --------------------------------------------------------------------------- #
# Request / response schemas
# --------------------------------------------------------------------------- #
class GenerateRequest(BaseModel):
    """Body for POST /api/generate."""

    video_url: str = Field(..., description="Source video URL (e.g. YouTube).")
    aspect_ratio: AspectRatio = AspectRatio.NINE_16
    fit_mode: FitMode = FitMode.CROP
    bar_text: Optional[str] = Field(
        default=None,
        description="Text drawn on the top bar. Only used when fit_mode='pad'.",
    )
    num_clips: int = Field(
        default=3, ge=1, le=10, description="How many clips to generate (1-10)."
    )
    caption_style: str = Field(
        default="bold_white", description="Caption style preset id."
    )


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
