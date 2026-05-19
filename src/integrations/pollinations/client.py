"""Free portrait fallback client — DiceBear illustrated avatars.

Pollinations.AI moved to a paid model in 2026.  This module now uses the
**DiceBear** API (https://dicebear.com) as the free, keyless fallback for
portrait generation.  DiceBear generates deterministic illustrated avatars
from a text seed; not photorealistic, but far better than a silhouette.

No account, no credits, no token required.  Uses only Python stdlib
(``urllib``).

Example::

    from src.integrations.pollinations.client import PollinationsClient

    client = PollinationsClient()
    path = client.generate_image(
        "a portrait of a scientist",
        output_dir=Path("/tmp"),
    )
"""

from __future__ import annotations

import hashlib
import urllib.parse
import urllib.request
from pathlib import Path

# DiceBear style that produces portrait-like illustrated characters.
_DICEBEAR_STYLE = "lorelei"
_DICEBEAR_BASE = "https://api.dicebear.com/9.x/{style}/png"
_DEFAULT_BG = "0d1a2a"  # dark navy — matches workspace dashboard aesthetic
_TIMEOUT_SECONDS = 30
_MIN_IMAGE_BYTES = 512


class PollinationsError(RuntimeError):
    """Raised when the free portrait API call fails."""


class PollinationsClient:
    """Free portrait client backed by DiceBear (https://dicebear.com).

    The public interface mirrors the original Pollinations.AI client so
    portrait generators do not need updating.  Internally calls DiceBear,
    deriving a deterministic seed from the prompt hash so the same prompt
    always produces the same avatar.

    Uses only Python stdlib.  No API key required.
    """

    def generate_image(
        self,
        prompt: str,
        output_dir: Path | str = ".",
        width: int = 1024,
        height: int = 1024,
        seed: int | None = None,  # kept for interface compat; DiceBear uses str seed
    ) -> Path:
        """Generate a portrait avatar and save it to *output_dir*.

        Parameters
        ----------
        prompt:
            Text description (used to derive a deterministic DiceBear seed).
        output_dir:
            Directory to save the generated image file.  Created if absent.
        width:
            Ignored (DiceBear returns SVG-rasterised PNGs; all sizes equal).
        height:
            Ignored (see *width*).
        seed:
            Ignored (seed derived from *prompt* hash for determinism).

        Returns
        -------
        Path
            Absolute path to the saved PNG image file.

        Raises
        ------
        PollinationsError
            On network error, non-200 HTTP response, or suspiciously small
            payload.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Derive a stable short string seed from the prompt so each persona
        # always gets the same illustrated avatar.
        dicebear_seed = hashlib.sha256(prompt.encode()).hexdigest()[:16]

        base = _DICEBEAR_BASE.format(style=_DICEBEAR_STYLE)
        params = urllib.parse.urlencode({
            "seed": dicebear_seed,
            "size": 512,
            "backgroundColor": _DEFAULT_BG,
        })
        url = f"{base}?{params}"

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "workspace-portrait-gen/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:
                if resp.status != 200:
                    raise PollinationsError(
                        f"HTTP {resp.status} from DiceBear"
                    )
                content: bytes = resp.read()
        except OSError as exc:
            raise PollinationsError(f"Network error contacting DiceBear: {exc}") from exc

        if len(content) < _MIN_IMAGE_BYTES:
            raise PollinationsError(
                f"Response only {len(content)} B — likely an error, not an image"
            )

        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:12]
        out_path = output_dir / f"dicebear_{prompt_hash}.png"
        out_path.write_bytes(content)
        return out_path

