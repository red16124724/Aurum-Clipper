# ClipForge — Local AI Video Clipper

Turn any video URL into short, reframed, captioned clips — **entirely on your own
machine**. No OpenAI/Anthropic/cloud AI calls. The only network use is:

1. **yt-dlp** fetching the source video, and
2. a **one-time** download of the whisper model weights (~1.5 GB) and the caption font.

After the first run, transcription and clip selection run **fully offline**.

---

## Pipeline

```
URL → download (yt-dlp) → transcribe w/ word timestamps (faster-whisper)
    → select N clips (LOCAL heuristic; optional local Ollama)
    → per clip: cut + reframe (crop-fill | rounded 1:1 square on 9:16) + burn styled captions (ASS) via ffmpeg
    → .mp4 + preview/download URLs
```

## Requirements

- **Python 3.11+**
- **ffmpeg on your PATH** — this does the cutting, reframing, and caption burning.
  Without it, nothing renders.
  - Windows: `winget install Gyan.FFmpeg`
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`
- **GPU (recommended):** NVIDIA + CUDA 12 + matching cuDNN for faster-whisper.
  The app **auto-detects** the GPU and falls back to CPU automatically. You can
  also force the device per run from the UI **Compute** selector (**Auto / GPU /
  CPU**); the GPU option is disabled automatically when no CUDA GPU is detected.

> **No API keys. No `.env`. Nothing to configure.**

## Setup

### Windows (PowerShell)
```powershell
cd ai-video-clipper
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### macOS / Linux
```bash
cd ai-video-clipper
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

Then open **http://127.0.0.1:8000**.

On first start the app downloads the whisper `medium` model and the Roboto caption
font once, loads the model on CUDA (or CPU), and is then ready.

## Using it

1. Choose a **Video source** — **Paste link** (a URL) or **Upload file** (drag &
   drop or pick a video from your machine; a status line shows upload progress).
2. Choose aspect ratio (**9:16** default / 16:9).
3. Choose fit mode — **Crop (fill)** (uses the aspect ratio above) or **1:1 Square**
   (a **9:16** reel with the video cropped to a **rounded 1:1 square centered on
   black**, a **Title** drawn above it, and captions below — **ignores the aspect
   ratio**).
4. Set the number of clips (1–10).
5. Choose **Compute** — **Auto** (GPU if available, else CPU), **GPU**, or **CPU**.
6. Pick a caption style — the **live preview** shows how captions will look.
7. Click **Generate Shorts**. A **live progress bar** tracks each stage
   (download → transcribe → analyze → render); clips appear as soon as each one
   finishes rendering.

## API

The pipeline runs **asynchronously** so the UI can show live progress.

- `POST /api/upload` — upload a video file (`multipart/form-data`, field `file`).
  Returns `{ "status":"ok", "upload_id":"…", "filename":"…", "ext":".mp4" }`. The
  file is streamed to `downloads/` and referenced by `upload_id` in the next call.
  Unsupported types or empty files return HTTP 400 with a readable message.
- `POST /api/generate` — start a job. Body:
  ```json
  {
    "video_url": "https://…",
    "upload_id": null,
    "aspect_ratio": "9:16",
    "fit_mode": "crop",
    "bar_text": null,
    "num_clips": 3,
    "caption_style": "bold_white",
    "device": "auto"
  }
  ```
  Supply **either** `video_url` **or** `upload_id` (from `/api/upload`) — at least
  one is required (HTTP 422 otherwise); `upload_id` wins if both are sent. `device`
  is one of `auto` | `cuda` | `cpu` (default `auto`). Returns `{ "job_id": "…" }`
  immediately — the work runs on a background thread.
- `GET /api/progress/{job_id}` — **Server-Sent Events** stream of progress
  snapshots until the job finishes. Each event is JSON:
  ```json
  {
    "status": "running|done|error",
    "stage": "downloading|transcribing|selecting|rendering|done",
    "progress": 0.0,
    "message": "Transcribing... 42%",
    "clips": [{ "index": 0, "title": "…", "start": 0.0, "end": 30.0, "url": "/clips/…/0.mp4" }],
    "error": null
  }
  ```
  Finished clips appear in `clips` as soon as each one renders.
- `GET /api/result/{job_id}` — one-shot snapshot of a job (used by the UI to
  recover if the SSE stream drops). Bad input surfaces as `status:"error"` with a
  readable `message` — the server never crashes.
- `GET /api/history` — all past generations and their clips, newest first (powers
  the **My Clips** panel; persisted in `clips/history.json` so it survives restarts).
- `DELETE /api/clip/{clip_id}/{index}` — remove one generated clip (deletes the
  file and drops it from history).
- `POST /api/reveal` — body `{ "clip_id": "…", "index": 0 }`; opens that clip's
  folder in the OS file manager with the file selected (local-only convenience).
- `GET /api/caption-styles` — caption presets for the UI.
- `GET /api/devices` — `{"devices":["cuda","cpu"],"default":"cuda","cuda_available":true}`
  — what the Compute selector offers and whether a GPU is present.
- `POST /api/warmup?device=auto|cuda|cpu` — load the Whisper model on that device
  and report readiness: `{"status":"ready","device":"cuda","cached":true}` (or
  `{"status":"error","message":"…"}`). The UI calls this when the Compute dropdown
  changes to show a live loading/ready status.
- `GET /health` — `{"status":"ok","device":"cuda|cpu"}`.

## Caption styles

Defined once in `app/captions.py` and used for **both** the UI preview and the burned-in
ASS render, so what you preview matches what you get:

- **bold_white** — big bold white text, black outline, bottom-center.
- **karaoke_yellow** — white text, current word highlighted yellow (per-word timing).
- **minimal** — clean smaller white text, subtle shadow, bottom.

## Clip selection is a local heuristic (be honest)

`app/selector.py` is **not** cloud "AI virality" detection. It builds candidate windows
(~20–45s) aligned to transcript segments and scores them with simple local signals:
word density, sentence completeness, questions / strong-statement words, and length fit,
then picks the top non-overlapping windows.

**Optional local Ollama** (off by default): if you run [Ollama](https://ollama.com) locally,
set `USE_OLLAMA=1` (and optionally `OLLAMA_MODEL=llama3`) to have a **local** model score and
title the windows. Still zero external API calls — Ollama runs on `localhost`.

## Troubleshooting

- **`Unable to load libcudnn…` / CUDA errors:** the most common GPU issue is a cuDNN
  version mismatch. Install CUDA 12 + the matching cuDNN, or just let it fall back to CPU
  (slower on `medium`). See the
  [faster-whisper docs](https://github.com/SYSTRAN/faster-whisper#gpu).
- **`ffmpeg was not found on PATH`:** install ffmpeg (see Requirements) and reopen the shell.
- **First run is slow:** it's downloading the ~1.5 GB model once. Subsequent runs are fast.

## Project layout

```
ai-video-clipper/
├── app/
│   ├── main.py         # FastAPI app: lifespan model load, job + SSE endpoints
│   ├── jobs.py         # background job model + live progress pipeline runner
│   ├── models.py       # Pydantic schemas + enums + exceptions
│   ├── paths.py        # central directory layout
│   ├── downloader.py   # yt-dlp download
│   ├── uploads.py      # save/resolve user-uploaded video files
│   ├── history.py      # persistent clip history (My Clips panel)
│   ├── transcriber.py  # faster-whisper (auto GPU→CPU)
│   ├── selector.py     # local heuristic clip selection (+ Ollama scaffold)
│   ├── captions.py     # ASS builder + style presets (single source of truth)
│   ├── clipper.py      # ffmpeg cut / reframe / caption burn
│   └── fonts.py        # one-time caption font download
├── assets/fonts/       # Roboto (auto-fetched)
├── assets/masks/       # rounded-corner mask for square mode (auto-generated)
├── static/index.html   # vanilla frontend
├── downloads/  transcripts/  clips/   # auto-created, gitignored
├── requirements.txt
└── README.md
```
