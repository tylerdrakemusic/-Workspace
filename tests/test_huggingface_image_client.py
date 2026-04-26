"""Tests for src/integrations/huggingface/client.py — mocked HTTP, no real API calls."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.integrations.huggingface.client import (
    HuggingFaceImageClient,
    HuggingFaceImageError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> HuggingFaceImageClient:
    monkeypatch.setenv("HF_TOKEN", "hf-test-fake-token")
    return HuggingFaceImageClient()


def _mock_ok_response(content: bytes = b"\x89PNG\r\n\x1a\n" + b"x" * 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.content = content
    return resp


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def test_client_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)
    with pytest.raises(EnvironmentError, match="HF_TOKEN"):
        HuggingFaceImageClient()


def test_client_accepts_explicit_key() -> None:
    c = HuggingFaceImageClient(api_key="hf-explicit")
    assert c._api_key == "hf-explicit"


def test_client_reads_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_TOKEN", "hf-from-env")
    c = HuggingFaceImageClient()
    assert c._api_key == "hf-from-env"


def test_custom_model_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_TOKEN", "tok")
    c = HuggingFaceImageClient(model_id="runwayml/stable-diffusion-v1-5")
    assert c._model_id == "runwayml/stable-diffusion-v1-5"


# ---------------------------------------------------------------------------
# _parse_size
# ---------------------------------------------------------------------------

def test_parse_size_standard() -> None:
    assert HuggingFaceImageClient._parse_size("1024x1024") == (1024, 1024)


def test_parse_size_non_square() -> None:
    assert HuggingFaceImageClient._parse_size("512x768") == (512, 768)


def test_parse_size_uppercase() -> None:
    assert HuggingFaceImageClient._parse_size("1024X1024") == (1024, 1024)


def test_parse_size_invalid_format() -> None:
    with pytest.raises(ValueError, match="WxH"):
        HuggingFaceImageClient._parse_size("1024")


def test_parse_size_non_integer() -> None:
    with pytest.raises(ValueError, match="Non-integer"):
        HuggingFaceImageClient._parse_size("abcxdef")


# ---------------------------------------------------------------------------
# generate_image — happy path
# ---------------------------------------------------------------------------

def test_generate_image_returns_path(client: HuggingFaceImageClient, tmp_path: Path) -> None:
    fake_png = b"\x89PNG\r\n\x1a\n" + b"z" * 200
    ok_resp = _mock_ok_response(fake_png)

    with patch("src.integrations.huggingface.client.httpx.Client") as mock_cls:
        mock_http = mock_cls.return_value.__enter__.return_value
        mock_http.post.return_value = ok_resp
        result = client.generate_image("a test portrait", output_dir=tmp_path)

    assert isinstance(result, Path)
    assert result.suffix == ".png"
    assert result.exists()
    assert result.read_bytes() == fake_png


def test_generate_image_creates_output_dir(client: HuggingFaceImageClient, tmp_path: Path) -> None:
    new_dir = tmp_path / "nested" / "output"
    ok_resp = _mock_ok_response()

    with patch("src.integrations.huggingface.client.httpx.Client") as mock_cls:
        mock_http = mock_cls.return_value.__enter__.return_value
        mock_http.post.return_value = ok_resp
        client.generate_image("portrait", output_dir=new_dir)

    assert new_dir.exists()


def test_generate_image_sends_correct_payload(client: HuggingFaceImageClient, tmp_path: Path) -> None:
    ok_resp = _mock_ok_response()

    with patch("src.integrations.huggingface.client.httpx.Client") as mock_cls:
        mock_http = mock_cls.return_value.__enter__.return_value
        mock_http.post.return_value = ok_resp
        client.generate_image("a portrait", size="512x768", output_dir=tmp_path)

        call_kwargs = mock_http.post.call_args
        payload = call_kwargs[1]["json"]  # keyword arg
        assert payload["parameters"]["width"] == 512
        assert payload["parameters"]["height"] == 768
        assert payload["inputs"] == "a portrait"


def test_generate_image_content_addressed(client: HuggingFaceImageClient, tmp_path: Path) -> None:
    content = b"\x89PNG\r\n\x1a\n" + b"b" * 100
    ok_resp = _mock_ok_response(content)

    with patch("src.integrations.huggingface.client.httpx.Client") as mock_cls:
        mock_http = mock_cls.return_value.__enter__.return_value
        mock_http.post.return_value = ok_resp
        p1 = client.generate_image("same prompt", output_dir=tmp_path)

    with patch("src.integrations.huggingface.client.httpx.Client") as mock_cls:
        mock_http = mock_cls.return_value.__enter__.return_value
        mock_http.post.return_value = ok_resp
        p2 = client.generate_image("same prompt", output_dir=tmp_path)

    assert p1.name == p2.name


# ---------------------------------------------------------------------------
# generate_image — error paths
# ---------------------------------------------------------------------------

def test_api_error_status_raises(client: HuggingFaceImageClient, tmp_path: Path) -> None:
    err_resp = MagicMock()
    err_resp.status_code = 503
    err_resp.text = "model loading"

    with patch("src.integrations.huggingface.client.httpx.Client") as mock_cls:
        mock_http = mock_cls.return_value.__enter__.return_value
        mock_http.post.return_value = err_resp
        with pytest.raises(HuggingFaceImageError, match="503"):
            client.generate_image("test", output_dir=tmp_path)


def test_empty_response_raises(client: HuggingFaceImageClient, tmp_path: Path) -> None:
    empty_resp = MagicMock()
    empty_resp.status_code = 200
    empty_resp.content = b""

    with patch("src.integrations.huggingface.client.httpx.Client") as mock_cls:
        mock_http = mock_cls.return_value.__enter__.return_value
        mock_http.post.return_value = empty_resp
        with pytest.raises(HuggingFaceImageError, match="empty"):
            client.generate_image("test", output_dir=tmp_path)


def test_network_error_raises(client: HuggingFaceImageClient, tmp_path: Path) -> None:
    import httpx as _httpx

    with patch("src.integrations.huggingface.client.httpx.Client") as mock_cls:
        mock_http = mock_cls.return_value.__enter__.return_value
        mock_http.post.side_effect = _httpx.ConnectError("connection refused")
        with pytest.raises(HuggingFaceImageError, match="Network error"):
            client.generate_image("test", output_dir=tmp_path)
