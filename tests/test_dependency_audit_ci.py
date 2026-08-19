from pathlib import Path


WORKFLOW_PATH = Path(__file__).parents[1] / ".github" / "workflows" / "test.yml"


def test_ci_runs_pip_audit_with_strict_any_finding_gate() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    install_step = workflow.index("- name: Install dependencies")
    audit_step = workflow.index("- name: Audit dependencies")
    pytest_step = workflow.index("- name: Run pytest")
    audit_command = "pip-audit --format=columns --progress-spinner off"

    assert install_step < audit_step < pytest_step
    assert audit_command not in workflow
    assert "python tools/audit_workspace_requirements.py requirements.txt" in workflow
    assert "pip install -r requirements.txt" in workflow
    assert "continue-on-error: true" not in workflow[audit_step:pytest_step]