"""FR-20260912 child 645: CI enforcement of the federated Mermaid transport guard.

The offline federated guard is wired into the workspace pytest suite, which CI
runs through ``tools/run_tests.py``. These tests enforce the transport boundary
against the *real, checked-out* Workspace-owned Mermaid sources, giving a
deterministic contract that holds on every branch and on ``main``.

Honest multi-repo scope: sibling repositories are not nested inside the Workspace
checkout, and their unmerged feature branches are never present in Workspace PR
CI. These tests therefore make no claim about cross-repo or cross-branch diagram
repairs; parent QA validates each PR branch in its own repository. Rooted at the
checkout, the federated guard measures the Workspace-owned sources on disk.
"""
from __future__ import annotations

import json
from pathlib import Path

from integrations.mermaid import MermaidClient
from utils.mermaid_transport_guard import (
    federated_transport_findings,
    format_findings,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = PROJECT_ROOT / "diagrams" / "diagram-manifest.json"


def _manifest_sources() -> list[Path]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return [PROJECT_ROOT / record["path"] for record in payload["diagrams"]]


def test_every_workspace_manifest_source_is_within_transport_boundary() -> None:
    client = MermaidClient(mmdc_path=None, prefer="http")
    limit = MermaidClient.MAX_REQUEST_TARGET_BYTES
    offenders: dict[str, int] = {}
    for source_path in _manifest_sources():
        measured = client.measure_request_target_bytes(
            source_path.read_text(encoding="utf-8"), "svg"
        )
        if measured > limit:
            offenders[str(source_path.relative_to(PROJECT_ROOT))] = measured
    assert offenders == {}, (
        f"Workspace sources exceed the {limit}-byte transport boundary: {offenders}"
    )


def test_federated_guard_reports_no_transport_findings_for_checkout() -> None:
    findings = federated_transport_findings(PROJECT_ROOT)
    assert findings == (), format_findings(findings)
