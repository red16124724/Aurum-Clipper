# ClipForge — Version 1.0.0 (Beta)

**Release date:** 2026-07-15
**Build:** 1
**Platform:** Windows 10/11 (64-bit)
**Distribution:** `.exe` installer (Inno Setup) — a portable ZIP build remains available for advanced users
**Price:** Free
**Stage:** Public Beta

> This is an early beta. The core pipeline (download/upload → transcribe → auto-clip → caption → render) is stable and has been tested end-to-end, but you will find rough edges. Please report anything that breaks.

---

## What's new in this build

- **Fixed — cinematic effects combining in export.** Verified end-to-end (frontend payload, backend render, and a full real render through the actual API) that enabling multiple effects together (e.g. Bottom Fade + Glow) sends and renders all of them — none get dropped when another is toggled on.
- **Reworked — Bottom Fade effect.** Replaced the linear opacity ramp with an eased (smoothstep) curve, applied identically in both the live preview and the final render. The result is a soft, photographic falloff with no visible seam or "black bar" edge.
- **Redesigned editor layout.** CapCut-inspired 3-panel workspace: style/transcript tools on the left, canvas in the center, export & settings on the right, timeline along the bottom.
- **New — Corner style option.** Square-format clips can now use sharp or rounded corners.
- **New — dark + lime visual theme**, applied across the whole app (landing page, sidebar, and editor).
- **New — Windows installer.** Start Menu and Desktop shortcuts, a clean per-user install (no admin required), and a proper uninstaller. Launching no longer shows a visible console window.
- **New — "Stop ClipForge" shortcut**, since closing the browser tab alone doesn't quit the background server (see Known Limitations).
- GPU/CPU compute device selection (unchanged from earlier internal builds, confirmed working in this release).

## Installation

1. Download `ClipForge-Setup-v1.0.0-beta.exe`.
2. Run it — no admin rights needed, it installs to your user profile.
3. Choose whether to add a desktop shortcut, then finish the wizard.
4. Launch **ClipForge** from the Start Menu (or the desktop shortcut). Your default browser opens automatically once the app is ready.
5. First launch may take a little longer while the local Whisper model warms up.

To fully close the app, use the **Stop ClipForge** shortcut (Start Menu) — closing the browser tab alone leaves the local server running so an accidental tab close doesn't interrupt a render in progress.

## Known limitations (Beta)

- **Windows only.** macOS/Linux are not packaged yet.
- **Runs as a local web app in your browser**, not a native window — this keeps the app lightweight, but it means there's no taskbar app icon while it's open, and closing the tab doesn't stop the server (use "Stop ClipForge").
- **Internet is required to fetch a video from a URL** (yt-dlp needs to reach the source). Uploading your own video file works fully offline.
- **GPU acceleration needs an NVIDIA (CUDA) card.** Other machines automatically fall back to CPU, which is noticeably slower for transcription.
- **No auto-update yet.** Future versions will need a manual reinstall over the old one.
- **Very long source videos** (well over an hour) are not yet specifically optimized and will take longer to transcribe.
- This is a **beta** — expect UI rough edges and the occasional bug as more features are added.

## Disclaimer

ClipForge Version 1 Beta is an early release of a personal project, shared publicly because people who saw it asked for access. It is provided free, as-is, with no guarantee of uptime, support response time, or data durability — please keep separate copies of anything important. Feedback and bug reports are very welcome and will directly shape the next version.
