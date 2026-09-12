"""Offline federated Mermaid transport guard.

Enumerates every repository-owned Mermaid source through the federation
discovery contract, measures the same compressed request-target the shared
client would send to mermaid.ink, and reports any source whose encoded
request-target exceeds the transport boundary. Pure measurement: no network
access and no live provider calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from integrations.mermaid.client import MermaidClient
from src.utils.diagram_federation import discover_diagram_sources_by_repository


@dataclass(frozen=True)
class TransportFinding:
    repository: str
    path: str
    measured_bytes: int
    limit_bytes: int
    remediation: str


def _client() -> MermaidClient:
    # http_base is irrelevant to measurement; force CLI discovery off for determinism.
    return MermaidClient(mmdc_path=None, prefer="http")


def discover_measured_sources(
    workspace_root: Path,
    fmt: str = "svg",
) -> tuple[tuple[str, Path, int], ...]:
    """Return (repository, source_path, measured_request_target_bytes) for every source."""
    client = _client()
    measured = [
        (repository, path, client.measure_request_target_bytes(
            path.read_text(encoding="utf-8"), fmt))
        for repository, path in discover_diagram_sources_by_repository(workspace_root)
    ]
    return tuple(measured)


def federated_transport_findings(
    workspace_root: Path,
    fmt: str = "svg",
) -> tuple[TransportFinding, ...]:
    """Report every discovered source whose encoded request-target is oversized."""
    limit = MermaidClient.MAX_REQUEST_TARGET_BYTES
    findings = [
        TransportFinding(
            repository=repository,
            path=str(path),
            measured_bytes=measured_bytes,
            limit_bytes=limit,
            remediation=(
                f"Split {path.name} into bounded derived views so its pako "
                f"request-target drops below {limit} bytes."
            ),
        )
        for repository, path, measured_bytes in discover_measured_sources(workspace_root, fmt)
        if measured_bytes > limit
    ]
    return tuple(findings)


def findings_by_repository(
    findings: tuple[TransportFinding, ...],
) -> dict[str, tuple[TransportFinding, ...]]:
    """Group transport findings by their owning repository."""
    grouped: dict[str, list[TransportFinding]] = {}
    for finding in findings:
        grouped.setdefault(finding.repository, []).append(finding)
    return {repository: tuple(items) for repository, items in grouped.items()}


def format_findings(findings: tuple[TransportFinding, ...]) -> str:
    """Render clean, deterministic diagnostics for CI logs and review evidence.

    A compliant run yields a single noise-free summary line. Each violation lists
    its owning repository, source path, measured/limit request-target bytes, and
    the split remediation guidance.
    """
    if not findings:
        return "Mermaid transport guard: no violations across all discovered sources."
    header = (
        f"Mermaid transport guard: {len(findings)} source(s) exceed the "
        f"{findings[0].limit_bytes}-byte request-target boundary."
    )
    lines = [
        f"  [{finding.repository}] {finding.path} — "
        f"{finding.measured_bytes}/{finding.limit_bytes} bytes — {finding.remediation}"
        for finding in findings
    ]
    return "\n".join([header, *lines])
