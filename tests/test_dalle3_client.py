"""Tests for src/integrations/dalle3/client.py — mocked HTTP, no real API calls."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.integrations.dalle3.client import DallE3Client, DallE3Error


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> DallE3Client:
    monkeypatch.setenv("OPENAPI_TOKEN", "sk-test-fake-token")
    return DallE3Client()


def _mock_generate_response(image_url: str) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": [{"url": image_url}]}
    return mock_resp


def _mock_b64json_response(content: bytes = b"\x89PNG\r\n\x1a\n" + b"x" * 100) -> MagicMock:
    """Mock API response using b64_json format (current API default)."""
    import base64 as _b64
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": [{"b64_json": _b64.b64encode(content).decode()}]}
    return mock_resp


def _mock_download_response(content: bytes = b"\x89PNG\r\n\x1a\n" + b"x" * 100) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = content
    return mock_resp


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def test_client_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAPI_TOKEN", raising=False)
    with pytest.raises(EnvironmentError, match="OPENAPI_TOKEN"):
        DallE3Client()


def test_client_accepts_explicit_key() -> None:
    c = DallE3Client(api_key="sk-explicit")
    assert c._api_key == "sk-explicit"


def test_client_reads_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAPI_TOKEN", "sk-from-env")
    c = DallE3Client()
    assert c._api_key == "sk-from-env"


# ---------------------------------------------------------------------------
# generate_image — happy path
# ---------------------------------------------------------------------------

def test_generate_image_b64json_returns_path(client: DallE3Client, tmp_path: Path) -> None:
    """b64_json response (current API default) — no secondary download."""
    fake_png = b"\x89PNG\r\n\x1a\n" + b"z" * 200
    gen_resp = _mock_b64json_response(fake_png)

    with patch("src.integrations.dalle3.client.httpx.Client") as mock_cls:
        mock_http = mock_cls.return_value.__enter__.return_value
        mock_http.post.return_value = gen_resp

        result = client.generate_image("a test portrait", output_dir=tmp_path)

    assert isinstance(result, Path)
    assert result.suffix == ".png"
    assert result.exists()
    assert result.read_bytes() == fake_png
    mock_http.get.assert_not_called()  # No download for b64 path


def test_generate_image_url_returns_path(client: DallE3Client, tmp_path: Path) -> None:
    """url response (legacy format) — image downloaded from URL."""
    fake_png = b"\x89PNG\r\n\x1a\n" + b"z" * 200
    gen_resp = _mock_generate_response("https://example.com/image.png")
    dl_resp = _mock_download_response(fake_png)

    with patch("src.integrations.dalle3.client.httpx.Client") as mock_cls:
        mock_http = mock_cls.return_value.__enter__.return_value
        mock_http.post.return_value = gen_resp
        mock_http.get.return_value = dl_resp

        result = client.generate_image("a test portrait", output_dir=tmp_path)

    assert isinstance(result, Path)
    assert result.suffix == ".png"
    assert result.exists()
    assert result.read_bytes() == fake_png


def test_generate_image_returns_path(client: DallE3Client, tmp_path: Path) -> None:
    """Alias test kept for backwards compatibility — url path."""
    fake_png = b"\x89PNG\r\n\x1a\n" + b"z" * 200

    gen_resp = _mock_generate_response("https://example.com/image.png")
    dl_resp = _mock_download_response(fake_png)

    with patch("src.integrations.dalle3.client.httpx.Client") as mock_cls:
        mock_http = mock_cls.return_value.__enter__.return_value
        mock_http.post.return_value = gen_resp
        mock_http.get.return_value = dl_resp

        result = client.generate_image("a test portrait", output_dir=tmp_path)

    assert isinstance(result, Path)
    assert result.suffix == ".png"
    assert result.exists()
    assert result.read_bytes() == fake_png


def test_generate_image_creates_output_dir(client: DallE3Client, tmp_path: Path) -> None:
    new_dir = tmp_path / "nested" / "output"
    gen_resp = _mock_b64json_response()

    with patch("src.integrations.dalle3.client.httpx.Client") as mock_cls:
        mock_http = mock_cls.return_value.__enter__.return_value
        mock_http.post.return_value = gen_resp
        client.generate_image("portrait", output_dir=new_dir)

    assert new_dir.exists()


def test_generate_image_content_addressed(client: DallE3Client, tmp_path: Path) -> None:
    """Same prompt + same first bytes → same filename."""
    content = b"\x89PNG\r\n\x1a\n" + b"a" * 100
    gen_resp = _mock_b64json_response(content)

    with patch("src.integrations.dalle3.client.httpx.Client") as mock_cls:
        mock_http = mock_cls.return_value.__enter__.return_value
        mock_http.post.return_value = gen_resp
        path1 = client.generate_image("same prompt", output_dir=tmp_path)

    with patch("src.integrations.dalle3.client.httpx.Client") as mock_cls:
        mock_http = mock_cls.return_value.__enter__.return_value
        mock_http.post.return_value = gen_resp
        path2 = client.generate_image("same prompt", output_dir=tmp_path)

    assert path1.name == path2.name


# ---------------------------------------------------------------------------
# generate_image — error paths
# ---------------------------------------------------------------------------

def test_api_error_status_raises(client: DallE3Client, tmp_path: Path) -> None:
    err_resp = MagicMock()
    err_resp.status_code = 429
    err_resp.text = "rate limit exceeded"

    with patch("src.integrations.dalle3.client.httpx.Client") as mock_cls:
        mock_http = mock_cls.return_value.__enter__.return_value
        mock_http.post.return_value = err_resp
        with pytest.raises(DallE3Error, match="429"):
            client.generate_image("test", output_dir=tmp_path)


def test_malformed_response_raises(client: DallE3Client, tmp_path: Path) -> None:
    bad_resp = MagicMock()
    bad_resp.status_code = 200
    bad_resp.json.return_value = {"data": []}  # empty list — IndexError

    with patch("src.integrations.dalle3.client.httpx.Client") as mock_cls:
        mock_http = mock_cls.return_value.__enter__.return_value
        mock_http.post.return_value = bad_resp
        with pytest.raises(DallE3Error, match="response shape"):
            client.generate_image("test", output_dir=tmp_path)


def test_unknown_item_shape_raises(client: DallE3Client, tmp_path: Path) -> None:
    """Item dict has neither url nor b64_json — should raise DallE3Error."""
    bad_resp = MagicMock()
    bad_resp.status_code = 200
    bad_resp.json.return_value = {"data": [{"revised_prompt": "something"}]}

    with patch("src.integrations.dalle3.client.httpx.Client") as mock_cls:
        mock_http = mock_cls.return_value.__enter__.return_value
        mock_http.post.return_value = bad_resp
        with pytest.raises(DallE3Error, match="item shape"):
            client.generate_image("test", output_dir=tmp_path)


def test_download_failure_raises(client: DallE3Client, tmp_path: Path) -> None:
    gen_resp = _mock_generate_response("https://example.com/img.png")
    fail_resp = MagicMock()
    fail_resp.status_code = 403
    fail_resp.content = b""

    with patch("src.integrations.dalle3.client.httpx.Client") as mock_cls:
        mock_http = mock_cls.return_value.__enter__.return_value
        mock_http.post.return_value = gen_resp
        mock_http.get.return_value = fail_resp
        with pytest.raises(DallE3Error, match="403"):
            client.generate_image("test", output_dir=tmp_path)


def test_network_error_raises(client: DallE3Client, tmp_path: Path) -> None:
    import httpx as _httpx

    with patch("src.integrations.dalle3.client.httpx.Client") as mock_cls:
        mock_http = mock_cls.return_value.__enter__.return_value
        mock_http.post.side_effect = _httpx.ConnectError("connection refused")
        with pytest.raises(DallE3Error, match="Network error"):
            client.generate_image("test", output_dir=tmp_path)
