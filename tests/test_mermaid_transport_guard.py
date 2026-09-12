"""Offline federated Mermaid transport guard (FR-20260912 child 643).

Deterministic, network-free enforcement that every discovered `.mmd` source
across the six repository manifests encodes to a request-target within the
shared transport boundary. Diagnostics report project, path, measured length,
limit, and remediation. No live provider calls.
"""
from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from integrations.mermaid import MermaidClient, MermaidTransportError  # noqa: E402
from utils.mermaid_transport_guard import (  # noqa: E402
    TransportFinding,
    federated_transport_findings,
    findings_by_repository,
)

REPOSITORIES = ("workspace", "life", "music", "quantum", "manifest", "capital")

SMALL_MMD = "graph LR\n    A --> B\n"


def _oversized_mmd() -> str:
    # Incompressible labels defeat pako, forcing an oversized request-target.
    return "graph LR\n" + "\n".join(
        f'    N{i}["{base64.b64encode(os.urandom(48)).decode()}"]' for i in range(600)
    )


def _write_manifest(root: Path, repository: str, sources: dict[str, str]) -> None:
    diagrams_dir = root / "diagrams"
    diagrams_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for name, content in sources.items():
        (diagrams_dir / name).write_text(content, encoding="utf-8")
        records.append(
            {
                "path": f"diagrams/{name}",
                "kind": "architecture",
                "renderer_risk": "low",
                "fallback_risk": "low",
                "split_required": False,
                "lineage": {"parent": None, "derived_views": []},
            }
        )
    (diagrams_dir / "diagram-manifest.json").write_text(
        json.dumps({"schema_version": 1, "repository": repository, "diagrams": records}),
        encoding="utf-8",
    )


def _federated_workspace(tmp_path: Path, oversized_repo: str | None) -> Path:
    for repository in REPOSITORIES:
        sources = {"architecture.mmd": SMALL_MMD}
        if repository == oversized_repo:
            sources["oversized.mmd"] = _oversized_mmd()
        _write_manifest(tmp_path / repository, repository, sources)
    return tmp_path


def test_all_compliant_sources_produce_no_findings(tmp_path: Path) -> None:
    workspace_root = _federated_workspace(tmp_path, oversized_repo=None)

    # Prove the guard never touches the network.
    with patch("integrations.mermaid.client.urllib.request.urlopen",
               side_effect=AssertionError("guard must not call the network")):
        findings = federated_transport_findings(workspace_root)

    assert findings == ()


def test_guard_discovers_every_repository_source(tmp_path: Path) -> None:
    workspace_root = _federated_workspace(tmp_path, oversized_repo=None)
    from utils.mermaid_transport_guard import discover_measured_sources

    measured = discover_measured_sources(workspace_root)
    assert {repository for repository, _, _ in measured} == set(REPOSITORIES)
    assert all(measured_bytes > 0 for _, _, measured_bytes in measured)


def test_oversized_source_is_reported_with_full_diagnostics(tmp_path: Path) -> None:
    workspace_root = _federated_workspace(tmp_path, oversized_repo="capital")

    findings = federated_transport_findings(workspace_root)

    assert len(findings) == 1
    finding = findings[0]
    assert isinstance(finding, TransportFinding)
    assert finding.repository == "capital"
    assert finding.path.endswith("oversized.mmd")
    assert finding.measured_bytes > finding.limit_bytes
    assert finding.limit_bytes == MermaidClient.MAX_REQUEST_TARGET_BYTES
    assert finding.remediation  # non-empty remediation guidance
    assert "split" in finding.remediation.lower()


def test_findings_are_grouped_by_owning_repository(tmp_path: Path) -> None:
    workspace_root = _federated_workspace(tmp_path, oversized_repo="quantum")
    # Add a second oversized source in a different repo.
    _write_manifest(
        tmp_path / "music",
        "music",
        {"architecture.mmd": SMALL_MMD, "oversized.mmd": _oversized_mmd()},
    )

    grouped = findings_by_repository(federated_transport_findings(workspace_root))

    assert set(grouped) == {"music", "quantum"}
    assert all(len(items) == 1 for items in grouped.values())


def test_guard_measurement_matches_client_encoding(tmp_path: Path) -> None:
    workspace_root = _federated_workspace(tmp_path, oversized_repo="capital")
    client = MermaidClient(mmdc_path=None, prefer="http")

    finding = federated_transport_findings(workspace_root)[0]
    source = Path(finding.path).read_text(encoding="utf-8")
    assert finding.measured_bytes == client.measure_request_target_bytes(source, "svg")


def test_mocked_renderer_rejects_oversized_source_before_http(tmp_path: Path) -> None:
    """A discovered oversized source is rejected by the client before urlopen."""
    workspace_root = _federated_workspace(tmp_path, oversized_repo="life")
    finding = federated_transport_findings(workspace_root)[0]
    source = Path(finding.path).read_text(encoding="utf-8")

    client = MermaidClient(mmdc_path=None, prefer="http")
    with patch("integrations.mermaid.client.urllib.request.urlopen") as up:
        with pytest.raises(MermaidTransportError):
            client.render(source)
        assert not up.called


def test_mocked_renderer_preserves_http_fallback_for_normal_source(tmp_path: Path) -> None:
    workspace_root = _federated_workspace(tmp_path, oversized_repo=None)
    from utils.mermaid_transport_guard import discover_measured_sources

    _, normal_path, _ = discover_measured_sources(workspace_root)[0]
    source = Path(normal_path).read_text(encoding="utf-8")

    fake_svg = b"<svg/>"
    fake_resp = MagicMock()
    fake_resp.read.return_value = fake_svg
    fake_resp.__enter__ = lambda self: self
    fake_resp.__exit__ = lambda self, *a: None

    client = MermaidClient(mmdc_path=None, prefer="http")
    with patch("integrations.mermaid.client.urllib.request.urlopen", return_value=fake_resp):
        assert client.render(source) == fake_svg
