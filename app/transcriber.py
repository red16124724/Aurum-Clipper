"""Local transcription with faster-whisper (word-level timestamps).

Each request can pick its compute device (``auto``/``cuda``/``cpu``). Models are
heavy (~1.5 GB for 'medium'), so we load one lazily per device and cache it for
reuse. ``auto`` prefers CUDA (float16) and falls back to CPU (int8); an explicit
``cuda`` request fails with a clear message if the GPU cannot be initialised.
No audio or text ever leaves the machine.
"""

from __future__ import annotations

import glob
import json
import logging
import os
import sys
import threading
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

# Per-device compute precision. float16 on the GPU, int8 on the CPU.
_COMPUTE_TYPE = {"cuda": "float16", "cpu": "int8"}

# One cached model per device ('cuda' / 'cpu') so switching devices between
# requests is cheap after the first load. `_device` records the most recently
# used device (drives the /health badge); `_cuda_available` is a cached probe.
_models: dict[str, WhisperModel] = {}
_device: str = "uninitialised"
_cuda_available: Optional[bool] = None

# Cached human-readable GPU name (e.g. "NVIDIA GeForce RTX 5060 Ti"). `_probed`
# guards the one-time lookup so a missing/None name isn't re-queried every call.
_gpu_name: Optional[str] = None
_gpu_name_probed: bool = False

# Serialises model loads so two requests warming the same device don't double-load.
_load_lock = threading.Lock()
# Serialises actual transcription passes — one GPU pass at a time. Concurrent passes
# on the single model thrash each other and look "stuck at 0%"; this queues them.
_transcribe_lock = threading.Lock()


def cuda_available() -> bool:
    """Best-effort, cached check for a usable CUDA GPU.

    Uses ctranslate2's device count (faster-whisper's backend) so the UI can
    offer/hide the GPU option without paying the cost of a full model load.
    """
    global _cuda_available
    if _cuda_available is None:
        try:
            from ctranslate2 import get_cuda_device_count

            _cuda_available = get_cuda_device_count() > 0
        except Exception:  # noqa: BLE001 - any failure means "no usable GPU"
            _cuda_available = False
    return _cuda_available


def available_devices() -> list[str]:
    """Devices the UI may offer, best (GPU) first."""
    return (["cuda", "cpu"] if cuda_available() else ["cpu"])


def gpu_name() -> Optional[str]:
    """Best-effort, cached human-readable name of the active CUDA GPU.

    Returns the marketing name (e.g. "NVIDIA GeForce RTX 5060 Ti") so the UI can
    auto-detect and show the real device instead of a generic "GPU" label, or
    ``None`` when there's no usable GPU / the name can't be read. Uses
    ``nvidia-smi`` (shipped with every NVIDIA driver) rather than pulling in a
    heavy dep like torch just to read a string. Probed once, then cached.
    """
    global _gpu_name, _gpu_name_probed
    if _gpu_name_probed:
        return _gpu_name
    _gpu_name_probed = True
    if not cuda_available():
        return None
    try:
        import subprocess

        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
            # Avoid a flashing console window on Windows (no-op elsewhere).
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if out.returncode == 0:
            lines = [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
            if lines:
                _gpu_name = lines[0]
    except Exception as exc:  # noqa: BLE001 - any failure -> unnamed GPU
        logger.debug("Could not read GPU name via nvidia-smi: %s", exc)
    return _gpu_name


def is_loaded(device: str) -> bool:
    """True if a model for this concrete device is already cached (warm)."""
    return device in _models


def _load_on(device: str) -> WhisperModel:
    """Load (or reuse the cached) model on a concrete device ('cuda'/'cpu')."""
    global _device
    with _load_lock:
        if device in _models:
            _device = device
            return _models[device]
        compute = _COMPUTE_TYPE[device]
        logger.info("Loading whisper '%s' on %s (%s)...", MODEL_SIZE, device, compute)
        model = WhisperModel(MODEL_SIZE, device=device, compute_type=compute)
        _models[device] = model
        _device = device
        logger.info("Whisper '%s' loaded on %s.", MODEL_SIZE, device)
        return model


def load_model(device: str = "auto") -> WhisperModel:
    """Load the whisper model for the requested device, caching per device.

    Args:
        device: 'auto' (GPU if available, else CPU), 'cuda', or 'cpu'.

    'auto' tries the GPU first and falls back to the CPU. An explicit 'cuda'
    request does NOT silently fall back - it raises a clear error so the user
    knows the GPU is unusable and can pick CPU. Safe to call repeatedly.
    """
    requested = (device or "auto").lower()
    if requested == "gpu":
        requested = "cuda"

    if requested == "cuda":
        try:
            return _load_on("cuda")
        except Exception as exc:  # noqa: BLE001 - GPU absent or cuDNN mismatched
            logger.warning("CUDA load failed (%s).", exc)
            raise TranscriptionError(
                "Could not run on the GPU (CUDA). Check CUDA 12 + matching cuDNN, "
                f"or choose CPU instead. Details: {exc}"
            ) from exc

    if requested == "cpu":
        try:
            return _load_on("cpu")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to load whisper on CPU.")
            raise TranscriptionError(
                f"Could not load the whisper model on CPU: {exc}"
            ) from exc

    # 'auto' (or anything unrecognised): prefer GPU, fall back to CPU.
    if cuda_available():
        try:
            return _load_on("cuda")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "CUDA load failed (%s). Falling back to CPU (int8). "
                "If you expected GPU, check CUDA 12 + matching cuDNN.",
                exc,
            )
    try:
        return _load_on("cpu")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to load whisper on CPU as well.")
        raise TranscriptionError(
            f"Could not load the whisper model on GPU or CPU: {exc}"
        ) from exc


def get_device() -> str:
    """Return the device of the most-recent model ('cuda', 'cpu', or 'uninitialised')."""
    return _device


def _normalize_language(language: Optional[str]) -> Optional[str]:
    """Map UI language values to a Whisper code, or None for auto-detect.

    Empty string / 'auto' (case-insensitive) -> None, which tells Whisper to
    detect the spoken language itself. 'hinglish' is not a Whisper language —
    it's Hindustani transcribed as Hindi and then romanised after the fact (see
    ``transcribe_video``), so here it maps to the Hindi model code.
    """
    if not language:
        return None
    lang = language.strip().lower()
    if lang in ("", "auto"):
        return None
    if lang == "hinglish":
        return "hi"
    return lang


def transcribe_video(
    video_path: Path,
    clip_id: str,
    progress: Optional[Callable[[float, str], None]] = None,
    device: str = "auto",
    language: Optional[str] = None,
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
    model = load_model(device)

    # One transcription at a time. If another is running, surface a clear "waiting"
    # message so the UI shows a queued state instead of a frozen 0%.
    if progress and _transcribe_lock.locked():
        progress(0.0, "Waiting for an earlier transcription to finish…")
    _transcribe_lock.acquire()
    try:
        segments_gen, info = model.transcribe(
            str(video_path),
            word_timestamps=True,
            vad_filter=True,  # trims long silences -> better segment boundaries
            language=_normalize_language(language),  # None -> auto-detect
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
    finally:
        _transcribe_lock.release()

    # Hinglish: the audio was transcribed as Hindi (Devanagari); romanise the
    # whole transcript to readable Roman Urdu/Hindi before caching/persisting.
    if (language or "").strip().lower() == "hinglish":
        from . import translit

        result = translit.romanize_transcript(result)

    # Persist the transcript for debugging / reuse.
    transcript_path = TRANSCRIPTS_DIR / f"{clip_id}.json"
    try:
        transcript_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as exc:
        logger.warning("Could not write transcript json: %s", exc)

    return result
