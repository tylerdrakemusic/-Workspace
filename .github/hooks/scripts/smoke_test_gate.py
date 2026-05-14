#!/usr/bin/env python3
"""
smoke_test_gate.py — pre-commit smoke test gate
FR-20260513-hooks-setup
Runs smoke tests for the current repo before allowing a commit.
Skipped gracefully if no smoke tests exist yet.
"""
import subprocess
import sys
from pathlib import Path


def get_python() -> str:
    win_python = Path("C:/G/python.exe")
    if win_python.exists():
        return str(win_python)
    return "python3"


def main() -> int:
    # Find repo root
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode != 0:
        return 0  # not in a git repo, skip
    repo_root = Path(result.stdout.strip())

    # Look for smoke tests
    smoke_candidates = list(repo_root.glob("tests/test_smoke.py"))
    if not smoke_candidates:
        # No smoke tests for this repo — skip gracefully
        return 0

    smoke_path = str(smoke_candidates[0])
    python = get_python()

    print(f"[smoke-test-gate] Running smoke tests: {smoke_path}")
    run = subprocess.run(
        [python, "-m", "pytest", smoke_path, "-q", "--tb=short", "--no-header"],
        cwd=str(repo_root)
    )

    if run.returncode != 0:
        print("")
        print("❌ pre-commit [smoke-test-gate]: smoke tests failed. Fix before committing.")
        print(f"   Re-run manually: cd {repo_root} && pytest tests/test_smoke.py -q")
        print("")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
