"""AI tracking using OpenCV Face Detection (YuNet ONNX & Haar Cascade) and Saliency (general objects)."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from .paths import MODELS_DIR, BUNDLED_MODELS_DIR, resolve_model_path

logger = logging.getLogger(__name__)


def _get_model_file(filename: str) -> Optional[Path]:
    """Locate a model file inside sys._MEIPASS bundled models or local models dir."""
    # First try resolve_model_path from paths.py
    try:
        p = resolve_model_path(filename)
        if p and p.is_file():
            return p
    except Exception:
        pass

    # Direct search prioritizing frozen bundle sys._MEIPASS
    meipass = getattr(sys, "_MEIPASS", None)
    candidates = []
    if meipass:
        candidates.append(Path(meipass) / "assets" / "models" / filename)
        candidates.append(Path(meipass) / "models" / filename)
        candidates.append(Path(meipass) / filename)
    candidates.extend([
        BUNDLED_MODELS_DIR / filename,
        MODELS_DIR / filename,
        Path(__file__).resolve().parent.parent / "assets" / "models" / filename,
    ])
    for c in candidates:
        try:
            if c.is_file():
                return c
        except Exception:
            pass
    return None


def _get_yunet(input_size: Tuple[int, int] = (320, 320)) -> Optional[cv2.FaceDetectorYN]:
    """Find and load the YuNet ONNX face detector from the bundled or local models."""
    if not hasattr(cv2, "FaceDetectorYN"):
        return None

    model_path = _get_model_file("face_detection_yunet.onnx")
    if model_path and model_path.exists():
        try:
            detector = cv2.FaceDetectorYN.create(
                str(model_path.resolve()),
                "",
                input_size,
                score_threshold=0.5,
                nms_threshold=0.3,
                top_k=5000,
            )
            return detector
        except Exception as e:
            logger.warning("Failed to initialize YuNet detector: %s", e)
    return None


def _get_cascade() -> Optional[cv2.CascadeClassifier]:
    """Find and load the face cascade classifier, prioritizing the frozen bundle."""
    model_path = _get_model_file("haarcascade_frontalface_default.xml")
    if model_path and model_path.exists():
        try:
            cascade = cv2.CascadeClassifier(str(model_path.resolve()))
            if not cascade.empty():
                return cascade
        except Exception as e:
            logger.debug("Failed to load cascade from %s: %s", model_path, e)

    # Fallback to cv2 data if available
    try:
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        if not cascade.empty():
            return cascade
    except Exception:
        pass
    return None


def track_face(video_path: Path, start: float, end: float, sample_rate: float = 0.5) -> List[dict]:
    """Detect and track the most prominent subject (face or salient region).
    
    Returns a list of ReframeKeyframe dicts: [{'time': t, 'pos_x': x, 'pos_y': y, 'zoom': 100}].
    """
    import math
    if math.isnan(start) or math.isinf(start):
        start = 0.0
    if math.isnan(end) or math.isinf(end) or end <= start:
        return []
    start = max(0.0, float(start))
    end = float(end)
    sample_rate = max(0.05, float(sample_rate) if not (math.isnan(sample_rate) or math.isinf(sample_rate)) else 0.5)

    logger.info("Starting AI subject tracking for %s [%.2f - %.2f]", video_path.name, start, end)
    
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        logger.warning("Could not open video %s for tracking", video_path)
        return []

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1920)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1080)

    # Resolution scaling for fast and accurate YuNet face detection
    scale = min(1.0, 1280.0 / max(width, height))
    detect_w = max(32, int(width * scale))
    detect_h = max(32, int(height * scale))

    yunet = _get_yunet((detect_w, detect_h))
    cascade = _get_cascade()
    saliency = None
    try:
        saliency = cv2.saliency.StaticSaliencySpectralResidual_create()
    except Exception:
        pass
    
    keyframes = []
    current_time = start
    
    while current_time <= end:
        frame_idx = int(current_time * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            break
            
        cx, cy = None, None
        
        # 1. Try YuNet ONNX face detection (high accuracy modern CNN)
        if yunet is not None:
            try:
                detect_frame = cv2.resize(frame, (detect_w, detect_h)) if scale < 1.0 else frame
                yunet.setInputSize((detect_w, detect_h))
                _, faces = yunet.detect(detect_frame)
                if faces is not None and len(faces) > 0:
                    best_face = max(faces, key=lambda f: float(f[2]) * float(f[3]))
                    fx, fy, fw, fh = float(best_face[0]), float(best_face[1]), float(best_face[2]), float(best_face[3])
                    if scale < 1.0:
                        fx, fy, fw, fh = fx / scale, fy / scale, fw / scale, fh / scale
                    cx = ((fx + fw / 2.0) / width) * 100.0
                    cy = ((fy + fh / 2.0) / height) * 100.0
            except Exception as e:
                logger.debug("YuNet detection error: %s", e)

        # 2. Fall back to Haar Cascade if YuNet found no face or is unavailable
        if (cx is None or cy is None) and cascade is not None:
            try:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30))
                if len(faces) > 0:
                    best_face = max(faces, key=lambda f: f[2] * f[3])
                    fx, fy, fw, fh = best_face
                    cx = ((fx + fw / 2.0) / width) * 100.0
                    cy = ((fy + fh / 2.0) / height) * 100.0
            except Exception as e:
                logger.debug("Cascade detection error: %s", e)
        
        # 3. If no face is found, fall back to Saliency Map tracking
        if (cx is None or cy is None) and saliency is not None:
            try:
                small = cv2.resize(frame, (256, max(1, int(256 * height / width))))
                success, saliency_map = saliency.computeSaliency(small)
                if success:
                    M = cv2.moments((saliency_map * 255).astype(np.uint8))
                    if M["m00"] > 0:
                        cx = ((M["m10"] / M["m00"]) / small.shape[1]) * 100.0
                        cy = ((M["m01"] / M["m00"]) / small.shape[0]) * 100.0
            except Exception as e:
                logger.debug("Saliency detection error: %s", e)
        
        # 4. Fallback to center
        if cx is None or cy is None:
            cx, cy = 50.0, 50.0
        
        cx = max(0.0, min(100.0, cx))
        cy = max(0.0, min(100.0, cy))
        
        clip_time = current_time - start
        keyframes.append({
            "time": round(clip_time, 2),
            "pos_x": round(cx, 2),
            "pos_y": round(cy, 2),
            "zoom": 100
        })
        
        current_time += sample_rate
        
    cap.release()
    
    if not keyframes:
        logger.info("No subjects found during tracking.")
        return []
        
    # Smooth the track using a moving average window
    window_size = 5
    smoothed = []
    for i in range(len(keyframes)):
        start_idx = max(0, i - window_size // 2)
        end_idx = min(len(keyframes), i + window_size // 2 + 1)
        window = keyframes[start_idx:end_idx]
        
        avg_x = sum(k["pos_x"] for k in window) / len(window)
        avg_y = sum(k["pos_y"] for k in window) / len(window)
        
        smoothed.append({
            "time": keyframes[i]["time"],
            "pos_x": round(avg_x, 2),
            "pos_y": round(avg_y, 2),
            "zoom": 100
        })
        
    logger.info("Subject tracking generated %d keyframes", len(smoothed))
    return smoothed
