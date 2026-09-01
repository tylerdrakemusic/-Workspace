"""Validate the evidence-backed scheduler architecture reference."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Mapping


REQUIRED_COLUMNS = ("Project", "Trigger", "Command", "Owner", "Status", "Evidence")
ALLOWED_STATUSES = {"documented", "deployed", "unverified", "no-entry"}


@dataclass(frozen=True)
class Finding:
    code: str
    message: str


@dataclass(frozen=True)
class InventoryRecord:
    project: str
    trigger: str
    command: str
    owner: str
    status: str
    evidence: str


def validate_scheduler_architecture(
    inventory_path: Path,
    diagram_path: Path,
    project_roots: Mapping[str, Path],
) -> tuple[Finding, ...]:
    """Return deterministic findings for the scheduler reference and diagram."""
    records = _read_records(inventory_path)
    findings: list[Finding] = []
    expected_projects = set(project_roots)
    actual_projects = {record.project for record in records}

    if actual_projects != expected_projects or len(records) != len(expected_projects):
        findings.append(
            Finding(
                "project_count",
                f"inventory has {len(records)} records for {len(expected_projects)} canonical projects",
            )
        )

    for record in records:
        fields = (record.project, record.trigger, record.command, record.owner, record.status, record.evidence)
        if not all(field.strip() for field in fields):
            findings.append(Finding("record_fields", f"{record.project} has an empty required field"))
        if record.status not in ALLOWED_STATUSES:
            findings.append(Finding("status", f"{record.project} has unsupported status {record.status!r}"))
        normalized_evidence = record.evidence.replace("\\", "/")
        evidence_path = Path(normalized_evidence)
        is_windows_absolute = bool(re.match(r"^[A-Za-z]:/", normalized_evidence))
        is_unc_absolute = normalized_evidence.startswith("//")
        has_traversal = ".." in normalized_evidence.split("/")
        if evidence_path.is_absolute() or is_windows_absolute or is_unc_absolute or has_traversal:
            findings.append(Finding("evidence_path", f"{record.project} evidence must be repository-relative"))
        elif record.project in project_roots and not (project_roots[record.project] / evidence_path).is_file():
            findings.append(Finding("evidence_missing", f"{record.project} evidence does not exist: {record.evidence}"))

    diagram = diagram_path.read_text(encoding="utf-8") if diagram_path.is_file() else ""
    diagram_without_spaces = re.sub(r"\s+", "", diagram)
    for record in records:
        project_token = re.sub(r"\s+", "", record.project)
        if project_token not in diagram_without_spaces or _diagram_token(record.command) not in diagram:
            findings.append(Finding("diagram_coverage", f"diagram does not cover {record.project} and its command"))
    return tuple(findings)


def _read_records(inventory_path: Path) -> tuple[InventoryRecord, ...]:
    records: list[InventoryRecord] = []
    header_seen = False
    for line in inventory_path.read_text(encoding="utf-8").splitlines():
        columns = [column.strip().strip("`") for column in line.strip().split("|")[1:-1]]
        if not columns:
            continue
        if tuple(columns) == REQUIRED_COLUMNS:
            header_seen = True
            continue
        if not header_seen or len(columns) != len(REQUIRED_COLUMNS) or set(columns) == {"---"}:
            continue
        records.append(InventoryRecord(*columns))
    return tuple(records)


def _diagram_token(command: str) -> str:
    """Use a stable command token while allowing prose labels in the diagram."""
    normalized_command = command.replace("\\", "/")
    path_match = re.search(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+", normalized_command)
    if path_match:
        return path_match.group(0).rsplit("/", 1)[-1].lower()
    words = re.findall(r"[A-Za-z][A-Za-z0-9_.-]*", command)
    return words[0].lower() if words else "none"