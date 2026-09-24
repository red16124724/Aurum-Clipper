import os
import sys
import pytest
from pathlib import Path

sys.path.insert(0, os.path.abspath("."))

from app.models import GenerateRequest, FitMode, AspectRatio, Device
import app.jobs as jobs
import app.pretranscribe as pretranscribe
import app.selector as selector
from app.jumpcut import calculate_segments, remap_words
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_stress_cancellation():
    req = GenerateRequest(video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ", num_clips=2)
    job = jobs.create_job(req)
    assert job.status == "queued"
    assert not job.cancelled
    
    # Cancel immediately
    job.cancel()
    assert job.cancelled
    
    # Check snapshot
    snap = job.snapshot()
    assert snap["cancelled"] is True

def test_stress_rapid_cache_keys():
    models = ["large-v3-turbo", "large-v3", "medium", "small", "base", "savi0ur/whisper-hindi-hinglish-ct2"]
    languages = ["en", "hi", "ur", "auto", "es", "fr"]
    
    keys = set()
    for m in models:
        for l in languages:
            k = pretranscribe._key("test_vid_123", l, m)
            assert k not in keys, f"Duplicate key generated for {m} and {l}"
            assert "/" not in k and "\\" not in k, f"Key contains invalid path separator: {k}"
            keys.add(k)
    assert len(keys) == len(models) * len(languages)

def test_stress_empty_transcript_selector():
    empty_transcript = {"segments": [], "duration": 0.0}
    # Should fall back to even split without crashing
    windows = selector.select_clips(empty_transcript, num_clips=3, clip_length=30.0)
    assert isinstance(windows, list)

def test_stress_silent_video_jumpcut():
    # Video with 60 seconds duration and no words
    segs = calculate_segments([], 0.0, 60.0)
    assert segs == [(0.0, 60.0)]
    
    remapped = remap_words([], segs)
    assert remapped == []

def test_stress_overlapping_words_jumpcut():
    words = [
        {"word": "word1", "start": 1.0, "end": 2.0},
        {"word": "word2", "start": 1.5, "end": 2.5}, # overlapping
        {"word": "word3", "start": 2.2, "end": 3.0}, # overlapping
    ]
    segs = calculate_segments(words, 0.0, 5.0)
    assert len(segs) == 1
    remapped = remap_words(words, segs)
    assert len(remapped) == 3

def test_stress_invalid_url_generate():
    res = client.post("/api/prefetch", json={"video_url": "invalid://not-a-url"})
    assert res.status_code == 200
    prefetch_id = res.json()["prefetch_id"]
    
    # Polling status
    status_res = client.get(f"/api/prefetch/{prefetch_id}")
    assert status_res.status_code == 200

def test_stress_nonexistent_transcript():
    res = client.get("/api/transcript/non_existent_source_id_999")
    assert res.status_code == 200
    assert res.json()["ready"] is False

def test_stress_nonexistent_music_suggest():
    res = client.get("/api/music-suggest/non_existent_source_id_999")
    assert res.status_code == 200
    assert res.json()["ready"] is False

def test_stress_reframe_missing_recipe():
    res = client.get("/api/clip/fake_id/0/reframe")
    assert res.status_code == 404

def test_stress_ultra_short_video_clip_selection():
    # A video with duration 2.5s (shorter than MIN_CLIP_LEN and default tail cutoff)
    transcript = {"segments": [], "duration": 2.5}
    clips = selector.select_clips(transcript, num_clips=1)
    assert len(clips) == 1
    assert clips[0]["start"] == 0.0
    assert clips[0]["end"] == 2.5

def test_stress_keyframe_nan_and_malformed_resilience():
    import math
    from app.clipper import _pos_frac_expr, _zoom_expr
    # Malformed keyframes containing NaN, Inf, strings, out of bounds
    malformed_kfs = [
        {"time": float("nan"), "pos_x": 50.0, "zoom": 100},
        {"time": 0.0, "pos_x": float("nan"), "pos_y": 50.0, "zoom": 100},
        {"time": 1.0, "pos_x": 30.0, "pos_y": float("inf"), "zoom": 50},
        {"time": 2.0, "pos_x": 120.0, "pos_y": -20.0, "zoom": 200}, # clamped
        {"time": "invalid", "pos_x": "bad"},
    ]
    expr_x = _pos_frac_expr(malformed_kfs, "pos_x")
    assert expr_x is not None
    assert "nan" not in expr_x.lower()
    assert "inf" not in expr_x.lower()

    expr_zoom = _zoom_expr(malformed_kfs)
    assert expr_zoom is not None
    assert "nan" not in expr_zoom.lower()

def test_stress_audio_graph_string_and_invalid_inputs():
    from app.clipper import _music_audio_graph
    # Passes string numbers and None without throwing TypeError
    graph = _music_audio_graph(1, volume="45", duck="85", in_a="0:a")
    assert "volume=0.315" in graph
    assert "ratio=" in graph

def test_stress_drawtext_carriage_return_stripping():
    from app.clipper import _escape_drawtext
    escaped = _escape_drawtext("Title Line 1\r\nTitle Line 2: 50% [Amazing]; 'quote'")
    assert "\r" not in escaped
    assert "\\:" in escaped
    assert "\\%" in escaped
    assert "\\[" in escaped
    assert "\\]" in escaped
    assert "’" in escaped

def test_stress_offline_font_fallback_to_bundled(tmp_path, monkeypatch):
    import app.fonts as fonts
    test_font_dir = tmp_path / "fonts"
    test_font_dir.mkdir()
    monkeypatch.setattr(fonts, "FONTS_DIR", test_font_dir)

    # Calling _download for Roboto-Bold.ttf should copy from BUNDLED_FONTS_DIR without internet
    ok = fonts._download("Roboto-Bold.ttf", "https://invalid.unreachable.domain/Roboto-Bold.ttf")
    assert ok is True
    assert (test_font_dir / "Roboto-Bold.ttf").is_file()
    assert (test_font_dir / "Roboto-Bold.ttf").stat().st_size > 0

def test_stress_cache_cleanup_locked_file_tolerance(tmp_path, monkeypatch):
    import app.main as main_mod
    downloads_tmp = tmp_path / "downloads"
    downloads_tmp.mkdir()
    f1 = downloads_tmp / "file1.mp4"
    f2 = downloads_tmp / "file2.mp4"
    f1.write_bytes(b"content1")
    f2.write_bytes(b"content2")

    monkeypatch.setattr(main_mod, "DOWNLOADS_DIR", downloads_tmp)

    # Simulate Windows PermissionError on f1 unlink
    original_unlink = Path.unlink
    def mock_unlink(self, missing_ok=False):
        if self.name == "file1.mp4":
            raise PermissionError("[WinError 32] The process cannot access the file because it is being used by another process")
        return original_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", mock_unlink)

    res = client.post("/api/cleanup")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    # f2 was deleted, freeing its bytes
    assert data["freed_bytes"] == len(b"content2")
    assert not f2.exists()
    assert f1.exists()


def test_stress_captions_nan_inf_and_crlf():
    import math
    from app.captions import _fmt_time, _ass_escape
    # NaN and Inf and negative timestamps
    assert _fmt_time(float("nan")) == "0:00:00.00"
    assert _fmt_time(float("inf")) == "0:00:00.00"
    assert _fmt_time(-100.5) == "0:00:00.00"
    assert _fmt_time(125.45) == "0:02:05.45"

    # Carriage returns and special ASS characters
    raw = "Line 1\r\nLine 2 with {special} \\backslash and \r carriage return"
    escaped = _ass_escape(raw)
    assert "\r" not in escaped
    assert "\n" not in escaped
    assert "{" not in escaped
    assert "}" not in escaped
    assert "\\\\" in escaped


def test_stress_face_tracker_zero_samplerate_and_bounds(tmp_path):
    import cv2
    import numpy as np
    from app.tracker import track_face

    video_file = tmp_path / "test_tracker.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(video_file), fourcc, 30.0, (320, 240))
    for _ in range(15):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        out.write(frame)
    out.release()

    # Zero or negative sample_rate should not cause infinite loop
    kfs1 = track_face(video_file, start=0.0, end=0.5, sample_rate=0.0)
    assert isinstance(kfs1, list)

    # Inverted bounds (start > end) or NaN bounds
    kfs2 = track_face(video_file, start=10.0, end=5.0)
    assert kfs2 == []
    kfs3 = track_face(video_file, start=float("nan"), end=float("inf"))
    assert kfs3 == []


def test_stress_resolve_upload_partial_file_filtering(tmp_path, monkeypatch):
    import app.uploads as uploads
    upload_dir = tmp_path / "downloads"
    upload_dir.mkdir()
    monkeypatch.setattr(uploads, "DOWNLOADS_DIR", upload_dir)

    uid = "0123456789abcdef0123456789abcdef"
    partial_file = upload_dir / f"{uid}.mp4.part"
    partial_file.write_bytes(b"partial content")
    temp_file = upload_dir / f"{uid}.tmp"
    temp_file.write_bytes(b"temp")

    # When only partial files exist, resolve_upload should raise error
    with pytest.raises(uploads.InvalidVideoURLError):
        uploads.resolve_upload(uid)

    # When complete file exists, it resolves the real file
    real_file = upload_dir / f"{uid}.mp4"
    real_file.write_bytes(b"real completed video content")
    resolved = uploads.resolve_upload(uid)
    assert resolved == real_file


def test_stress_gemini_effects_and_spellcheck_malformed_json(monkeypatch):
    import app.effects as effects
    from unittest.mock import MagicMock

    monkeypatch.setattr(effects, "get_gemini_api_key", lambda: "mock_api_key")

    mock_client = MagicMock()
    mock_resp = MagicMock()
    # Return malformed JSON / non-list response
    mock_resp.text = '{"unexpected": "object instead of array"}'
    mock_client.models.generate_content.return_value = mock_resp

    monkeypatch.setattr("google.genai.Client", lambda api_key: mock_client)

    words = [
        {"word": "Hello", "start": 0.0, "end": 0.5},
        {"word": "world", "start": 0.5, "end": 1.0},
    ]

    # Malformed effects response should fall back cleanly to local heuristic
    fx = effects.analyze_effects_with_gemini(words, clip_start=0.0)
    assert isinstance(fx, list)

    # Malformed spell check response should fall back cleanly to original words
    sc = effects.spell_check_with_gemini(words)
    assert sc == words


def test_stress_selector_gemini_malformed_scores_and_inf(monkeypatch):
    import app.selector as selector
    from unittest.mock import MagicMock

    monkeypatch.setattr(selector, "get_gemini_api_key", lambda: "mock_api_key")

    mock_client = MagicMock()
    mock_resp = MagicMock()
    # Non-numeric score string
    mock_resp.text = '{"score": "SuperViral!", "title": "Viral Moment"}'
    mock_client.models.generate_content.return_value = mock_resp
    monkeypatch.setattr("google.genai.Client", lambda api_key: mock_client)

    candidates = [
        {"start": 0.0, "end": 30.0, "text": "This is a great moment in the video.", "score": 5.0}
    ]
    chosen = selector._select_with_gemini(candidates, num_clips=1)
    assert len(chosen) == 1
    assert chosen[0]["title"] == "Viral Moment"
    assert chosen[0]["start"] == 0.0


def test_stress_even_split_nan_duration():
    import app.selector as selector
    # NaN and Inf durations
    res_nan = selector._fallback_even_split({"duration": float("nan")}, num_clips=3)
    assert res_nan == []
    res_inf = selector._fallback_even_split({"duration": float("inf")}, num_clips=3)
    assert res_inf == []
    res_zero = selector._fallback_even_split({"duration": 0.0}, num_clips=3)
    assert res_zero == []


def test_stress_jumpcut_inverted_timestamps_and_bounds():
    # Words with negative duration or end < start
    words = [
        {"word": "test1", "start": 5.0, "end": 2.0},
        {"word": "test2", "start": 3.0, "end": 6.0},
    ]
    segs = calculate_segments(words, clip_start=10.0, clip_end=5.0)
    assert isinstance(segs, list)
    remapped = remap_words(words, [(0.0, 10.0)])
    assert len(remapped) == 2
    assert remapped[0]["end"] >= remapped[0]["start"]

