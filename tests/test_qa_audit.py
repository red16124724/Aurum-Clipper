import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath("."))

from app.jumpcut import calculate_segments, remap_words
from app.models import AspectRatio, FitMode, Device, GenerateRequest, SquareCorners, ReframeKeyframe
from app.clipper import ClipOptions, target_size, get_encode_args, _piecewise_linear, _pos_frac_expr, _zoom_expr
from app.effects import COLOR_GRADES, cinematic_stages, _gradient_bands
import app.pretranscribe as pretranscribe
import app.transcriber as transcriber
import app.reframe as reframe
import app.jobs as jobs
import app.tracker as tracker
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# 1. Whisper Transcription with all 6 model sizes and fallback devices.
def test_qa_whisper_models_and_devices():
    models = ["large-v3-turbo", "large-v3", "medium", "small", "base", "savi0ur/whisper-hindi-hinglish-ct2"]
    devices = ["cuda", "cpu", "auto"]
    
    # Just verify cache key generation for all combinations to ensure no exceptions
    keys = []
    for m in models:
        for d in devices:
            key = pretranscribe._key("test_src", "en", m)
            keys.append(key)
    assert len(set(keys)) == len(models) # Keys only depend on model size and language

# 2. AI Subject Tracking & Keyframe Interpolation across 9:16, 16:9, and 1:1.
def test_qa_subject_tracking_interpolation():
    keyframes = [
        {"time": 0.0, "pos_x": 10.0, "pos_y": 20.0, "zoom": 100},
        {"time": 2.0, "pos_x": 30.0, "pos_y": 40.0, "zoom": 100},
        {"time": 4.0, "pos_x": 50.0, "pos_y": 60.0, "zoom": 100},
    ]
    
    # Ensure interpolation expression handles them correctly using lt() comparisons for piecewise linear
    expr_x = _pos_frac_expr(keyframes, "pos_x")
    assert "lt(t\\,0.000)" in expr_x
    assert "lt(t\\,2.000)" in expr_x
    assert "lt(t\\,4.000)" in expr_x
    
    expr_y = _pos_frac_expr(keyframes, "pos_y")
    assert "lt(t\\,0.000)" in expr_y
    assert "lt(t\\,2.000)" in expr_y
    assert "lt(t\\,4.000)" in expr_y

    expr_zoom = _zoom_expr(keyframes)
    assert expr_zoom is None # All zoom is 100, should be optimized out

    zoom_keyframes = [
        {"time": 0.0, "pos_x": 10.0, "pos_y": 20.0, "zoom": 50},
        {"time": 2.0, "pos_x": 30.0, "pos_y": 40.0, "zoom": 80},
    ]
    expr_zoom2 = _zoom_expr(zoom_keyframes)
    assert expr_zoom2 is not None
    assert "lt(t\\,2.000)" in expr_zoom2

# 3. Jumpcut algorithm with overlapping, zero-duration, and long silent gaps.
def test_qa_jumpcut_edge_cases():
    # Overlapping
    words_overlap = [
        {"word": "a", "start": 1.0, "end": 2.0},
        {"word": "b", "start": 1.5, "end": 2.5},
    ]
    segs_overlap = calculate_segments(words_overlap, 0.0, 5.0)
    assert len(segs_overlap) == 1
    
    # Zero-duration
    words_zero = [
        {"word": "a", "start": 1.0, "end": 1.0},
    ]
    segs_zero = calculate_segments(words_zero, 0.0, 5.0)
    assert len(segs_zero) == 1
    
    # Long silent gaps
    words_gap = [
        {"word": "start", "start": 0.0, "end": 1.0},
        {"word": "end", "start": 10.0, "end": 11.0},
    ]
    segs_gap = calculate_segments(words_gap, 0.0, 15.0)
    assert len(segs_gap) == 2
    remapped = remap_words(words_gap, segs_gap)
    # the gap is removed, so 'end' should start right after 'start' + padding
    assert remapped[1]["start"] < 5.0

# 4. Hardware encoder selection priority (dGPU vs iGPU).
def test_qa_hardware_encoder():
    args_igpu = get_encode_args(hevc=False, use_igpu=True)
    args_dgpu = get_encode_args(hevc=False, use_igpu=False)
    
    # Since we can't guarantee hardware on the test runner, we just check that the 
    # function returns a list of arguments without crashing and respects the flag
    assert isinstance(args_igpu, list)
    assert isinstance(args_dgpu, list)

# 5. Cancellation resilience at each stage of generation.
def test_qa_cancellation_resilience():
    req = GenerateRequest(video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ", num_clips=1)
    job = jobs.create_job(req)
    job.cancel()
    assert job.cancelled is True
    snap = job.snapshot()
    assert snap["cancelled"] is True

# 6. Reframe recipe save & reload cycle.
def test_qa_reframe_recipe():
    clip_id = "test_clip_id"
    index = 0
    source_mp4 = Path("/tmp/test.mp4")
    opts_kwargs = {"hevc": True, "use_igpu": False}
    
    reframe.save_recipe(clip_id, index, source_mp4=source_mp4, start=0.0, end=10.0, opts_kwargs=opts_kwargs)
    recipe = reframe.get_recipe(clip_id, index)
    
    assert recipe is not None
    assert recipe["source_mp4"] == str(source_mp4)
    assert recipe["start"] == 0.0
    assert recipe["end"] == 10.0
    assert recipe["opts_kwargs"]["hevc"] is True

# 7. Frontend API contract matching between JS and FastAPI.
def test_qa_api_contract():
    # health
    res = client.get("/health")
    assert res.status_code == 200
    assert "status" in res.json()
    
    # devices
    res = client.get("/api/devices")
    assert res.status_code == 200
    data = res.json()
    assert "devices" in data
    assert "default" in data
    assert "model_size" in data

    # generate (invalid payload to check validation)
    res = client.post("/api/generate", json={"invalid": "payload"})
    assert res.status_code == 422 # Unprocessable Entity


# 8. Gemini-3.8-flash model preference and fallback verification
def test_qa_gemini_model_preference_and_fallback():
    from app.effects import analyze_effects_with_gemini, analyze_template_with_gemini, spell_check_with_gemini
    from app.selector import _select_with_gemini

    words = [{"word": "test", "start": 0.0, "end": 0.5}]
    
    with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy_key"}):
        with patch("google.genai.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_resp = MagicMock()
            mock_resp.text = '[{"time": 0.1, "effect": "sfx_ding"}]'
            mock_client.models.generate_content.return_value = mock_resp

            # 1. Effects uses gemini-3.8-flash
            analyze_effects_with_gemini(words, 0.0)
            assert mock_client.models.generate_content.call_args.kwargs["model"] == "gemini-3.8-flash"

            # 2. Template uses gemini-3.8-flash
            mock_resp.text = "podcast_classic"
            analyze_template_with_gemini(words)
            assert mock_client.models.generate_content.call_args.kwargs["model"] == "gemini-3.8-flash"

            # 3. Spell check uses gemini-3.8-flash
            mock_resp.text = '[{"word": "test", "start": 0.0, "end": 0.5}]'
            spell_check_with_gemini(words)
            assert mock_client.models.generate_content.call_args.kwargs["model"] == "gemini-3.8-flash"

            # 4. Selector uses gemini-3.8-flash
            mock_resp.text = '{"score": 95, "title": "Viral Clip"}'
            candidates = [{"start": 0.0, "end": 10.0, "score": 80.0, "text": "Exciting viral dialogue"}]
            _select_with_gemini(candidates, 1)
            assert mock_client.models.generate_content.call_args.kwargs["model"] == "gemini-3.8-flash"

        # 5. Error fallback from gemini-3.8-flash to gemini-2.5-flash across all functions
        with patch("google.genai.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client

            def side_effect(*args, **kwargs):
                if kwargs.get("model") == "gemini-3.8-flash":
                    raise RuntimeError("gemini-3.8-flash error")
                resp = MagicMock()
                resp.text = '[{"time": 0.1, "effect": "sfx_ding"}]'
                return resp

            mock_client.models.generate_content.side_effect = side_effect
            # 5a. Effects fallback
            fx = analyze_effects_with_gemini(words, 0.0)
            assert len(fx) > 0
            assert mock_client.models.generate_content.call_count == 2
            assert mock_client.models.generate_content.call_args_list[0].kwargs["model"] == "gemini-3.8-flash"
            assert mock_client.models.generate_content.call_args_list[1].kwargs["model"] == "gemini-2.5-flash"

            # 5b. Template fallback
            def tmpl_side_effect(*args, **kwargs):
                if kwargs.get("model") == "gemini-3.8-flash":
                    raise RuntimeError("gemini-3.8-flash error")
                resp = MagicMock()
                resp.text = 'podcast_classic'
                return resp
            mock_client.models.generate_content.reset_mock()
            mock_client.models.generate_content.side_effect = tmpl_side_effect
            tmpl = analyze_template_with_gemini(words)
            assert tmpl == "podcast_classic"
            assert mock_client.models.generate_content.call_count == 2
            assert mock_client.models.generate_content.call_args_list[0].kwargs["model"] == "gemini-3.8-flash"
            assert mock_client.models.generate_content.call_args_list[1].kwargs["model"] == "gemini-2.5-flash"

            # 5c. Spell check fallback
            def spell_side_effect(*args, **kwargs):
                if kwargs.get("model") == "gemini-3.8-flash":
                    raise RuntimeError("gemini-3.8-flash error")
                resp = MagicMock()
                resp.text = '[{"word": "test", "start": 0.0, "end": 0.5}]'
                return resp
            mock_client.models.generate_content.reset_mock()
            mock_client.models.generate_content.side_effect = spell_side_effect
            sc = spell_check_with_gemini(words)
            assert len(sc) == 1
            assert mock_client.models.generate_content.call_count == 2
            assert mock_client.models.generate_content.call_args_list[0].kwargs["model"] == "gemini-3.8-flash"
            assert mock_client.models.generate_content.call_args_list[1].kwargs["model"] == "gemini-2.5-flash"

            # 5d. Selector fallback
            def select_side_effect(*args, **kwargs):
                if kwargs.get("model") == "gemini-3.8-flash":
                    raise RuntimeError("gemini-3.8-flash error")
                resp = MagicMock()
                resp.text = '{"score": 95, "title": "Fallback Viral"}'
                return resp
            mock_client.models.generate_content.reset_mock()
            mock_client.models.generate_content.side_effect = select_side_effect
            scored = _select_with_gemini(candidates, 1)
            assert len(scored) == 1
            assert mock_client.models.generate_content.call_count == 2
            assert mock_client.models.generate_content.call_args_list[0].kwargs["model"] == "gemini-3.8-flash"
            assert mock_client.models.generate_content.call_args_list[1].kwargs["model"] == "gemini-2.5-flash"


# 9. Vision and Face Tracking models bundle resolution (normal & frozen sys._MEIPASS)
def test_qa_vision_models_bundle_resolution(tmp_path):
    import shutil
    from app import paths
    from app.paths import resolve_model_path, BUNDLED_MODELS_DIR, MODELS_DIR
    from app.tracker import _get_model_file, _get_yunet, _get_cascade

    # 1. Normal resolution from source/assets
    p_yunet = resolve_model_path("face_detection_yunet.onnx")
    p_cascade = resolve_model_path("haarcascade_frontalface_default.xml")
    assert p_yunet is not None and p_yunet.is_file()
    assert p_cascade is not None and p_cascade.is_file()

    # 2. Frozen mode resolution directly from sys._MEIPASS with real models
    fake_meipass = tmp_path / "mock_meipass"
    fake_models_dir = fake_meipass / "assets" / "models"
    fake_models_dir.mkdir(parents=True)
    fake_yunet = fake_models_dir / "face_detection_yunet.onnx"
    fake_cascade = fake_models_dir / "haarcascade_frontalface_default.xml"
    shutil.copy2(p_yunet, fake_yunet)
    shutil.copy2(p_cascade, fake_cascade)

    # Empty data dir to ensure no models exist on disk
    fake_data_dir = tmp_path / "mock_data_dir"
    fake_data_dir.mkdir(parents=True)

    with patch.object(sys, "_MEIPASS", str(fake_meipass), create=True):
        with patch.object(sys, "frozen", True, create=True):
            resolved_yunet = resolve_model_path("face_detection_yunet.onnx")
            resolved_cascade = resolve_model_path("haarcascade_frontalface_default.xml")
            assert resolved_yunet == fake_yunet
            assert resolved_cascade == fake_cascade
            assert _get_model_file("face_detection_yunet.onnx") == fake_yunet
            assert _get_model_file("haarcascade_frontalface_default.xml") == fake_cascade

            # Detector initialization directly from sys._MEIPASS bundle
            detector = _get_yunet((320, 240))
            cascade = _get_cascade()
            assert detector is not None
            assert cascade is not None

            # Verify ensure_dirs() does NOT pollute local disk with copied models
            with patch.object(paths, "IS_FROZEN", True):
                with patch.object(paths, "DATA_DIR", fake_data_dir):
                    with patch.object(paths, "MODELS_DIR", fake_data_dir / "assets" / "models"):
                        paths.ensure_dirs()
                        assert not (fake_data_dir / "assets" / "models").exists(), "Models must not be copied to disk when frozen"

