"""
Tests for feedback_cli.py (FR-20260704-agent-self-improve-feedback).

Mirrors the tests/test_fr_cli_gate.py convention: patch the module's `_conn`
helper to return a file-backed unencrypted sqlite3 connection carrying the
agent_feedback schema, and call the cmd_* functions directly with an
argparse.Namespace.
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src" / "utils"))

import feedback_cli  # noqa: E402
import init_db  # noqa: E402


def _agent_feedback_ddl() -> str:
    text = Path(init_db.__file__).read_text(encoding="utf-8")
    match = re.search(
        r"CREATE TABLE IF NOT EXISTS agent_feedback \(.*?\);", text, re.DOTALL
    )
    assert match, "agent_feedback table DDL not found in init_db.py"
    return match.group(0)


def _make_conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(_agent_feedback_ddl())
    conn.commit()
    return conn


def _reopen(db_path: Path) -> sqlite3.Connection:
    """Open a fresh connection to an already-initialized db file.

    cmd_* functions close their connection after each call (matching the
    fr_cli/perf_cli convention of one connection per invocation), so tests
    that call multiple cmd_* functions or inspect state afterward must patch
    `_conn` to reopen the file each time rather than reuse a single object.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _log_args(**overrides) -> argparse.Namespace:
    defaults = dict(
        agent_name="⊕workspace-tdd-heavy",
        artifact_type="instructions",
        target_file="f:/⊕Workspace/.github/instructions/foo.md",
        finding_text="stale path reference",
        severity="trivial",
        fr_id=None,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class TestCmdLog:
    def test_log_inserts_pending_row(self, tmp_path, capsys) -> None:
        db_path = tmp_path / "wf.db"
        _make_conn(db_path).close()
        with patch.object(feedback_cli, "_conn", side_effect=lambda: _reopen(db_path)):
            feedback_cli.cmd_log(_log_args())
        conn = _reopen(db_path)
        row = conn.execute("SELECT * FROM agent_feedback ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        assert row["status"] == "pending"
        assert row["agent_or_prompt_name"] == "⊕workspace-tdd-heavy"
        assert row["fr_id"] is None
        out = capsys.readouterr().out
        assert str(row["id"]) in out

    def test_log_with_fr_id(self, tmp_path) -> None:
        db_path = tmp_path / "wf.db"
        _make_conn(db_path).close()
        with patch.object(feedback_cli, "_conn", side_effect=lambda: _reopen(db_path)):
            feedback_cli.cmd_log(_log_args(fr_id="FR-20260704-agent-self-improve-feedback"))
        conn = _reopen(db_path)
        row = conn.execute("SELECT fr_id FROM agent_feedback ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        assert row["fr_id"] == "FR-20260704-agent-self-improve-feedback"

    def test_log_rejects_invalid_severity(self, tmp_path) -> None:
        db_path = tmp_path / "wf.db"
        _make_conn(db_path).close()
        with patch.object(feedback_cli, "_conn", side_effect=lambda: _reopen(db_path)):
            with pytest.raises(SystemExit):
                feedback_cli.cmd_log(_log_args(severity="urgent"))

    def test_log_rejects_invalid_artifact_type(self, tmp_path) -> None:
        db_path = tmp_path / "wf.db"
        _make_conn(db_path).close()
        with patch.object(feedback_cli, "_conn", side_effect=lambda: _reopen(db_path)):
            with pytest.raises(SystemExit):
                feedback_cli.cmd_log(_log_args(artifact_type="nope"))


class TestCmdList:
    def test_list_filters_by_status(self, tmp_path, capsys) -> None:
        db_path = tmp_path / "wf.db"
        _make_conn(db_path).close()
        with patch.object(feedback_cli, "_conn", side_effect=lambda: _reopen(db_path)):
            feedback_cli.cmd_log(_log_args(finding_text="finding A"))
            feedback_cli.cmd_log(_log_args(finding_text="finding B"))
            conn = _reopen(db_path)
            conn.execute("UPDATE agent_feedback SET status='applied' WHERE finding_text='finding B'")
            conn.commit()
            conn.close()
            capsys.readouterr()
            feedback_cli.cmd_list(argparse.Namespace(status="pending", severity=None))
        out = capsys.readouterr().out
        assert "finding A" in out
        assert "finding B" not in out

    def test_list_filters_by_severity(self, tmp_path, capsys) -> None:
        db_path = tmp_path / "wf.db"
        _make_conn(db_path).close()
        with patch.object(feedback_cli, "_conn", side_effect=lambda: _reopen(db_path)):
            feedback_cli.cmd_log(_log_args(finding_text="trivial finding", severity="trivial"))
            feedback_cli.cmd_log(_log_args(finding_text="substantive finding", severity="substantive"))
            capsys.readouterr()
            feedback_cli.cmd_list(argparse.Namespace(status=None, severity="substantive"))
        out = capsys.readouterr().out
        assert "substantive finding" in out
        assert "trivial finding" not in out

    def test_list_empty_prints_message(self, tmp_path, capsys) -> None:
        db_path = tmp_path / "wf.db"
        _make_conn(db_path).close()
        with patch.object(feedback_cli, "_conn", side_effect=lambda: _reopen(db_path)):
            feedback_cli.cmd_list(argparse.Namespace(status=None, severity=None))
        out = capsys.readouterr().out
        assert "no feedback" in out.lower()


class TestCmdApply:
    def test_apply_marks_applied_with_timestamp_and_by(self, tmp_path) -> None:
        db_path = tmp_path / "wf.db"
        _make_conn(db_path).close()
        with patch.object(feedback_cli, "_conn", side_effect=lambda: _reopen(db_path)):
            feedback_cli.cmd_log(_log_args(severity="substantive"))
            conn = _reopen(db_path)
            row_id = conn.execute("SELECT id FROM agent_feedback ORDER BY id DESC LIMIT 1").fetchone()["id"]
            conn.close()
            feedback_cli.cmd_apply(argparse.Namespace(id=row_id, applied_by="tyler"))
        conn = _reopen(db_path)
        row = conn.execute("SELECT * FROM agent_feedback WHERE id=?", (row_id,)).fetchone()
        conn.close()
        assert row["status"] == "applied"
        assert row["applied_at"] is not None
        assert row["applied_by"] == "tyler"

    def test_apply_missing_id_errors(self, tmp_path) -> None:
        db_path = tmp_path / "wf.db"
        _make_conn(db_path).close()
        with patch.object(feedback_cli, "_conn", side_effect=lambda: _reopen(db_path)):
            with pytest.raises(SystemExit):
                feedback_cli.cmd_apply(argparse.Namespace(id=9999, applied_by="tyler"))


class TestCmdAutoApplyTrivial:
    def test_auto_apply_trivial_updates_only_trivial_pending(self, tmp_path) -> None:
        db_path = tmp_path / "wf.db"
        _make_conn(db_path).close()
        with patch.object(feedback_cli, "_conn", side_effect=lambda: _reopen(db_path)):
            feedback_cli.cmd_log(_log_args(finding_text="trivial pending", severity="trivial"))
            feedback_cli.cmd_log(_log_args(finding_text="substantive pending", severity="substantive"))
            feedback_cli.cmd_log(_log_args(finding_text="already applied trivial", severity="trivial"))
            conn = _reopen(db_path)
            conn.execute("UPDATE agent_feedback SET status='applied' WHERE finding_text='already applied trivial'")
            conn.commit()
            conn.close()
            feedback_cli.cmd_auto_apply_trivial(argparse.Namespace())

        conn = _reopen(db_path)
        rows = {r["finding_text"]: r["status"] for r in conn.execute("SELECT finding_text, status FROM agent_feedback")}
        conn.close()
        assert rows["trivial pending"] == "auto_applied"
        assert rows["substantive pending"] == "pending"
        assert rows["already applied trivial"] == "applied"


class TestEndToEndSmoke:
    def test_trivial_finding_auto_applied_end_to_end(self, tmp_path) -> None:
        db_path = tmp_path / "wf.db"
        _make_conn(db_path).close()
        with patch.object(feedback_cli, "_conn", side_effect=lambda: _reopen(db_path)):
            feedback_cli.cmd_log(_log_args(finding_text="trivial e2e", severity="trivial"))
            feedback_cli.cmd_auto_apply_trivial(argparse.Namespace())
        conn = _reopen(db_path)
        row = conn.execute("SELECT status FROM agent_feedback WHERE finding_text='trivial e2e'").fetchone()
        conn.close()
        assert row["status"] == "auto_applied"

    def test_substantive_finding_applied_end_to_end(self, tmp_path) -> None:
        db_path = tmp_path / "wf.db"
        _make_conn(db_path).close()
        with patch.object(feedback_cli, "_conn", side_effect=lambda: _reopen(db_path)):
            feedback_cli.cmd_log(_log_args(finding_text="substantive e2e", severity="substantive"))
            conn = _reopen(db_path)
            row_id = conn.execute(
                "SELECT id FROM agent_feedback WHERE finding_text='substantive e2e'"
            ).fetchone()["id"]
            conn.close()
            feedback_cli.cmd_apply(argparse.Namespace(id=row_id, applied_by="tyler"))
        conn = _reopen(db_path)
        row = conn.execute(
            "SELECT status, applied_at, applied_by FROM agent_feedback WHERE id=?", (row_id,)
        ).fetchone()
        conn.close()
        assert row["status"] == "applied"
        assert row["applied_at"] is not None
        assert row["applied_by"] == "tyler"

