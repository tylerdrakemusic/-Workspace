"""Tests for src/integrations/pollinations/client.py — mocked HTTP, no real API calls."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.integrations.pollinations.client import (
    PollinationsClient,
    PollinationsError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_JPEG = b"\xff\xd8\xff\xe0" + b"x" * 20_000   # fake 20KB JPEG header + body
_FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 5_000    # fake DiceBear PNG


def _mock_urlopen(content: bytes, status: int = 200):
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = content
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


# ---------------------------------------------------------------------------
# Pollinations.AI (primary tier) tests
# ---------------------------------------------------------------------------

class TestPollinationsPrimary:
    def test_happy_path_returns_jpg(self, tmp_path: Path) -> None:
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(_FAKE_JPEG)):
            client = PollinationsClient()
            result = client.generate_image("portrait of a scientist", output_dir=tmp_path)
        assert result.exists()
        assert result.suffix == ".jpg"
        assert result.stat().st_size == len(_FAKE_JPEG)

    def test_uses_prompt_hash_in_filename(self, tmp_path: Path) -> None:
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(_FAKE_JPEG)):
            client = PollinationsClient()
            result = client.generate_image("test prompt", output_dir=tmp_path)
        assert "pollinations_" in result.name

    def test_seed_derived_from_prompt_when_none(self, tmp_path: Path) -> None:
        calls = []
        def fake_urlopen(req, timeout):
            calls.append(req.full_url)
            return _mock_urlopen(_FAKE_JPEG)
        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            client = PollinationsClient()
            client.generate_image("deterministic test", output_dir=tmp_path)
        assert "seed=" in calls[0]

    def test_explicit_seed_used(self, tmp_path: Path) -> None:
        calls = []
        def fake_urlopen(req, timeout):
            calls.append(req.full_url)
            return _mock_urlopen(_FAKE_JPEG)
        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            client = PollinationsClient()
            client.generate_image("test", output_dir=tmp_path, seed=12345)
        assert "seed=12345" in calls[0]

    def test_width_height_in_url(self, tmp_path: Path) -> None:
        calls = []
        def fake_urlopen(req, timeout):
            calls.append(req.full_url)
            return _mock_urlopen(_FAKE_JPEG)
        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            client = PollinationsClient()
            client.generate_image("test", output_dir=tmp_path, width=512, height=512)
        assert "width=512" in calls[0]
        assert "height=512" in calls[0]


# ---------------------------------------------------------------------------
# Fallthrough to DiceBear tests
# ---------------------------------------------------------------------------

class TestDiceBearFallback:
    def test_falls_back_on_small_response(self, tmp_path: Path) -> None:
        """Pollinations returning <10KB should fall through to DiceBear."""
        tiny = b"\xff\xd8" + b"x" * 100   # 102 bytes — below _MIN_PHOTOREALISTIC_BYTES
        call_count = [0]

        def fake_urlopen(req, timeout):
            call_count[0] += 1
            if call_count[0] == 1:
                return _mock_urlopen(tiny)   # Pollinations returns tiny
            return _mock_urlopen(_FAKE_PNG)  # DiceBear returns real PNG

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            client = PollinationsClient()
            result = client.generate_image("test prompt", output_dir=tmp_path)

        assert result.exists()
        assert call_count[0] == 2  # both tiers were called
        assert "dicebear_" in result.name

    def test_falls_back_on_network_error(self, tmp_path: Path) -> None:
        call_count = [0]

        def fake_urlopen(req, timeout):
            call_count[0] += 1
            if call_count[0] == 1:
                raise OSError("connection refused")
            return _mock_urlopen(_FAKE_PNG)

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            client = PollinationsClient()
            result = client.generate_image("test prompt", output_dir=tmp_path)

        assert result.exists()
        assert call_count[0] == 2

    def test_raises_if_both_tiers_fail(self, tmp_path: Path) -> None:
        with patch("urllib.request.urlopen", side_effect=OSError("no network")):
            client = PollinationsClient()
            with pytest.raises(PollinationsError):
                client.generate_image("test prompt", output_dir=tmp_path)

    def test_creates_output_dir(self, tmp_path: Path) -> None:
        new_dir = tmp_path / "portraits" / "nested"
        assert not new_dir.exists()
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(_FAKE_JPEG)):
            PollinationsClient().generate_image("test", output_dir=new_dir)
        assert new_dir.exists()
