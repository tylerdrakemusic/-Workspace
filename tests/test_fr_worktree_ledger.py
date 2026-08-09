"""Regression coverage for canonical FR ledger access from a Git worktree."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


WORKTREE_ROOT = Path(__file__).resolve().parents[1]
FR_CLI = WORKTREE_ROOT / "src" / "utils" / "fr_cli.py"
FR_ID = "FR-20260809-mcp-db-invocation-coverage"


@pytest.mark.skipif(
    not (os.environ.get("FR_LEDGERS_DB_KEY") or os.environ.get("WORKSPACE_DB_KEY")),
    reason="requires the configured FR ledger key for the real CLI invocation",
)
def test_fr_cli_get_from_isolated_worktree_reads_canonical_ledger() -> None:
    result = subprocess.run(
        [sys.executable, str(FR_CLI), "get", FR_ID],
        cwd=WORKTREE_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert f"ID:          {FR_ID}" in result.stdout
    assert "Expose all governed workspace SQLite databases through MCP" in result.stdout