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

# Browsers we'll borrow cookies from (in order) when YouTube throws up a
# sign-in / "confirm you're not a bot" wall. Override with env vars below.
_DEFAULT_BROWSERS = ["chrome", "edge", "brave", "firefox", "opera", "vivaldi"]
_COOKIE_FILE_ENV = "CLIPFORGE_COOKIES_FILE"       # path to a cookies.txt
_COOKIE_BROWSER_ENV = "CLIPFORGE_COOKIES_BROWSER"  # force one browser, e.g. "chrome"


def _needs_cookies(reason: str) -> bool:
    """True when a failure reason looks like a sign-in / bot / cookie wall —
    used to add a helpful cookie hint to the final error message.
    """
    r = (reason or "").lower()
    return any(k in r for k in (
        "sign in", "not a bot", "cookie", "log in", "login", "consent",
        "age", "members-only", "account", "authentication",
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


# YouTube player clients to fall back through. Different clients are served by
# different endpoints, and the cookie-free mobile/TV ones frequently slip past
# the "confirm you're not a bot" wall the default web client trips.
_PLAYER_CLIENTS = ["android", "ios", "tv", "mweb"]


def _download_attempts(base_opts: dict) -> list[tuple[str, dict]]:
    """Ordered (label, ydl_opts) attempts.

    Order is cheapest-and-most-likely first:
      1. explicit cookies (only if the user configured a file/browser),
      2. the plain default pass (fast for public videos),
      3. cookie-free alternate YouTube player clients (dodge the bot wall),
      4. browser cookies (needs the browser closed on Windows) as a last resort.
    """
    cookie_file = os.environ.get(_COOKIE_FILE_ENV)
    forced = os.environ.get(_COOKIE_BROWSER_ENV)

    attempts: list[tuple[str, dict]] = []
    if cookie_file:
        attempts.append(("cookies file", {**base_opts, "cookiefile": cookie_file}))
    if forced:
        b = forced.strip().lower()
        attempts.append((f"{b} cookies", {**base_opts, "cookiesfrombrowser": (b,)}))

    attempts.append(("default", dict(base_opts)))

    for client in _PLAYER_CLIENTS:
        attempts.append((
            f"{client} client",
            {**base_opts, "extractor_args": {"youtube": {"player_client": [client]}}},
        ))

    if not forced:  # auto-try common browsers unless the user pinned one
        for b in _DEFAULT_BROWSERS:
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


def download_video(
    url: str, progress_hook: Optional[Callable[[dict], None]] = None
) -> Path:
    """Download `url` to downloads/<uuid>.mp4 and return the file path.

    Args:
        url: source video URL.
        progress_hook: optional yt-dlp progress callback (receives the raw
            progress dict with ``status``/``downloaded_bytes``/``total_bytes``)
            so callers can surface live download progress.

    Raises:
        InvalidVideoURLError: on any download failure, with a readable message.
    """
    if not url or not url.strip():
        raise InvalidVideoURLError("No video URL was provided.")

    clip_uuid = uuid.uuid4().hex
    # yt-dlp fills in the real extension; we force a merge to mp4 below so the
    # final file is downloads/<uuid>.mp4.
    out_template = str(DOWNLOADS_DIR / f"{clip_uuid}.%(ext)s")
    expected_path = DOWNLOADS_DIR / f"{clip_uuid}.mp4"

    base_opts = {
        # Prefer the best stream up to 1080p (plenty for shorts, avoids slow 4K
        # downloads). Container is normalised to mp4 by merge_output_format, so
        # we don't restrict by extension - that was too strict and could fall
        # back to a tiny stream when no progressive mp4 existed.
        "format": (
            "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
        ),
        "merge_output_format": "mp4",
        "outtmpl": out_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        # Be resilient: keep going if a single fragment hiccups.
        "ignoreerrors": False,
    }
    if progress_hook is not None:
        base_opts["progress_hooks"] = [progress_hook]

    # Try in order: explicit cookies (if set) → plain → browser cookies. We only
    # fall through to the cookie-based attempts when the failure looks like a
    # sign-in / bot wall, so public videos still download on the first (fast) try.
    last_reason = ""
    last_exc: Optional[Exception] = None
    ok = False
    for label, opts in _download_attempts(base_opts):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url.strip()])
            ok = True
            if label != "default":
                logger.info("Downloaded %s using %s", url, label)
            break
        except Exception as exc:  # noqa: BLE001 - never let the server crash here
            last_reason = _clean_ydl_error(str(exc))
            last_exc = exc
            logger.warning("yt-dlp [%s] failed for %s: %s", label, url, last_reason)
            if _is_terminal(last_reason):
                break  # dead/blocked link — no fallback can recover it

    if not ok:
        msg = ("Could not download that video. Check the URL is correct, public, "
               "and reachable from this machine.")
        if last_reason:
            msg += f"\nReason: {last_reason}"
        if _needs_cookies(last_reason):
            msg += (
                "\n\nThis video is behind YouTube's sign-in / bot check. Make sure "
                "you're logged into YouTube in your browser, then close the browser "
                "and try again. To pin a browser set CLIPFORGE_COOKIES_BROWSER "
                "(chrome/edge/firefox), or point CLIPFORGE_COOKIES_FILE at a cookies.txt."
            )
        raise InvalidVideoURLError(msg) from last_exc

    if expected_path.exists():
        return expected_path

    # Some sources may not produce exactly <uuid>.mp4 (e.g. a different
    # container survived the merge). Fall back to any file with our uuid prefix.
    candidates = sorted(DOWNLOADS_DIR.glob(f"{clip_uuid}.*"))
    if candidates:
        return candidates[0]

    raise InvalidVideoURLError(
        "The download completed but no output file was produced. The video may "
        "be unavailable or region-locked."
    )
