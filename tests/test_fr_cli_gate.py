"""
Tests for fr_cli.py — MERGED transition gate.

FR-20260703-architecture-diagram-catchup: a feature request must not be
allowed to transition to state MERGED unless its event log contains a
recorded ARCHITECTURE_REVIEW:PASS (or PASS_WITH_UPDATES) event. This
prevents merges from silently skipping the architecture review step.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src" / "utils"))

import fr_cli


def _make_conn(db_path: Path) -> sqlite3.Connection:
    """File-backed sqlite3 connection with the FR ledger schema (unencrypted, test-only).

    A file (not :memory:) is used so a fresh connection can be reopened after
    cmd_update_state closes the one it was given, matching production usage
    where each CLI invocation opens/closes its own connection.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE feature_requests (
            id TEXT PRIMARY KEY,
            title TEXT,
            type TEXT,
            risk TEXT,
            projects TEXT,
            state TEXT,
            branch TEXT,
            prs TEXT,
            owner TEXT,
            opened_at TEXT,
            updated_at TEXT,
            merged_at TEXT,
            signed_off_at TEXT,
            closed_at TEXT,
            final_state TEXT,
            cycle_timer_run_id TEXT,
            cost_status TEXT,
            cost_source TEXT,
            cost_reconciliation_status TEXT
        );
        CREATE TABLE fr_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fr_id TEXT NOT NULL,
            ts TEXT NOT NULL,
            agent TEXT NOT NULL,
            event_type TEXT NOT NULL,
            summary TEXT NOT NULL,
            details TEXT,
            next_action TEXT
        );
        """
    )
    conn.execute(
        "INSERT INTO feature_requests "
        "(id, title, state, opened_at, updated_at, cost_status, cost_source) "
        "VALUES ('FR-TEST-001', 'Test FR', 'ARCHITECTURE_REVIEW', '2026-07-03', "
        "'2026-07-03', 'estimated', 'test')"
    )
    conn.commit()
    return conn


def _state_args(fr_id: str, new_state: str) -> argparse.Namespace:
    return argparse.Namespace(
        fr_id=fr_id,
        new_state=new_state,
        branch=None,
        prs=None,
        merged_at=None,
        signed_off_at=None,
        owner=None,
        cycle_timer=None,
    )


class TestMergedGate:
    @pytest.mark.parametrize(
        "new_state",
        ["FUNCTIONAL_QA", "ARCHITECTURE_REVIEW", "TYLER_APPROVED", "MERGED", "SOAKING", "SIGNED_OFF"],
    )
    def test_parent_join_blocks_every_post_implementation_state(
        self, tmp_path, capsys, new_state: str
    ) -> None:
        db_path = tmp_path / "fr.db"
        conn = _make_conn(db_path)
        conn.execute(
            "INSERT INTO fr_events (fr_id, ts, agent, event_type, summary) "
            "VALUES ('FR-TEST-001', '2026-07-03T00:00:00Z', 'test', 'note', "
            "'PARENT_JOIN:REQUIRED — child TODO 333-1 is not joined')"
        )
        conn.commit()
        with patch.object(fr_cli, "_conn", return_value=conn):
            with pytest.raises(SystemExit) as exc_info:
                fr_cli.cmd_update_state(_state_args("FR-TEST-001", new_state))

        assert exc_info.value.code != 0
        assert "parent join is incomplete" in capsys.readouterr().err
        check_conn = sqlite3.connect(str(db_path))
        row = check_conn.execute(
            "SELECT state FROM feature_requests WHERE id='FR-TEST-001'"
        ).fetchone()
        check_conn.close()
        assert row[0] == "ARCHITECTURE_REVIEW"

    def test_merged_blocked_without_architecture_review_pass(self, tmp_path, capsys) -> None:
        db_path = tmp_path / "fr.db"
        conn = _make_conn(db_path)
        with patch.object(fr_cli, "_conn", return_value=conn):
            with pytest.raises(SystemExit) as exc_info:
                fr_cli.cmd_update_state(_state_args("FR-TEST-001", "MERGED"))
        assert exc_info.value.code != 0
        err = capsys.readouterr().err
        assert "ARCHITECTURE_REVIEW" in err

        check_conn = sqlite3.connect(str(db_path))
        row = check_conn.execute(
            "SELECT state FROM feature_requests WHERE id='FR-TEST-001'"
        ).fetchone()
        check_conn.close()
        assert row[0] == "ARCHITECTURE_REVIEW"  # unchanged

    def test_merged_allowed_with_architecture_review_pass(self, tmp_path, capsys) -> None:
        db_path = tmp_path / "fr.db"
        conn = _make_conn(db_path)
        conn.execute(
            "INSERT INTO fr_events (fr_id, ts, agent, event_type, summary) "
            "VALUES ('FR-TEST-001', '2026-07-03T00:00:00Z', "
            "'⊕workspace-architecture-reviewer', 'note', 'ARCHITECTURE_REVIEW:PASS — all diagrams current')"
        )
        conn.commit()
        with patch.object(fr_cli, "_conn", return_value=conn):
            fr_cli.cmd_update_state(_state_args("FR-TEST-001", "MERGED"))

        check_conn = sqlite3.connect(str(db_path))
        row = check_conn.execute(
            "SELECT state FROM feature_requests WHERE id='FR-TEST-001'"
        ).fetchone()
        check_conn.close()
        assert row[0] == "MERGED"

    def test_merged_allowed_with_pass_with_updates(self, tmp_path, capsys) -> None:
        db_path = tmp_path / "fr.db"
        conn = _make_conn(db_path)
        conn.execute(
            "INSERT INTO fr_events (fr_id, ts, agent, event_type, summary) "
            "VALUES ('FR-TEST-001', '2026-07-03T00:00:00Z', "
            "'⊕workspace-architecture-reviewer', 'note', 'ARCHITECTURE_REVIEW:PASS_WITH_UPDATES — diagrams refreshed')"
        )
        conn.commit()
        with patch.object(fr_cli, "_conn", return_value=conn):
            fr_cli.cmd_update_state(_state_args("FR-TEST-001", "MERGED"))

        check_conn = sqlite3.connect(str(db_path))
        row = check_conn.execute(
            "SELECT state FROM feature_requests WHERE id='FR-TEST-001'"
        ).fetchone()
        check_conn.close()
        assert row[0] == "MERGED"

    def test_merged_blocked_with_only_fail_event(self, tmp_path, capsys) -> None:
        db_path = tmp_path / "fr.db"
        conn = _make_conn(db_path)
        conn.execute(
            "INSERT INTO fr_events (fr_id, ts, agent, event_type, summary) "
            "VALUES ('FR-TEST-001', '2026-07-03T00:00:00Z', "
            "'⊕workspace-architecture-reviewer', 'note', 'ARCHITECTURE_REVIEW:FAIL — diagram stale')"
        )
        conn.commit()
        with patch.object(fr_cli, "_conn", return_value=conn):
            with pytest.raises(SystemExit) as exc_info:
                fr_cli.cmd_update_state(_state_args("FR-TEST-001", "MERGED"))
        assert exc_info.value.code != 0

    def test_non_merged_transition_not_gated(self, tmp_path, capsys) -> None:
        """Transitioning to any other state must not require the architecture-review event."""
        db_path = tmp_path / "fr.db"
        conn = _make_conn(db_path)
        with patch.object(fr_cli, "_conn", return_value=conn):
            fr_cli.cmd_update_state(_state_args("FR-TEST-001", "REVIEW_REQUESTED"))

        check_conn = sqlite3.connect(str(db_path))
        row = check_conn.execute(
            "SELECT state FROM feature_requests WHERE id='FR-TEST-001'"
        ).fetchone()
        check_conn.close()
        assert row[0] == "REVIEW_REQUESTED"
