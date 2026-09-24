"""Download the source video with yt-dlp (the only video-fetch network call).

We use the yt-dlp *Python API* rather than shelling out so failures surface as
exceptions we can translate into a clean 400. The server must never crash on a
bad or blocked URL.
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from pathlib import Path
from typing import Callable, Optional

import yt_dlp

from .models import InvalidVideoURLError
from .paths import DOWNLOADS_DIR

logger = logging.getLogger(__name__)

# Strip ANSI colour codes yt-dlp sometimes embeds in its error strings.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Browsers we'll check for cookies when YouTube throws up a
# sign-in / "confirm you're not a bot" wall.
_COOKIE_FILE_ENV = "CLIPFORGE_COOKIES_FILE"       # path to a cookies.txt
_COOKIE_BROWSER_ENV = "CLIPFORGE_COOKIES_BROWSER"  # force one browser, e.g. "chrome"


def _installed_browsers() -> list[str]:
    """Return only the browsers physically installed with user data on this machine."""
    installed = []
    candidates = [
        ("brave", os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data")),
        ("chrome", os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")),
        ("edge", os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data")),
        ("firefox", os.path.expandvars(r"%APPDATA%\Mozilla\Firefox\Profiles")),
        ("opera", os.path.expandvars(r"%APPDATA%\Opera Software\Opera Stable")),
        ("vivaldi", os.path.expandvars(r"%LOCALAPPDATA%\Vivaldi\User Data")),
    ]
    for name, path in candidates:
        if os.path.isdir(path):
            installed.append(name)
    return installed


def _find_cookie_file() -> Optional[str]:
    """Auto-discover a user-supplied cookies.txt file in the app directory or env."""
    env_file = os.environ.get(_COOKIE_FILE_ENV)
    if env_file and os.path.isfile(env_file):
        return env_file

    search_dirs = [
        Path.cwd(),
        DOWNLOADS_DIR.parent,
        DOWNLOADS_DIR,
    ]
    for d in search_dirs:
        for name in ("cookies.txt", "youtube_cookies.txt", "cookies.netscape", "youtube.cookies"):
            candidate = d / name
            if candidate.is_file() and candidate.stat().st_size > 0:
                return str(candidate)
    return None


def _needs_cookies(reason: str) -> bool:
    """True when a failure reason looks like a sign-in / bot / cookie wall —
    used to add a helpful cookie hint to the final error message.
    """
    r = (reason or "").lower()
    return any(k in r for k in (
        "sign in", "not a bot", "cookie", "log in", "login", "consent",
        "age", "members-only", "account", "authentication", "bot",
    ))


def _is_terminal(reason: str) -> bool:
    """True when no retry (other client / cookies) can possibly help, so we stop
    early instead of grinding through every fallback for a dead/blocked link.
    """
    r = (reason or "").lower()
    return any(k in r for k in (
        "unavailable", "been removed", "does not exist", "no longer",
        "unsupported url", "not available in your", "is not a valid",
        "deleted", "terminated",
    ))


# YouTube player client fallback configurations to bypass bot/login walls
_PLAYER_CLIENT_COMBOS = [
    ["default", "web", "tv", "mweb", "android_vr", "ios", "android"],
    ["mweb", "tv", "android", "ios"],
    ["tv", "mweb"],
    ["android", "ios"],
    ["web_safari", "web_embedded"],
]


def _download_attempts(base_opts: dict) -> list[tuple[str, dict]]:
    """Ordered (label, ydl_opts) attempts.

    Order is fastest, cleanest, and most reliable first:
      1. explicit/auto-discovered cookies file (highest reliability if present),
      2. forced browser cookies (if user explicitly set CLIPFORGE_COOKIES_BROWSER),
      3. default pass with JS challenge solver & highest quality format sorting,
      4. alternate player client combinations (mweb, tv, android, ios),
      5. installed browser cookies (fallback if bot check or login walls encountered).
    """
    cookie_file = _find_cookie_file()
    forced = os.environ.get(_COOKIE_BROWSER_ENV)

    attempts: list[tuple[str, dict]] = []
    if cookie_file:
        attempts.append(("cookies file", {**base_opts, "cookiefile": cookie_file}))
    if forced:
        b = forced.strip().lower()
        attempts.append((f"{b} cookies", {**base_opts, "cookiesfrombrowser": (b,)}))

    # Clean, non-intrusive passes that do not touch locked browser SQLite databases
    attempts.append(("default", dict(base_opts)))

    for i, clients in enumerate(_PLAYER_CLIENT_COMBOS, 1):
        attempts.append((
            f"client group {i} ({'+'.join(clients)})",
            {**base_opts, "extractor_args": {"youtube": {"player_client": clients}}},
        ))

    # Fallback to local browser cookies only if no explicit cookie source was configured
    if not cookie_file and not forced:
        for b in _installed_browsers():
            attempts.append((f"{b} cookies", {**base_opts, "cookiesfrombrowser": (b,)}))

    return attempts


def _clean_ydl_error(raw: str) -> str:
    """Turn a raw yt-dlp DownloadError string into one short, readable line.

    yt-dlp prefixes messages with ``ERROR:`` (sometimes coloured) and can append
    a hint about reporting bugs — we drop both and keep just the real reason so
    the UI can show *why* a video failed (private, age-gated, geo-blocked, etc.).
    """
    text = _ANSI_RE.sub("", raw or "").strip()
    # Keep only the first line — that's the human reason.
    line = text.splitlines()[0] if text else ""
    line = re.sub(r"^ERROR:\s*", "", line).strip()
    # Drop yt-dlp's "; please report this issue …" tail and extractor prefixes.
    line = re.split(r";\s*(please report|you might want)", line, maxsplit=1)[0].strip()
    line = re.sub(r"^\[[^\]]+\]\s*[^:]*:\s*", "", line)  # e.g. "[youtube] ID: "
    return line[:300]


def _cleanup_partials(clip_uuid: str) -> None:
    """Remove any leftover partial files for this download ID on cancellation or failure."""
    try:
        for p in DOWNLOADS_DIR.glob(f"{clip_uuid}.*"):
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass
    except Exception:
        pass


def download_video(
    url: str,
    progress_hook: Optional[Callable[[dict], None]] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> Path:
    """Download `url` to downloads/<uuid>.mp4 and return the file path.

    Downloads the highest resolution video stream (8K, 4K, 1440p, 1080p, 720p, etc.)
    and highest bitrate audio stream available on the source with zero quality loss.

    Args:
        url: source video URL.
        progress_hook: optional yt-dlp progress callback (receives the raw
            progress dict with ``status``/``downloaded_bytes``/``total_bytes``)
            so callers can surface live download progress.
        is_cancelled: optional callable returning True if the download was cancelled.

    Raises:
        InvalidVideoURLError: on any download failure, with a readable message.
    """
    if not url or not url.strip():
        raise InvalidVideoURLError("No video URL was provided.")

    if is_cancelled and is_cancelled():
        raise InvalidVideoURLError("Download cancelled by user.")

    clip_uuid = uuid.uuid4().hex
    out_template = str(DOWNLOADS_DIR / f"{clip_uuid}.%(ext)s")
    expected_path = DOWNLOADS_DIR / f"{clip_uuid}.mp4"

    import shutil
    import subprocess
    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
    node_bin = shutil.which("node")

    base_opts = {
        # Always download the highest available video resolution and highest quality audio stream.
        # Format selector sorts by maximum resolution, framerate, and bitrate losslessly.
        "format": "bestvideo*+bestaudio/best",
        "format_sort": ["quality", "res", "fps", "hdr:12", "vcodec", "channels", "acodec", "br"],
        "merge_output_format": "mp4",
        "ffmpeg_location": ffmpeg_bin,
        "outtmpl": out_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": False,
        "retries": 10,
        "fragment_retries": 10,
        "file_access_retries": 5,
        "socket_timeout": 30,
    }
    if node_bin:
        base_opts["js_runtimes"] = {"node": {"path": node_bin}}
        base_opts["remote_components"] = {"ejs:github"}

    def _safe_progress_hook(d: dict) -> None:
        if is_cancelled and is_cancelled():
            _cleanup_partials(clip_uuid)
            raise InvalidVideoURLError("Download cancelled by user.")
        if progress_hook is not None:
            progress_hook(d)

    base_opts["progress_hooks"] = [_safe_progress_hook]

    primary_reason = ""
    last_reason = ""
    last_exc: Optional[Exception] = None
    ok = False
    for label, opts in _download_attempts(base_opts):
        if is_cancelled and is_cancelled():
            _cleanup_partials(clip_uuid)
            raise InvalidVideoURLError("Download cancelled by user.")
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url.strip()])
            ok = True
            if label != "default":
                logger.info("Downloaded %s using %s", url, label)
            break
        except InvalidVideoURLError:
            _cleanup_partials(clip_uuid)
            raise
        except Exception as exc:  # noqa: BLE001 - never let the server crash here
            if is_cancelled and is_cancelled():
                _cleanup_partials(clip_uuid)
                raise InvalidVideoURLError("Download cancelled by user.") from exc
            clean_err = _clean_ydl_error(str(exc))
            last_reason = clean_err
            last_exc = exc
            # Keep primary_reason from meaningful failures (e.g. bot checks, private video, unavailable)
            # rather than internal browser database lookup issues.
            if not primary_reason or ("could not find" not in clean_err.lower() and "cookies database" not in clean_err.lower()):
                primary_reason = clean_err
            logger.warning("yt-dlp [%s] failed for %s: %s", label, url, clean_err)
            if _is_terminal(clean_err):
                break

    if not ok:
        display_reason = primary_reason or last_reason
        msg = ("Could not download that video. Check the URL is correct, public, "
               "and reachable from this machine.")
        if display_reason:
            msg += f"\nReason: {display_reason}"
        if _needs_cookies(display_reason):
            msg += (
                "\n\nYouTube requires verification / login for this video. To resolve this:\n"
                "1. Export your YouTube cookies using a browser extension (like 'Get cookies.txt LOCALLY')\n"
                "2. Save the file as 'cookies.txt' in your Aurum Clipper app folder\n"
                "3. Or ensure you are logged into YouTube in your browser, close the browser, and try again."
            )
        raise InvalidVideoURLError(msg) from last_exc

    if expected_path.exists() and expected_path.stat().st_size > 0:
        return expected_path

    # Filter out temporary partial files and find valid downloaded media
    candidates = sorted(
        [
            p for p in DOWNLOADS_DIR.glob(f"{clip_uuid}.*")
            if not p.name.endswith((".part", ".ytdl", ".temp", ".tmp"))
            and p.is_file() and p.stat().st_size > 0
        ],
        key=lambda p: p.stat().st_size,
        reverse=True,
    )
    if candidates:
        primary = candidates[0]
        if primary.suffix.lower() == ".mp4":
            return primary
        # Remux non-mp4 media (e.g. mkv/webm) losslessly into standard mp4 container
        try:
            subprocess.run(
                [
                    ffmpeg_bin, "-y", "-i", str(primary),
                    "-c", "copy", "-movflags", "+faststart",
                    str(expected_path)
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            if expected_path.exists() and expected_path.stat().st_size > 0:
                try:
                    primary.unlink(missing_ok=True)
                except Exception:
                    pass
                return expected_path
        except Exception:
            pass
        return primary

    raise InvalidVideoURLError(
        "The download completed but no output file was produced. The video may "
        "be unavailable or region-locked."
    )
