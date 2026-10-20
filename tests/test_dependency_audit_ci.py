from pathlib import Path
from packaging.requirements import Requirement


WORKFLOW_PATH = Path(__file__).parents[1] / ".github" / "workflows" / "test.yml"
REQUIREMENTS_PATH = Path(__file__).parents[1] / "requirements.txt"


def test_mcp_dependency_excludes_the_known_vulnerable_release() -> None:
    requirement_lines = REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines()
    requirement = next(
        Requirement(line.strip())
        for line in requirement_lines
        if line.strip().lower().startswith("mcp")
    )

    assert not requirement.specifier.contains("1.28.1")
    assert requirement.specifier.contains("1.30.0")
    assert str(requirement.specifier) == "<2,>=1.30.0"


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