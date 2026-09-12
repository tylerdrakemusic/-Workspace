"""Tests for src/integrations/mermaid client.

Covers:
- CLI path: subprocess.run mocked
- HTTP path: urlopen mocked
- Fallback: CLI fails → HTTP succeeds
- Both fail → MermaidRenderError raised
- pako encoding format
- Transport boundary preflight (rejects oversized request-target before network)
"""
from __future__ import annotations

import base64
import io
import json
import re
import sys
import zlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from integrations.mermaid import (  # noqa: E402
    MermaidClient,
    MermaidRenderError,
    MermaidTransportError,
)


SAMPLE_MMD = "graph LR\n    A --> B\n"
FAKE_SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><g/></svg>'


def _decode_pako(encoded: str) -> str:
    assert encoded.startswith("pako:"), f"expected pako prefix, got {encoded[:12]!r}"
    raw = encoded[len("pako:"):]
    padded = raw + "=" * (-len(raw) % 4)
    payload = json.loads(zlib.decompress(base64.urlsafe_b64decode(padded)))
    return payload["code"]


def test_encode_source_uses_pako_transport():
    """Documented mermaid.ink pako transport: zlib(JSON({code})) base64url."""
    encoded = MermaidClient._encode_source(SAMPLE_MMD)
    assert encoded.startswith("pako:")
    assert _decode_pako(encoded) == SAMPLE_MMD


def test_pako_transport_is_smaller_than_plain_base64_for_large_source():
    large = "graph LR\n" + "\n".join(f"    N{i} --> N{i + 1}" for i in range(400))
    pako = MermaidClient._encode_source(large)
    plain = base64.b64encode(large.encode("utf-8")).decode("ascii")
    assert len(pako) < len(plain)


def test_render_cli_success(tmp_path):
    client = MermaidClient(mmdc_path="mmdc-fake", prefer="cli")

    def fake_run(cmd, capture_output, text, timeout):
        # cmd: [mmdc, -i, in.mmd, -o, out.svg, -b, transparent]
        out_path = Path(cmd[4])
        out_path.write_bytes(FAKE_SVG)
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    with patch("integrations.mermaid.client.subprocess.run", side_effect=fake_run):
        result = client.render(SAMPLE_MMD, fmt="svg")
    assert result == FAKE_SVG


def test_render_cli_failure_falls_back_to_http():
    client = MermaidClient(mmdc_path="mmdc-fake", prefer="cli")

    def fake_run(*args, **kwargs):
        result = MagicMock()
        result.returncode = 1
        result.stderr = "boom"
        return result

    fake_resp = MagicMock()
    fake_resp.read.return_value = FAKE_SVG
    fake_resp.__enter__ = lambda self: self
    fake_resp.__exit__ = lambda self, *a: None

    with patch("integrations.mermaid.client.subprocess.run", side_effect=fake_run), \
         patch("integrations.mermaid.client.urllib.request.urlopen", return_value=fake_resp):
        result = client.render(SAMPLE_MMD, fmt="svg")
    assert result == FAKE_SVG


def test_render_http_only_when_no_cli():
    client = MermaidClient(mmdc_path=None, prefer="cli")
    assert not client.cli_available()

    fake_resp = MagicMock()
    fake_resp.read.return_value = FAKE_SVG
    fake_resp.__enter__ = lambda self: self
    fake_resp.__exit__ = lambda self, *a: None

    with patch("integrations.mermaid.client.urllib.request.urlopen", return_value=fake_resp):
        result = client.render(SAMPLE_MMD)
    assert result == FAKE_SVG


def test_render_both_backends_fail_raises():
    client = MermaidClient(mmdc_path="mmdc-fake", prefer="cli")

    def fake_run(*args, **kwargs):
        result = MagicMock()
        result.returncode = 1
        result.stderr = "cli fail"
        return result

    import urllib.error
    with patch("integrations.mermaid.client.subprocess.run", side_effect=fake_run), \
         patch("integrations.mermaid.client.urllib.request.urlopen",
               side_effect=urllib.error.URLError("net dead")):
        with pytest.raises(MermaidRenderError) as exc:
            client.render(SAMPLE_MMD)
    assert "cli" in str(exc.value) and "http" in str(exc.value)


def test_render_http_414_is_reported_with_status():
    client = MermaidClient(mmdc_path=None, prefer="http")
    import urllib.error

    http_error = urllib.error.HTTPError(
        url="https://mermaid.ink/svg/encoded",
        code=414,
        msg="Request-URI Too Long",
        hdrs=None,
        fp=io.BytesIO(),
    )
    with patch("integrations.mermaid.client.urllib.request.urlopen", side_effect=http_error):
        with pytest.raises(MermaidRenderError, match=r"HTTP 414: Request-URI Too Long"):
            client.render(SAMPLE_MMD)


def test_render_unsupported_format_raises():
    client = MermaidClient(mmdc_path="mmdc-fake")
    with pytest.raises(ValueError):
        client.render(SAMPLE_MMD, fmt="pdf")


def test_prefer_http_tries_http_first():
    client = MermaidClient(mmdc_path="mmdc-fake", prefer="http")
    fake_resp = MagicMock()
    fake_resp.read.return_value = FAKE_SVG
    fake_resp.__enter__ = lambda self: self
    fake_resp.__exit__ = lambda self, *a: None

    with patch("integrations.mermaid.client.urllib.request.urlopen", return_value=fake_resp) as up, \
         patch("integrations.mermaid.client.subprocess.run") as run:
        client.render(SAMPLE_MMD)
        assert up.called
        assert not run.called


# ── transport boundary preflight (TODO 641/642) ──────────────────────────────


def test_transport_error_is_mermaidrendererror_subclass():
    assert issubclass(MermaidTransportError, MermaidRenderError)


def test_request_target_measures_encoded_bytes_within_boundary_for_small_source():
    client = MermaidClient(mmdc_path=None, prefer="http")
    target = client._request_target(SAMPLE_MMD, "svg")
    assert target.startswith("/svg/pako:")
    measured = client.measure_request_target_bytes(SAMPLE_MMD, "svg")
    assert measured == len(target.encode("utf-8"))
    assert 0 < measured < MermaidClient.MAX_REQUEST_TARGET_BYTES


def test_boundary_is_derived_from_node_header_evidence():
    # Provider evidence (Node default) minus documented local-policy headroom.
    assert MermaidClient.NODE_MAX_HTTP_HEADER_BYTES == 16384
    assert (
        MermaidClient.MAX_REQUEST_TARGET_BYTES
        == MermaidClient.NODE_MAX_HTTP_HEADER_BYTES
        - MermaidClient.REQUEST_HEADER_HEADROOM_BYTES
    )
    assert 0 < MermaidClient.MAX_REQUEST_TARGET_BYTES < MermaidClient.NODE_MAX_HTTP_HEADER_BYTES


def test_preflight_rejects_oversized_request_target_before_network():
    """An oversized encoded request-target must fail before urlopen is called."""
    client = MermaidClient(mmdc_path=None, prefer="http")
    # Incompressible random-ish content forces a large pako payload.
    import os
    oversized = "graph LR\n" + "\n".join(
        f'    N{i}["{base64.b64encode(os.urandom(48)).decode()}"]' for i in range(600)
    )
    assert client.measure_request_target_bytes(oversized, "svg") > MermaidClient.MAX_REQUEST_TARGET_BYTES

    with patch("integrations.mermaid.client.urllib.request.urlopen") as up:
        with pytest.raises(MermaidTransportError) as exc:
            client.render(oversized, fmt="svg")
        assert not up.called
    err = exc.value
    assert err.measured_bytes > err.limit_bytes == MermaidClient.MAX_REQUEST_TARGET_BYTES
    assert re.search(r"split", str(err), re.IGNORECASE)


def test_preflight_rejection_does_not_break_cli_first_ordering():
    """CLI-first path still renders locally without touching the transport boundary."""
    client = MermaidClient(mmdc_path="mmdc-fake", prefer="cli")
    oversized = "graph LR\n" + "\n".join(f"    N{i} --> N{i + 1}" for i in range(5000))

    def fake_run(cmd, capture_output, text, timeout):
        Path(cmd[4]).write_bytes(FAKE_SVG)
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    with patch("integrations.mermaid.client.subprocess.run", side_effect=fake_run), \
         patch("integrations.mermaid.client.urllib.request.urlopen") as up:
        assert client.render(oversized) == FAKE_SVG
        assert not up.called


def test_documented_boundary_matches_client_constants():
    """TODO 641: the diagram contract doc records the same numbers the client enforces."""
    doc = (PROJECT_ROOT / "docs" / "diagram-federation.md").read_text(encoding="utf-8")
    assert "Transport boundary" in doc
    assert str(MermaidClient.NODE_MAX_HTTP_HEADER_BYTES) in doc
    assert str(MermaidClient.MAX_REQUEST_TARGET_BYTES) in doc
    assert str(MermaidClient.REQUEST_HEADER_HEADROOM_BYTES) in doc
    # Evidence vs local policy must be explicitly distinguished.
    assert re.search(r"provider evidence", doc, re.IGNORECASE)
    assert re.search(r"local policy", doc, re.IGNORECASE)
    assert "pako" in doc
