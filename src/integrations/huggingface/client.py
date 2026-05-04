"""HuggingFace Inference API image generation client.

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
- Default model: ``black-forest-labs/FLUX.1-schnell`` via the HuggingFace router.
  Fast (~5 s); no cold-start penalty.
- API base changed from ``api-inference.huggingface.co/models`` to
  ``router.huggingface.co/hf-inference/models`` (the old path returns 404).
- ``size`` is parsed from ``"WxH"`` string to ``{"width": W, "height": H}``
  as expected by the HuggingFace Inference payload.
- Model ID is constructor-injectable for easy swap to other models.
- ``negative_prompt`` is accepted by ``generate_image`` and forwarded in
  ``parameters`` when the model supports it.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import httpx

DEFAULT_MODEL_ID = "black-forest-labs/FLUX.1-schnell"
HF_INFERENCE_BASE = "https://router.huggingface.co/hf-inference/models"
REQUEST_TIMEOUT = 60.0  # FLUX.1-schnell typically completes in 5-15 s
DEFAULT_SIZE = "1024x1024"


class HuggingFaceImageError(RuntimeError):
    """Raised when the HuggingFace Inference API returns an error."""


class HuggingFaceImageClient:
    """Thin wrapper around the HuggingFace Inference API for image generation.

    API key resolution order:
    1. ``api_key`` constructor argument
    2. ``HF_TOKEN`` environment variable

    Parameters
    ----------
    model_id:
        HuggingFace model ID to use for inference. Defaults to SDXL.
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
                "Set the HF_TOKEN environment variable or pass api_key= explicitly."
            )
        self._api_key = resolved
        self._model_id = model_id
        self._headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

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
        url = f"{HF_INFERENCE_BASE}/{self._model_id}"
        parameters: dict = {"width": width, "height": height}
        if negative_prompt:
            parameters["negative_prompt"] = negative_prompt
        payload = {
            "inputs": prompt,
            "parameters": parameters,
        }

        try:
            with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
                resp = client.post(url, json=payload, headers=self._headers)
        except httpx.RequestError as exc:
            raise HuggingFaceImageError(
                f"Network error calling HuggingFace Inference API: {exc}"
            ) from exc

        if resp.status_code != 200:
            raise HuggingFaceImageError(
                f"HuggingFace API error {resp.status_code}: {resp.text[:400]}"
            )

        content = resp.content
        if not content:
            raise HuggingFaceImageError("HuggingFace API returned empty response body.")

        return self._save_image(content, prompt, save_dir)

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
