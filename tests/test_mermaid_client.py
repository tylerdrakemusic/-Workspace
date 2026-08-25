"""Tests for src/integrations/mermaid client.

Covers:
- CLI path: subprocess.run mocked
- HTTP path: urlopen mocked
- Fallback: CLI fails → HTTP succeeds
- Both fail → MermaidRenderError raised
- pako encoding format
"""
from __future__ import annotations

import io
import sys
import zlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from integrations.mermaid import MermaidClient, MermaidRenderError  # noqa: E402


SAMPLE_MMD = "graph LR\n    A --> B\n"
FAKE_SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><g/></svg>'


def test_encode_source_is_base64():
    encoded = MermaidClient._encode_source(SAMPLE_MMD)
    import base64
    assert base64.b64decode(encoded).decode("utf-8") == SAMPLE_MMD


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
