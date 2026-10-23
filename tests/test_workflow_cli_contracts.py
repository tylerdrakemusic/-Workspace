from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("script", "contract"),
    [
        (
            "fr_cli.py",
            "canonical FR ledger interface",
        ),
        (
            "proof_cli.py",
            "does not change FR state",
        ),
        (
            "perf_cli.py",
            "Record FR linkage through fr_cli.py",
        ),
        (
            "feedback_cli.py",
            "does not edit source",
        ),
        (
            "complexity_router.py",
            "persist routing evidence with fr_cli.py record-event",
        ),
    ],
)
def test_workflow_cli_help_exposes_agent_contract(script: str, contract: str) -> None:
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "src" / "utils" / script), "--help"],
        capture_output=True,
        check=False,
        cwd=PROJECT_ROOT,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stderr
    assert contract in " ".join(result.stdout.split())