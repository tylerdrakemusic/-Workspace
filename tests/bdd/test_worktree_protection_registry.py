import json
import subprocess
import sys
from pathlib import Path

from pytest_bdd import given, scenarios, then, when

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLI_PATH = PROJECT_ROOT / "tools" / "worktree_protection.py"

scenarios("worktree_protection_registry.feature")


@given("a repository contains a registered worktree candidate", target_fixture="candidate_context")
def registered_candidate(tmp_path: Path) -> tuple[Path, str]:
    repo_root = tmp_path / "repository"
    candidate = ".worktrees/active-branch"
    worktree = repo_root / candidate
    worktree.mkdir(parents=True)
    (worktree / "private.txt").write_text("not registry output", encoding="utf-8")
    registry_path = repo_root / ".worktrees" / "worktree-protection.json"
    registry_path.write_text(
        json.dumps(
            {
                "version": 1,
                "worktrees": [
                    {
                        "path": candidate,
                        "owner": "repository-owner",
                        "purpose": "active work",
                        "reviewed_at": "2026-10-11T10:00:00Z",
                        "review_interval_days": 14,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return repo_root, candidate


@when(
    "the generic worktree protection command checks the candidate",
    target_fixture="protection_result",
)
def check_registered_candidate(candidate_context: tuple[Path, str]) -> subprocess.CompletedProcess[str]:
    repo_root, candidate = candidate_context
    return subprocess.run(
        [
            sys.executable,
            str(CLI_PATH),
            "--repo-root",
            str(repo_root),
            "check",
            candidate,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


@then("the candidate is reported protected without disclosing worktree contents")
def candidate_is_protected(protection_result: subprocess.CompletedProcess[str]) -> None:
    assert protection_result.returncode == 0, protection_result.stderr
    output = protection_result.stdout
    assert "\"status\": \"protected\"" in output
    assert "active-branch" in output
    assert "repository-owner" in output
    assert "not registry output" not in output