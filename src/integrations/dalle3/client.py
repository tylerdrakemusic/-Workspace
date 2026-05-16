"""DALL-E 3 image generation client.

Self-contained: reads OPENAPI_TOKEN from environment.
No dependency on any per-project config.

Usage (from any workspace project)::

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(r"f:\\⊕Workspace")))
    from src.integrations.dalle3 import DallE3Client

    client = DallE3Client()
    path = client.generate_image("a professional portrait", size="1024x1024")
    print(path)  # f:\\...\\output\\images\\<sha256>.png
Notes
-----
- ``response_format`` is no longer passed in the request payload — the parameter
  was removed from the OpenAI images API.  The client handles both ``b64_json``
  (current default) and ``url`` (legacy) response shapes automatically."""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path
from typing import Literal

import httpx

DALLE3_URL = "https://api.openai.com/v1/images/generations"
DEFAULT_SIZE: Literal["1024x1024", "1024x1792", "1792x1024"] = "1024x1024"
DEFAULT_QUALITY: Literal["standard", "hd"] = "standard"
DEFAULT_MODEL = "dall-e-3"
REQUEST_TIMEOUT = 60.0  # seconds


class DallE3Error(RuntimeError):
    """Raised when the DALL-E 3 API returns an error or the response is invalid."""


class DallE3Client:
    """Thin wrapper around the OpenAI DALL-E 3 images/generations endpoint.

    API key resolution order:
    1. ``api_key`` constructor argument
    2. ``OPENAPI_TOKEN`` environment variable
    """

    def __init__(self, api_key: str | None = None) -> None:
        resolved = api_key or os.environ.get("OPENAPI_TOKEN", "").strip()
        if not resolved:
            raise EnvironmentError(
                "OpenAI API key not found. "
                "Set the OPENAPI_TOKEN environment variable or pass api_key= explicitly."
            )
        self._api_key = resolved
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
        size: Literal["1024x1024", "1024x1792", "1792x1024"] = DEFAULT_SIZE,
        quality: Literal["standard", "hd"] = DEFAULT_QUALITY,
        model: str = DEFAULT_MODEL,
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
            Image dimensions. DALL-E 3 supports ``1024x1024``,
            ``1024x1792``, and ``1792x1024``.
        quality:
            ``"standard"`` or ``"hd"`` (costs 2× tokens).
        model:
            Model to use. Defaults to ``"dall-e-3"``.

        Returns
        -------
        Path
            Absolute path to the saved PNG file.

        Raises
        ------
        DallE3Error
            On API error, unexpected response shape, or download failure.
        """
        save_dir = output_dir or (Path.cwd() / "output" / "images")
        save_dir.mkdir(parents=True, exist_ok=True)

        payload = {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "size": size,
            "quality": quality,
            # response_format is intentionally omitted — the parameter was removed
            # from the OpenAI images API.  We handle both b64_json and url below.
        }

        try:
            with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
                resp = client.post(DALLE3_URL, json=payload, headers=self._headers)
        except httpx.RequestError as exc:
            raise DallE3Error(f"Network error calling DALL-E 3: {exc}") from exc

        if resp.status_code != 200:
            raise DallE3Error(
                f"DALL-E 3 API error {resp.status_code}: {resp.text[:400]}"
            )

        data = resp.json()
        try:
            item: dict = data["data"][0]
        except (KeyError, IndexError) as exc:
            raise DallE3Error(
                f"Unexpected DALL-E 3 response shape: {data}"
            ) from exc

        # Handle b64_json (current API default) and url (legacy) transparently.
        if "b64_json" in item:
            content = base64.b64decode(item["b64_json"])
            return self._save_image(content, prompt, save_dir)
        elif "url" in item:
            return self._download_image(item["url"], save_dir, prompt)
        else:
            raise DallE3Error(f"Unexpected DALL-E 3 response item shape: {item}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _save_image(self, content: bytes, prompt: str, save_dir: Path) -> Path:
        """Save *content* to *save_dir* using a content-addressed filename."""
        digest = hashlib.sha256(prompt.encode() + content[:64]).hexdigest()[:16]
        out_path = save_dir / f"{digest}.png"
        out_path.write_bytes(content)
        return out_path

    def _download_image(self, url: str, save_dir: Path, prompt: str) -> Path:
        """Download *url* and save to *save_dir* using a content-addressed filename.

        Used when the API returns a URL instead of inline b64_json bytes.
        """
        try:
            with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
                resp = client.get(url)
        except httpx.RequestError as exc:
            raise DallE3Error(f"Failed to download image from DALL-E 3: {exc}") from exc

        if resp.status_code != 200:
            raise DallE3Error(
                f"Image download failed {resp.status_code}: {url}"
            )

        return self._save_image(resp.content, prompt, save_dir)
