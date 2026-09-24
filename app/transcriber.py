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
import re
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable, Optional

import numpy as np

logger = logging.getLogger(__name__)


def _add_cuda_dll_directories() -> None:
    """Make pip-installed, bundled, and system NVIDIA CUDA libraries discoverable on Windows."""
    if os.name != "nt":
        return

    candidate_roots = set()

    # 1. PyInstaller frozen environment
    if hasattr(sys, "_MEIPASS"):
        candidate_roots.add(sys._MEIPASS)
        candidate_roots.add(os.path.join(sys._MEIPASS, "nvidia"))

    # 2. Executable / script directory and virtual environment
    exe_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidate_roots.add(exe_dir)
    candidate_roots.add(os.path.join(exe_dir, "_internal"))
    candidate_roots.add(os.path.join(exe_dir, ".venv", "Lib", "site-packages"))
    candidate_roots.add(os.path.join(exe_dir, ".venv", "Lib", "site-packages", "nvidia"))
    candidate_roots.add(os.path.join(exe_dir, "assets", "bin"))

    # 3. sys.path entries
    for entry in sys.path:
        candidate_roots.add(entry)
        candidate_roots.add(os.path.join(entry, "nvidia"))

    # 4. Standard CUDA toolkit paths on Windows
    for cuda_v in glob.glob(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v*\bin"):
        candidate_roots.add(cuda_v)
    for cudnn_v in glob.glob(r"C:\Program Files\NVIDIA\CUDNN\v*\bin"):
        candidate_roots.add(cudnn_v)

    added_dirs = set()
    for root in candidate_roots:
        if not os.path.isdir(root):
            continue
        try:
            # Check root directly
            if any(f.lower().endswith(".dll") for f in os.listdir(root) if os.path.isfile(os.path.join(root, f))):
                added_dirs.add(root)
            # Search subdirectories like nvidia/*/bin, nvidia/*/lib
            for bin_dir in glob.glob(os.path.join(root, "**", "bin"), recursive=True):
                if os.path.isdir(bin_dir):
                    added_dirs.add(bin_dir)
            for lib_dir in glob.glob(os.path.join(root, "**", "lib"), recursive=True):
                if os.path.isdir(lib_dir):
                    added_dirs.add(lib_dir)
        except Exception:
            pass

    for d in added_dirs:
        try:
            os.add_dll_directory(d)
        except (OSError, AttributeError):
            pass
        if d not in os.environ.get("PATH", ""):
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")


# Must run before faster_whisper/ctranslate2 try to load the CUDA DLLs.
_add_cuda_dll_directories()

from faster_whisper import WhisperModel  # noqa: E402

from .models import TranscriptionError  # noqa: E402
from .paths import TRANSCRIPTS_DIR  # noqa: E402

# Fallback when hardware can't be probed at all. Per-device auto-selection
# (see _pick_model_size) normally overrides this — kept only as a last resort.
MODEL_SIZE = "medium"

# Per-device compute precision. int8_float16 on the GPU halves VRAM usage 
# with near-zero accuracy loss, preventing OOMs and slow CPU fallbacks.
_COMPUTE_TYPE = {"cuda": "int8_float16", "cpu": "int8"}

# One cached model per device ('cuda' / 'cpu') so switching devices between
# requests is cheap after the first load. `_device` records the most recently
# used device (drives the /health badge); `_cuda_available` is a cached probe.
_models: dict[str, WhisperModel] = {}
_model_sizes: dict[str, str] = {}  # device -> whisper model size actually loaded
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
    """Best-effort, cached check for a usable CUDA GPU and cuBLAS/cuDNN runtime libraries."""
    global _cuda_available
    if _cuda_available is None:
        try:
            _add_cuda_dll_directories()
            from ctranslate2 import get_cuda_device_count

            count = get_cuda_device_count()
            if count <= 0:
                _cuda_available = False
            else:
                if os.name == "nt":
                    import ctypes
                    loaded = False
                    for dll_name in ["cublas64_12.dll", "cublas64_11.dll", "nvcuda.dll"]:
                        try:
                            ctypes.CDLL(dll_name)
                            loaded = True
                            break
                        except Exception:
                            continue
                    _cuda_available = loaded
                    if not loaded:
                        logger.info("NVIDIA GPU detected but cuBLAS DLL not loaded. Defaulting to CPU.")
                else:
                    _cuda_available = True
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


def _gpu_vram_gb() -> Optional[float]:
    """Best-effort total VRAM of the active CUDA GPU, in GB. None if unknown."""
    if not cuda_available():
        return None
    try:
        import subprocess

        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if out.returncode == 0:
            lines = [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
            if lines:
                return float(lines[0]) / 1024.0  # MiB -> GiB
    except Exception as exc:  # noqa: BLE001 - any failure -> unknown VRAM
        logger.debug("Could not read GPU VRAM via nvidia-smi: %s", exc)
    return None


def _system_ram_gb() -> Optional[float]:
    """Best-effort total system RAM, in GB. None if unknown.

    No new dependency (e.g. psutil) needed: ``GlobalMemoryStatusEx`` on
    Windows, ``sysconf`` on POSIX (Linux and macOS both support it) covers
    every platform this app packages for.
    """
    try:
        if os.name == "nt":
            import ctypes

            class _MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = _MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return stat.ullTotalPhys / (1024**3)
        return (os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")) / (1024**3)
    except Exception as exc:  # noqa: BLE001 - any failure -> unknown RAM
        logger.debug("Could not read system RAM: %s", exc)
        return None


def system_ram_gb() -> Optional[float]:
    """Report total physical RAM in GB (e.g. 16.0) or None if unreadable."""
    return _system_ram_gb()


def get_model_size(device: Optional[str] = None) -> str:
    """The whisper model size loaded (or that WOULD be picked) for a device.

    With no argument, returns the size for the most-recently-used device
    (falls back to 'large-v3-turbo' if nothing has loaded yet).
    """
    dev = device or (_device if _device != "uninitialised" else ("cuda" if cuda_available() else "cpu"))
    return _model_sizes.get(dev) or "large-v3-turbo"


def is_loaded(device: str) -> bool:
    """True if a model for this concrete device is already cached (warm)."""
    return device in _models


# ---------------------------------------------------------------------------
# Whisper Models Catalog & System Requirements
# ---------------------------------------------------------------------------
MODELS_CATALOG = [
    {
        "id": "large-v3-turbo",
        "name": "Large V3 Turbo",
        "tag": "Recommended",
        "size_label": "~1.6 GB",
        "size_bytes": 1_621_665_983,
        "min_ram": "8 GB RAM",
        "min_vram": "6 GB VRAM",
        "device_rec": "NVIDIA GPU (CUDA) or 6+ Core CPU",
        "description": "Optimized version of Large-V3. Up to 8x faster while maintaining top-tier multi-lingual transcription quality.",
        "accuracy": 5,
        "speed": 4.5,
    },
    {
        "id": "large-v3",
        "name": "Large V3",
        "tag": "Max Accuracy",
        "size_label": "~3.1 GB",
        "size_bytes": 3_090_835_702,
        "min_ram": "16 GB RAM",
        "min_vram": "10 GB VRAM",
        "device_rec": "Dedicated NVIDIA GPU (10GB+ VRAM)",
        "description": "The most powerful OpenAI Whisper model. Flawless punctuation and handling of complex accents and languages.",
        "accuracy": 5,
        "speed": 2.5,
    },
    {
        "id": "medium",
        "name": "Medium",
        "tag": "Balanced",
        "size_label": "~1.5 GB",
        "size_bytes": 1_530_111_874,
        "min_ram": "8 GB RAM",
        "min_vram": "5 GB VRAM",
        "device_rec": "Mid-tier GPU or Modern Multi-Core CPU",
        "description": "Excellent balance of accuracy and resource usage. Great for gaming rigs and standard workstations.",
        "accuracy": 4,
        "speed": 3.5,
    },
    {
        "id": "small",
        "name": "Small",
        "tag": "Lightweight",
        "size_label": "~480 MB",
        "size_bytes": 485_752_511,
        "min_ram": "4 GB RAM",
        "min_vram": "2 GB VRAM",
        "device_rec": "Laptops, Integrated Graphics & Standard CPUs",
        "description": "Compact footprint with very fast transcription. Ideal for quick clipping on low-spec devices.",
        "accuracy": 3.5,
        "speed": 4.5,
    },
    {
        "id": "base",
        "name": "Base",
        "tag": "Ultra Fast",
        "size_label": "~145 MB",
        "size_bytes": 147_423_080,
        "min_ram": "4 GB RAM",
        "min_vram": "1 GB VRAM",
        "device_rec": "Budget PCs & Legacy Hardware",
        "description": "Instant download with minimal memory impact. Great for testing or rapid drafting on any hardware.",
        "accuracy": 2.5,
        "speed": 5,
    },
    {
        "id": "savi0ur/whisper-hindi-hinglish-ct2",
        "name": "Hinglish Apex Turbo",
        "tag": "Hinglish",
        "size_label": "~1.6 GB",
        "size_bytes": 1_617_884_929,
        "min_ram": "8 GB RAM",
        "min_vram": "5 GB VRAM",
        "device_rec": "Dedicated NVIDIA GPU or Fast CPU",
        "description": "Specialized CTranslate2 model for transcribing Hindi and Hinglish directly into Romanized English script.",
        "accuracy": 4.5,
        "speed": 4.0,
    },
]


def _repo_id_for_size(size: str) -> str:
    """Return the HuggingFace repository ID for a given model size."""
    if "/" in size:
        return size
    try:
        import faster_whisper.utils
        return faster_whisper.utils._MODELS.get(size, f"Systran/faster-whisper-{size}")
    except Exception:
        if size == "large-v3-turbo":
            return "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
        return f"Systran/faster-whisper-{size}"


def _repo_dir_name_for_size(size: str) -> str:
    """Return the HuggingFace cache folder name for a given model size."""
    repo = _repo_id_for_size(size)
    return "models--" + repo.replace("/", "--")


def get_candidate_cache_dirs() -> list[Path]:
    """Return all directories on the system where Whisper models might be cached."""
    dirs: list[Path] = []
    try:
        from huggingface_hub.constants import HF_HUB_CACHE
        if HF_HUB_CACHE:
            dirs.append(Path(HF_HUB_CACHE))
    except Exception:
        pass

    env_hf = os.environ.get("HUGGINGFACE_HUB_CACHE") or os.environ.get("HF_HOME")
    if env_hf:
        p = Path(env_hf)
        dirs.append(p / "hub" if not str(p).endswith("hub") else p)

    user_home = Path.home() / ".cache" / "huggingface" / "hub"
    if user_home not in dirs:
        dirs.append(user_home)

    from app.paths import DATA_DIR
    local_models = DATA_DIR / "models"
    if local_models not in dirs:
        dirs.append(local_models)

    return [d for d in dirs if d.is_dir()]


def _is_valid_model_dir(dir_path: Path) -> bool:
    """Ensure model directory contains valid CTranslate2 model.bin and config.json with size > 0."""
    try:
        config_path = dir_path / "config.json"
        if not (config_path.is_file() and config_path.stat().st_size > 0):
            return False
        model_bins = [
            f for f in dir_path.iterdir()
            if f.is_file()
            and (f.name == "model.bin" or bool(re.match(r"^model\.bin\.\d+$", f.name)))
            and f.stat().st_size > 0
            and not f.name.endswith((".incomplete", ".tmp", ".part", ".crdownload"))
        ]
        return len(model_bins) > 0
    except OSError:
        return False


def scan_installed_models() -> list[dict]:
    """Scan all device caches and local folders for fully downloaded Whisper models."""
    installed = []
    seen_ids = set()
    candidate_dirs = get_candidate_cache_dirs()

    for model_meta in MODELS_CATALOG:
        mid = model_meta["id"]
        repo_dir_name = _repo_dir_name_for_size(mid)

        for cache_dir in candidate_dirs:
            # 1. Check HuggingFace structured repo format (e.g. models--mobiuslabsgmbh--faster-whisper-large-v3-turbo)
            repo_path = cache_dir / repo_dir_name
            if repo_path.is_dir():
                snapshots = repo_path / "snapshots"
                if snapshots.is_dir():
                    for snap in snapshots.iterdir():
                        if snap.is_dir():
                            if _is_valid_model_dir(snap) and mid not in seen_ids:
                                seen_ids.add(mid)
                                installed.append({
                                    "id": mid,
                                    "name": model_meta["name"],
                                    "size_label": model_meta["size_label"],
                                    "tag": model_meta["tag"],
                                    "path": str(snap.resolve()),
                                    "type": "huggingface_snapshot",
                                })
                                break

            # 2. Check direct model folder format (e.g. models/large-v3-turbo)
            direct_path = cache_dir / mid
            if direct_path.is_dir() and mid not in seen_ids:
                if _is_valid_model_dir(direct_path):
                    seen_ids.add(mid)
                    installed.append({
                        "id": mid,
                        "name": model_meta["name"],
                        "size_label": model_meta["size_label"],
                        "tag": model_meta["tag"],
                        "path": str(direct_path.resolve()),
                        "type": "direct_folder",
                    })

    return installed


def is_model_cached(model_size: str) -> bool:
    """Check if model_size is fully installed anywhere on the device."""
    installed = scan_installed_models()
    return any(m["id"] == model_size for m in installed)


def _cleanup_stale_incompletes(repo_dir: Path) -> None:
    """Remove abandoned .incomplete download chunks from older interrupted attempts."""
    blobs_dir = repo_dir / "blobs"
    if not blobs_dir.is_dir():
        return
    try:
        incomplete_by_prefix: dict[str, list[Path]] = {}
        for p in blobs_dir.iterdir():
            if p.is_file() and ".incomplete" in p.name:
                prefix = p.name.split(".")[0]
                incomplete_by_prefix.setdefault(prefix, []).append(p)
        for prefix, files in incomplete_by_prefix.items():
            if len(files) > 1:
                # Sort descending by size: keep largest active attempt, remove stale duplicates
                files.sort(key=lambda f: f.stat().st_size, reverse=True)
                for stale in files[1:]:
                    try:
                        stale.unlink(missing_ok=True)
                        logger.debug("Cleaned up duplicate download chunk: %s", stale.name)
                    except OSError:
                        pass
    except Exception as exc:
        logger.debug("Error cleaning up stale downloads: %s", exc)


def _get_downloaded_bytes(repo_dir: Path) -> int:
    """Calculate total downloaded bytes across unique blobs without summing duplicate incomplete attempts."""
    if not repo_dir.is_dir():
        return 0

    blobs_dir = repo_dir / "blobs"
    if not blobs_dir.is_dir():
        return 0

    # Clean up any stale duplicate .incomplete files
    _cleanup_stale_incompletes(repo_dir)

    blob_sizes: dict[str, int] = {}
    for p in blobs_dir.iterdir():
        if not p.is_file():
            continue
        try:
            size = p.stat().st_size
            prefix = p.name.split(".")[0]
            if prefix == p.name:
                # Completed blob file
                blob_sizes[prefix] = size
            else:
                # Incomplete downloading file: take largest if multiple
                if prefix not in blob_sizes or blob_sizes[prefix] < size:
                    blob_sizes[prefix] = size
        except OSError:
            pass

    return sum(blob_sizes.values())


def get_models_info() -> list[dict]:
    """Return the list of all available Whisper models with specs and local download status."""
    active_dev = _device if _device != "uninitialised" else None
    active_size = _model_sizes.get(active_dev) if active_dev else None
    res = []
    for m in MODELS_CATALOG:
        entry = dict(m)
        entry["is_cached"] = is_model_cached(m["id"])
        entry["is_active"] = (m["id"] == active_size) and (active_dev in _models)
        res.append(entry)
    return res


# ---------------------------------------------------------------------------
# First-run download progress tracker
# ---------------------------------------------------------------------------
_status_lock = threading.Lock()
_load_status: dict = {"status": "unselected", "message": "No model selected", "progress": None, "model_size": None, "device": None}

# Exact total byte sizes for CTranslate2 quantized Whisper models
_MODEL_BYTES_EST = {
    "tiny": 75_000_000,
    "base": 147_423_080,
    "small": 485_752_511,
    "medium": 1_530_111_874,
    "large-v3-turbo": 1_621_665_983,
    "large-v3": 3_090_835_702,
    "savi0ur/whisper-hindi-hinglish-ct2": 1_617_884_929,
}

def _set_status(**kwargs) -> None:
    with _status_lock:
        _load_status.update(kwargs)


def model_status() -> dict:
    """Snapshot of the background model load — polled by /api/model-status."""
    with _status_lock:
        return dict(_load_status)


def _poll_download_progress(size: str, stop_event: threading.Event) -> None:
    """Watch HuggingFace's partial-download file(s) and update progress."""
    total = _MODEL_BYTES_EST.get(size, 1_621_665_983)
    try:
        from huggingface_hub.constants import HF_HUB_CACHE
    except ImportError:
        return

    repo_dir = Path(HF_HUB_CACHE) / _repo_dir_name_for_size(size)

    while not stop_event.is_set():
        try:
            raw_got = _get_downloaded_bytes(repo_dir)
            if raw_got > 0:
                got = min(raw_got, total)
                frac = max(0.01, min(0.99, got / total))
                mb_got = got / (1024 * 1024)
                mb_total = total / (1024 * 1024)
                pct = int(frac * 100)
                _set_status(
                    status="downloading",
                    progress=round(frac, 4),
                    message=f"Downloading '{size}' ({pct}% — {mb_got:.0f} MB / {mb_total:.0f} MB)...",
                    model_size=size,
                )
            else:
                _set_status(
                    status="downloading",
                    progress=0.0,
                    message=f"Connecting to Hugging Face and downloading '{size}'...",
                    model_size=size,
                )
        except Exception as e:
            logger.debug("Error in download poller: %s", e)
        stop_event.wait(0.4)


def _clean_all_locks() -> None:
    """Remove any stale huggingface .lock files that cause downloads to hang forever on Windows."""
    try:
        from huggingface_hub.constants import HF_HUB_CACHE
        locks_dir = Path(HF_HUB_CACHE) / ".locks"
        if locks_dir.exists():
            import shutil
            shutil.rmtree(locks_dir, ignore_errors=True)
            logger.debug("Cleaned up stale HF .locks directory")
    except Exception as e:
        logger.debug("Error cleaning .locks: %s", e)


def _ensure_downloaded(size: str) -> str:
    """Ensure model files are fully downloaded, tracking live progress and cleaning stale locks."""
    _clean_all_locks()

    # Check if already installed
    installed = scan_installed_models()
    for m in installed:
        if m["id"] == size:
            logger.info("Found cached model '%s' at: %s", size, m["path"])
            return m["path"]

    try:
        from huggingface_hub.constants import HF_HUB_CACHE
        repo_dir = Path(HF_HUB_CACHE) / _repo_dir_name_for_size(size)
        _cleanup_stale_incompletes(repo_dir)
    except Exception:
        pass

    stop_event = threading.Event()
    poller = threading.Thread(target=_poll_download_progress, args=(size, stop_event), daemon=True)
    poller.start()
    try:
        import faster_whisper.utils
        logger.info("Starting download of '%s' from Hugging Face Hub...", size)
        try:
            model_path = faster_whisper.utils.download_model(size)
        except Exception as dl_err:
            logger.warning("Direct download of '%s' failed: %s", size, dl_err)
            raise
        _set_status(status="downloading", progress=1.0, message=f"Downloaded '{size}'. Initializing engine...", model_size=size)
        return model_path
    finally:
        stop_event.set()


def _load_on(device: str, model_size: str = "large-v3-turbo") -> WhisperModel:
    """Load (or reuse the cached) model on a concrete device ('cuda'/'cpu')."""
    global _device
    with _load_lock:
        if device in _models and _model_sizes.get(device) == model_size:
            _device = device
            return _models[device]

        # If a different model is loaded on this device, unload it
        if device in _models:
            del _models[device]
            import gc
            gc.collect()

        compute = _COMPUTE_TYPE[device]
        size = model_size
        _set_status(status="downloading", message=f"Preparing '{size}' AI model...",
                    progress=0.0, model_size=size, device=device)
        logger.info("Loading whisper '%s' on %s (%s)...", size, device, compute)

        loaded_size = size
        try:
            # 1. Ensure files are fully downloaded (cleans locks, tracks progress)
            model_path = _ensure_downloaded(size)

            # 2. Instantiate WhisperModel from local path
            _set_status(status="loading", message=f"Loading '{size}' into {device.upper()} memory...",
                        progress=1.0, model_size=size, device=device)
            model = WhisperModel(model_path, device=device, compute_type=compute)
        except Exception as exc:
            if size != "large-v3-turbo":
                logger.warning("Could not load '%s' directly (%s). Falling back to large-v3-turbo...", size, exc)
                _set_status(status="loading", message=f"Initializing fallback engine for '{size}'...",
                            progress=1.0, model_size="large-v3-turbo", device=device)
                try:
                    fallback_path = _ensure_downloaded("large-v3-turbo")
                    model = WhisperModel(fallback_path, device=device, compute_type=compute)
                    loaded_size = "large-v3-turbo"
                except Exception as fallback_exc:
                    _models.pop(device, None)
                    _model_sizes.pop(device, None)
                    _set_status(status="error", message=str(fallback_exc), model_size=size, device=device)
                    raise
            else:
                _models.pop(device, None)
                _model_sizes.pop(device, None)
                _set_status(status="error", message=str(exc), model_size=size, device=device)
                raise

        _models[device] = model
        _model_sizes[device] = loaded_size
        _device = device
        _set_status(status="ready", message="Ready", progress=1.0, model_size=loaded_size, device=device)
        logger.info("Whisper '%s' successfully loaded on %s.", loaded_size, device)
        return model


def load_model(device: str = "auto", model_size: str = "large-v3-turbo") -> WhisperModel:
    """Load the whisper model for the requested device, caching per device.

    Args:
        device: 'auto' (GPU if available, else CPU), 'cuda', or 'cpu'.
        model_size: the specific Whisper weight size to load

    'auto' tries the GPU first and falls back to the CPU. An explicit 'cuda'
    request does NOT silently fall back - it raises a clear error so the user
    knows the GPU is unusable and can pick CPU. Safe to call repeatedly.
    """
    requested = (device or "auto").lower()
    if requested == "gpu":
        requested = "cuda"

    if requested == "cuda":
        try:
            return _load_on("cuda", model_size)
        except Exception as exc:  # noqa: BLE001 - GPU absent or cuDNN mismatched
            logger.warning("CUDA load failed (%s).", exc)
            _set_status(status="error", message=str(exc))
            raise TranscriptionError(
                "Could not run on the GPU (CUDA). Check CUDA 12 + matching cuDNN, "
                f"or choose CPU instead. Details: {exc}"
            ) from exc

    if requested == "cpu":
        try:
            return _load_on("cpu", model_size)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to load whisper on CPU.")
            _set_status(status="error", message=str(exc))
            raise TranscriptionError(
                f"Could not load the whisper model on CPU: {exc}"
            ) from exc

    # 'auto' (or anything unrecognised): prefer GPU, fall back to CPU.
    if cuda_available():
        try:
            return _load_on("cuda", model_size)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "CUDA load failed (%s). Falling back to CPU (int8). "
                "Set device to 'CPU' to stop seeing this.", exc,
            )
    try:
        return _load_on("cpu", model_size)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to load whisper on CPU as well.")
        _set_status(status="error", message=str(exc))
        raise TranscriptionError(
            f"Could not load the whisper model on GPU or CPU: {exc}"
        ) from exc


def get_device() -> str:
    """Return the device of the most-recent model ('cuda', 'cpu', or 'uninitialised')."""
    if _device != "uninitialised":
        return _device
    return "cuda" if cuda_available() else "cpu"


def _normalize_language(language: Optional[str], model_size: Optional[str] = None) -> Optional[str]:
    """Map UI language values to a Whisper code, or None for auto-detect.

    Empty string / 'auto' (case-insensitive) -> None, which tells Whisper to
    detect the spoken language itself.

    For native Hinglish models like 'savi0ur/whisper-hindi-hinglish-ct2', when
    language is 'hinglish', map to 'en' so the decoder generates Romanized
    Hinglish text directly instead of forcing Devanagari Hindi. For standard
    multilingual models, 'hinglish' maps to 'hi' and is post-processed via transliteration.
    """
    if not language:
        return None
    lang = language.strip().lower()
    if lang in ("", "auto"):
        return None
    if lang == "hinglish":
        if model_size and ("hinglish" in model_size.lower() or "apex" in model_size.lower()):
            return "en"
        return "hi"
    return lang


def load_audio(video_path: Path, sr: int = 16000) -> np.ndarray:
    """Extract audio from video as 16kHz mono float32 array using FFmpeg.

    Returns an empty numpy array if the video has no audio stream or if extraction fails.
    """
    cmd = [
        "ffmpeg", "-nostdin", "-threads", "0",
        "-i", str(video_path),
        "-f", "s16le",
        "-ac", "1",
        "-acodec", "pcm_s16le",
        "-ar", str(sr),
        "-",
    ]
    try:
        with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as proc:
            out, _ = proc.communicate(timeout=300)
            if proc.returncode != 0 or not out:
                return np.zeros(0, dtype=np.float32)
            return np.frombuffer(out, np.int16).flatten().astype(np.float32) / 32768.0
    except Exception as exc:
        logger.debug("FFmpeg audio extraction failed (%s), returning empty audio", exc)
        return np.zeros(0, dtype=np.float32)


def transcribe_video(
    video_path: Path,
    clip_id: str,
    progress: Optional[Callable[[float, str], None]] = None,
    device: str = "auto",
    language: Optional[str] = None,
    model_size: str = "large-v3-turbo",
    is_cancelled: Optional[Callable[[], bool]] = None,
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
    # One transcription at a time. If another is running, surface a clear "waiting"
    # message so the UI shows a queued state instead of a frozen 0%.
    if progress and _transcribe_lock.locked():
        progress(0.0, "Waiting for an earlier transcription to finish…")
    _transcribe_lock.acquire()
    try:
        model = load_model(device, model_size)

        if is_cancelled and is_cancelled():
            raise TranscriptionError("Transcription cancelled")

        # 1. Extract 16kHz mono audio via FFmpeg
        audio = load_audio(video_path, sr=16000)

        # 2. Check if video has no audio track or is silent
        if len(audio) == 0:
            logger.info("Video %s contains no audio stream or extraction was empty.", video_path)
            duration = 0.0
            try:
                import cv2
                cap = cv2.VideoCapture(str(video_path))
                fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
                duration = frame_count / fps if fps > 0 else 0.0
                cap.release()
            except Exception:
                pass

            if duration <= 0:
                try:
                    probe_cmd = [
                        "ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(video_path)
                    ]
                    out = subprocess.check_output(probe_cmd, text=True).strip()
                    if out:
                        duration = float(out)
                except Exception as probe_err:
                    logger.debug("ffprobe duration fallback failed: %s", probe_err)

            result = {
                "language": "en",
                "duration": duration,
                "text": "",
                "words": [],
                "segments": [],
            }
            if progress:
                progress(1.0, "Complete (No speech detected)")
            safe_clip_id = clip_id.replace("/", "--")
            transcript_path = TRANSCRIPTS_DIR / f"{safe_clip_id}.json"
            try:
                transcript_path.parent.mkdir(parents=True, exist_ok=True)
                transcript_path.write_text(
                    json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            except OSError as exc:
                logger.warning("Could not write transcript json: %s", exc)
            return result

        total_dur = len(audio) / 16000.0
        if progress:
            progress(0.01, "Transcribing audio with local Whisper...")

        def _do_transcribe(m):
            active_size = _model_sizes.get(_device) or model_size
            s_gen, inf = m.transcribe(
                audio,
                word_timestamps=True,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
                condition_on_previous_text=False,
                beam_size=5,
                language=_normalize_language(language, active_size),
            )
            segs: list[dict] = []
            wrds: list[dict] = []
            txt_parts: list[str] = []

            for seg in s_gen:
                if is_cancelled and is_cancelled():
                    logger.info("Transcription cancelled during processing of %s", video_path)
                    raise TranscriptionError("Transcription cancelled")

                seg_text = (seg.text or "").strip()
                if progress and total_dur > 0:
                    frac = min(0.99, float(seg.end) / total_dur)
                    progress(frac, f"Transcribing... {int(frac * 100)}%")
                segs.append(
                    {
                        "id": seg.id,
                        "start": float(seg.start),
                        "end": float(seg.end),
                        "text": seg_text,
                    }
                )
                txt_parts.append(seg_text)

                seg_words = seg.words or []
                if not seg_words and seg_text:
                    raw_tokens = [t for t in seg_text.split() if t.strip()]
                    if raw_tokens:
                        s_start = float(seg.start)
                        s_end = float(seg.end)
                        s_dur = max(0.1, s_end - s_start)
                        step = s_dur / len(raw_tokens)
                        for i, tok in enumerate(raw_tokens):
                            w_s = round(s_start + i * step, 3)
                            w_e = round(s_start + (i + 1) * step, 3)
                            wrds.append({"word": tok, "start": w_s, "end": w_e})
                else:
                    for w in seg_words:
                        token = (w.word or "").strip()
                        if not token:
                            continue
                        wrds.append(
                            {
                                "word": token,
                                "start": float(w.start),
                                "end": float(w.end),
                            }
                        )

            det_lang = getattr(inf, "language", None) or language or "en"
            dur = float(getattr(inf, "duration", total_dur)) if getattr(inf, "duration", None) else total_dur
            return {
                "language": det_lang,
                "duration": dur,
                "text": " ".join(txt_parts).strip(),
                "words": wrds,
                "segments": segs,
            }

        try:
            result = _do_transcribe(model)
        except Exception as exc:
            if "cublas" in str(exc).lower() or "cuda" in str(exc).lower() or "gpu" in str(exc).lower():
                logger.warning("CUDA transcription failed (%s). Retrying smoothly on CPU...", exc)
                if progress:
                    progress(0.05, "Falling back to CPU transcription...")
                cpu_model = load_model("cpu", model_size)
                result = _do_transcribe(cpu_model)
            else:
                raise
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
    safe_clip_id = clip_id.replace("/", "--")
    transcript_path = TRANSCRIPTS_DIR / f"{safe_clip_id}.json"
    try:
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        transcript_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as exc:
        logger.warning("Could not write transcript json: %s", exc)

    return result
