"""Tests for src/integrations/huggingface/spaces_client.py — mocked HTTP, no real API calls."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.integrations.huggingface.spaces_client import (
    HFSpacesImageClient,
    HFSpacesError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 20_000

_SPACE = "https://black-forest-labs-flux-1-schnell.hf.space"


def _post_response(event_id: str = "abc123") -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = {"event_id": event_id}
    resp.text = json.dumps({"event_id": event_id})
    return resp


def _stream_lines(lines: list[str]):
    """Return an iter_lines mock producing the given SSE lines."""
    ctx = MagicMock()
    ctx.__enter__ = lambda s: s
    ctx.__exit__ = MagicMock(return_value=False)
    ctx.iter_lines.return_value = iter(lines)
    return ctx


def _download_response(
    content: bytes = _FAKE_PNG,
    *,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.content = content
    resp.headers = headers or {}
    return resp


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestConstruction:
    def test_reads_hf_token_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HF_TOKEN", "hf-test-token")
        client = HFSpacesImageClient()
        assert client._token == "hf-test-token"

    def test_works_without_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("HF_TOKEN", raising=False)
        client = HFSpacesImageClient()
        assert client._token == ""

    def test_custom_space_base(self) -> None:
        client = HFSpacesImageClient(space_base="https://my-space.hf.space/")
        assert client._space_base == "https://my-space.hf.space"  # trailing / stripped


# ---------------------------------------------------------------------------
# Happy path — image URL in SSE data
# ---------------------------------------------------------------------------

class TestHappyPath:
    def test_image_downloaded_and_saved(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HF_TOKEN", "hf-test")
        img_url = f"{_SPACE}/file=/tmp/out.png"
        sse_lines = [
            f"data: {json.dumps([{'url': img_url, 'path': None}])}",
        ]

        with (
            patch("httpx.post", return_value=_post_response("ev1")),
            patch.object(
                httpx.Client, "stream",
                return_value=_stream_lines(sse_lines),
            ),
            patch("httpx.get", return_value=_download_response(_FAKE_PNG)),
        ):
            client = HFSpacesImageClient()
            result = client.generate_image("a portrait", output_dir=tmp_path)

        assert result.exists()
        assert result.stat().st_size == len(_FAKE_PNG)
        assert "hf_spaces_" in result.name

    def test_relative_url_resolved_against_space(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HF_TOKEN", "hf-test")
        sse_lines = [
            f"data: {json.dumps([{'url': '/file=/tmp/out.png', 'path': None}])}",
        ]
        captured_url = []

        def fake_get(url, **kwargs):
            captured_url.append(url)
            return _download_response()

        with (
            patch("httpx.post", return_value=_post_response("ev2")),
            patch.object(httpx.Client, "stream", return_value=_stream_lines(sse_lines)),
            patch("httpx.get", side_effect=fake_get),
        ):
            HFSpacesImageClient().generate_image("test", output_dir=tmp_path)

        assert captured_url[0].startswith(_SPACE)

    def test_rejects_untrusted_custom_space_base_before_download_request(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HF_TOKEN", "hf-test")
        hostile_base = "https://attacker.example"
        sse_lines = [f"data: {json.dumps([{'url': f'{hostile_base}/out.png'}])}"]

        with (
            patch("httpx.post", return_value=_post_response()),
            patch.object(httpx.Client, "stream", return_value=_stream_lines(sse_lines)),
            patch("httpx.get", return_value=_download_response()) as get,
        ):
            with pytest.raises(HFSpacesError, match="Unsafe"):
                HFSpacesImageClient(space_base=hostile_base).generate_image(
                    "test", output_dir=tmp_path
                )

        get.assert_not_called()

    @pytest.mark.parametrize(
        "img_url",
        [
            "http://black-forest-labs-flux-1-schnell.hf.space/file=/tmp/out.png",
            "https://attacker.example/out.png",
            "ftp://black-forest-labs-flux-1-schnell.hf.space/out.png",
            "//attacker.example/out.png",
        ],
    )
    def test_rejects_unsafe_image_url_before_request(
        self,
        img_url: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("HF_TOKEN", "hf-test")
        sse_lines = [f"data: {json.dumps([{'url': img_url}])}"]

        with (
            patch("httpx.post", return_value=_post_response()),
            patch.object(httpx.Client, "stream", return_value=_stream_lines(sse_lines)),
            patch("httpx.get") as get,
        ):
            with pytest.raises(HFSpacesError, match="Unsafe image URL"):
                HFSpacesImageClient().generate_image("test", output_dir=tmp_path)

        get.assert_not_called()

    def test_follows_only_validated_same_host_redirects_manually(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HF_TOKEN", "hf-test")
        img_url = f"{_SPACE}/file=/tmp/out.png"
        sse_lines = [f"data: {json.dumps([{'url': img_url}])}"]
        redirect = _download_response(
            status_code=302, headers={"location": "/file=/tmp/final.png"}
        )

        with (
            patch("httpx.post", return_value=_post_response()),
            patch.object(httpx.Client, "stream", return_value=_stream_lines(sse_lines)),
            patch("httpx.get", side_effect=[redirect, _download_response()]) as get,
        ):
            result = HFSpacesImageClient().generate_image("test", output_dir=tmp_path)

        assert result.read_bytes() == _FAKE_PNG
        assert [call.args[0] for call in get.call_args_list] == [
            img_url,
            f"{_SPACE}/file=/tmp/final.png",
        ]
        assert all(call.kwargs["follow_redirects"] is False for call in get.call_args_list)

    def test_rejects_unsafe_redirect_before_requesting_target(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HF_TOKEN", "hf-test")
        img_url = f"{_SPACE}/file=/tmp/out.png"
        sse_lines = [f"data: {json.dumps([{'url': img_url}])}"]
        redirect = _download_response(
            status_code=302, headers={"location": "https://attacker.example/out.png"}
        )

        with (
            patch("httpx.post", return_value=_post_response()),
            patch.object(httpx.Client, "stream", return_value=_stream_lines(sse_lines)),
            patch("httpx.get", return_value=redirect) as get,
        ):
            with pytest.raises(HFSpacesError, match="Unsafe image URL"):
                HFSpacesImageClient().generate_image("test", output_dir=tmp_path)

        assert get.call_count == 1
        assert get.call_args.kwargs["follow_redirects"] is False

    def test_stops_after_bounded_same_host_redirects(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HF_TOKEN", "hf-test")
        img_url = f"{_SPACE}/file=/tmp/out.png"
        sse_lines = [f"data: {json.dumps([{'url': img_url}])}"]
        redirect = _download_response(
            status_code=302, headers={"location": "/file=/tmp/next.png"}
        )

        with (
            patch("httpx.post", return_value=_post_response()),
            patch.object(httpx.Client, "stream", return_value=_stream_lines(sse_lines)),
            patch("httpx.get", return_value=redirect) as get,
        ):
            with pytest.raises(HFSpacesError, match="redirect limit"):
                HFSpacesImageClient().generate_image("test", output_dir=tmp_path)

        assert get.call_count == 4


# ---------------------------------------------------------------------------
# Error / failure paths
# ---------------------------------------------------------------------------

class TestErrorPaths:
    def test_zerogpu_error_event_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HF_TOKEN", "hf-test")
        sse_lines = ["event: error", "data: null"]

        with (
            patch("httpx.post", return_value=_post_response()),
            patch.object(httpx.Client, "stream", return_value=_stream_lines(sse_lines)),
        ):
            with pytest.raises(HFSpacesError, match="ZeroGPU"):
                HFSpacesImageClient().generate_image("test", output_dir=tmp_path)

    def test_submit_http_error_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HF_TOKEN", "hf-test")
        bad_resp = MagicMock(spec=httpx.Response)
        bad_resp.status_code = 503
        bad_resp.text = "Service Unavailable"

        with patch("httpx.post", return_value=bad_resp):
            with pytest.raises(HFSpacesError, match="503"):
                HFSpacesImageClient().generate_image("test", output_dir=tmp_path)

    def test_network_error_on_submit_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HF_TOKEN", "hf-test")
        with patch("httpx.post", side_effect=httpx.ConnectError("no route")):
            with pytest.raises(HFSpacesError, match="Network error"):
                HFSpacesImageClient().generate_image("test", output_dir=tmp_path)

    def test_empty_data_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HF_TOKEN", "hf-test")
        sse_lines = ["data: []"]

        with (
            patch("httpx.post", return_value=_post_response()),
            patch.object(httpx.Client, "stream", return_value=_stream_lines(sse_lines)),
        ):
            with pytest.raises(HFSpacesError, match="No image data"):
                HFSpacesImageClient().generate_image("test", output_dir=tmp_path)

    def test_tiny_download_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HF_TOKEN", "hf-test")
        sse_lines = [f"data: {json.dumps([{'url': f'{_SPACE}/img.png'}])}"]

        with (
            patch("httpx.post", return_value=_post_response()),
            patch.object(httpx.Client, "stream", return_value=_stream_lines(sse_lines)),
            patch("httpx.get", return_value=_download_response(b"\x89PNG\r\n" + b"x" * 10)),
        ):
            with pytest.raises(HFSpacesError, match="too small"):
                HFSpacesImageClient().generate_image("test", output_dir=tmp_path)

    def test_creates_output_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HF_TOKEN", "hf-test")
        new_dir = tmp_path / "deep" / "nested"
        img_url = f"{_SPACE}/img.png"
        sse_lines = [f"data: {json.dumps([{'url': img_url}])}"]

        with (
            patch("httpx.post", return_value=_post_response()),
            patch.object(httpx.Client, "stream", return_value=_stream_lines(sse_lines)),
            patch("httpx.get", return_value=_download_response()),
        ):
            HFSpacesImageClient().generate_image("test", output_dir=new_dir)

        assert new_dir.exists()
