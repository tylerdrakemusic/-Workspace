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
    accepts_negative_prompt: bool = False


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
        self,
        prompt: str,
        *,
        output_dir: Path | None = None,
        negative_prompt: str | None = None,
    ) -> ImageGenerationResult:
        """Generate an image from *prompt* using the first successful provider."""
        if not prompt.strip():
            raise ValueError("prompt must not be empty")
        diagnostics: list[ImageProviderDiagnostic] = []
        for provider in self.providers:
            try:
                if provider.accepts_negative_prompt:
                    path = provider.generate(
                        prompt, output_dir=output_dir, negative_prompt=negative_prompt
                    )
                else:
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


def portrait_image_cascade(persona_svg: Path | str) -> ImageGenerationCascade:
    """Build the portrait-specific provider sequence with a local SVG fallback."""
    from .huggingface.client import DEFAULT_MODEL_ID, HuggingFaceImageClient
    from .huggingface.spaces_client import HFSpacesImageClient
    from .pollinations.client import PollinationsClient

    svg_path = Path(persona_svg)

    def generate_huggingface(
        prompt: str,
        *,
        output_dir: Path | None,
        negative_prompt: str | None,
    ) -> Path:
        return HuggingFaceImageClient().generate_image(
            prompt, output_dir=output_dir, negative_prompt=negative_prompt
        )

    def generate_hf_spaces(prompt: str, *, output_dir: Path | None) -> Path:
        return HFSpacesImageClient().generate_image(
            prompt, output_dir=output_dir or "."
        )

    def generate_pollinations(prompt: str, *, output_dir: Path | None) -> Path:
        return PollinationsClient().generate_image(prompt, output_dir=output_dir or ".")

    def use_persona_svg(prompt: str, *, output_dir: Path | None) -> Path:
        if svg_path.suffix.lower() != ".svg" or not svg_path.is_file():
            raise FileNotFoundError(f"persona SVG is unavailable: {svg_path}")
        return svg_path

    return ImageGenerationCascade(
        (
            ImageProvider(
                "huggingface", DEFAULT_MODEL_ID, generate_huggingface,
                accepts_negative_prompt=True,
            ),
            ImageProvider("hf_spaces", "black-forest-labs/FLUX.1-schnell", generate_hf_spaces),
            ImageProvider("pollinations", "default", generate_pollinations),
            ImageProvider("persona_svg", svg_path.stem, use_persona_svg),
        )
    )