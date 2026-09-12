"""Mermaid renderer — local `mmdc` CLI preferred, mermaid.ink HTTP fallback.

No API key required. Both back-ends are free.

Usage:
    from integrations.mermaid import MermaidClient
    client = MermaidClient()
    svg_bytes = client.render(mmd_source)
"""

from __future__ import annotations

import base64
import json
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


class MermaidTransportError(MermaidRenderError):
    """Raised before network access when the encoded request-target exceeds the
    documented transport boundary. Subclasses ``MermaidRenderError`` so existing
    callers that catch render failures keep working.
    """

    def __init__(self, message: str, *, measured_bytes: int, limit_bytes: int) -> None:
        super().__init__(message)
        self.measured_bytes = measured_bytes
        self.limit_bytes = limit_bytes


class MermaidClient:
    """Render mermaid diagrams to SVG.

    Strategy: try local `mmdc` (Node CLI from `@mermaid-js/mermaid-cli`)
    first; on any failure (not installed, exit non-zero, timeout) fall
    back to the public mermaid.ink HTTP service.
    """

    HTTP_BASE = "https://mermaid.ink"
    CLI_TIMEOUT_SEC = 30
    HTTP_TIMEOUT_SEC = 30

    # Provider evidence: Node.js default --max-http-header-size (bytes). mermaid.ink
    # is a Node service and documents raising this flag for large diagrams; it does
    # NOT publish a numeric URI cap. This ceiling bounds the HTTP request line
    # (which carries the request-target) plus request headers.
    NODE_MAX_HTTP_HEADER_BYTES = 16384
    # Local policy: reserve headroom under the Node ceiling for the request-line
    # tokens (method, HTTP version) and standard request headers (Host, User-Agent,
    # Accept-Encoding, Connection). Chosen conservatively; not a provider value.
    REQUEST_HEADER_HEADROOM_BYTES = 2048
    # Local policy: maximum encoded request-target length enforced before network.
    MAX_REQUEST_TARGET_BYTES = NODE_MAX_HTTP_HEADER_BYTES - REQUEST_HEADER_HEADROOM_BYTES

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
        transport_error: MermaidTransportError | None = None

        for backend in order:
            try:
                if backend == "cli":
                    if not self.mmdc_path:
                        errors.append("cli: mmdc not on PATH")
                        continue
                    return self._render_cli(source, fmt)
                else:
                    return self._render_http(source, fmt)
            except MermaidTransportError as exc:
                # Deterministic boundary breach: remember the typed diagnostic but
                # keep trying other backends (e.g. local CLI can still render).
                transport_error = exc
                errors.append(f"{backend}: {exc}")
            except Exception as exc:  # noqa: BLE001 — surface all backend errors
                errors.append(f"{backend}: {exc}")

        if transport_error is not None:
            raise transport_error
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
        request_target = self._request_target(source, fmt)
        # Preflight: reject an oversized request-target before any network access.
        self._check_transport_boundary(request_target)
        url = f"{self.http_base}{request_target}"
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

    # ── transport boundary ───────────────────────────────────────

    def _request_target(self, source: str, fmt: str) -> str:
        """Return the exact HTTP request-target (`/svg/pako:…` or `/img/pako:…`)."""
        path = "svg" if fmt == "svg" else "img"
        return f"/{path}/{self._encode_source(source)}"

    def measure_request_target_bytes(self, source: str, fmt: str = "svg") -> int:
        """Measure the encoded request-target length (UTF-8 bytes) sent to the host."""
        return len(self._request_target(source, fmt).encode("utf-8"))

    def _check_transport_boundary(self, request_target: str) -> None:
        measured = len(request_target.encode("utf-8"))
        if measured > self.MAX_REQUEST_TARGET_BYTES:
            raise MermaidTransportError(
                f"Encoded mermaid request-target is {measured} bytes, over the "
                f"{self.MAX_REQUEST_TARGET_BYTES}-byte transport boundary; split the "
                f"diagram into bounded derived views before rendering over HTTP.",
                measured_bytes=measured,
                limit_bytes=self.MAX_REQUEST_TARGET_BYTES,
            )

    # ── helpers ──────────────────────────────────────────────────

    @staticmethod
    def _encode_source(source: str) -> str:
        """Compressed pako transport, matching mermaid.ink / the mermaid live editor.

        JSON-wrap the source, zlib-compress (a zlib stream that mermaid.ink's
        ``pako.inflate`` decodes), then base64url without padding, prefixed with
        ``pako:``. This compresses the request-target so large diagrams stay well
        under the transport boundary.
        Reference: https://mermaid.ink (pako endpoint)
        """
        payload = json.dumps(
            {"code": source, "mermaid": {"theme": "default"}},
            separators=(",", ":"),
        )
        compressed = zlib.compress(payload.encode("utf-8"), 9)
        encoded = base64.urlsafe_b64encode(compressed).decode("ascii").rstrip("=")
        return f"pako:{encoded}"

    @staticmethod
    def _discover_mmdc() -> str | None:
        for name in ("mmdc", "mmdc.cmd", "mmdc.exe"):
            path = shutil.which(name)
            if path:
                return path
        return None
