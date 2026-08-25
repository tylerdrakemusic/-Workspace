from __future__ import annotations

import sqlite3
import sys
import os
import subprocess
from pathlib import Path

from src.utils import init_db


def test_package_cli_entrypoints_start_under_src_package_context() -> None:
    workspace_root = Path(__file__).resolve().parents[1]
    environment = {**os.environ, "PYTHONPATH": str(workspace_root / "src")}

    for module in ("utils.perf_cli", "utils.proof_cli"):
        result = subprocess.run(
            [sys.executable, "-m", module, "--help"],
            cwd=workspace_root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "usage:" in result.stdout


def test_init_db_imports_lifecycle_through_src_package_and_initializes_schema(
    monkeypatch, tmp_path: Path
) -> None:
    utils_path = str(Path(init_db.__file__).resolve().parent)
    monkeypatch.setattr(sys, "path", [path for path in sys.path if path != utils_path])
    database_path = tmp_path / "workspace.db"
    monkeypatch.setattr(
        init_db,
        "get_connection",
        lambda: sqlite3.connect(database_path),
    )

    init_db.init_db()

    connection = sqlite3.connect(database_path)
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    assert {
        "todo_execution_lifecycle",
        "todo_execution_events",
        "todo_execution_stale_recoveries",
    } <= tables