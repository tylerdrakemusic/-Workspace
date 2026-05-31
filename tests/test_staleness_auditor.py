"""Tests for tools/staleness_auditor.py — TDD RED phase.

FR-20260530-portal-staleness-auditor
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import pytest

# staleness_auditor lives in tools/ which is on sys.path via conftest
from staleness_auditor import (
    classify_dashboard,
    scan_dashboards,
    scan_stuck_frs,
    write_report,
    WARN_SECS,
    STALE_SECS,
    STUCK_SECS,
    TERMINAL_STATES,
    ACTIVE_STATES,
)

# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def fresh_output(tmp_path: Path) -> Path:
    """HTML file touched 5 minutes ago."""
    f = tmp_path / "fresh.html"
    f.write_text("<html/>", encoding="utf-8")
    mtime = time.time() - 5 * 60  # 5 min ago
    import os; os.utime(f, (mtime, mtime))
    return f


@pytest.fixture()
def warn_output(tmp_path: Path) -> Path:
    """HTML file touched 3 hours ago (>= 2h warn threshold)."""
    f = tmp_path / "warn.html"
    f.write_text("<html/>", encoding="utf-8")
    mtime = time.time() - 3 * 60 * 60  # 3 h ago
    import os; os.utime(f, (mtime, mtime))
    return f


@pytest.fixture()
def stale_output(tmp_path: Path) -> Path:
    """HTML file touched 5 hours ago (>= 4h stale threshold)."""
    f = tmp_path / "stale.html"
    f.write_text("<html/>", encoding="utf-8")
    mtime = time.time() - 5 * 60 * 60  # 5 h ago
    import os; os.utime(f, (mtime, mtime))
    return f


def _make_dash(output_abs: str | None = None, type_: str = "static_html") -> dict:
    return {
        "id": "test-dash",
        "title": "Test Dashboard",
        "type": type_,
        "project": "workspace",
        "output_abs": output_abs,
        "cli": "C:\\G\\python.exe tools/test_gen.py",
    }


def _make_fr_conn(rows: list[tuple]) -> sqlite3.Connection:
    """In-memory sqlite3 DB (plain, no encryption) mimicking fr_ledgers schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE feature_requests (
            id TEXT PRIMARY KEY,
            title TEXT,
            state TEXT,
            updated_at TEXT
        )
    """)
    conn.executemany(
        "INSERT INTO feature_requests (id, title, state, updated_at) VALUES (?,?,?,?)",
        rows,
    )
    conn.commit()
    return conn


# ── classify_dashboard ────────────────────────────────────────────────────────

def test_fresh_dashboard_classified_as_fresh(fresh_output: Path) -> None:
    dash = _make_dash(output_abs=str(fresh_output))
    result = classify_dashboard(dash)
    assert result["status"] == "fresh"
    assert result["age_secs"] < WARN_SECS


def test_dashboard_at_warn_threshold(warn_output: Path) -> None:
    dash = _make_dash(output_abs=str(warn_output))
    result = classify_dashboard(dash)
    assert result["status"] == "warn"
    assert result["age_secs"] >= WARN_SECS


def test_dashboard_at_stale_threshold(stale_output: Path) -> None:
    dash = _make_dash(output_abs=str(stale_output))
    result = classify_dashboard(dash)
    assert result["status"] == "stale"
    assert result["age_secs"] >= STALE_SECS


def test_missing_output_classified_as_missing(tmp_path: Path) -> None:
    dash = _make_dash(output_abs=str(tmp_path / "nonexistent.html"))
    result = classify_dashboard(dash)
    assert result["status"] == "missing"


def test_no_output_abs_classified_as_missing() -> None:
    dash = _make_dash(output_abs=None)
    result = classify_dashboard(dash)
    assert result["status"] == "missing"


def test_classify_result_has_required_keys(fresh_output: Path) -> None:
    dash = _make_dash(output_abs=str(fresh_output))
    result = classify_dashboard(dash)
    for key in ("id", "title", "project", "type", "status", "age_secs", "age_label", "cli"):
        assert key in result, f"Missing key: {key}"


# ── scan_dashboards ───────────────────────────────────────────────────────────

def test_non_static_dashboard_excluded(fresh_output: Path) -> None:
    """flask_app and console types have no output file — skip them."""
    manifest = {"dashboards": [_make_dash(output_abs=str(fresh_output), type_="flask_app")]}
    results = scan_dashboards(manifest)
    assert results == []


def test_console_dashboard_excluded(fresh_output: Path) -> None:
    manifest = {"dashboards": [_make_dash(output_abs=str(fresh_output), type_="console")]}
    results = scan_dashboards(manifest)
    assert results == []


def test_scan_dashboards_returns_all_static(
    fresh_output: Path, warn_output: Path, stale_output: Path
) -> None:
    manifest = {
        "dashboards": [
            _make_dash(output_abs=str(fresh_output)),
            {**_make_dash(output_abs=str(warn_output)), "id": "warn-dash"},
            {**_make_dash(output_abs=str(stale_output)), "id": "stale-dash"},
        ]
    }
    results = scan_dashboards(manifest)
    assert len(results) == 3
    statuses = {r["id"]: r["status"] for r in results}
    assert statuses["test-dash"] == "fresh"
    assert statuses["warn-dash"] == "warn"
    assert statuses["stale-dash"] == "stale"


def test_scan_dashboards_empty_manifest() -> None:
    results = scan_dashboards({"dashboards": []})
    assert results == []


# ── scan_stuck_frs ────────────────────────────────────────────────────────────

def _iso_hours_ago(h: float) -> str:
    from datetime import datetime, timezone, timedelta
    return (datetime.now(timezone.utc) - timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_fr_stuck_when_updated_beyond_threshold() -> None:
    conn = _make_fr_conn([
        ("FR-001", "Stuck FR", "BRANCHED", _iso_hours_ago(49)),
    ])
    results = scan_stuck_frs(conn=conn)
    assert len(results) == 1
    assert results[0]["id"] == "FR-001"
    assert results[0]["hours_stuck"] >= 49


def test_fr_not_stuck_when_recently_updated() -> None:
    conn = _make_fr_conn([
        ("FR-002", "Fresh FR", "IN_PROGRESS", _iso_hours_ago(1)),
    ])
    results = scan_stuck_frs(conn=conn)
    assert results == []


def test_fr_exactly_at_threshold_is_stuck() -> None:
    """Exactly STUCK_SECS old (48h) → flagged."""
    conn = _make_fr_conn([
        ("FR-003", "Borderline FR", "TRIAGED", _iso_hours_ago(48.01)),
    ])
    results = scan_stuck_frs(conn=conn)
    assert len(results) == 1


def test_terminal_state_fr_not_flagged_even_if_old() -> None:
    for terminal_state in TERMINAL_STATES:
        conn = _make_fr_conn([
            ("FR-004", "Old closed FR", terminal_state, _iso_hours_ago(200)),
        ])
        results = scan_stuck_frs(conn=conn)
        assert results == [], f"Terminal state {terminal_state!r} should not be flagged as stuck"


def test_active_state_fr_is_eligible_for_stuck_detection() -> None:
    """FRs in any ACTIVE_STATE that are old enough should appear in results."""
    for active_state in ACTIVE_STATES:
        conn = _make_fr_conn([
            ("FR-X", "Old active FR", active_state, _iso_hours_ago(72)),
        ])
        results = scan_stuck_frs(conn=conn)
        assert len(results) == 1, f"Active state {active_state!r} should be flagged when stuck"


def test_stuck_fr_result_has_required_keys() -> None:
    conn = _make_fr_conn([
        ("FR-005", "Stuck FR", "IN_PROGRESS", _iso_hours_ago(72)),
    ])
    results = scan_stuck_frs(conn=conn)
    assert len(results) == 1
    for key in ("id", "title", "state", "hours_stuck", "updated_at"):
        assert key in results[0], f"Missing key: {key}"


def test_scan_stuck_frs_no_active_frs() -> None:
    conn = _make_fr_conn([])
    results = scan_stuck_frs(conn=conn)
    assert results == []


# ── write_report ──────────────────────────────────────────────────────────────

def test_report_written_to_disk(tmp_path: Path) -> None:
    out = tmp_path / "staleness_audit.json"
    write_report(dashboards=[], stuck_frs=[], out_path=out)
    assert out.is_file()


def test_report_has_required_top_level_keys(tmp_path: Path) -> None:
    out = tmp_path / "staleness_audit.json"
    write_report(dashboards=[], stuck_frs=[], out_path=out)
    data = json.loads(out.read_text(encoding="utf-8"))
    for key in ("generated_at", "dashboards", "stuck_frs", "summary"):
        assert key in data, f"Missing top-level key: {key}"


def test_report_summary_counts_correctly(tmp_path: Path, stale_output: Path) -> None:
    dash = _make_dash(output_abs=str(stale_output))
    stale_result = classify_dashboard(dash)
    out = tmp_path / "staleness_audit.json"
    write_report(dashboards=[stale_result], stuck_frs=[], out_path=out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["summary"]["total_dashboards"] == 1
    assert data["summary"]["stale"] == 1
    assert data["summary"]["stuck_frs"] == 0
    assert data["summary"]["all_clean"] is False


def test_report_summary_all_clean_on_empty(tmp_path: Path) -> None:
    out = tmp_path / "staleness_audit.json"
    write_report(dashboards=[], stuck_frs=[], out_path=out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["summary"]["all_clean"] is True


def test_report_summary_all_clean_with_only_fresh(tmp_path: Path, fresh_output: Path) -> None:
    dash = _make_dash(output_abs=str(fresh_output))
    fresh_result = classify_dashboard(dash)
    out = tmp_path / "staleness_audit.json"
    write_report(dashboards=[fresh_result], stuck_frs=[], out_path=out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["summary"]["all_clean"] is True
