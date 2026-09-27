from __future__ import annotations

from pathlib import Path

import pytest

from src.integrations.image_cascade import (
    ImageGenerationCascade,
    ImageGenerationError,
    ImageProvider,
    default_image_cascade,
)


def test_cascade_returns_first_success_with_provider_provenance(tmp_path: Path) -> None:
    calls: list[str] = []
    first_path = tmp_path / "first.png"

    def first_provider(prompt: str, *, output_dir: Path | None) -> Path:
        calls.append(prompt)
        first_path.write_bytes(b"first image")
        return first_path

    def later_provider(prompt: str, *, output_dir: Path | None) -> Path:
        calls.append("later")
        raise AssertionError("providers after the first success must not run")

    cascade = ImageGenerationCascade(
        (
            ImageProvider("openai", "gpt-image-1", first_provider),
            ImageProvider("huggingface", "flux-schnell", later_provider),
        )
    )

    result = cascade.generate("an arbitrary prompt", output_dir=tmp_path)

    assert result.path == first_path
    assert result.provider == "openai"
    assert result.model == "gpt-image-1"
    assert result.diagnostics == ()
    assert calls == ["an arbitrary prompt"]


def test_cascade_records_failed_provider_before_next_success(tmp_path: Path) -> None:
    image_path = tmp_path / "recovered.png"

    def unavailable(prompt: str, *, output_dir: Path | None) -> Path:
        raise RuntimeError("provider offline")

    def available(prompt: str, *, output_dir: Path | None) -> Path:
        image_path.write_bytes(b"recovered image")
        return image_path

    cascade = ImageGenerationCascade(
        (
            ImageProvider("openai", "gpt-image-1", unavailable),
            ImageProvider("huggingface", "flux-schnell", available),
        )
    )

    result = cascade.generate("a landscape", output_dir=tmp_path)

    assert result.path == image_path
    assert result.provider == "huggingface"
    assert result.model == "flux-schnell"
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].provider == "openai"
    assert result.diagnostics[0].model == "gpt-image-1"
    assert result.diagnostics[0].error == "provider offline"


def test_total_failure_exposes_ordered_provider_diagnostics(tmp_path: Path) -> None:
    cascade = ImageGenerationCascade(
        (
            ImageProvider(
                "openai", "gpt-image-1",
                lambda prompt, *, output_dir: (_ for _ in ()).throw(RuntimeError("rate limited")),
            ),
            ImageProvider(
                "pollinations", "default",
                lambda prompt, *, output_dir: (_ for _ in ()).throw(RuntimeError("timeout")),
            ),
        )
    )

    with pytest.raises(ImageGenerationError) as caught:
        cascade.generate("a city at dusk", output_dir=tmp_path)

    assert [(item.provider, item.model, item.error) for item in caught.value.diagnostics] == [
        ("openai", "gpt-image-1", "rate limited"),
        ("pollinations", "default", "timeout"),
    ]


def test_default_cascade_preserves_provider_order_and_model_provenance(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[str] = []
    image_path = tmp_path / "huggingface.png"

    class FakeOpenAI:
        def generate_image(self, prompt: str, *, output_dir: Path | None) -> Path:
            calls.append("openai")
            raise RuntimeError("rate limited")

    class FakeHuggingFace:
        def generate_image(self, prompt: str, *, output_dir: Path | None) -> Path:
            calls.append("huggingface")
            image_path.write_bytes(b"image")
            return image_path

    class FakePollinations:
        def generate_image(self, prompt: str, *, output_dir: Path | None) -> Path:
            calls.append("pollinations")
            raise AssertionError("later providers must not run after success")

    monkeypatch.setattr("src.integrations.dalle3.client.DallE3Client", FakeOpenAI)
    monkeypatch.setattr(
        "src.integrations.huggingface.client.HuggingFaceImageClient", FakeHuggingFace
    )
    monkeypatch.setattr(
        "src.integrations.pollinations.client.PollinationsClient", FakePollinations
    )

    result = default_image_cascade().generate("a mountain at dawn", output_dir=tmp_path)

    assert calls == ["openai", "huggingface"]
    assert result.provider == "huggingface"
    assert result.model == "black-forest-labs/FLUX.1-Krea-dev"
    assert result.diagnostics[0].provider == "openai"
    assert result.diagnostics[0].model == "gpt-image-1"