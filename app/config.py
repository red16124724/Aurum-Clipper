"""Application configuration management and Google Gemini API integration.

Handles persisting user settings (such as the Google Gemini API key) in a local
config.json file, synchronizing with os.environ, and validating connectivity
with Google AI Studio / Gemini models.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from .paths import DATA_DIR

logger = logging.getLogger("ai_video_clipper.config")

CONFIG_FILE = DATA_DIR / "config.json"
_CONFIG_LOCK = threading.Lock()

# Preferred default models for verification and tasks
PRIMARY_GEMINI_MODEL = "gemini-3.8-flash"
FALLBACK_GEMINI_MODEL = "gemini-2.5-flash"


def _read_config_file() -> Dict[str, Any]:
    """Read config.json safely, returning an empty dict if not found or invalid."""
    if not CONFIG_FILE.is_file():
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning("Could not read config file %s: %s", CONFIG_FILE, e)
        return {}


def _write_config_file(data: Dict[str, Any]) -> None:
    """Write data to config.json atomically and safely."""
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp_file = CONFIG_FILE.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        temp_file.replace(CONFIG_FILE)
    except Exception as e:
        logger.error("Could not write config file %s: %s", CONFIG_FILE, e)


def init_config() -> None:
    """Initialize application configuration on startup.
    
    Loads saved API keys into os.environ if they are not already set.
    """
    with _CONFIG_LOCK:
        cfg = _read_config_file()
        saved_key = (cfg.get("gemini_api_key") or cfg.get("google_api_key") or "").strip()
        if saved_key:
            if not os.environ.get("GEMINI_API_KEY"):
                os.environ["GEMINI_API_KEY"] = saved_key
            if not os.environ.get("GOOGLE_API_KEY"):
                os.environ["GOOGLE_API_KEY"] = saved_key
            logger.info("Loaded Google Gemini API key from %s", CONFIG_FILE.name)


def get_gemini_api_key() -> Optional[str]:
    """Return the active Gemini API key from environment or config file."""
    env_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip()
    with _CONFIG_LOCK:
        cfg = _read_config_file()
        saved = (cfg.get("gemini_api_key") or cfg.get("google_api_key") or "").strip()
        return saved if saved else None


def set_gemini_api_key(key: Optional[str]) -> bool:
    """Save or clear the Gemini API key in config.json and update os.environ.
    
    Args:
        key: The Google Gemini API key string, or None/empty to remove it.
        
    Returns:
        bool: True if key is set, False if cleared.
    """
    clean_key = (key or "").strip()
    with _CONFIG_LOCK:
        cfg = _read_config_file()
        if clean_key:
            cfg["gemini_api_key"] = clean_key
            cfg["google_api_key"] = clean_key
            _write_config_file(cfg)
            os.environ["GEMINI_API_KEY"] = clean_key
            os.environ["GOOGLE_API_KEY"] = clean_key
            return True
        else:
            cfg.pop("gemini_api_key", None)
            cfg.pop("google_api_key", None)
            _write_config_file(cfg)
            os.environ.pop("GEMINI_API_KEY", None)
            os.environ.pop("GOOGLE_API_KEY", None)
            return False


def mask_api_key(key: Optional[str]) -> Optional[str]:
    """Mask an API key for safe display in UI (e.g. AIzaSy...4X9z)."""
    if not key:
        return None
    k = key.strip()
    if len(k) <= 8:
        return "••••••••"
    return f"{k[:6]}...{k[-4:]}"


def validate_gemini_api_key(key_to_test: Optional[str] = None) -> Dict[str, Any]:
    """Validate a Google Gemini API key by connecting to Google AI Studio.
    
    Args:
        key_to_test: Specific key to validate, or None to test current active key.
        
    Returns:
        dict: {"valid": bool, "message": str, "models": list[str]}
    """
    target_key = (key_to_test or "").strip() or get_gemini_api_key()
    if not target_key:
        return {
            "valid": False,
            "message": "No Google Gemini API key provided or configured.",
            "models": [],
        }

    try:
        from google import genai

        client = genai.Client(api_key=target_key)
        
        # Test model listing to verify credentials and connectivity
        models_iter = client.models.list(config={"page_size": 10})
        found_models: list[str] = []
        for m in models_iter:
            name = getattr(m, "name", str(m))
            # Clean model name (e.g. 'models/gemini-2.5-flash' -> 'gemini-2.5-flash')
            if "/" in name:
                name = name.split("/")[-1]
            found_models.append(name)
            if len(found_models) >= 10:
                break

        return {
            "valid": True,
            "message": "Google Gemini API connected and verified successfully.",
            "models": found_models,
            "masked_key": mask_api_key(target_key),
        }
    except Exception as exc:
        err_msg = str(exc)
        # Simplify Google API errors for user clarity
        if "API_KEY_INVALID" in err_msg or "API key not valid" in err_msg:
            clean_msg = "Invalid API key. Please check your key on Google AI Studio."
        elif "PERMISSION_DENIED" in err_msg:
            clean_msg = "Permission denied for this API key. Verify project permissions."
        elif "RESOURCE_EXHAUSTED" in err_msg or "429" in err_msg:
            clean_msg = "Rate limit reached for Google Gemini API."
        else:
            clean_msg = f"Connection failed: {err_msg[:120]}"

        logger.warning("Gemini API key validation failed: %s", exc)
        return {
            "valid": False,
            "message": clean_msg,
            "models": [],
            "masked_key": mask_api_key(target_key),
        }
