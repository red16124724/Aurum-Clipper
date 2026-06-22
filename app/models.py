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
