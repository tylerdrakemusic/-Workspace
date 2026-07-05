"""
Tests for the agent_feedback table schema (FR-20260704-agent-self-improve-feedback).

Uses a file-backed unencrypted sqlite3 connection (mirrors test_fr_cli_gate.py
convention) with the schema copied from init_db.py's init_db() script, so we
don't need WORKSPACE_DB_KEY / sqlcipher in unit tests.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src" / "utils"))

import init_db  # noqa: E402


def _agent_feedback_ddl() -> str:
    """Extract the agent_feedback CREATE TABLE statement from init_db.py's script.

    This keeps the test honest against the real schema instead of a hand
    duplicated copy that could drift.
    """
    import re

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


def _insert_row(conn: sqlite3.Connection, **overrides) -> int:
    row = {
        "timestamp": "2026-07-04T00:00:00Z",
        "agent_or_prompt_name": "⊕workspace-tdd-heavy",
        "artifact_type": "instructions",
        "target_file_path": "f:/⊕Workspace/.github/instructions/foo.md",
        "finding_text": "stale path reference",
        "severity": "trivial",
        "status": "pending",
        "fr_id": None,
        "applied_at": None,
        "applied_by": None,
    }
    row.update(overrides)
    cur = conn.execute(
        """INSERT INTO agent_feedback
           (timestamp, agent_or_prompt_name, artifact_type, target_file_path,
            finding_text, severity, status, fr_id, applied_at, applied_by)
           VALUES (:timestamp, :agent_or_prompt_name, :artifact_type, :target_file_path,
                   :finding_text, :severity, :status, :fr_id, :applied_at, :applied_by)""",
        row,
    )
    conn.commit()
    return cur.lastrowid


class TestAgentFeedbackSchema:
    def test_table_creates_and_inserts_and_reads(self, tmp_path: Path) -> None:
        conn = _make_conn(tmp_path / "wf.db")
        row_id = _insert_row(conn)
        fetched = conn.execute("SELECT * FROM agent_feedback WHERE id=?", (row_id,)).fetchone()
        assert fetched["agent_or_prompt_name"] == "⊕workspace-tdd-heavy"
        assert fetched["artifact_type"] == "instructions"
        assert fetched["severity"] == "trivial"
        assert fetched["status"] == "pending"
        assert fetched["fr_id"] is None
        conn.close()

    def test_artifact_type_check_constraint(self, tmp_path: Path) -> None:
        conn = _make_conn(tmp_path / "wf.db")
        with pytest.raises(sqlite3.IntegrityError):
            _insert_row(conn, artifact_type="not_a_real_type")
        conn.close()

    @pytest.mark.parametrize("artifact_type", ["agent", "instructions", "prompt", "skill", "reference"])
    def test_artifact_type_allows_all_valid_values(self, tmp_path: Path, artifact_type: str) -> None:
        conn = _make_conn(tmp_path / "wf.db")
        row_id = _insert_row(conn, artifact_type=artifact_type)
        assert row_id is not None
        conn.close()

    def test_severity_check_constraint(self, tmp_path: Path) -> None:
        conn = _make_conn(tmp_path / "wf.db")
        with pytest.raises(sqlite3.IntegrityError):
            _insert_row(conn, severity="urgent")
        conn.close()

    @pytest.mark.parametrize("severity", ["trivial", "substantive"])
    def test_severity_allows_all_valid_values(self, tmp_path: Path, severity: str) -> None:
        conn = _make_conn(tmp_path / "wf.db")
        row_id = _insert_row(conn, severity=severity)
        assert row_id is not None
        conn.close()

    def test_status_check_constraint(self, tmp_path: Path) -> None:
        conn = _make_conn(tmp_path / "wf.db")
        with pytest.raises(sqlite3.IntegrityError):
            _insert_row(conn, status="bogus")
        conn.close()

    @pytest.mark.parametrize(
        "status", ["pending", "auto_applied", "approved", "rejected", "applied"]
    )
    def test_status_allows_all_valid_values(self, tmp_path: Path, status: str) -> None:
        conn = _make_conn(tmp_path / "wf.db")
        row_id = _insert_row(conn, status=status)
        assert row_id is not None
        conn.close()

    def test_fr_id_is_nullable_and_settable(self, tmp_path: Path) -> None:
        conn = _make_conn(tmp_path / "wf.db")
        row_id = _insert_row(conn, fr_id="FR-20260704-agent-self-improve-feedback")
        fetched = conn.execute("SELECT fr_id FROM agent_feedback WHERE id=?", (row_id,)).fetchone()
        assert fetched["fr_id"] == "FR-20260704-agent-self-improve-feedback"
        conn.close()

    def test_default_status_is_pending_when_omitted(self, tmp_path: Path) -> None:
        conn = _make_conn(tmp_path / "wf.db")
        conn.execute(
            """INSERT INTO agent_feedback
               (timestamp, agent_or_prompt_name, artifact_type, target_file_path,
                finding_text, severity)
               VALUES (?,?,?,?,?,?)""",
            ("2026-07-04T00:00:00Z", "agent-x", "agent", "path.md", "finding", "trivial"),
        )
        conn.commit()
        fetched = conn.execute("SELECT status FROM agent_feedback ORDER BY id DESC LIMIT 1").fetchone()
        assert fetched["status"] == "pending"
        conn.close()


class TestInitDbIncludesAgentFeedback:
    def test_init_db_script_contains_agent_feedback_table(self) -> None:
        text = Path(init_db.__file__).read_text(encoding="utf-8")
        assert "CREATE TABLE IF NOT EXISTS agent_feedback" in text
