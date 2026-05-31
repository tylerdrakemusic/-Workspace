"""Free portrait client — Pollinations.AI photorealistic images with DiceBear fallback.

Primary:  **Pollinations.AI** (https://image.pollinations.ai) — free, keyless,
photorealistic images via the default turbo model.  Returns JPEG, ~1-2 s.

Fallback: **DiceBear** (https://dicebear.com) — deterministic illustrated avatars
when Pollinations is unreachable.  No API key required for either service.

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
_MIN_PHOTOREALISTIC_BYTES = 10_000  # real JPEG; DiceBear SVG-PNGs are ~2-8 KB

# ---------------------------------------------------------------------------
# DiceBear fallback
# ---------------------------------------------------------------------------
_DICEBEAR_STYLE = "lorelei"
_DICEBEAR_BASE = "https://api.dicebear.com/9.x/{style}/png"
_DEFAULT_BG = "0d1a2a"
_DICEBEAR_TIMEOUT = 30
_MIN_IMAGE_BYTES = 512


class PollinationsError(RuntimeError):
    """Raised when all free portrait tiers fail."""


class PollinationsClient:
    """Free portrait client — Pollinations.AI → DiceBear fallback.

    Tries Pollinations.AI first (photorealistic JPEG, ~1-2 s, free, no key).
    If that fails or returns a suspiciously small payload, falls through to
    DiceBear illustrated avatars (always succeeds).

    The public interface is unchanged from before so all portrait generators
    continue to work without modification.
    """

    def generate_image(
        self,
        prompt: str,
        output_dir: Path | str = ".",
        width: int = 1024,
        height: int = 1024,
        seed: int | None = None,
    ) -> Path:
        """Generate a portrait and save it to *output_dir*.

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
            Only if both Pollinations.AI and DiceBear fail.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:12]

        # --- Tier 1: Pollinations.AI photorealistic image ---
        try:
            path = self._pollinations(prompt, output_dir, prompt_hash, width, height, seed)
            if path is not None:
                return path
        except Exception:  # nosec B110
            pass

        # --- Tier 2: DiceBear illustrated avatar ---
        try:
            return self._dicebear(prompt, output_dir, prompt_hash)
        except Exception as exc:  # nosec B110
            raise PollinationsError(f"All free image tiers failed: {exc}") from exc

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
        """Call image.pollinations.ai; return Path on success, None on failure."""
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
            return None  # silently fall through to DiceBear

        ext = "jpg"
        out_path = output_dir / f"pollinations_{prompt_hash}.{ext}"
        out_path.write_bytes(content)
        return out_path

    def _dicebear(self, prompt: str, output_dir: Path, prompt_hash: str) -> Path:
        """Call DiceBear; return Path on success, raise on failure."""
        dicebear_seed = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        base = _DICEBEAR_BASE.format(style=_DICEBEAR_STYLE)
        params = urllib.parse.urlencode({
            "seed": dicebear_seed,
            "size": 512,
            "backgroundColor": _DEFAULT_BG,
        })
        url = f"{base}?{params}"

        req = urllib.request.Request(
            url, headers={"User-Agent": "workspace-portrait-gen/2.0"}
        )
        with urllib.request.urlopen(req, timeout=_DICEBEAR_TIMEOUT) as resp:  # nosec B310
            if resp.status != 200:
                raise PollinationsError(f"HTTP {resp.status} from DiceBear")
            content: bytes = resp.read()

        if len(content) < _MIN_IMAGE_BYTES:
            raise PollinationsError(
                f"DiceBear returned only {len(content)} B — likely an error"
            )

        out_path = output_dir / f"dicebear_{prompt_hash}.png"
        out_path.write_bytes(content)
        return out_path

