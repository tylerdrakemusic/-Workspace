"""Reusable ordered image-generation cascade for arbitrary prompts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable


ImageGenerator = Callable[..., Path]


@dataclass(frozen=True)
class ImageProvider:
    """One image provider and its model-specific generation callable."""

    name: str
    model: str
    generate: ImageGenerator


@dataclass(frozen=True)
class ImageProviderDiagnostic:
    """Failure details from one provider attempt."""

    provider: str
    model: str
    error: str


@dataclass(frozen=True)
class ImageGenerationResult:
    """Successful image path, provenance, and preceding provider failures."""

    path: Path
    provider: str
    model: str
    diagnostics: tuple[ImageProviderDiagnostic, ...]


class ImageGenerationError(RuntimeError):
    """Raised when every configured image provider fails."""

    def __init__(self, diagnostics: tuple[ImageProviderDiagnostic, ...]) -> None:
        self.diagnostics = diagnostics
        super().__init__("All image providers failed")


class ImageGenerationCascade:
    """Try injected providers in order and return the first generated image."""

    def __init__(self, providers: tuple[ImageProvider, ...]) -> None:
        if not providers:
            raise ValueError("at least one image provider is required")
        self.providers = providers

    def generate(
        self, prompt: str, *, output_dir: Path | None = None
    ) -> ImageGenerationResult:
        """Generate an image from *prompt* using the first successful provider."""
        if not prompt.strip():
            raise ValueError("prompt must not be empty")
        diagnostics: list[ImageProviderDiagnostic] = []
        for provider in self.providers:
            try:
                path = provider.generate(prompt, output_dir=output_dir)
            except Exception as exc:
                diagnostics.append(
                    ImageProviderDiagnostic(provider.name, provider.model, str(exc))
                )
                continue
            return ImageGenerationResult(
                path=path,
                provider=provider.name,
                model=provider.model,
                diagnostics=tuple(diagnostics),
            )
        raise ImageGenerationError(tuple(diagnostics))


def default_image_cascade() -> ImageGenerationCascade:
    """Build the Workspace provider sequence with clients created on demand."""
    from .dalle3.client import DEFAULT_MODEL, DallE3Client
    from .huggingface.client import DEFAULT_MODEL_ID, HuggingFaceImageClient
    from .pollinations.client import PollinationsClient

    def generate_openai(prompt: str, *, output_dir: Path | None) -> Path:
        return DallE3Client().generate_image(prompt, output_dir=output_dir)

    def generate_huggingface(prompt: str, *, output_dir: Path | None) -> Path:
        return HuggingFaceImageClient().generate_image(prompt, output_dir=output_dir)

    def generate_pollinations(prompt: str, *, output_dir: Path | None) -> Path:
        return PollinationsClient().generate_image(prompt, output_dir=output_dir or ".")

    return ImageGenerationCascade(
        (
            ImageProvider("openai", DEFAULT_MODEL, generate_openai),
            ImageProvider("huggingface", DEFAULT_MODEL_ID, generate_huggingface),
            ImageProvider("pollinations", "default", generate_pollinations),
        )
    )