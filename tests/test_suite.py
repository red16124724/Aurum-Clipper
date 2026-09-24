import os
import sys
import subprocess
import pytest
from pathlib import Path

sys.path.insert(0, os.path.abspath("."))

from app.jumpcut import calculate_segments, remap_words
from app.models import AspectRatio, FitMode, Device, GenerateRequest, SquareCorners
from app.clipper import ClipOptions, target_size, get_encode_args, _piecewise_linear, _pos_frac_expr, _zoom_expr
from app.effects import COLOR_GRADES, cinematic_stages, _gradient_bands
import app.pretranscribe as pretranscribe
import app.transcriber as transcriber
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# -------------------------------------------------------------------------- #
# JumpCut Unit Tests
# -------------------------------------------------------------------------- #
def test_jumpcut_empty_words():
    segs = calculate_segments([], 0.0, 10.0)
    assert segs == [(0.0, 10.0)]
    assert remap_words([], segs) == []

def test_jumpcut_continuous_speech():
    words = [
        {"word": "hello", "start": 0.5, "end": 1.0},
        {"word": "world", "start": 1.2, "end": 1.8},
        {"word": "this", "start": 2.0, "end": 2.5},
    ]
    segs = calculate_segments(words, 0.0, 3.0, max_silence=0.6, pad=0.15)
    # No gap exceeds 0.6s with pad=0.15
    assert len(segs) == 1
    assert segs[0][0] <= 0.5
    assert segs[0][1] >= 2.5

def test_jumpcut_with_silence_gap():
    words = [
        {"word": "hello", "start": 0.5, "end": 1.0},
        {"word": "there", "start": 1.1, "end": 1.5},
        # Big silence from 1.5s to 4.5s (3 seconds gap)
        {"word": "after", "start": 4.5, "end": 5.0},
        {"word": "silence", "start": 5.2, "end": 5.8},
    ]
    segs = calculate_segments(words, 0.0, 6.0, max_silence=0.6, pad=0.15)
    assert len(segs) == 2
    # First segment ends around 1.65, second starts around 4.35
    assert segs[0][1] < segs[1][0]
    
    # Test remapping
    remapped = remap_words(words, segs)
    assert len(remapped) == 4
    # The gap should be collapsed
    gap_removed = (segs[1][0] - segs[0][1])
    assert pytest.approx(remapped[2]["start"], 0.01) == words[2]["start"] - gap_removed

def test_jumpcut_remap_keyframes():
    from app.jumpcut import remap_keyframes
    segs = [(0.0, 1.5), (4.5, 6.0)] # 3.0s gap from 1.5 to 4.5
    kfs = [
        {"time": 0.5, "crop_x": 0.5, "crop_y": 0.5},
        {"time": 1.0, "crop_x": 0.6, "crop_y": 0.5},
        {"time": 5.0, "crop_x": 0.7, "crop_y": 0.5}, # should shift by -3.0s -> 2.0s
    ]
    remapped = remap_keyframes(kfs, segs)
    assert len(remapped) == 3
    assert remapped[0]["time"] == 0.5
    assert remapped[1]["time"] == 1.0
    assert pytest.approx(remapped[2]["time"], 0.01) == 2.0

# -------------------------------------------------------------------------- #
# Models & Schemas Validation Tests
# -------------------------------------------------------------------------- #
def test_models_defaults():
    req = GenerateRequest(video_url="https://youtube.com/watch?v=12345")
    assert req.model_size == "large-v3-turbo"
    assert req.device == Device.AUTO
    assert req.fit_mode == FitMode.CROP
    assert req.aspect_ratio == AspectRatio.NINE_16
    assert req.hevc is False
    assert req.use_igpu is False

def test_models_validation_source_required():
    with pytest.raises(ValueError):
        GenerateRequest()

def test_models_upload_source():
    req = GenerateRequest(upload_id="abc123upload")
    assert req.upload_id == "abc123upload"

# -------------------------------------------------------------------------- #
# Clipper & Hardware Acceleration Tests
# -------------------------------------------------------------------------- #
def test_target_sizes():
    w, h = target_size(AspectRatio.NINE_16, FitMode.CROP)
    assert (w, h) == (1080, 1920)
    w, h = target_size(AspectRatio.SIXTEEN_9, FitMode.CROP)
    assert (w, h) == (1920, 1080)
    w, h = target_size(AspectRatio.NINE_16, FitMode.SQUARE)
    assert (w, h) == (1080, 1920)

def test_get_encode_args_fallback():
    args_h264 = get_encode_args(hevc=False, use_igpu=False)
    assert "-c:a" in args_h264
    assert "aac" in args_h264
    assert "-b:v" in args_h264
    assert "10000k" in args_h264
    assert "-minrate" in args_h264
    assert "-maxrate" in args_h264
    assert "-bufsize" in args_h264
    
    args_hevc = get_encode_args(hevc=True, use_igpu=False)
    assert "hvc1" in args_hevc
    assert "10000k" in args_hevc

def test_selector_emotion_and_action_scoring():
    from app.selector import _score_window
    
    # High action window with explosion, gunshot, screaming
    action_text = "BOOM! Look out, they are shooting! Run for the bomb explosion now!"
    action_score = _score_window(action_text, 40.0)
    
    # Comedic viral window with joke, laughter
    comedy_text = "Bro that was hilarious! He literally did the funniest prank ever hahaha!"
    comedy_score = _score_window(comedy_text, 40.0)
    
    # Sad crying window
    sad_text = "I couldn't stop crying, the grief and heartbreak of losing you hurts so much."
    sad_score = _score_window(sad_text, 40.0)
    
    # Romantic passion window
    romantic_text = "I love you with all my heart, I want to marry you and be together forever."
    romantic_score = _score_window(romantic_text, 40.0)
    
    # Dry, monotone conversation with no emotion
    dry_text = "As I was saying, moving on to the next slide, the spreadsheet table column has five items."
    dry_score = _score_window(dry_text, 40.0)
    
    assert action_score > 10.0
    assert comedy_score > 10.0
    assert sad_score > 10.0
    assert romantic_score > 10.0
    assert dry_score < 4.0
    assert action_score > dry_score * 2.5
    assert comedy_score > dry_score * 2.5

def test_piecewise_linear_expression():
    pts = [(0.0, 50.0), (2.0, 80.0), (4.0, 30.0)]
    expr = _piecewise_linear(pts)
    assert "if(lt(t" in expr
    assert "50.0" in expr

# -------------------------------------------------------------------------- #
# Effects & Cinematic Filter Tests
# -------------------------------------------------------------------------- #
def test_cinematic_stages_disabled():
    stages, label = cinematic_stages(None, "in_v", 1080, 1920)
    assert stages == []
    assert label == "in_v"

def test_cinematic_stages_all_enabled():
    cfg = {
        "color_grade": "vibrant",
        "glow": True,
        "glow_strength": 60,
        "grain": True,
        "grain_strength": 30,
        "vignette": True,
        "vignette_strength": 50,
        "bottom_gradient": True,
        "top_gradient": True,
        "letterbox": True,
        "sharpen": True,
        "chroma_shift": True,
    }
    stages, label = cinematic_stages(cfg, "in_v", 1080, 1920)
    assert len(stages) >= 7
    assert label != "in_v"

# -------------------------------------------------------------------------- #
# Pretranscribe Cache Tests
# -------------------------------------------------------------------------- #
def test_pretranscribe_cache_keys():
    k1 = pretranscribe._key("vid123", "en", "large-v3-turbo")
    k2 = pretranscribe._key("vid123", "en", "medium")
    k3 = pretranscribe._key("vid123", "auto", "large-v3-turbo")
    assert k1 != k2
    assert k1 != k3
    assert k2 != k3

# -------------------------------------------------------------------------- #
# FastAPI Endpoint Tests
# -------------------------------------------------------------------------- #
def test_health_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"

def test_devices_endpoint():
    res = client.get("/api/devices")
    assert res.status_code == 200
    data = res.json()
    assert "devices" in data
    assert "default" in data
    assert "model_size" in data

def test_caption_styles_endpoint():
    res = client.get("/api/caption-styles")
    assert res.status_code == 200
    presets = res.json()
    assert isinstance(presets, list)
    assert len(presets) > 0

def test_fonts_endpoint():
    res = client.get("/api/fonts")
    assert res.status_code == 200
    fonts = res.json()
    assert "bundled" in fonts

def test_music_endpoint():
    res = client.get("/api/music")
    assert res.status_code == 200
    assert "tracks" in res.json()

def test_models_info_endpoint():
    res = client.get("/api/models-info")
    assert res.status_code == 200
    data = res.json()
    assert "models" in data
    assert "installed_models" in data
    assert len(data["models"]) == 6
    ids = [m["id"] for m in data["models"]]
    assert "large-v3-turbo" in ids
    assert "large-v3" in ids
    assert "medium" in ids
    assert "small" in ids
    assert "base" in ids
    # Verify system requirement fields
    for m in data["models"]:
        assert "min_ram" in m
        assert "min_vram" in m
        assert "size_label" in m
        assert "description" in m
        assert "is_cached" in m

def test_transcribe_audio_less_video(tmp_path):
    # Generate 1-second video with no audio stream
    video_file = tmp_path / "silent_no_audio.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x240:d=1",
        "-c:v", "libx264", str(video_file)
    ], check=True, capture_output=True)
    
    # transcribe_video should handle audio-less videos cleanly without tuple index error
    res = transcriber.transcribe_video(video_file, clip_id="test_silent_no_audio", device="cpu", model_size="base")
    assert "words" in res
    assert "segments" in res
    assert res["words"] == []
    assert res["segments"] == []

def test_ass_subtitles_escaping_and_rtl(tmp_path):
    from app.captions import build_ass
    words = [
        {"start": 0.0, "end": 0.5, "word": "Hello, world!"},
        {"start": 0.5, "end": 1.0, "word": "Testing {special} \\characters & 100% audio."},
        {"start": 1.0, "end": 2.0, "word": "یہ اردو جملہ ہے"},  # Urdu RTL test
    ]
    ass_file = tmp_path / "test_ass.ass"
    ass_path = build_ass(words, style_preset="hormozi", video_w=1080, video_h=1920, out_path=ass_file, clip_start=0.0, overrides={"font_family": "Roboto"}, fit_mode="crop")
    assert ass_path is not None
    assert os.path.exists(ass_path)
    with open(ass_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "[Script Info]" in content
    assert "[V4+ Styles]" in content
    assert "[Events]" in content
    assert "Dialogue:" in content

def test_sfx_audio_synthesis():
    from app.sfx_generator import generate_sfx
    generate_sfx()
    sfx_dir = Path(__file__).parent.parent / "assets" / "sfx"
    for name in ["ding.mp3", "boom.mp3", "whoosh.mp3"]:
        target = sfx_dir / name
        assert target.exists()
        assert target.stat().st_size > 0


def test_local_sfx_and_template_analysis():
    from app.effects import analyze_effects_with_gemini, analyze_template_with_gemini
    words = [
        {"word": "Why", "start": 0.5, "end": 0.8},
        {"word": "did", "start": 0.8, "end": 1.0},
        {"word": "this", "start": 1.0, "end": 1.2},
        {"word": "happen?", "start": 1.2, "end": 1.6},
        {"word": "It", "start": 2.0, "end": 2.2},
        {"word": "was", "start": 2.2, "end": 2.4},
        {"word": "the", "start": 2.4, "end": 2.6},
        {"word": "biggest", "start": 2.6, "end": 3.0},
        {"word": "mistake!", "start": 3.0, "end": 3.4},
        {"word": "Suddenly", "start": 5.0, "end": 5.4},
        {"word": "everything", "start": 5.4, "end": 5.8},
        {"word": "changed.", "start": 5.8, "end": 6.2},
    ]
    # Ensure offline heuristic produces sound effects
    fx = analyze_effects_with_gemini(words, clip_start=0.0)
    assert len(fx) > 0
    effect_names = [e["effect"] for e in fx]
    assert any(e in effect_names for e in ["sfx_ding", "sfx_boom", "sfx_whoosh"])
    for e in fx:
        assert "time" in e
        assert "effect" in e

    # Test template analysis
    tmpl = analyze_template_with_gemini(words)
    assert tmpl in ["sigma_grindset", "storytime_chill", "podcast_classic", "hype_beast"]


def test_split_view_filter_generation(tmp_path):
    from app.clipper import _build_split_filter_complex, ClipOptions
    from app.models import AspectRatio, FitMode
    
    opts = ClipOptions(
        aspect_ratio=AspectRatio.NINE_16,
        fit_mode=FitMode.DYNAMIC_SPLIT,
        ass_path=tmp_path / "dummy.ass",
        clip_id="test_split",
        index=0,
        reframe=[{"time": 0.0, "pos_x": 30.0, "pos_y": 40.0, "zoom": 100}],
    )
    fc = _build_split_filter_complex(1080, 1920, opts, tmp_path, is_dynamic=True)
    assert "vstack" in fc
    assert "scale=1080:960" in fc
    assert "crop=1080:960" in fc

