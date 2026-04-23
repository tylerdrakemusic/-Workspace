"""Tests for tools/agent_ops_monitor.py — migration, backfill, health scoring."""
import time
from datetime import datetime, timedelta

import pytest

import agent_ops_monitor as aom


# ── AC1: Path rewriter ───────────────────────────────────────

def test_rewrite_executedcode_path():
    old = "f:/executedcode/❤Music/tools/foo.py"
    assert aom.rewrite_artifact_path(old) == "f:\\❤Music\\tools\\foo.py"


def test_rewrite_security_folder():
    old = "f:\\⊕Workspace\\!!security\\creds.md"
    assert aom.rewrite_artifact_path(old) == "f:\\⊕Workspace\\!!☾⛧security\\creds.md"


def test_rewrite_clean_path_untouched():
    clean = "f:\\⊕Workspace\\tools\\agent_ops_monitor.py"
    assert aom.rewrite_artifact_path(clean) == clean


def test_rewrite_none_path_untouched():
    assert aom.rewrite_artifact_path(None) is None
    assert aom.rewrite_artifact_path("") == ""


def test_migrate_architecture_rewrites_paths(db_conn, insert_run, insert_proof, monkeypatch):
    """Fixture DB with 3 rows: executedcode path, !!security path, clean path."""
    # Prevent touching real workspace.db during live migration.
    monkeypatch.setattr(aom, "_backup_db", lambda dry_run=False: None)

    rid = insert_run()
    p_exec = insert_proof(run_id=rid, artifact_path="f:/executedcode/❤Music/tools/foo.py")
    p_sec = insert_proof(run_id=rid, artifact_path="f:\\⊕Workspace\\!!security\\note.md")
    p_clean = insert_proof(run_id=rid, artifact_path="f:\\⊕Workspace\\tools\\ok.py")

    result = aom.migrate_architecture(db_conn, dry_run=False)

    assert result["fixed_paths"] == 2
    new_paths = {r["proof_id"]: r["artifact_path"] for r in
                 db_conn.execute("SELECT proof_id, artifact_path FROM proof_artifacts")}
    assert new_paths[p_exec] == "f:\\❤Music\\tools\\foo.py"
    assert new_paths[p_sec] == "f:\\⊕Workspace\\!!☾⛧security\\note.md"
    assert new_paths[p_clean] == "f:\\⊕Workspace\\tools\\ok.py"


def test_migrate_dry_run_no_mutation(db_conn, insert_run, insert_proof):
    rid = insert_run()
    pid = insert_proof(run_id=rid, artifact_path="f:/executedcode/❤Music/a.py")
    result = aom.migrate_architecture(db_conn, dry_run=True)
    assert result["fixed_paths"] == 1
    row = db_conn.execute("SELECT artifact_path FROM proof_artifacts WHERE proof_id = ?", (pid,)).fetchone()
    assert row["artifact_path"] == "f:/executedcode/❤Music/a.py"  # unchanged


# ── AC1: Agent sigil normalization ───────────────────────────

def test_normalize_agent_adds_sigil():
    assert aom.normalize_agent("workspace-overseer") == "⊕workspace-overseer"
    assert aom.normalize_agent("⊕workspace-doer") == "⊕workspace-doer"
    assert aom.normalize_agent("∞life-data-ingestion") == "∞life-data-ingestion"
    assert aom.normalize_agent(None) is None


def test_migrate_normalizes_agent_sigil(db_conn, insert_run, insert_proof, monkeypatch):
    monkeypatch.setattr(aom, "_backup_db", lambda dry_run=False: None)
    rid = insert_run()
    pid = insert_proof(run_id=rid, agent="workspace-overseer")
    result = aom.migrate_architecture(db_conn, dry_run=False)
    assert result["fixed_agents"] == 1
    row = db_conn.execute("SELECT agent FROM proof_artifacts WHERE proof_id = ?", (pid,)).fetchone()
    assert row["agent"] == "⊕workspace-overseer"


# ── AC2: backfill_legacy wired into --fix ────────────────────

def test_backfill_legacy_predates_proof_system(db_conn, insert_run, insert_proof):
    """Orphan run predating earliest proof gets backfilled with status=legacy + metric proof."""
    now = time.time()
    # Earliest proof is recent (today)
    recent_run = insert_run(ended_at=now - 10, status="ok")
    insert_proof(run_id=recent_run, agent="⊕workspace-doer",
                 created_at=datetime.now().isoformat())

    # Legacy orphan: ended well before earliest proof
    legacy_run = insert_run(
        started_at=now - 86400 * 30,
        ended_at=now - 86400 * 30 + 60,
        status="ok",
        name="legacy-session",
    )

    health = aom.collect_health(db_conn)
    count = aom.backfill_legacy(db_conn, health)

    assert count == 1
    # Verify metric proof created with correct description
    proofs = db_conn.execute(
        "SELECT agent, proof_type, description, verified FROM proof_artifacts WHERE run_id = ?",
        (legacy_run,),
    ).fetchall()
    assert len(proofs) == 1
    assert proofs[0]["proof_type"] == "metric"
    assert proofs[0]["description"] == "predates proof system"
    assert proofs[0]["verified"] == 1
    # Run status flipped to legacy
    run_row = db_conn.execute("SELECT status FROM perf_runs WHERE run_id = ?", (legacy_run,)).fetchone()
    assert run_row["status"] == "legacy"


def test_fix_gaps_invokes_backfill_legacy(db_conn, insert_run, insert_proof):
    """fix_gaps must include fixed_legacy in its summary."""
    now = time.time()
    # Anchor proof
    anchor_run = insert_run(ended_at=now - 5, status="ok")
    insert_proof(run_id=anchor_run, created_at=datetime.now().isoformat())
    # Legacy orphan
    insert_run(started_at=now - 86400 * 30, ended_at=now - 86400 * 30 + 30, status="ok")

    health = aom.collect_health(db_conn)
    summary = aom.fix_gaps(db_conn, health)

    assert "fixed_legacy" in summary
    assert summary["fixed_legacy"] == 1


# ── AC5: Health score math ───────────────────────────────────

def test_health_score_math(db_conn, insert_run, insert_proof):
    """Fixture: 1 zombie, 1 orphan, 2 healthy → health_pct = 50%."""
    now = time.time()
    stale = now - 7201  # 2h + 1s ago

    # Zombie: started > 2h ago, never ended
    insert_run(started_at=stale, ended_at=None, status=None, name="zombie")

    # Orphan: ended, 0 proofs
    insert_run(started_at=now - 100, ended_at=now - 50, status="ok", name="orphan")

    # Healthy 1: has proof
    h1 = insert_run(started_at=now - 100, ended_at=now - 50, status="ok", name="healthy1")
    insert_proof(run_id=h1, verified=1)

    # Healthy 2: currently running but recent
    insert_run(started_at=now - 30, ended_at=None, status=None, name="healthy2")

    health = aom.collect_health(db_conn)
    # 4 total, 1 zombie, 1 orphan, 2 healthy
    assert health["total_runs"] == 4
    assert len(health["zombies"]) == 1
    assert len(health["orphans"]) == 1
    assert health["healthy"] == 2
    # health_pct = (4 - 1 - 1) / 4 * 100 = 50.0
    assert health["health_pct"] == 50.0


def test_live_recent_historical_counts(db_conn, insert_run):
    """AC3 banner counts."""
    now = time.time()
    insert_run(started_at=now - 60)          # live
    insert_run(started_at=now - 1000)        # recent only (zombie by threshold)
    insert_run(started_at=now - 86400 * 2)   # historical only

    health = aom.collect_health(db_conn)
    assert health["live_count"] == 1
    assert health["recent_count"] == 2
    assert health["historical_total"] == 3


# ── AC6(a): zombie detection uses last_heartbeat, not started_at ─────────────

def test_zombie_uses_last_heartbeat_not_started_at(db_conn, insert_run):
    """A session with old started_at but recent last_heartbeat is NOT a zombie."""
    now = time.time()
    threshold = aom.ZOMBIE_THRESHOLD_MIN * 60

    # started_at is old (would be zombie under old logic) but heartbeat is fresh
    insert_run(
        started_at=now - threshold * 3,
        ended_at=None,
        last_heartbeat=now - 30,   # 30s ago — very fresh
        name="old-start-fresh-heartbeat",
    )
    health = aom.collect_health(db_conn)
    assert len(health["zombies"]) == 0, "Fresh last_heartbeat must prevent zombie classification"
    assert health["live_count"] == 1, "Session with fresh heartbeat must appear in live count"


def test_zombie_triggered_by_stale_last_heartbeat(db_conn, insert_run):
    """A session with recent started_at but stale last_heartbeat IS a zombie."""
    now = time.time()
    threshold = aom.ZOMBIE_THRESHOLD_MIN * 60

    # started_at is recent, but last_heartbeat is stale
    insert_run(
        started_at=now - 30,               # started 30s ago
        ended_at=None,
        last_heartbeat=now - threshold * 2,  # heartbeat far beyond threshold
        name="recent-start-stale-heartbeat",
    )
    health = aom.collect_health(db_conn)
    assert len(health["zombies"]) == 1, "Stale last_heartbeat must trigger zombie even if started_at is recent"
    assert health["live_count"] == 0


# ── AC6(b): zombie close runs before live count ───────────────────────────────

def test_fix_closes_zombie_before_live_count(db_conn, insert_run, insert_proof):
    """After fix_gaps, a previously zombie session is closed and excluded from live_count."""
    now = time.time()
    threshold = aom.ZOMBIE_THRESHOLD_MIN * 60

    # Zombie: no heartbeat, started far beyond threshold
    zombie_id = insert_run(
        started_at=now - threshold * 3,
        ended_at=None,
        name="stale-zombie",
    )
    # An actually live session (recent start, no heartbeat — uses started_at fallback)
    insert_run(
        started_at=now - 30,
        ended_at=None,
        name="actually-live",
    )

    # Before fix: zombie is visible, live_count may count zombie if started_at is checked
    health_before = aom.collect_health(db_conn)
    assert any(z["run_id"] == zombie_id for z in health_before["zombies"]), "Zombie must be detected before fix"

    # Run fix — closes zombies FIRST, then live count on the re-collected health is clean
    fix_summary = aom.fix_gaps(db_conn, health_before)
    assert fix_summary["fixed_zombies"] >= 1

    # Re-collect after fix (mirrors the --fix flow in main())
    health_after = aom.collect_health(db_conn)

    # Zombie is now closed — must not appear in zombies or live
    assert not any(z["run_id"] == zombie_id for z in health_after["zombies"]), "Zombie must be gone after fix"
    assert health_after["live_count"] == 1, "Only the actually-live session should appear after zombie is closed"


# ── AC7: validate_agent_names detects phantoms ───────────────────────────────

def test_validate_agent_names_detects_phantom(db_conn, insert_run, insert_proof):
    """validate_agent_names flags agent names that have no .agent.md file."""
    rid = insert_run()
    insert_proof(run_id=rid, agent="\u2295ops-monitor")   # known phantom alias

    report = aom.validate_agent_names(db_conn, fix=False)
    phantom_names = [p["agent"] for p in report["phantoms"]]
    assert "\u2295ops-monitor" in phantom_names


def test_validate_agent_names_fix_renames_known_alias(db_conn, insert_run, insert_proof):
    """validate_agent_names(fix=True) renames known aliases to canonical names."""
    rid = insert_run()
    pid = insert_proof(run_id=rid, agent="\u2295ops-monitor")

    report = aom.validate_agent_names(db_conn, fix=True)
    assert report["renamed"] >= 1

    row = db_conn.execute("SELECT agent FROM proof_artifacts WHERE proof_id = ?", (pid,)).fetchone()
    assert row["agent"] == "\u2295workspace-overseer"
