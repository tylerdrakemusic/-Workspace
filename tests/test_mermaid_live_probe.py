"""Optional live mermaid.ink probe — non-blocking evidence only (FR-20260912 child 645).

This is NOT a unit-test dependency. It is excluded from CI by
``tools/parallel_test_policy.json`` (the ``live`` marker) and additionally
self-skips unless ``MERMAID_LIVE_PROBE=1`` is set, so a bare ``pytest`` run never
touches the network. Run manually to collect evidence that a bounded diagram
renders over the real hosted transport::

    $env:MERMAID_LIVE_PROBE="1"; pytest -m live tests/test_mermaid_live_probe.py
"""
from __future__ import annotations

import os

import pytest

from integrations.mermaid import MermaidClient

pytestmark = pytest.mark.live

_PROBE_ENABLED = os.getenv("MERMAID_LIVE_PROBE") == "1"


@pytest.mark.skipif(
    not _PROBE_ENABLED,
    reason="Set MERMAID_LIVE_PROBE=1 to run the opt-in live mermaid.ink probe",
)
def test_live_mermaid_ink_renders_bounded_diagram() -> None:
    client = MermaidClient(mmdc_path=None, prefer="http")
    source = "graph LR\n  A[Start] --> B[End]\n"
    # Well under the transport boundary; evidence only, never blocking.
    assert (
        client.measure_request_target_bytes(source, "svg")
        < MermaidClient.MAX_REQUEST_TARGET_BYTES
    )
    svg = client.render(source, fmt="svg")
    assert b"<svg" in svg[:512]
