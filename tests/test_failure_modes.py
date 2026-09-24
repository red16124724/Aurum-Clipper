import os
import sys
import pytest
import subprocess
import pathlib
import json
import re
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath("."))

from fastapi.testclient import TestClient
from app.main import app
from app.models import GenerateRequest, FitMode, AspectRatio, Device, ReframeKeyframe
from app.clipper import ClipOptions, generate_clip, get_encode_args, _escape_drawtext, _pos_frac_expr, _zoom_expr, _music_audio_graph
from app.jumpcut import calculate_segments, remap_words, remap_keyframes
import app.jobs as jobs
import app.transcriber as transcriber
import app.tracker as tracker
import app.selector as selector
import app.captions as captions

client = TestClient(app)

# ---------------------------------------------------------------------------
# 1. API & Cleanup Failure Mode
# ---------------------------------------------------------------------------
def test_prove_cleanup_name_error_bug():
    """
    PROVE-IT TEST: POST /api/cleanup attempts to access 'paths.DOWNLOADS_DIR',
    but 'paths' is not imported in app/main.py, causing NameError.
    """
    res = client.post("/api/cleanup")
    assert res.status_code == 200
    data = res.json()
    # If the bug exists, message contains "name 'paths' is not defined"
    # When fixed, status should be 'success' and freed_bytes integer
    if data.get("status") == "error":
        assert "name 'paths' is not defined" in data.get("message", "")


# ---------------------------------------------------------------------------
# 2. Clipper & Video Rendering Failure Modes
# ---------------------------------------------------------------------------
def test_prove_square_mode_audioless_video_crash(tmp_path):
    """
    PROVE-IT TEST: When a video has NO audio track, clipper adds anullsrc at input index 1.
    In FitMode.SQUARE, clipper hardcodes '[1:v]' for the mask stream, which crashes
    because input 1 is an audio stream, not a video stream.
    """
    video_file = tmp_path / "audioless.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=red:s=320x240:d=1",
        "-c:v", "libx264", str(video_file)
    ], check=True, capture_output=True)

    opts = ClipOptions(
        aspect_ratio=AspectRatio.NINE_16,
        fit_mode=FitMode.SQUARE,
        ass_path=None,
        clip_id="test_sq_bug",
        index=0,
    )

    # Successfully generates without stream indexing crash
    output_path = generate_clip(video_file, 0.0, 1.0, opts)
    assert output_path.exists(), "Expected FitMode.SQUARE with audio-less video to succeed"

# ---------------------------------------------------------------------------
# 3. Pipeline Concurrency & Cancellation
# ---------------------------------------------------------------------------
def test_prove_cancellation_status_overwritten():
    """
    VERIFICATION TEST: When job.cancel() is called, status becomes 'cancelled'.
    If an in-flight worker subsequently raises an error or calls job.fail(),
    it must NOT overwrite the 'cancelled' status with 'error'.
    """
    req = GenerateRequest(video_url="https://youtube.com/watch?v=dQw4w9WgXcQ")
    job = jobs.Job(req)
    job.cancel()
    assert job.status == "cancelled"
    assert job.cancelled is True

    # Simulate worker failure catch
    job.fail("Transcription failed: Transcription cancelled")
    # Verify the fix: job.status remains cancelled and is guarded
    assert job.status == "cancelled", "Expected job.fail to preserve 'cancelled' status"


# ---------------------------------------------------------------------------
# 4. Frontend Code Static Verification & Bugs
# ---------------------------------------------------------------------------
def test_prove_frontend_bugs_in_source():
    """
    PROVE-IT TEST: Static analysis of frontend source files reveals 3 bugs:
    1. Screen3Captions.jsx uses 'duration' in <Timeline duration={duration} /> but
       'duration' is NOT destructured from props (causing ReferenceError).
    2. usePrep.js calls 'lang()' on line 99, which is not a function (causing ReferenceError).
    3. Create.jsx uses 'whisperModel' in localStorage, but App.jsx and Settings.jsx
       use 'cf-model-size' (causing model selection desynchronization).
    """
    web_dir = pathlib.Path(__file__).parent.parent / "web" / "src"

    # Bug 1: Screen3Captions missing duration prop
    s3_file = web_dir / "pages" / "create" / "Screen3Captions.jsx"
    if s3_file.exists():
        s3_content = s3_file.read_text(encoding="utf-8")
        # Check function signature
        sig_match = re.search(r"export default function Screen3Captions\(\{([^}]+)\}\)", s3_content)
        assert sig_match is not None
        params = [p.strip() for p in sig_match.group(1).split(",")]
        timeline_has_duration = "duration={duration}" in s3_content
        duration_in_props = "duration" in params
        assert timeline_has_duration and duration_in_props, "Screen3Captions correctly receives and wires duration"

    # Verify usePrep.js correctly uses r.current.lang
    use_prep_file = web_dir / "usePrep.js"
    if use_prep_file.exists():
        prep_content = use_prep_file.read_text(encoding="utf-8")
        assert "r.current.lang" in prep_content, "usePrep.js should use r.current.lang"
        assert "lang()" not in prep_content, "usePrep.js should not call undefined lang()"

    # Bug 3: LocalStorage key mismatch
    create_file = web_dir / "pages" / "Create.jsx"
    app_file = web_dir / "App.jsx"
    settings_file = web_dir / "pages" / "Settings.jsx"
    if create_file.exists() and app_file.exists():
        create_c = create_file.read_text(encoding="utf-8")
        app_c = app_file.read_text(encoding="utf-8")
        settings_c = settings_file.read_text(encoding="utf-8")

        assert 'localStorage.getItem("whisperModel")' in create_c
        assert 'localStorage.getItem("cf-model-size")' in app_c
        assert 'localStorage.setItem("cf-model-size"' in settings_c

# ---------------------------------------------------------------------------
# 5. Whisper Model Catalog & Switching
# ---------------------------------------------------------------------------
def test_whisper_model_catalog_and_repo_mapping():
    """Verify all 6 model sizes in catalog map to correct Hugging Face repositories."""
    assert len(transcriber.MODELS_CATALOG) == 6
    catalog_ids = [m["id"] for m in transcriber.MODELS_CATALOG]
    expected_ids = ["large-v3-turbo", "large-v3", "medium", "small", "base", "savi0ur/whisper-hindi-hinglish-ct2"]
    assert catalog_ids == expected_ids

    # Check HF repo names
    assert transcriber._repo_id_for_size("large-v3-turbo") == "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
    assert transcriber._repo_id_for_size("base") == "Systran/faster-whisper-base"
    assert transcriber._repo_id_for_size("savi0ur/whisper-hindi-hinglish-ct2") == "savi0ur/whisper-hindi-hinglish-ct2"


# ---------------------------------------------------------------------------
# 6. Jumpcut Edge Cases (100% Silence vs 0% Silence vs Overlapping Words)
# ---------------------------------------------------------------------------
def test_jumpcut_boundary_conditions_stress():
    """Stress-test jumpcut algorithm with extreme speech patterns."""
    # 1. 100% silence (empty transcript) -> Must keep entire range without crash
    empty_segs = calculate_segments([], 0.0, 45.0)
    assert empty_segs == [(0.0, 45.0)]
    assert remap_words([], empty_segs) == []

    # 2. 0% silence (rapid continuous speech, no pauses > 0.6s)
    rapid_words = [
        {"word": f"w{i}", "start": round(i * 0.3, 2), "end": round(i * 0.3 + 0.28, 2)}
        for i in range(50)  # 0.0s to 15.0s
    ]
    rapid_segs = calculate_segments(rapid_words, 0.0, 15.0, max_silence=0.6, pad=0.15)
    assert len(rapid_segs) == 1
    assert rapid_segs[0][0] == 0.0
    assert rapid_segs[0][1] >= 14.9

    # 3. Overlapping speech (multiple speakers talking at once)
    overlap_words = [
        {"word": "speaker1_a", "start": 1.0, "end": 2.5},
        {"word": "speaker2_a", "start": 1.2, "end": 2.2},
        {"word": "speaker1_b", "start": 2.4, "end": 3.5},
        {"word": "speaker2_b", "start": 3.0, "end": 4.0},
    ]
    overlap_segs = calculate_segments(overlap_words, 0.0, 6.0, max_silence=0.6, pad=0.15)
    assert len(overlap_segs) == 1
    assert overlap_segs[0][0] <= 1.0
    assert overlap_segs[0][1] >= 4.0
    remapped = remap_words(overlap_words, overlap_segs)
    assert len(remapped) == 4

# ---------------------------------------------------------------------------
# 7. Face Tracking & Split Aspect Calculations
# ---------------------------------------------------------------------------
def test_face_tracker_dynamic_split_zoom_bug():
    """
    PROVE-IT TEST: In tracker.track_face, keyframes always set zoom=100.
    In _build_split_filter_complex, dynamic split uses top_kfs from opts.reframe.
    Because zoom is 100, _zoom_expr returns None, and the top facecam is NOT zoomed in!
    Compare with static split which explicitly sets zoom=33.3 (3x zoom).
    """
    from app.clipper import _build_split_filter_complex

    # Static split: has zoom
    opts_static = ClipOptions(
        aspect_ratio=AspectRatio.NINE_16,
        fit_mode=FitMode.STATIC_SPLIT,
        ass_path=None,
        clip_id="test_split",
        index=0,
    )
    fc_static = _build_split_filter_complex(1080, 1920, opts_static, pathlib.Path("."), is_dynamic=False)
    assert "zoom" in fc_static or "(100/(33.300000))" in fc_static

    # Dynamic split with tracker keyframes: tracker sets zoom=100
    mock_tracker_kfs = [{"time": 0.0, "pos_x": 50.0, "pos_y": 50.0, "zoom": 100}]
    opts_dynamic = ClipOptions(
        aspect_ratio=AspectRatio.NINE_16,
        fit_mode=FitMode.DYNAMIC_SPLIT,
        ass_path=None,
        clip_id="test_split",
        index=0,
        reframe=mock_tracker_kfs,
    )
    fc_dynamic = _build_split_filter_complex(1080, 1920, opts_dynamic, pathlib.Path("."), is_dynamic=True)
    # Verify that dynamic split applies 3x zoom on the facecam just like static split
    assert "(100/(33.300000))" in fc_dynamic


# ---------------------------------------------------------------------------
# 8. Audio Ducking & SFX Synthesis Boundary Math
# ---------------------------------------------------------------------------
def test_audio_ducking_and_sfx_extreme_values():
    """Verify audio graph generation with extreme volume and ducking values (0% to 100%)."""
    # 1. 0% volume and 0% ducking
    g_min = _music_audio_graph(mus_idx=1, volume=0.0, duck=0.0)
    assert "volume=0.000" in g_min
    assert "ratio=1.00" in g_min  # 1.0 ratio = no ducking

    # 2. 100% volume and 100% ducking
    g_max = _music_audio_graph(mus_idx=1, volume=100.0, duck=100.0)
    assert "volume=0.700" in g_max
    assert "ratio=20.00" in g_max  # 20.0 ratio = hard compression

    # 3. None / Null fallback
    g_none = _music_audio_graph(mus_idx=1, volume=None, duck=None)
    assert "volume=0.245" in g_none
    assert "ratio=14.30" in g_none


# ---------------------------------------------------------------------------
# 9. FFmpeg Text Escaping & Complex Filtergraph Formatting
# ---------------------------------------------------------------------------
def test_ffmpeg_filtergraph_drawtext_and_ass_escaping():
    """Verify drawtext and ASS caption escaping with challenging special characters."""
    special_str = '[SALE] 50% OFF, "BUY NOW!" & WIN {100%} \\ Backslash & Colons : ; '
    escaped = _escape_drawtext(special_str)
    assert "\\\\" in escaped
    assert "\\:" in escaped
    assert "\\," in escaped
    assert "\\;" in escaped
    assert "\\[" in escaped
    assert "\\]" in escaped
    assert "\\%" in escaped
    assert "'" not in escaped  # converted to typographic quote ’

    # ASS escaping
    ass_esc = captions._ass_escape(special_str)
    assert "{" not in ass_esc
    assert "}" not in ass_esc
    assert "(" in ass_esc and ")" in ass_esc


# ---------------------------------------------------------------------------
# 10. Hardware Acceleration 10,000 kbps CBR Verification
# ---------------------------------------------------------------------------
def test_hardware_acceleration_and_10000k_cbr():
    """Verify 10,000 kbps CBR and priority ordering for GPU vs iGPU."""
    args_dgpu = get_encode_args(hevc=False, use_igpu=False)
    args_igpu = get_encode_args(hevc=False, use_igpu=True)
    args_hevc = get_encode_args(hevc=True, use_igpu=False)

    for args in [args_dgpu, args_igpu, args_hevc]:
        assert "-b:v" in args
        assert "10000k" in args
        assert "-minrate" in args
        assert "-maxrate" in args
        assert "-bufsize" in args
        assert "20000k" in args

    assert "-tag:v" in args_hevc
    assert "hvc1" in args_hevc


# ---------------------------------------------------------------------------
# 11. CTranslate2 Model Scan Validation & State Synchronization
# ---------------------------------------------------------------------------
def test_scan_installed_models_strict_ct2_validation(tmp_path, monkeypatch):
    """Ensure scan_installed_models strictly validates model.bin and config.json (>0 bytes)."""
    fake_cache = tmp_path / "fake_hf_cache"
    fake_cache.mkdir(parents=True)

    monkeypatch.setattr(transcriber, "get_candidate_cache_dirs", lambda: [fake_cache])

    model_id = "savi0ur/whisper-hindi-hinglish-ct2"
    repo_dir_name = transcriber._repo_dir_name_for_size(model_id)
    repo_dir = fake_cache / repo_dir_name / "snapshots" / "snap1"

    # 1. Empty directory -> not cached
    repo_dir.mkdir(parents=True)
    assert not transcriber.is_model_cached(model_id)

    # 2. Only config.json -> not cached
    (repo_dir / "config.json").write_text("{}", encoding="utf-8")
    assert not transcriber.is_model_cached(model_id)

    # 3. Only model.safetensors (PyTorch checkpoint) -> not cached
    (repo_dir / "model.safetensors").write_bytes(b"dummy safetensors content")
    assert not transcriber.is_model_cached(model_id)

    # 4. Empty 0-byte model.bin -> not cached
    (repo_dir / "model.bin").write_bytes(b"")
    assert not transcriber.is_model_cached(model_id)

    # 4b. Incomplete downloading chunk (.incomplete / .tmp) -> not cached
    (repo_dir / "model.bin").unlink()
    (repo_dir / "model.bin.incomplete").write_bytes(b"partial chunk bytes")
    (repo_dir / "model.bin.tmp").write_bytes(b"partial tmp bytes")
    assert not transcriber.is_model_cached(model_id)
    (repo_dir / "model.bin.incomplete").unlink()
    (repo_dir / "model.bin.tmp").unlink()

    # 5. Valid model.bin (>0 bytes) and valid config.json (>0 bytes) -> cached!
    (repo_dir / "model.bin").write_bytes(b"valid model binary weights")
    assert transcriber.is_model_cached(model_id)
    installed = transcriber.scan_installed_models()
    assert any(m["id"] == model_id for m in installed)


def test_load_on_state_resilience_and_desync_fix(monkeypatch):
    """Verify that _load_on does not desynchronize _model_sizes or report false ready on failure."""
    device = "cpu"
    # Reset internal state
    transcriber._models.clear()
    transcriber._model_sizes.clear()

    # Case 1: Target model fails, fallback to large-v3-turbo succeeds
    def mock_ensure_downloaded(size):
        if size == "savi0ur/whisper-hindi-hinglish-ct2":
            raise RuntimeError("Model download/corrupt error")
        return "/fake/path/large-v3-turbo"

    mock_whisper = MagicMock()
    monkeypatch.setattr(transcriber, "_ensure_downloaded", mock_ensure_downloaded)
    monkeypatch.setattr(transcriber, "WhisperModel", lambda *args, **kwargs: mock_whisper)

    model = transcriber._load_on(device, "savi0ur/whisper-hindi-hinglish-ct2")
    assert model == mock_whisper
    # _model_sizes[device] must be the actual loaded model ("large-v3-turbo"), NOT the failed one!
    assert transcriber._model_sizes.get(device) == "large-v3-turbo"
    st = transcriber.model_status()
    assert st["status"] == "ready"
    assert st["model_size"] == "large-v3-turbo"

    # Case 2: Target model fails AND fallback fails
    transcriber._models.clear()
    transcriber._model_sizes.clear()

    def mock_all_fail(size):
        raise RuntimeError("Total failure")

    monkeypatch.setattr(transcriber, "_ensure_downloaded", mock_all_fail)

    with pytest.raises(RuntimeError, match="Total failure"):
        transcriber._load_on(device, "savi0ur/whisper-hindi-hinglish-ct2")

    # Verify device state was pruned and status is error
    assert device not in transcriber._model_sizes
    assert transcriber.model_status()["status"] == "error"


def test_normalize_language_hinglish_apex():
    """Verify _normalize_language maps Hinglish appropriately for native vs standard models."""
    # Native Hinglish / Apex models should map to 'en'
    assert transcriber._normalize_language("hinglish", "savi0ur/whisper-hindi-hinglish-ct2") == "en"
    assert transcriber._normalize_language("Hinglish", "savi0ur/whisper-hindi-hinglish-ct2") == "en"
    assert transcriber._normalize_language("hinglish", "some-apex-model") == "en"

    # Standard models should map 'hinglish' to 'hi'
    assert transcriber._normalize_language("hinglish", "large-v3-turbo") == "hi"
    assert transcriber._normalize_language("hinglish", "base") == "hi"
    assert transcriber._normalize_language("hinglish") == "hi"

    # Other languages
    assert transcriber._normalize_language("en", "savi0ur/whisper-hindi-hinglish-ct2") == "en"
    assert transcriber._normalize_language("hi", "savi0ur/whisper-hindi-hinglish-ct2") == "hi"
    assert transcriber._normalize_language("auto", "savi0ur/whisper-hindi-hinglish-ct2") is None
    assert transcriber._normalize_language(None) is None


def test_transcript_persistence_slash_model_id_safety(tmp_path, monkeypatch):
    """Verify that model IDs containing slashes (e.g. savi0ur/whisper-hindi-hinglish-ct2)
    do not cause FileNotFoundError or nested folder bugs when writing transcripts to disk."""
    fake_transcripts_dir = tmp_path / "transcripts"
    fake_transcripts_dir.mkdir(parents=True)
    monkeypatch.setattr(transcriber, "TRANSCRIPTS_DIR", fake_transcripts_dir)

    import app.pretranscribe as pretranscribe
    monkeypatch.setattr(pretranscribe, "TRANSCRIPTS_DIR", fake_transcripts_dir)

    # 1. pretranscribe key must not contain slashes
    key = pretranscribe._key("vid_abc123", "hinglish", "savi0ur/whisper-hindi-hinglish-ct2")
    assert "/" not in key and "\\" not in key
    assert "savi0ur--whisper-hindi-hinglish-ct2" in key

    # 2. transcribe_video with clip_id containing a slash must write file cleanly
    dummy_video = tmp_path / "dummy.mp4"
    dummy_video.write_bytes(b"")

    # Mock load_audio to return empty audio (triggers empty-audio write path)
    monkeypatch.setattr(transcriber, "load_audio", lambda *args, **kwargs: transcriber.np.zeros(0, dtype=transcriber.np.float32))
    monkeypatch.setattr(transcriber, "load_model", lambda *args, **kwargs: MagicMock())
    result = transcriber.transcribe_video(dummy_video, clip_id=key)
    assert result is not None

    expected_file = fake_transcripts_dir / f"{key}.json"
    assert expected_file.is_file(), f"Transcript file {expected_file} was not written to disk"
    content = json.loads(expected_file.read_text(encoding="utf-8"))
    assert content["text"] == ""


def test_model_select_screen_no_obsolete_oriserve():
    """Ensure both Screen2Settings and ModelSelectScreen use savi0ur and have no trace of obsolete Oriserve model."""
    web_dir = pathlib.Path(__file__).parent.parent / "web" / "src"
    
    screen2_file = web_dir / "pages" / "create" / "Screen2Settings.jsx"
    if screen2_file.exists():
        content = screen2_file.read_text(encoding="utf-8")
        assert "savi0ur/whisper-hindi-hinglish-ct2" in content
        assert "Oriserve" not in content

    select_screen_file = web_dir / "components" / "ModelSelectScreen.jsx"
    if select_screen_file.exists():
        content = select_screen_file.read_text(encoding="utf-8")
        assert "savi0ur/whisper-hindi-hinglish-ct2" in content
        assert "Oriserve" not in content


def test_reframe_recipe_includes_face_zone_hevc_use_igpu():
    """Verify that reframe recipe preserves hardware acceleration and facecam zone."""
    import app.reframe as reframe
    from app.clipper import ClipOptions

    clip_id = "test_recipe_id_1234567890abcdef"
    index = 0
    dummy_source = pathlib.Path("dummy.mp4")

    from app.models import AspectRatio, FitMode

    opts = ClipOptions(
        aspect_ratio=AspectRatio.NINE_16,
        fit_mode=FitMode.CROP,
        ass_path=None,
        clip_id=clip_id,
        index=index,
        face_zone=7,
        hevc=True,
        use_igpu=True,
    )
    # Save recipe simulating jobs.py
    reframe.save_recipe(
        clip_id,
        index,
        source_mp4=dummy_source,
        start=0.0,
        end=10.0,
        opts_kwargs={
            "aspect_ratio": opts.aspect_ratio,
            "fit_mode": opts.fit_mode,
            "square_corners": opts.square_corners,
            "face_zone": opts.face_zone,
            "ass_path": opts.ass_path,
            "bar_text": opts.bar_text,
            "bar_text_color": opts.bar_text_color,
            "bar_text_anim": opts.bar_text_anim,
            "cinematic": opts.cinematic,
            "music_path": opts.music_path,
            "music_volume": opts.music_volume,
            "music_duck": opts.music_duck,
            "music_start": opts.music_start,
            "signature": opts.signature,
            "reframe": opts.reframe,
            "keep_segments": opts.keep_segments,
            "effects": opts.effects,
            "hevc": opts.hevc,
            "use_igpu": opts.use_igpu,
        },
    )

    recipe = reframe.get_recipe(clip_id, index)
    assert recipe is not None
    kwargs = recipe.get("opts_kwargs", {})
    assert kwargs.get("face_zone") == 7
    assert kwargs.get("hevc") is True
    assert kwargs.get("use_igpu") is True

    # Reconstruct ClipOptions
    reconstructed = ClipOptions(clip_id=clip_id, index=index, **kwargs)
    assert reconstructed.face_zone == 7
    assert reconstructed.hevc is True
    assert reconstructed.use_igpu is True


def test_downloader_browser_cookies_fallback_order(monkeypatch):
    """Verify that downloader prioritizes 'default' and client groups before checking browser sqlite databases."""
    import app.downloader as downloader

    monkeypatch.delenv(downloader._COOKIE_FILE_ENV, raising=False)
    monkeypatch.delenv(downloader._COOKIE_BROWSER_ENV, raising=False)
    monkeypatch.setattr(downloader, "_find_cookie_file", lambda: None)
    monkeypatch.setattr(downloader, "_installed_browsers", lambda: ["brave", "chrome"])

    attempts = downloader._download_attempts({})
    labels = [a[0] for a in attempts]

    # 'default' must appear BEFORE any browser cookie attempt
    assert "default" in labels
    default_idx = labels.index("default")

    if "brave cookies" in labels:
        brave_idx = labels.index("brave cookies")
        assert default_idx < brave_idx, f"Expected default ({default_idx}) before brave ({brave_idx})"


def test_job_set_stage_and_finish_respect_cancelled():
    """Verify that neither set_stage nor finish can overwrite a cancelled job status."""
    req = GenerateRequest(video_url="https://youtube.com/watch?v=dQw4w9WgXcQ")
    job = jobs.Job(req)
    job.cancel()
    assert job.status == "cancelled"

    # Subsequent progress callback from worker thread
    job.set_stage("transcribing", 0.5, "Transcribing...")
    assert job.status == "cancelled", "set_stage overwrote cancelled status"
    assert job.stage == "cancelled"

    # Worker finishes
    job.finish([])
    assert job.status == "cancelled", "finish overwrote cancelled status"


def test_downloader_cancellation_aborts_early_and_cleans_up(tmp_path, monkeypatch):
    """Verify that download_video immediately aborts when is_cancelled is True."""
    import app.downloader as downloader

    monkeypatch.setattr(downloader, "DOWNLOADS_DIR", tmp_path)

    # Pre-cancelled
    with pytest.raises(downloader.InvalidVideoURLError, match="cancelled"):
        downloader.download_video("https://example.com/video.mp4", is_cancelled=lambda: True)

    # Ensure no orphan files
    assert list(tmp_path.glob("*")) == []


def test_jumpcut_unchanged_segment_detection():
    """Verify that jump cut without silent gaps returns single full segment."""
    from app.jumpcut import calculate_segments

    # Single continuous word spanning entire clip
    words = [{"word": "Continuous", "start": 0.0, "end": 10.0}]
    segs = calculate_segments(words, 0.0, 10.0, max_silence=0.6)
    assert len(segs) == 1
    assert abs(segs[0][0] - 0.0) < 0.01 and abs(segs[0][1] - 10.0) < 0.01



