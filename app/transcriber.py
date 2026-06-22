"""Local transcription with faster-whisper (word-level timestamps).

The model is loaded ONCE at startup and reused for every request. We auto-detect
hardware: try CUDA (float16) first, and fall back to CPU (int8) if the GPU path
cannot be initialised. No audio or text ever leaves the machine.
"""

from __future__ import annotations

import glob
import json
import logging
import os
import sys
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


def _add_cuda_dll_directories() -> None:
    """Make pip-installed NVIDIA CUDA libraries discoverable on Windows.

    ctranslate2 (faster-whisper's backend) loads cuBLAS/cuDNN lazily at compute
    time. The ``nvidia-*-cu12`` wheels drop those DLLs under
    ``site-packages/nvidia/**/bin``, which Windows does NOT search by default -
    so without this the GPU path fails with "cublas64_12.dll is not found".
    No-op on non-Windows (there the loader uses RPATH/LD_LIBRARY_PATH).
    """
    if os.name != "nt":
        return
    for entry in sys.path:
        nvidia_root = os.path.join(entry, "nvidia")
        if not os.path.isdir(nvidia_root):
            continue
        for bin_dir in glob.glob(os.path.join(nvidia_root, "*", "bin")):
            # add_dll_directory helps DLLs loaded with the user-dirs flag, but
            # ctranslate2's native dependency load uses the standard search
            # order - which consults PATH, not these added dirs. So do BOTH.
            try:
                os.add_dll_directory(bin_dir)
            except OSError:
                pass
            if bin_dir not in os.environ.get("PATH", ""):
                os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")


# Must run before faster_whisper/ctranslate2 try to load the CUDA DLLs.
_add_cuda_dll_directories()

from faster_whisper import WhisperModel  # noqa: E402

from .models import TranscriptionError  # noqa: E402
from .paths import TRANSCRIPTS_DIR  # noqa: E402

MODEL_SIZE = "medium"

# Module-global model + a record of which device actually loaded.
_model: Optional[WhisperModel] = None
_device: str = "uninitialised"


def load_model() -> WhisperModel:
    """Load the whisper model once, auto-detecting GPU then falling back to CPU.

    Returns the loaded model. Safe to call multiple times (idempotent).
    """
    global _model, _device
    if _model is not None:
        return _model

    # Preferred: NVIDIA GPU with CUDA 12 + cuDNN.
    try:
        logger.info("Loading whisper '%s' on cuda (float16)...", MODEL_SIZE)
        _model = WhisperModel(MODEL_SIZE, device="cuda", compute_type="float16")
        _device = "cuda"
        logger.info("Whisper '%s' loaded on cuda.", MODEL_SIZE)
        return _model
    except Exception as exc:  # noqa: BLE001 - GPU may be absent or cuDNN mismatched
        logger.warning(
            "CUDA load failed (%s). Falling back to CPU (int8). "
            "If you expected GPU, check CUDA 12 + matching cuDNN.",
            exc,
        )

    # Fallback: CPU. Slower on 'medium' but works everywhere.
    try:
        logger.info("Loading whisper '%s' on cpu (int8)...", MODEL_SIZE)
        _model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
        _device = "cpu"
        logger.info("Whisper '%s' loaded on cpu.", MODEL_SIZE)
        return _model
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to load whisper on CPU as well.")
        raise TranscriptionError(
            f"Could not load the whisper model on GPU or CPU: {exc}"
        ) from exc


def get_device() -> str:
    """Return the device the model loaded on ('cuda', 'cpu', or 'uninitialised')."""
    return _device


def transcribe_video(
    video_path: Path,
    clip_id: str,
    progress: Optional[Callable[[float, str], None]] = None,
) -> dict:
    """Transcribe `video_path`, returning a dict with word-level timestamps.

    Returns a dict shaped like:
        {
          "language": "en",
          "duration": 123.4,
          "text": "full transcript ...",
          "words": [{"word": "Hello", "start": 0.0, "end": 0.4}, ...],
          "segments": [{"id": 0, "start": 0.0, "end": 3.2, "text": "..."}, ...],
        }

    The result is also saved to transcripts/<clip_id>.json.

    Raises:
        TranscriptionError: on any failure.
    """
    model = load_model()

    try:
        segments_gen, info = model.transcribe(
            str(video_path),
            word_timestamps=True,
            vad_filter=True,  # trims long silences -> better segment boundaries
        )

        segments: list[dict] = []
        words: list[dict] = []
        text_parts: list[str] = []

        total_dur = float(info.duration) or 0.0
        if progress:
            progress(0.01, "Transcribing audio with local Whisper...")

        # IMPORTANT: `segments_gen` is a lazy generator. We must iterate it fully
        # to actually run transcription and collect every word. Each yielded
        # segment lets us report progress as seg.end / total_duration.
        for seg in segments_gen:
            seg_text = (seg.text or "").strip()
            if progress and total_dur > 0:
                frac = min(0.99, float(seg.end) / total_dur)
                progress(frac, f"Transcribing... {int(frac * 100)}%")
            segments.append(
                {
                    "id": seg.id,
                    "start": float(seg.start),
                    "end": float(seg.end),
                    "text": seg_text,
                }
            )
            text_parts.append(seg_text)

            for w in (seg.words or []):
                token = (w.word or "").strip()
                if not token:
                    continue
                words.append(
                    {
                        "word": token,
                        "start": float(w.start),
                        "end": float(w.end),
                    }
                )

        result = {
            "language": info.language,
            "duration": float(info.duration),
            "text": " ".join(text_parts).strip(),
            "words": words,
            "segments": segments,
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Transcription failed for %s", video_path)
        raise TranscriptionError(f"Transcription failed: {exc}") from exc

    # Persist the transcript for debugging / reuse.
    transcript_path = TRANSCRIPTS_DIR / f"{clip_id}.json"
    try:
        transcript_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as exc:
        logger.warning("Could not write transcript json: %s", exc)

    return result
