from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from src.utils import fr_approval_notification, fr_cli, perf_cli, proof_cli


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_proof_hashing_directory_path_is_optional(tmp_path: Path) -> None:
    assert proof_cli._hash_file(str(tmp_path)) is None


def test_fr_get_prints_criteria_complete_events_and_artifacts(
    tmp_path: Path, capsys
) -> None:
    db_path = tmp_path / "fr.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE feature_requests (
            id TEXT PRIMARY KEY, title TEXT, type TEXT, risk TEXT, projects TEXT,
            state TEXT, branch TEXT, prs TEXT, owner TEXT, opened_at TEXT,
            updated_at TEXT, merged_at TEXT, signed_off_at TEXT, closed_at TEXT,
            final_state TEXT, cycle_timer_run_id TEXT, acceptance_criteria TEXT,
            ai_credits_estimated REAL, usd_cost_estimated REAL, cost_status TEXT,
            cost_source TEXT, cost_reconciliation_status TEXT, cost_finalized_at TEXT
        );
        CREATE TABLE fr_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, fr_id TEXT, ts TEXT, agent TEXT,
            event_type TEXT, summary TEXT, details TEXT, next_action TEXT
        );
        CREATE TABLE fr_artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, fr_id TEXT, ts TEXT,
            artifact_type TEXT, label TEXT, path_or_url TEXT
        );
        INSERT INTO feature_requests
            (id, title, type, state, opened_at, updated_at, acceptance_criteria)
        VALUES
            ('FR-TEST-READ', 'Complete read contract', 'chore', 'IN_PROGRESS',
             '2026-09-13', '2026-09-13', '{"checks":["criteria"]}');
        INSERT INTO fr_events (fr_id, ts, agent, event_type, summary)
        VALUES ('FR-TEST-READ', '2026-09-13T00:00:00Z', 'test', 'finding',
                'This event summary is deliberately longer than eighty characters so truncation is observable.');
        INSERT INTO fr_artifacts (fr_id, ts, artifact_type, label, path_or_url)
        VALUES ('FR-TEST-READ', '2026-09-13T00:01:00Z', 'test_pass',
                'focused proof artifact', 'proof/example.txt');
        """
    )
    conn.commit()

    with patch.object(fr_cli, "_conn", return_value=conn):
        fr_cli.cmd_get(argparse.Namespace(fr_id="FR-TEST-READ"))

    output = capsys.readouterr().out
    assert 'Acceptance criteria: {"checks":["criteria"]}' in output
    assert "truncation is observable." in output
    assert "focused proof artifact" in output


def _run_help(script: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("WORKSPACE_DB_KEY", None)
    environment.pop("FR_LEDGERS_DB_KEY", None)
    return subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_perf_cli_direct_invocation_bootstraps_package_imports() -> None:
    script = (
        "import importlib.util, sys; "
        "path = r'src/utils/perf_cli.py'; "
        "spec = importlib.util.spec_from_file_location('perf_script', path); "
        "module = importlib.util.module_from_spec(spec); "
        "spec.loader.exec_module(module); "
        "raise SystemExit(0 if 'src.utils.init_db' in sys.modules else 1)"
    )
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_fr_approval_notification_direct_invocation_bootstraps_package_imports() -> None:
    result = _run_help(PROJECT_ROOT / "src" / "utils" / "fr_approval_notification.py")
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()