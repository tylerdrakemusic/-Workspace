from __future__ import annotations

from pathlib import Path

import pytest

from src.utils.scheduler_architecture import _diagram_token, validate_scheduler_architecture


REPO_ROOT = Path(__file__).parents[1]


def test_scheduler_architecture_test_does_not_require_sibling_worktrees() -> None:
    source = Path(__file__).read_text(encoding="utf-8")

    assert ".work" + "trees" not in source


def _portable_project_roots(tmp_path: Path) -> dict[str, Path]:
    evidence_paths = {project: "docs/scheduler-live-audit-2026-09-01.md" for project in (
        "∞Life", "⟨ψ⟩Quantum", "👁AI-Manifest", "⊕Workspace", "ΣCapital"
    )}
    evidence_paths["❤Music"] = "AGENT_STARTUP.md"
    project_roots = {}
    for project, evidence_path in evidence_paths.items():
        project_root = tmp_path / project
        evidence_file = project_root / evidence_path
        evidence_file.parent.mkdir(parents=True)
        evidence_file.write_text("fixture evidence\n", encoding="utf-8")
        project_roots[project] = project_root
    return project_roots


def test_scheduler_architecture_reference_covers_six_projects_and_diagram_evidence(tmp_path: Path) -> None:
    findings = validate_scheduler_architecture(
        REPO_ROOT / "docs" / "scheduler-architecture-inventory.md",
        REPO_ROOT / "diagrams" / "workspace-scheduler-architecture.mmd",
        _portable_project_roots(tmp_path),
    )

    assert findings == ()


def test_scheduler_architecture_reference_has_one_record_per_audited_job() -> None:
    inventory = (REPO_ROOT / "docs" / "scheduler-architecture-inventory.md").read_text(encoding="utf-8")

    expected_jobs = {
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

    assert inventory.count("| ") >= 19
    for job_name in expected_jobs:
        assert job_name in inventory
    assert "❤Music" in inventory
    assert "no-entry" in inventory


def test_scheduler_architecture_records_expose_job_identity_task_path_and_action() -> None:
    inventory = (REPO_ROOT / "docs" / "scheduler-architecture-inventory.md").read_text(encoding="utf-8")

    assert "Task Name" in inventory
    assert "Task Path" in inventory
    assert "Action / Command" in inventory
    assert "Last Observed Result" in inventory
    assert "Operational Findings" in inventory


def test_scheduler_architecture_validation_rejects_missing_evidence_and_uncovered_records(
    tmp_path: Path,
) -> None:
    inventory = tmp_path / "inventory.md"
    inventory.write_text(
        """# Scheduler Architecture Inventory

    | Project | Task Name | Task Path | Trigger / Cadence | Action / Command | Owner | Status | Evidence | Last Observed Result | Operational Findings |
    | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
    | Demo | DemoTask | none | none verified | none | unknown | no-entry | missing.md | none | none |
""",
        encoding="utf-8",
    )
    diagram = tmp_path / "diagram.mmd"
    diagram.write_text("graph LR\n    Other[Other]\n", encoding="utf-8")

    findings = validate_scheduler_architecture(inventory, diagram, {"Demo": tmp_path, "Other": tmp_path})

    assert {finding.code for finding in findings} == {
        "project_count",
        "evidence_missing",
        "diagram_coverage",
    }


@pytest.mark.parametrize(
    "evidence",
    [r"C:\other-repository\proof.md", r"C:proof.md", r"\\server\share\proof.md", r"tools\..\proof.md"],
)
def test_scheduler_architecture_rejects_windows_absolute_and_traversal_evidence(
    tmp_path: Path, evidence: str
) -> None:
    inventory = tmp_path / "inventory.md"
    inventory.write_text(
        f"""| Project | Task Name | Task Path | Trigger / Cadence | Action / Command | Owner | Status | Evidence | Last Observed Result | Operational Findings |
    | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
    | Demo | DemoTask | \\Demo\\DemoTask | manual | `tools/run_task.py` | owner | documented | `{evidence}` | none | none |
""",
        encoding="utf-8",
    )
    diagram = tmp_path / "diagram.mmd"
    diagram.write_text("graph LR\n    Demo --> run_task.py\n", encoding="utf-8")

    findings = validate_scheduler_architecture(inventory, diagram, {"Demo": tmp_path})

    finding_codes = {finding.code for finding in findings}
    assert "evidence_path" in finding_codes
    assert "evidence_missing" not in finding_codes


def test_diagram_token_uses_command_filename_instead_of_tools_directory() -> None:
    assert _diagram_token(r"tools\register_hygiene_task.ps1") == "register_hygiene_task.ps1"


def test_scheduler_architecture_requires_command_filename_in_diagram(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.md"
    inventory.write_text(
        """| Project | Task Name | Task Path | Trigger / Cadence | Action / Command | Owner | Status | Evidence | Last Observed Result | Operational Findings |
    | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
    | Demo | DemoTask | \\Demo\\DemoTask | manual | `tools/run_task.py` | owner | documented | proof.md | none | none |
""",
        encoding="utf-8",
    )
    (tmp_path / "proof.md").write_text("fixture evidence\n", encoding="utf-8")
    diagram = tmp_path / "diagram.mmd"
    diagram.write_text("graph LR\n    Demo --> tools\n", encoding="utf-8")

    findings = validate_scheduler_architecture(inventory, diagram, {"Demo": tmp_path})

    assert {finding.code for finding in findings} == {"diagram_coverage"}


def test_scheduler_architecture_matches_diagram_coverage_case_insensitively(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.md"
    inventory.write_text(
        """| Project | Task Name | Task Path | Trigger / Cadence | Action / Command | Owner | Status | Evidence | Last Observed Result | Operational Findings |
    | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
    | Demo | DemoTask | \\Demo\\DemoTask | manual | `tools/run_task.py` | owner | documented | proof.md | none | none |
""",
        encoding="utf-8",
    )
    (tmp_path / "proof.md").write_text("fixture evidence\n", encoding="utf-8")
    diagram = tmp_path / "diagram.mmd"
    diagram.write_text(
        "graph LR\n    demo --> DemoTask\n    DemoTask --> \\Demo\\DemoTask\n    DemoTask --> RUN_TASK.PY\n",
        encoding="utf-8",
    )

    findings = validate_scheduler_architecture(inventory, diagram, {"Demo": tmp_path})

    assert findings == ()


def test_scheduler_reference_declares_statuses_and_excludes_runtime_scheduler_scope() -> None:
    inventory = (REPO_ROOT / "docs" / "scheduler-architecture-inventory.md").read_text(encoding="utf-8")
    diagram = (REPO_ROOT / "diagrams" / "workspace-scheduler-architecture.mmd").read_text(encoding="utf-8")

    for status in ("documented", "deployed", "unverified", "no-entry"):
        assert status in inventory
        assert status in diagram
    assert "in-process" in inventory
    assert "live monitoring" in inventory
    assert "schedule editing" in inventory