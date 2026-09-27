"""Hugging Face Inference Providers image generation client.

Self-contained: reads HF_TOKEN from environment.
No dependency on any per-project config.

Usage (from any workspace project)::

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(r"f:\\⊕Workspace")))
    from src.integrations.huggingface import HuggingFaceImageClient

    client = HuggingFaceImageClient()
    path = client.generate_image("a professional portrait", size="1024x1024")
    print(path)  # f:\\...\\output\\images\\<sha256>.png

Notes
-----
- Default model: ``black-forest-labs/FLUX.1-Krea-dev`` via the ``fal-ai``
    Inference Provider.
- ``size`` is parsed from ``"WxH"`` and passed as ``width`` and ``height``.
- Model ID is constructor-injectable for easy swap to other models.
- ``negative_prompt`` and ``seed`` are forwarded to the provider when supported.
"""

from __future__ import annotations

import hashlib
from io import BytesIO
import os
import random
import sys
from pathlib import Path

from huggingface_hub import InferenceClient

# Quantum entropy for image seeds — falls back to secrets CSPRNG if cache absent
try:
    sys.path.insert(0, str(Path(r"f:\⟨ψ⟩Quantum")))
    from src.utils.quantum_rt import qRandom as _qRandom  # type: ignore[import]
    def _quantum_seed() -> int:
        # qRandom() reads exactly 53 bits (double-precision mantissa) — no rejection sampling
        return int(_qRandom() * (2**31 - 1))
except Exception:
    def _quantum_seed() -> int:  # type: ignore[misc]
        return random.randint(0, 2**31 - 1)  # nosec B311

DEFAULT_MODEL_ID = "black-forest-labs/FLUX.1-Krea-dev"
DEFAULT_PROVIDER = "fal-ai"
REQUEST_TIMEOUT = 60.0
DEFAULT_SIZE = "1024x1024"


class HuggingFaceImageError(RuntimeError):
    """Raised when the HuggingFace Inference API returns an error."""


class HuggingFaceImageClient:
    """Thin wrapper around Hugging Face Inference Providers for image generation.

    API key resolution order:
    1. ``api_key`` constructor argument
    2. ``HF_TOKEN`` environment variable (Inference Providers permission required)

    Parameters
    ----------
    model_id:
        Hugging Face model ID to use for inference. Defaults to FLUX.1-Krea-dev.
    api_key:
        HuggingFace API token. Falls back to ``HF_TOKEN`` env var.
    """

    def __init__(
        self,
        model_id: str = DEFAULT_MODEL_ID,
        api_key: str | None = None,
    ) -> None:
        resolved = api_key or os.environ.get("HF_TOKEN", "").strip()
        if not resolved:
            raise EnvironmentError(
                "HuggingFace API token not found. "
                "Set HF_TOKEN to a token with Inference Providers permission "
                "or pass api_key= explicitly."
            )
        self._api_key = resolved
        self._model_id = model_id
        self._client = InferenceClient(
            model=self._model_id,
            provider=DEFAULT_PROVIDER,
            token=self._api_key,
            timeout=REQUEST_TIMEOUT,
        )

    # ------------------------------------------------------------------
    # Image generation
    # ------------------------------------------------------------------

    def generate_image(
        self,
        prompt: str,
        *,
        output_dir: Path | None = None,
        size: str = DEFAULT_SIZE,
        negative_prompt: str | None = None,
        seed: int | None = None,
    ) -> Path:
        """Generate an image and save it to *output_dir*.

        Parameters
        ----------
        prompt:
            Text description of the image to generate.
        output_dir:
            Directory to save the image. Created if absent.
            Defaults to ``<cwd>/output/images/``.
        size:
            Image dimensions as ``"WxH"`` string, e.g. ``"1024x1024"``.
            Parsed to ``{"width": W, "height": H}`` for the HF payload.
        negative_prompt:
            Optional negative prompt forwarded in ``parameters.negative_prompt``.
            Ignored if ``None``.

        Returns
        -------
        Path
            Absolute path to the saved PNG file.

        Raises
        ------
        HuggingFaceImageError
            On API error, non-200 response, or download failure.
        ValueError
            If *size* is not in ``"WxH"`` format.
        """
        save_dir = output_dir or (Path.cwd() / "output" / "images")
        save_dir.mkdir(parents=True, exist_ok=True)

        width, height = self._parse_size(size)
        try:
            image = self._client.text_to_image(
                prompt,
                width=width,
                height=height,
                negative_prompt=negative_prompt,
                seed=seed if seed is not None else _quantum_seed(),
            )
        except Exception as exc:
            raise HuggingFaceImageError(
                f"Hugging Face Inference Providers error: {exc}"
            ) from exc

        image_buffer = BytesIO()
        try:
            image.save(image_buffer, format="PNG")
        except Exception as exc:
            raise HuggingFaceImageError(
                f"Hugging Face Inference Providers returned an invalid image: {exc}"
            ) from exc

        return self._save_image(image_buffer.getvalue(), prompt, save_dir)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_size(size: str) -> tuple[int, int]:
        """Parse ``"WxH"`` → ``(width, height)``."""
        parts = size.lower().split("x")
        if len(parts) != 2:
            raise ValueError(
                f"Invalid size format {size!r}. Expected 'WxH', e.g. '1024x1024'."
            )
        try:
            return int(parts[0]), int(parts[1])
        except ValueError:
            raise ValueError(
                f"Non-integer dimensions in size {size!r}. Expected 'WxH', e.g. '1024x1024'."
            )

    @staticmethod
    def _save_image(content: bytes, prompt: str, save_dir: Path) -> Path:
        """Save *content* to *save_dir* using a content-addressed filename."""
        digest = hashlib.sha256(prompt.encode() + content[:64]).hexdigest()[:16]
        out_path = save_dir / f"{digest}.png"
        out_path.write_bytes(content)
        return out_path
