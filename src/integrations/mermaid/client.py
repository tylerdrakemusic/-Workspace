"""Mermaid renderer — local `mmdc` CLI preferred, mermaid.ink HTTP fallback.

No API key required. Both back-ends are free.

Usage:
    from integrations.mermaid import MermaidClient
    client = MermaidClient()
    svg_bytes = client.render(mmd_source)
"""

from __future__ import annotations

import base64
import shutil
import subprocess  # nosec B404
import tempfile
import zlib
from pathlib import Path
from typing import Literal

import urllib.request
import urllib.error
import urllib.parse


class MermaidRenderError(RuntimeError):
    """Raised when neither the local CLI nor the HTTP fallback can render."""


class MermaidClient:
    """Render mermaid diagrams to SVG.

    Strategy: try local `mmdc` (Node CLI from `@mermaid-js/mermaid-cli`)
    first; on any failure (not installed, exit non-zero, timeout) fall
    back to the public mermaid.ink HTTP service.
    """

    HTTP_BASE = "https://mermaid.ink"
    CLI_TIMEOUT_SEC = 30
    HTTP_TIMEOUT_SEC = 30

    def __init__(
        self,
        mmdc_path: str | None = None,
        http_base: str | None = None,
        prefer: Literal["cli", "http"] = "cli",
    ) -> None:
        self.mmdc_path = mmdc_path or self._discover_mmdc()
        self.http_base = http_base or self.HTTP_BASE
        self.prefer = prefer

    # ── public API ───────────────────────────────────────────────

    def render(self, source: str, fmt: str = "svg") -> bytes:
        """Render mermaid `source` to `fmt` (svg or png). Returns raw bytes."""
        if fmt not in ("svg", "png"):
            raise ValueError(f"Unsupported format: {fmt!r} (use 'svg' or 'png')")

        order = ["cli", "http"] if self.prefer == "cli" else ["http", "cli"]
        errors: list[str] = []

        for backend in order:
            try:
                if backend == "cli":
                    if not self.mmdc_path:
                        errors.append("cli: mmdc not on PATH")
                        continue
                    return self._render_cli(source, fmt)
                else:
                    return self._render_http(source, fmt)
            except Exception as exc:  # noqa: BLE001 — surface all backend errors
                errors.append(f"{backend}: {exc}")

        raise MermaidRenderError("All mermaid backends failed: " + " | ".join(errors))

    def cli_available(self) -> bool:
        return bool(self.mmdc_path)

    # ── backends ─────────────────────────────────────────────────

    def _render_cli(self, source: str, fmt: str) -> bytes:
        with tempfile.TemporaryDirectory() as td:
            in_path = Path(td) / f"in.mmd"
            out_path = Path(td) / f"out.{fmt}"
            in_path.write_text(source, encoding="utf-8")
            cmd = [
                self.mmdc_path,
                "-i", str(in_path),
                "-o", str(out_path),
                "-b", "transparent",
            ]
            proc = subprocess.run(  # nosec B603
                cmd,
                capture_output=True,
                text=True,
                timeout=self.CLI_TIMEOUT_SEC,
            )
            if proc.returncode != 0:
                raise MermaidRenderError(
                    f"mmdc exit={proc.returncode}: {proc.stderr.strip()[:200]}"
                )
            if not out_path.exists():
                raise MermaidRenderError("mmdc produced no output")
            return out_path.read_bytes()

    def _render_http(self, source: str, fmt: str) -> bytes:
        encoded = urllib.parse.quote(self._encode_source(source), safe="")
        path = "svg" if fmt == "svg" else "img"
        url = f"{self.http_base}/{path}/{encoded}"
        req = urllib.request.Request(url, headers={"User-Agent": "workspace-mermaid/1.0"})
        # Retry transient 5xx / connection errors with linear backoff
        # (mermaid.ink rate-limits under burst).
        import time
        last_exc: Exception | None = None
        for attempt in range(4):
            if attempt:
                time.sleep(attempt * 1.5)
            try:
                with urllib.request.urlopen(req, timeout=self.HTTP_TIMEOUT_SEC) as resp:  # nosec B310
                    return resp.read()
            except urllib.error.HTTPError as exc:
                last_exc = MermaidRenderError(f"HTTP {exc.code}: {exc.reason}")
                if exc.code < 500 and exc.code != 429:
                    raise last_exc from exc
            except urllib.error.URLError as exc:
                last_exc = MermaidRenderError(f"URL error: {exc.reason}")
        if last_exc is None:  # pragma: no cover
            raise MermaidRenderError("Retry loop exited without capturing an error")
        raise last_exc

    # ── helpers ──────────────────────────────────────────────────

    @staticmethod
    def _encode_source(source: str) -> str:
        """mermaid.ink accepts a plain base64 of the diagram source.

        The pako-prefixed variant requires a JSON-wrapped payload + raw
        deflate; we use the simpler base64 endpoint for reliability.
        Reference: https://mermaid.ink
        """
        return base64.b64encode(source.encode("utf-8")).decode("ascii")

    @staticmethod
    def _discover_mmdc() -> str | None:
        for name in ("mmdc", "mmdc.cmd", "mmdc.exe"):
            path = shutil.which(name)
            if path:
                return path
        return None
