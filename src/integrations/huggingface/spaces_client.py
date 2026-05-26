"""HuggingFace Spaces image client — FLUX.1-schnell via Gradio REST API.

Calls the public ``black-forest-labs/FLUX.1-schnell`` HuggingFace Space
using the Gradio 4.x REST API (POST + SSE stream).  No ``gradio_client``
dependency — uses only ``httpx`` which is already a workspace dep.

This tier sits between the paid HF Inference API and Pollinations.AI in the
portrait generation cascade.  The space runs on ZeroGPU (``zero-a10g``);
calls succeed when the account has ZeroGPU quota (HF Pro or granted access).
When quota is exhausted the space returns ``event: error`` and this client
raises ``HFSpacesError`` so the cascade falls through to Pollinations.AI.

Usage::

    from src.integrations.huggingface.spaces_client import HFSpacesImageClient

    client = HFSpacesImageClient()
    path = client.generate_image(
        "A photorealistic portrait of a scientist",
        output_dir=Path("/tmp"),
    )
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import httpx

_SPACE_BASE = "https://black-forest-labs-flux-1-schnell.hf.space"
_INFER_ENDPOINT = "/gradio_api/call/infer"
_DEFAULT_STEPS = 4
_SUBMIT_TIMEOUT = 20      # seconds to submit the job
_STREAM_TIMEOUT = 90      # seconds to stream the result (generation ~5-30s on ZeroGPU)
_MIN_IMAGE_BYTES = 10_000


class HFSpacesError(RuntimeError):
    """Raised when the HF Spaces call fails or quota is exhausted."""


class HFSpacesImageClient:
    """Generate images via HuggingFace Spaces FLUX.1-schnell (Gradio REST API).

    Reads ``HF_TOKEN`` from environment for ZeroGPU authentication.
    Fails fast (raises ``HFSpacesError``) when the space returns an error,
    allowing the caller to fall through to the next cascade tier.
    """

    def __init__(self, space_base: str = _SPACE_BASE) -> None:
        self._space_base = space_base.rstrip("/")
        self._token = os.environ.get("HF_TOKEN", "")

    def generate_image(
        self,
        prompt: str,
        output_dir: Path | str = ".",
        width: int = 1024,
        height: int = 1024,
        seed: int | None = None,
        num_inference_steps: int = _DEFAULT_STEPS,
    ) -> Path:
        """Generate an image and save it to *output_dir*.

        Parameters
        ----------
        prompt:
            Text description of the desired image.
        output_dir:
            Directory to save the generated image.  Created if absent.
        width / height:
            Output dimensions.  Default 1024×1024.
        seed:
            Deterministic seed.  Derived from prompt hash if not provided.
        num_inference_steps:
            FLUX.1-schnell quality / speed trade-off (4 is the sweet spot).

        Returns
        -------
        Path
            Absolute path to the saved PNG.

        Raises
        ------
        HFSpacesError
            On network error, ZeroGPU quota exhausted, or missing image data.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if seed is None:
            seed = int(hashlib.sha256(prompt.encode()).hexdigest()[:8], 16) % (2**31)

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._token:
            headers["HF-Token"] = self._token

        # --- Step 1: submit job ---
        payload = {
            "data": [prompt, seed, False, width, height, num_inference_steps]
        }
        try:
            resp = httpx.post(
                f"{self._space_base}{_INFER_ENDPOINT}",
                json=payload,
                headers=headers,
                timeout=_SUBMIT_TIMEOUT,
                follow_redirects=True,
            )
        except httpx.RequestError as exc:
            raise HFSpacesError(f"Network error submitting job: {exc}") from exc

        if resp.status_code != 200:
            raise HFSpacesError(
                f"Job submission failed: HTTP {resp.status_code} — {resp.text[:200]}"
            )

        event_id = resp.json().get("event_id")
        if not event_id:
            raise HFSpacesError("No event_id in submission response")

        # --- Step 2: stream result via SSE ---
        img_url: str | None = None
        img_bytes: bytes | None = None

        stream_headers = dict(headers)
        stream_headers.pop("Content-Type", None)

        try:
            with httpx.Client(timeout=_STREAM_TIMEOUT, follow_redirects=True) as client:
                with client.stream(
                    "GET",
                    f"{self._space_base}{_INFER_ENDPOINT}/{event_id}",
                    headers=stream_headers,
                ) as stream:
                    for line in stream.iter_lines():
                        if not line.strip():
                            continue
                        if line == "event: error":
                            raise HFSpacesError(
                                "ZeroGPU quota exhausted or space error (event: error)"
                            )
                        if line.startswith("data:"):
                            data_str = line[5:].strip()
                            try:
                                data = json.loads(data_str)
                            except json.JSONDecodeError:
                                continue
                            if isinstance(data, list) and data:
                                item = data[0]
                                if isinstance(item, dict):
                                    img_url = item.get("url") or item.get("path")
                                elif isinstance(item, str) and "data:image" in item:
                                    import base64
                                    _, b64 = item.split(",", 1)
                                    img_bytes = base64.b64decode(b64)
                            break
        except HFSpacesError:
            raise
        except httpx.RequestError as exc:
            raise HFSpacesError(f"Stream error: {exc}") from exc

        # --- Step 3: save result ---
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:12]
        out_path = output_dir / f"hf_spaces_{prompt_hash}.png"

        if img_bytes:
            if len(img_bytes) < _MIN_IMAGE_BYTES:
                raise HFSpacesError(f"Image too small ({len(img_bytes)} B)")
            out_path.write_bytes(img_bytes)
            return out_path

        if img_url:
            full_url = (
                img_url if img_url.startswith("http")
                else f"{self._space_base}/{img_url.lstrip('/')}"
            )
            try:
                dl = httpx.get(full_url, timeout=30, follow_redirects=True)
            except httpx.RequestError as exc:
                raise HFSpacesError(f"Download error: {exc}") from exc
            if dl.status_code != 200:
                raise HFSpacesError(f"Image download HTTP {dl.status_code}")
            if len(dl.content) < _MIN_IMAGE_BYTES:
                raise HFSpacesError(f"Downloaded image too small ({len(dl.content)} B)")
            out_path.write_bytes(dl.content)
            return out_path

        raise HFSpacesError("No image data in space response")
