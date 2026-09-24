# ✨ Aurum Clipper — Local AI Video Clipper

**Made by RED4724**

[![GitHub Release](https://img.shields.io/github/v/release/red16124724/aurum-clipper?color=orange&label=Release)](https://github.com/red16124724/aurum-clipper/releases)
[![Tests](https://img.shields.io/badge/Tests-78%20passed-10b981)](https://github.com/red16124724/aurum-clipper)
[![License](https://img.shields.io/badge/License-MIT-3b82f6)](https://github.com/red16124724/aurum-clipper)
[![AI Engine](https://img.shields.io/badge/AI%20Engine-Gemini%20%2B%20Whisper-8b5cf6)](https://github.com/red16124724/aurum-clipper)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11%20(64--bit)-0284c7)](https://github.com/red16124724/aurum-clipper)

---

## 🌟 What is Aurum Clipper?

**Aurum Clipper** is a high-performance, studio-grade AI video editor that turns long YouTube videos, podcasts, interviews, gaming sessions, and local recordings into **viral vertical Shorts, Reels, and TikToks** — **100% on your own computer**.

Unlike web-based subscription clippers that cost \$20–\$50 every month, place watermarks, or upload your private footage to remote servers, **Aurum Clipper runs locally on your PC**. It combines the offline speed of OpenAI Whisper with the intelligence of Google Gemini AI for smart hook curation.

```
Long Video (URL or File) 
   │
   ▼
[ 🎙️ Offline Whisper AI ] ──► Instant word-level transcript
   │
   ▼
[ 🧠 Google Gemini AI ]   ──► Finds highest-retention viral moments
   │
   ▼
[ 🎯 YuNet Face Tracking] ──► Smart vertical crop & dynamic split-screen
   │
   ▼
[ 💬 ASS Subtitle Engine ] ──► Animated karaoke captions & custom fonts
   │
   ▼
[ 🎵 Smart Audio Ducking ]──► Background music ducks during speech
   │
   ▼
⚡ High-Resolution MP4 Vertical Clips (Ready to Post!)
```

---

## 🚀 Key Features (Explained Simply)

### 1. 🧠 Google Gemini AI Virality Scoring
Aurum Clipper analyzes the cadence, excitement, questions, and narrative arc of the speech using **Google Gemini Pro / Flash** models. It automatically discovers the most engaging 15-to-60-second hooks that stop people from scrolling past.

### 2. 🎯 Dynamic AI Split-Screen & Face Tracking
- **Auto-Face Tracking**: Automatically centers the speaker in frame using onboard computer vision (**YuNet neural network** + Haar cascades).
- **Dynamic Split**: Places the speaker on top and gaming/screen-share footage on the bottom for podcast and gameplay clips with **zero black bars**.
- **1:1 Square Mode & Crop (Fill)**: Choose between modern full-bleed 9:16 vertical video or square letterboxed framing.

### 3. 💬 19+ Animated Kinetic Caption Styles
- **Hormozi / MrBeast Style**: Big bold kinetic text with pop animations.
- **Word-Level Karaoke Highlighting**: Highlights each word in real-time as it is spoken.
- **Custom Fonts & Emojis**: Pre-bundled with top creator fonts (Komika Axis, Outfit, Anton, Montserrat) plus upload support for any `.ttf` / `.otf` font.
- **Bilingual & Multi-Language Support**: English, Spanish, Hindi, Hinglish, Arabic, French, German, Japanese, and more.

### 4. 🎬 Cinematic Visual Effects (VFX)
- **Auto Color Grading & LUTs**: Vibrant, Warm Film, Moody Cold, or Cinematic Dark color profiles.
- **Vignette & Glow**: Soft edge vignetting and active word highlight bloom for depth.
- **Bottom Gradient Falloff**: Smooth photographic fade behind captions to ensure crystal-clear text readability on any background.
- **Watermark & Signature**: Add your custom handle (e.g. `@RED4724`) anywhere on the screen with adjustable opacity.

### 5. 🎵 Smart Background Music & Audio Ducking
- Pick from pre-loaded upbeat, chill, cinematic, and motivational background tracks or upload your own.
- **Intelligent Audio Ducking**: The music automatically lowers in volume whenever someone speaks and smoothly returns to full volume during dramatic pauses.
- **Auto-Generated Sound Effects (SFX)**: Sub-bass impacts, whooshes, and dings triggered at key moments.

### 6. ⚡ 100% Private, Offline & GPU Accelerated
- Auto-detects **NVIDIA GeForce / RTX GPUs (CUDA)** with instant automatic fallback to multi-threaded CPU.
- Works offline after downloading your preferred Whisper model size (`tiny`, `base`, `small`, `medium`, `large-v3`, or `large-v3-turbo`).

---

## 💻 Quick Start & Installation

### Option A: Standalone Release (Recommended for Everyone)
*No Python, Node.js, or Git required! Everything is pre-bundled.*

1. Go to the [GitHub Releases Page](https://github.com/red16124724/aurum-clipper/releases/tag/v1.0.0).
2. **Download both parts into the same folder:**
   - `Aurum_Clipper_v1.0.0_Windows_x64.zip.001` (Part 1)
   - `Aurum_Clipper_v1.0.0_Windows_x64.zip.002` (Part 2)
   *(⚠️ Both files must be in the same folder on your computer).*
3. **Extract:**
   - **Using 7-Zip or WinRAR**: Right-click `Aurum_Clipper_v1.0.0_Windows_x64.zip.001` ➔ **"Extract Here"** (both parts merge automatically).
   - **Or Windows Command Prompt**: `copy /b Aurum_Clipper_v1.0.0_Windows_x64.zip.001 + Aurum_Clipper_v1.0.0_Windows_x64.zip.002 Aurum_Clipper.zip` and then extract `Aurum_Clipper.zip`.
4. Double-click **`Aurum Clipper.exe`** (or `Start.bat`).
5. Your browser will automatically open to **`http://127.0.0.1:8000`** — start creating clips immediately!

---

### Option B: Run from Source (For Developers)

#### 1. Prerequisites
- **Python 3.10+** (64-bit)
- **FFmpeg** installed and added to PATH:
  - Windows: `winget install Gyan.FFmpeg`
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`

#### 2. Clone & Install
```powershell
# Clone the repository
git clone https://github.com/red16124724/aurum-clipper.git
cd aurum-clipper

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

#### 3. Launch App
```powershell
# Start the full app (FastAPI Backend + React Studio)
python run.py
```
Open **http://127.0.0.1:8000** in your browser.

---

## 🎬 How to Create Viral Clips in 5 Simple Steps

```
[ Step 1: Input ] ──► [ Step 2: Split & Framing ] ──► [ Step 3: Captions ] ──► [ Step 4: VFX & Music ] ──► [ Step 5: Export ]
```

1. **Step 1: Video Source**
   - Paste a YouTube URL, or drag and drop any `.mp4`, `.mov`, or `.mkv` video file from your computer.
2. **Step 2: Dynamic Split & Layout**
   - Choose your framing (**9:16 Vertical**, **1:1 Square**, or **16:9 Landscape**).
   - Toggle **Dynamic AI Split Screen** if you have a facecam + gameplay video.
3. **Step 3: Subtitles & Font Styling**
   - Select from 19+ pre-built caption presets or customize font family, text color, stroke thickness, and karaoke highlight color.
4. **Step 4: Cinematic VFX & Background Music**
   - Choose a color grade LUT and select a background soundtrack with automatic speech ducking.
5. **Step 5: Review & Instant Export**
   - Review AI-selected moments in the timeline, adjust start/end timestamps if needed, and hit **Export Video** to render final MP4s.

---

## 🔑 Google Gemini AI Setup (Free & 1-Minute)

Aurum Clipper includes free Google Gemini AI integration to dramatically improve clip selection:

1. Get a free API key at [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Launch Aurum Clipper. On first launch, a setup window will appear.
3. Paste your key and click **Save & Test Connection**.
4. That's it! Gemini will now automatically find the most engaging hooks and generate viral titles for your clips.

*(Note: If you don't connect a Gemini key, Aurum Clipper will automatically use its built-in local heuristic analysis with zero internet required).*

---

## 🏗️ Architecture & Technology Stack

- **Backend**: Python 3.12, FastAPI, Uvicorn, Pydantic v2
- **Speech Recognition**: Faster-Whisper (CTranslate2 CUDA & CPU engine)
- **Computer Vision**: OpenCV (YuNet Neural Network + Haar Cascades)
- **Video & Audio Processing**: FFmpeg (CBR 10000k, NVENC GPU encoder, ASS subtitle filter, libmp3lame, afade, sidechain audio ducking)
- **Frontend**: React 18, Vite 5, Lucide Icons, Glassmorphic Aurora Design System
- **Testing**: PyTest (78 automated unit, stress, cancellation, and failure-mode test suites)

---

## 🧪 Testing & Verification

Aurum Clipper is engineered with exhaustive test coverage:

```powershell
# Run the complete test suite
pytest tests/ -v
```

```
============================= 78 passed in 14.40s =============================
```

---

## ❓ Frequently Asked Questions (FAQ)

<details>
<summary><b>Q: Do I need an expensive NVIDIA graphics card to use Aurum Clipper?</b></summary>
No! Aurum Clipper runs smoothly on standard multi-core CPUs. If you have an NVIDIA GPU, it will automatically use CUDA acceleration for up to 8x faster rendering, but it works 100% on CPU as well.
</details>

<details>
<summary><b>Q: Windows SmartScreen gave a warning when opening the app. Is it safe?</b></summary>
Yes, 100%. The application is completely open-source and free from malware. Windows SmartScreen displays a warning on newly downloaded unsigned `.exe` files. Click <b>"More info"</b> and then <b>"Run anyway"</b>.
</details>

<details>
<summary><b>Q: How do I completely close Aurum Clipper when finished?</b></summary>
Simply close the terminal window or double-click the <b>"Stop Aurum Clipper.vbs"</b> shortcut.
</details>

---

## 👨‍💻 Authorship & Credits

- **Creator & Lead Developer**: **RED4724**
- **Repository**: [https://github.com/red16124724/aurum-clipper](https://github.com/red16124724/aurum-clipper)
- **License**: MIT License — free for personal and commercial content creation.

---

<div align="center">
  <sub><b>Aurum Clipper</b> — Made with ❤️ by <b>RED4724</b></sub>
</div>
