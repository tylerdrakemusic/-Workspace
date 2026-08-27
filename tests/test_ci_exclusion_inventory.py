from pathlib import Path


REPORT_PATH = Path(__file__).parents[1] / "reports" / "FR-20260826-workspace-ci-exclusion-audit-TODO-346.md"
REQUIRED_COLUMNS = (
    "Location",
    "Classification",
    "Reason",
    "Count",
    "Workflow impact",
    "Substitute coverage",
)
EXPECTED_REPOSITORIES = (
    "∞Life",
    "❤Music",
    "⟨ψ⟩Quantum",
    "👁AI-Manifest",
    "ΣCapital",
    "⊕Workspace",
)


def test_todo_346_report_covers_required_matrix_and_exact_repositories() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8")

    assert all(column in report for column in REQUIRED_COLUMNS)
    assert all(repository in report for repository in EXPECTED_REPOSITORIES)
    assert "superpowers" not in report
    assert "mp-skills" not in report
    assert "f:\\worktrees" not in report


def test_workspace_ci_does_not_deselect_integration_tests_and_reports_skips() -> None:
    project_root = REPORT_PATH.parents[1]
    pytest_config = (project_root / "pytest.ini").read_text(encoding="utf-8")
    workflow = (project_root / ".github" / "workflows" / "test.yml").read_text(
        encoding="utf-8"
    )
    integration_tests = (project_root / "tests" / "test_perplexity_integration.py").read_text(
        encoding="utf-8"
    )

    assert '-m "not integration"' not in pytest_config
    assert "-rs" in workflow
    assert "continue-on-error" not in workflow
    assert "--deselect" not in workflow
    assert "--ignore" not in workflow
    assert "never run in CI" not in pytest_config
    assert "CI collects these tests" in integration_tests
    assert "Perplexity live integration tests require PERPLEXITY_API_KEY" in integration_tests


def test_workspace_workflow_keeps_pytest_failures_blocking() -> None:
    workflow = (REPORT_PATH.parents[1] / ".github" / "workflows" / "test.yml").read_text(
        encoding="utf-8"
    )

    run_pytest_lines = [line for line in workflow.splitlines() if "run: pytest" in line]
    assert run_pytest_lines == ["        run: pytest -v --tb=short -rs"]