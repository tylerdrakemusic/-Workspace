"""Tests for src/integrations/ollama/client.py -- mocked HTTP, no running Ollama needed."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.integrations.ollama.client import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    OllamaClient,
    OllamaError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok_response(body: dict) -> MagicMock:
    mock = MagicMock(spec=httpx.Response)
    mock.status_code = 200
    mock.json.return_value = body
    mock.text = str(body)
    return mock


def _error_response(status: int, text: str = "error") -> MagicMock:
    mock = MagicMock(spec=httpx.Response)
    mock.status_code = status
    mock.json.side_effect = ValueError("not json")
    mock.text = text
    return mock


# ---------------------------------------------------------------------------
# Construction / default resolution
# ---------------------------------------------------------------------------

class TestConstruction:
    def test_defaults_without_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        monkeypatch.delenv("OLLAMA_MODEL", raising=False)
        c = OllamaClient()
        assert c.base_url == DEFAULT_BASE_URL
        assert c.model == DEFAULT_MODEL

    def test_constructor_args_override_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        monkeypatch.delenv("OLLAMA_MODEL", raising=False)
        c = OllamaClient(base_url="http://myhost:11434", model="mistral:7b")
        assert c.base_url == "http://myhost:11434"
        assert c.model == "mistral:7b"

    def test_env_vars_override_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://envhost:11434")
        monkeypatch.setenv("OLLAMA_MODEL", "phi3:mini")
        c = OllamaClient()
        assert c.base_url == "http://envhost:11434"
        assert c.model == "phi3:mini"

    def test_constructor_args_override_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://envhost:11434")
        monkeypatch.setenv("OLLAMA_MODEL", "phi3:mini")
        c = OllamaClient(base_url="http://explicit:11434", model="gemma:2b")
        assert c.base_url == "http://explicit:11434"
        assert c.model == "gemma:2b"

    def test_trailing_slash_stripped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        c = OllamaClient(base_url="http://localhost:11434/")
        assert not c.base_url.endswith("/")


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------

class TestHealthCheck:
    def test_returns_true_on_200(self) -> None:
        with patch("httpx.get", return_value=_ok_response({"status": "ok"})):
            c = OllamaClient()
            assert c.health_check() is True

    def test_returns_false_on_connect_error(self) -> None:
        with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
            c = OllamaClient()
            assert c.health_check() is False

    def test_returns_false_on_timeout(self) -> None:
        with patch("httpx.get", side_effect=httpx.TimeoutException("timed out")):
            c = OllamaClient()
            assert c.health_check() is False

    def test_returns_false_on_non_200(self) -> None:
        with patch("httpx.get", return_value=_error_response(503)):
            c = OllamaClient()
            assert c.health_check() is False


# ---------------------------------------------------------------------------
# list_models
# ---------------------------------------------------------------------------

class TestListModels:
    def test_returns_model_list(self) -> None:
        models_payload = {
            "models": [
                {"name": "llama3.1:8b", "size": 1234},
                {"name": "mistral:7b", "size": 5678},
            ]
        }
        with patch("httpx.get", return_value=_ok_response(models_payload)):
            c = OllamaClient()
            result = c.list_models()
        assert len(result) == 2
        assert result[0]["name"] == "llama3.1:8b"

    def test_returns_empty_list_when_key_missing(self) -> None:
        with patch("httpx.get", return_value=_ok_response({})):
            c = OllamaClient()
            result = c.list_models()
        assert result == []

    def test_raises_on_http_error(self) -> None:
        with patch("httpx.get", return_value=_error_response(500, "internal error")):
            c = OllamaClient()
            with pytest.raises(OllamaError, match="HTTP 500"):
                c.list_models()

    def test_raises_on_connect_error(self) -> None:
        with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
            c = OllamaClient()
            with pytest.raises(OllamaError, match="Cannot reach Ollama"):
                c.list_models()


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------

class TestGenerate:
    def test_returns_response_text(self) -> None:
        payload = {"response": "Paris", "done": True}
        with patch("httpx.post", return_value=_ok_response(payload)):
            c = OllamaClient()
            result = c.generate("What is the capital of France?")
        assert result == "Paris"

    def test_uses_instance_model_by_default(self) -> None:
        with patch("httpx.post", return_value=_ok_response({"response": "ok"})) as mock_post:
            c = OllamaClient(model="phi3:mini")
            c.generate("hello")
            call_kwargs = mock_post.call_args
            sent_payload = call_kwargs[1]["json"]
            assert sent_payload["model"] == "phi3:mini"

    def test_model_arg_overrides_instance_model(self) -> None:
        with patch("httpx.post", return_value=_ok_response({"response": "ok"})) as mock_post:
            c = OllamaClient(model="phi3:mini")
            c.generate("hello", model="gemma:2b")
            sent_payload = mock_post.call_args[1]["json"]
            assert sent_payload["model"] == "gemma:2b"

    def test_raises_if_response_key_missing(self) -> None:
        with patch("httpx.post", return_value=_ok_response({"done": True})):
            c = OllamaClient()
            with pytest.raises(OllamaError, match="'response' key missing"):
                c.generate("hello")

    def test_raises_on_http_error(self) -> None:
        with patch("httpx.post", return_value=_error_response(404, "model not found")):
            c = OllamaClient()
            with pytest.raises(OllamaError, match="HTTP 404"):
                c.generate("hello")

    def test_stream_false_in_payload(self) -> None:
        with patch("httpx.post", return_value=_ok_response({"response": "ok"})) as mock_post:
            OllamaClient().generate("hello")
            sent = mock_post.call_args[1]["json"]
            assert sent["stream"] is False


# ---------------------------------------------------------------------------
# ensure_model_available
# ---------------------------------------------------------------------------

class TestEnsureModelAvailable:
    def _models_response(self, names: list[str]) -> MagicMock:
        return _ok_response({"models": [{"name": n} for n in names]})

    def test_returns_true_when_model_present(self) -> None:
        with patch("httpx.get", return_value=self._models_response(["llama3.1:8b", "mistral:7b"])):
            c = OllamaClient(model="llama3.1:8b")
            assert c.ensure_model_available() is True

    def test_returns_false_when_model_absent(self) -> None:
        with patch("httpx.get", return_value=self._models_response(["mistral:7b"])):
            c = OllamaClient(model="llama3.1:8b")
            assert c.ensure_model_available() is False

    def test_explicit_model_arg_checked(self) -> None:
        with patch("httpx.get", return_value=self._models_response(["gemma:2b"])):
            c = OllamaClient(model="llama3.1:8b")
            assert c.ensure_model_available("gemma:2b") is True

    def test_returns_false_on_connection_failure(self) -> None:
        with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
            c = OllamaClient()
            assert c.ensure_model_available() is False

    def test_model_field_fallback(self) -> None:
        # Some Ollama versions use 'model' key instead of 'name'
        resp = _ok_response({"models": [{"model": "llama3.1:8b"}]})
        with patch("httpx.get", return_value=resp):
            c = OllamaClient(model="llama3.1:8b")
            assert c.ensure_model_available() is True
