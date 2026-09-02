"""Validate the evidence-backed scheduler architecture reference."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Mapping


REQUIRED_COLUMNS = (
    "Project",
    "Task Name",
    "Task Path",
    "Trigger / Cadence",
    "Action / Command",
    "Owner",
    "Status",
    "Evidence",
    "Last Observed Result",
    "Operational Findings",
)
ALLOWED_STATUSES = {"documented", "deployed", "unverified", "no-entry"}
CANONICAL_PROJECTS = {"∞Life", "❤Music", "⟨ψ⟩Quantum", "👁AI-Manifest", "⊕Workspace", "ΣCapital"}
AUDITED_JOB_NAMES = {
    "InfiniteLife-NightlySync",
    "InfiniteLife_Withings_Token_Watcher",
    "QuantumCacheDepletionGuard_Daily",
    "QuantumCacheFill_Monthly",
    "ShorsMonthlyBench",
    "VQEMonthlyBench",
    "PolicyComplianceAudit_Daily",
    "AI_Manifest_Priority_Rescore",
    "⊕Workspace-DatabaseBackup",
    "⊕Workspace-SecurityScan",
    "WorkspaceHygiene",
    "Workspace-PerfRegressionAlerter",
    "ProofHealthVerifier",
    "SkillSyncNightly",
    "PositionRealization",
    "ProductionFillReconciliation",
    "ReconcileOrders",
}


@dataclass(frozen=True)
class Finding:
    code: str
    message: str


@dataclass(frozen=True)
class InventoryRecord:
    project: str
    task_name: str
    task_path: str
    trigger: str
    command: str
    owner: str
    status: str
    evidence: str
    last_observed_result: str
    operational_findings: str


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

    expected_record_count = 18 if expected_projects == CANONICAL_PROJECTS else len(expected_projects)
    if actual_projects != expected_projects or len(records) != expected_record_count:
        findings.append(
            Finding(
                "project_count",
                f"inventory has {len(records)} records; expected {expected_record_count} for {len(expected_projects)} canonical projects",
            )
        )

    task_names = [record.task_name for record in records if record.task_name and record.status != "no-entry"]
    if len(task_names) != len(set(task_names)):
        findings.append(Finding("task_identity", "inventory contains duplicate task names"))
    if expected_projects == CANONICAL_PROJECTS:
        if set(task_names) != AUDITED_JOB_NAMES:
            findings.append(Finding("task_identity", "inventory does not contain exactly the 17 audited jobs"))
        music_records = [record for record in records if record.project == "❤Music"]
        if len(music_records) != 1 or music_records[0].status != "no-entry":
            findings.append(Finding("no_entry", "❤Music must have exactly one no-entry record"))

    for record in records:
        fields = (
            record.project,
            record.task_name,
            record.task_path,
            record.trigger,
            record.command,
            record.owner,
            record.status,
            record.evidence,
            record.last_observed_result,
            record.operational_findings,
        )
        if not all(field.strip() for field in fields):
            findings.append(Finding("record_fields", f"{record.project} has an empty required field"))
        if record.status not in ALLOWED_STATUSES:
            findings.append(Finding("status", f"{record.project} has unsupported status {record.status!r}"))
        normalized_evidence = record.evidence.replace("\\", "/")
        evidence_path = Path(normalized_evidence)
        has_windows_drive_prefix = bool(re.match(r"^[A-Za-z]:", normalized_evidence))
        is_unc_absolute = normalized_evidence.startswith("//")
        has_traversal = ".." in normalized_evidence.split("/")
        if evidence_path.is_absolute() or has_windows_drive_prefix or is_unc_absolute or has_traversal:
            findings.append(Finding("evidence_path", f"{record.project} evidence must be repository-relative"))
        elif record.project in project_roots:
            project_evidence = project_roots[record.project] / evidence_path
            shared_evidence = inventory_path.parent.parent / evidence_path
            if not project_evidence.is_file() and not shared_evidence.is_file():
                findings.append(Finding("evidence_missing", f"{record.project} evidence does not exist: {record.evidence}"))

    diagram = diagram_path.read_text(encoding="utf-8") if diagram_path.is_file() else ""
    diagram_without_spaces = re.sub(r"\s+", "", diagram).casefold()
    for record in records:
        project_token = re.sub(r"\s+", "", record.project).casefold()
        if (
            project_token not in diagram_without_spaces
            or record.task_name.casefold() not in diagram.casefold()
            or record.task_path.casefold() not in diagram.casefold()
            or _diagram_token(record.command).casefold() not in diagram.casefold()
        ):
            findings.append(Finding("diagram_coverage", f"diagram does not cover {record.project} and {record.task_name}"))
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