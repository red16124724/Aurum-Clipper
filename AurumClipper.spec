# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs

block_cipher = None

BASE_DIR = os.path.abspath(".")

# Collect data files and submodules for heavy libraries
datas = [
    ('web/dist', 'web/dist'),
    ('assets/fonts', 'assets/fonts'),
    ('assets/music', 'assets/music'),
    ('assets/sfx', 'assets/sfx'),
    ('assets/masks', 'assets/masks'),
    ('assets/models', 'assets/models'),
    ('static', 'static'),
]

# Add library data files
datas += collect_data_files('faster_whisper')
datas += collect_data_files('ctranslate2')
datas += collect_data_files('indic_transliteration')
datas += collect_data_files('google_genai')
datas += collect_data_files('yt_dlp')

# Collect dynamic libraries
binaries = []
binaries += collect_dynamic_libs('ctranslate2')
binaries += collect_dynamic_libs('cv2')

import glob
for base_entry in [
    os.path.join(BASE_DIR, ".venv", "Lib", "site-packages", "nvidia"),
    os.path.join(sys.prefix, "Lib", "site-packages", "nvidia"),
]:
    if os.path.isdir(base_entry):
        for dll_file in glob.glob(os.path.join(base_entry, "**", "*.dll"), recursive=True):
            binaries.append((dll_file, "."))

try:
    binaries += collect_dynamic_libs('nvidia.cublas')
    binaries += collect_dynamic_libs('nvidia.cudnn')
except Exception:
    pass

# Hidden imports
hiddenimports = [
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.loops.asyncio',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.http.httptools_impl',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.protocols.websockets.websockets_impl',
    'uvicorn.lifespans',
    'uvicorn.lifespans.on',
    'uvicorn.lifespans.off',
    'fastapi',
    'starlette',
    'starlette.routing',
    'starlette.middleware',
    'starlette.middleware.cors',
    'starlette.responses',
    'starlette.staticfiles',
    'pydantic',
    'pydantic.deprecated.decorator',
    'webview',
    'webview.platforms',
    'webview.platforms.winforms',
    'pythonnet',
    'clr_loader',
    'ctranslate2',
    'faster_whisper',
    'mediapipe',
    'cv2',
    'google.genai',
    'google.genai.types',
    'indic_transliteration',
    'indic_transliteration.sansscript',
    'indic_transliteration.sansscript.schemes',
    'indic_transliteration.sansscript.schemes.brahmic',
    'yt_dlp',
    'psutil',
    'requests',
]

hiddenimports += collect_submodules('faster_whisper')
hiddenimports += collect_submodules('ctranslate2')
hiddenimports += collect_submodules('indic_transliteration')
hiddenimports += collect_submodules('google_genai')
hiddenimports += collect_submodules('app')

icon_path = None

a = Analysis(
    ['run.py'],
    pathex=[BASE_DIR],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'pydoc'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Aurum Clipper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)
