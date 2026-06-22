"""Local AI video clipping tool — all inference runs on the user's machine.

No external/cloud AI APIs are used anywhere in this package. The only network
access is yt-dlp fetching the source video and a one-time download of the
whisper model weights and the bundled caption font.
"""

__version__ = "0.1.0"
