import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app import config

client = TestClient(app)

def test_config_save_and_load(tmp_path):
    with patch("app.config.CONFIG_FILE", tmp_path / "config.json"):
        with patch.dict(os.environ, {}, clear=True):
            # Test setting key
            res = config.set_gemini_api_key("test_api_key_123456789")
            assert res is True
            assert os.environ.get("GEMINI_API_KEY") == "test_api_key_123456789"
            assert os.environ.get("GOOGLE_API_KEY") == "test_api_key_123456789"
            assert config.get_gemini_api_key() == "test_api_key_123456789"
            assert config.mask_api_key("test_api_key_123456789") == "test_a...6789"

            # Test clearing key
            res_clear = config.set_gemini_api_key("")
            assert res_clear is False
            assert "GEMINI_API_KEY" not in os.environ
            assert config.get_gemini_api_key() is None
            assert config.mask_api_key(None) is None


def test_api_endpoints_gemini(tmp_path):
    with patch("app.config.CONFIG_FILE", tmp_path / "config.json"):
        with patch.dict(os.environ, {}, clear=True):
            # 1. Get when empty
            r = client.get("/api/settings/api-key")
            assert r.status_code == 200
            assert r.json()["configured"] is False
            assert r.json()["masked_key"] is None

            # 2. Post key
            r = client.post("/api/settings/api-key", json={"api_key": "AIzaSyTestKey987654321"})
            assert r.status_code == 200
            assert r.json()["configured"] is True
            assert r.json()["masked_key"] == "AIzaSy...4321"

            # 3. Get after configured
            r = client.get("/api/settings/api-key")
            assert r.status_code == 200
            assert r.json()["configured"] is True
            assert r.json()["masked_key"] == "AIzaSy...4321"

            # 4. Status endpoint
            r = client.get("/api/gemini/status")
            assert r.status_code == 200
            assert r.json()["configured"] is True
            assert "primary_model" in r.json()

            # 5. Validation endpoint - success mock
            with patch("google.genai.Client") as mock_genai:
                mock_instance = MagicMock()
                mock_genai.return_value = mock_instance
                mock_m1 = MagicMock()
                mock_m1.name = "models/gemini-3.8-flash"
                mock_m2 = MagicMock()
                mock_m2.name = "models/gemini-2.5-flash"
                mock_instance.models.list.return_value = [mock_m1, mock_m2]

                r = client.post("/api/gemini/validate", json={})
                assert r.status_code == 200
                data = r.json()
                assert data["valid"] is True
                assert "gemini-3.8-flash" in data["models"]

            # 6. Validation endpoint - failure mock
            with patch("google.genai.Client") as mock_genai:
                mock_instance = MagicMock()
                mock_genai.return_value = mock_instance
                mock_instance.models.list.side_effect = RuntimeError("API_KEY_INVALID")

                r = client.post("/api/gemini/validate", json={"api_key": "bad_key"})
                assert r.status_code == 200
                data = r.json()
                assert data["valid"] is False
                assert "Invalid API key" in data["message"]
