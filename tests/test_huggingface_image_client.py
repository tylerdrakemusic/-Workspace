"""Tests for src/integrations/huggingface/client.py — mocked HTTP, no real API calls."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

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


def _mock_image(size: tuple[int, int] = (16, 16)) -> Image.Image:
    return Image.new("RGB", size, "black")


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


def test_default_generation_uses_live_krea_model_through_fal_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from src.integrations.huggingface import client as huggingface_client

    captured: dict[str, object] = {}

    class FakeInferenceClient:
        def __init__(
            self,
            *,
            model: str,
            provider: str,
            token: str,
            timeout: float,
        ) -> None:
            captured["client_args"] = {
                "model": model,
                "provider": provider,
                "token": token,
                "timeout": timeout,
            }

        def text_to_image(
            self,
            prompt: str,
            *,
            width: int,
            height: int,
            negative_prompt: str | None,
            seed: int,
        ) -> Image.Image:
            captured["generation_args"] = {
                "prompt": prompt,
                "width": width,
                "height": height,
                "negative_prompt": negative_prompt,
                "seed": seed,
            }
            return Image.new("RGB", (width, height), "black")

    monkeypatch.setattr(
        huggingface_client,
        "InferenceClient",
        FakeInferenceClient,
        raising=False,
    )
    monkeypatch.setenv("HF_TOKEN", "hf-test-token")

    result = HuggingFaceImageClient().generate_image(
        "print-ready guitar artwork",
        output_dir=tmp_path,
        seed=17,
    )

    assert captured.get("client_args") == {
        "model": "black-forest-labs/FLUX.1-Krea-dev",
        "provider": "fal-ai",
        "token": "hf-test-token",
        "timeout": 60.0,
    }
    assert captured.get("generation_args") == {
        "prompt": "print-ready guitar artwork",
        "width": 1024,
        "height": 1024,
        "negative_prompt": None,
        "seed": 17,
    }
    with Image.open(result) as generated_image:
        assert generated_image.size == (1024, 1024)


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
    with patch.object(client._client, "text_to_image", return_value=_mock_image()):
        result = client.generate_image("a test portrait", output_dir=tmp_path)

    assert isinstance(result, Path)
    assert result.suffix == ".png"
    assert result.exists()
    with Image.open(result) as generated_image:
        assert generated_image.size == (16, 16)


def test_generate_image_creates_output_dir(client: HuggingFaceImageClient, tmp_path: Path) -> None:
    new_dir = tmp_path / "nested" / "output"
    with patch.object(client._client, "text_to_image", return_value=_mock_image()):
        client.generate_image("portrait", output_dir=new_dir)

    assert new_dir.exists()


def test_generate_image_sends_correct_payload(client: HuggingFaceImageClient, tmp_path: Path) -> None:
    with patch.object(
        client._client,
        "text_to_image",
        return_value=_mock_image((512, 768)),
    ) as generate_image:
        client.generate_image("a portrait", size="512x768", output_dir=tmp_path, seed=42)

    generate_image.assert_called_once_with(
        "a portrait",
        width=512,
        height=768,
        negative_prompt=None,
        seed=42,
    )


def test_generate_image_content_addressed(client: HuggingFaceImageClient, tmp_path: Path) -> None:
    with patch.object(
        client._client,
        "text_to_image",
        return_value=_mock_image((8, 8)),
    ):
        p1 = client.generate_image("same prompt", output_dir=tmp_path)
        p2 = client.generate_image("same prompt", output_dir=tmp_path)

    assert p1.name == p2.name


# ---------------------------------------------------------------------------
# generate_image — error paths
# ---------------------------------------------------------------------------

def test_provider_error_raises(client: HuggingFaceImageClient, tmp_path: Path) -> None:
    with patch.object(
        client._client,
        "text_to_image",
        side_effect=RuntimeError("provider unavailable"),
    ):
        with pytest.raises(HuggingFaceImageError, match="provider unavailable"):
            client.generate_image("test", output_dir=tmp_path)


def test_empty_response_raises(client: HuggingFaceImageClient, tmp_path: Path) -> None:
    with patch.object(client._client, "text_to_image", return_value=None):
        with pytest.raises(HuggingFaceImageError, match="invalid image"):
            client.generate_image("test", output_dir=tmp_path)


def test_inference_provider_error_raises(
    client: HuggingFaceImageClient, tmp_path: Path
) -> None:
    with patch.object(
        client._client,
        "text_to_image",
        side_effect=RuntimeError("connection refused"),
    ):
        with pytest.raises(HuggingFaceImageError, match="Inference Providers error"):
            client.generate_image("test", output_dir=tmp_path)
