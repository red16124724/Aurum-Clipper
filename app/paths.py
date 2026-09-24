"""Central filesystem layout for the project.

All other modules import these so directory locations are defined exactly once.
Supports running from source and as a frozen standalone PyInstaller executable.
When running as a frozen executable, all app data is stored in the folder where
the .exe is located, making it 100% portable.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Optional

# When packaged with PyInstaller:
# - sys.frozen is True
# - sys._MEIPASS holds the bundled read-only assets (web/dist, static, base fonts/music)
# - sys.executable is the path to AurumClipper.exe
IS_FROZEN = getattr(sys, "frozen", False)

if IS_FROZEN:
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    DATA_DIR = Path(sys.executable).resolve().parent
else:
    BUNDLE_DIR = Path(__file__).resolve().parent.parent
    DATA_DIR = BUNDLE_DIR

ROOT_DIR = DATA_DIR

# Persistent data directories (located where the .exe is)
DOWNLOADS_DIR = DATA_DIR / "downloads"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
CLIPS_DIR = DATA_DIR / "clips"
ASSETS_DIR = DATA_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
MASKS_DIR = ASSETS_DIR / "masks"
MUSIC_DIR = ASSETS_DIR / "music"
SFX_DIR = ASSETS_DIR / "sfx"
MODELS_DIR = ASSETS_DIR / "models"

# Read-only bundled assets (served from PyInstaller bundle)
STATIC_DIR = BUNDLE_DIR / "static"
WEB_DIST_DIR = BUNDLE_DIR / "web" / "dist"
BUNDLED_FONTS_DIR = BUNDLE_DIR / "assets" / "fonts"
BUNDLED_MUSIC_DIR = BUNDLE_DIR / "assets" / "music"
BUNDLED_SFX_DIR = BUNDLE_DIR / "assets" / "sfx"
BUNDLED_MODELS_DIR = BUNDLE_DIR / "assets" / "models"


def resolve_model_path(model_name: str) -> Optional[Path]:
    """Resolve a vision/tracking model file path from the frozen bundle or local assets.
    
    Prioritizes the read-only assets embedded in the standalone executable
    (sys._MEIPASS / 'assets' / 'models'), falling back to persistent and source directories.
    """
    candidates: list[Path] = []

    # 1. Direct sys._MEIPASS check when frozen
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "assets" / "models" / model_name)
        candidates.append(Path(meipass) / "models" / model_name)
        candidates.append(Path(meipass) / model_name)

    # 2. Bundled models directory
    candidates.append(BUNDLED_MODELS_DIR / model_name)

    # 3. Persistent models directory
    candidates.append(MODELS_DIR / model_name)

    # 4. Project source directory fallback
    src_dir = Path(__file__).resolve().parent.parent
    candidates.append(src_dir / "assets" / "models" / model_name)

    for path in candidates:
        try:
            if path.is_file():
                return path
        except Exception:
            pass

    return None


def ensure_dirs() -> None:
    """Create every runtime directory and copy bundled user-customizable assets if needed."""
    for directory in (
        DOWNLOADS_DIR,
        TRANSCRIPTS_DIR,
        CLIPS_DIR,
        ASSETS_DIR,
        FONTS_DIR,
        MASKS_DIR,
        MUSIC_DIR,
        SFX_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    # When frozen, seed fonts/music/sfx from the bundle to the data directory if not already present.
    # Note: Vision & face tracking models (YuNet, Haar cascade) are kept purely inside the exe bundle
    # (sys._MEIPASS / 'assets' / 'models') and resolved directly from memory/bundle without polluting disk.
    if IS_FROZEN:
        for src_dir, dst_dir in [
            (BUNDLED_FONTS_DIR, FONTS_DIR),
            (BUNDLED_MUSIC_DIR, MUSIC_DIR),
            (BUNDLED_SFX_DIR, SFX_DIR),
        ]:
            if src_dir.is_dir():
                for item in src_dir.iterdir():
                    dest_file = dst_dir / item.name
                    if item.is_file() and not dest_file.exists():
                        try:
                            shutil.copy2(item, dest_file)
                        except Exception:
                            pass


def ensure_ffmpeg() -> Optional[Path]:
    """Ensure ffmpeg and ffprobe are discoverable on PATH across frozen, local, and WinGet environments."""
    if shutil.which("ffmpeg"):
        return Path(shutil.which("ffmpeg"))

    # 1. Local bundle / app directories
    for candidate_dir in (
        BUNDLE_DIR / "ffmpeg",
        DATA_DIR / "ffmpeg",
        Path("C:/ffmpeg/bin"),
        Path("C:/tools/ffmpeg/bin"),
    ):
        if (candidate_dir / "ffmpeg.exe").is_file():
            os.environ["PATH"] = str(candidate_dir) + os.pathsep + os.environ.get("PATH", "")
            return candidate_dir / "ffmpeg.exe"

    # 2. WinGet package directory on Windows
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        winget_pkg = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        if winget_pkg.is_dir():
            try:
                for ff in winget_pkg.glob("**/ffmpeg.exe"):
                    if ff.is_file():
                        os.environ["PATH"] = str(ff.parent) + os.pathsep + os.environ.get("PATH", "")
                        return ff
            except Exception:
                pass

    return None


# Create directories and ensure FFmpeg is in PATH eagerly so importing any module is enough.
ensure_dirs()
ensure_ffmpeg()
