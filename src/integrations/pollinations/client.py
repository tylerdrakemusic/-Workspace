"""Free image client for Pollinations.AI.

Primary:  **Pollinations.AI** (https://image.pollinations.ai) — free, keyless,
photorealistic images via the default turbo model.  Returns JPEG, ~1-2 s.

Uses only Python stdlib (``urllib``).

Example::

    from src.integrations.pollinations.client import PollinationsClient

    client = PollinationsClient()
    path = client.generate_image(
        "a photorealistic portrait of a scientist",
        output_dir=Path("/tmp"),
    )
"""

from __future__ import annotations

import hashlib
import urllib.parse
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Pollinations.AI
# ---------------------------------------------------------------------------
_POLLINATIONS_BASE = "https://image.pollinations.ai/prompt/{encoded}"
_POLLINATIONS_TIMEOUT = 35
_MIN_PHOTOREALISTIC_BYTES = 10_000


class PollinationsError(RuntimeError):
    """Raised when all free portrait tiers fail."""


class PollinationsClient:
    """Free image client that reports Pollinations failures to its caller."""

    def generate_image(
        self,
        prompt: str,
        output_dir: Path | str = ".",
        width: int = 1024,
        height: int = 1024,
        seed: int | None = None,
    ) -> Path:
        """Generate an image and save it to *output_dir*.

        Parameters
        ----------
        prompt:
            Text description of the desired image.
        output_dir:
            Directory to save the generated image file.  Created if absent.
        width:
            Image width in pixels (Pollinations only; ignored by DiceBear).
        height:
            Image height in pixels (Pollinations only; ignored by DiceBear).
        seed:
            Optional integer seed for reproducibility (Pollinations).
            If None, a deterministic seed derived from the prompt hash is used.

        Returns
        -------
        Path
            Absolute path to the saved image file.

        Raises
        ------
        PollinationsError
            If Pollinations fails or returns an undersized response.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:12]

        try:
            path = self._pollinations(prompt, output_dir, prompt_hash, width, height, seed)
        except Exception as exc:  # nosec B110
            raise PollinationsError(f"Pollinations image generation failed: {exc}") from exc
        if path is None:
            raise PollinationsError("Pollinations returned an undersized image")
        return path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _pollinations(
        self,
        prompt: str,
        output_dir: Path,
        prompt_hash: str,
        width: int,
        height: int,
        seed: int | None,
    ) -> Path | None:
        """Call image.pollinations.ai; return Path on a sufficiently large image."""
        if seed is None:
            seed = int(hashlib.sha256(prompt.encode()).hexdigest()[:8], 16) % (2**31)

        encoded = urllib.parse.quote(prompt)
        params = urllib.parse.urlencode({
            "width": width,
            "height": height,
            "nologo": "true",
            "seed": seed,
        })
        url = _POLLINATIONS_BASE.format(encoded=encoded) + f"?{params}"

        req = urllib.request.Request(
            url, headers={"User-Agent": "workspace-portrait-gen/2.0"}
        )
        with urllib.request.urlopen(req, timeout=_POLLINATIONS_TIMEOUT) as resp:  # nosec B310
            if resp.status != 200:
                return None
            content: bytes = resp.read()

        if len(content) < _MIN_PHOTOREALISTIC_BYTES:
            return None

        ext = "jpg"
        out_path = output_dir / f"pollinations_{prompt_hash}.{ext}"
        out_path.write_bytes(content)
        return out_path

