"""Tests for roadmap_generator.py — dependency parsing, quarter bucketing, graph build."""
import json
import os
import subprocess
import sqlite3
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "utils"))

from roadmap_generator import (  # noqa: E402
    ACTIVE_FR_STATES,
    UNMAPPED_PROJECT,
    add_quarters,
    assign_quarter,
    build_roadmap,
    canonicalize_project,
    current_quarter,
    extract_fr_dependencies,
    extract_todo_fr_references,
    fetch_active_frs,
    generate_roadmap,
    parse_dependencies,
)


# ─────────────────────────────────────────────────────────────────────────────
# Dependency parsing

def test_parse_dependencies_single():
    text = "This FR requires prior work. Depends on: FR-20260524-tts-batch-queue."
    assert parse_dependencies(text) == ["FR-20260524-tts-batch-queue"]


def test_parse_dependencies_multiple_comma_separated():
    text = "Depends on: FR-20260501-a, FR-20260502-b"
    assert parse_dependencies(text) == ["FR-20260501-a", "FR-20260502-b"]


def test_parse_dependencies_none_present():
    assert parse_dependencies("No dependency markers here.") == []


def test_parse_dependencies_handles_none_and_empty():
    assert parse_dependencies(None) == []
    assert parse_dependencies("") == []


def test_extract_fr_dependencies_scans_multiple_fields_and_dedupes():
    fr = {
        "id": "FR-20260601-self",
        "title": "Depends on: FR-20260524-tts-batch-queue",
        "acceptance_criteria": "Also depends on: FR-20260524-tts-batch-queue, FR-20260502-b",
        "concurrency_notes": None,
    }
    deps = extract_fr_dependencies(fr)
    assert deps == ["FR-20260524-tts-batch-queue", "FR-20260502-b"]


def test_extract_fr_dependencies_excludes_self_reference():
    fr = {
        "id": "FR-20260524-tts-batch-queue",
        "title": "Depends on: FR-20260524-tts-batch-queue",
        "acceptance_criteria": None,
        "concurrency_notes": None,
    }
    assert extract_fr_dependencies(fr) == []


def test_extract_todo_fr_references_known_case():
    # Real todo #102 text referencing FR-20260524-tts-batch-queue
    text = (
        "Split executive_audio_brief.py into per-section audio clips "
        "(intro, life summary, music summary, quantum summary, workspace summary) "
        "and route generation through TtsQueueWorker — enables per-section replay, "
        "concurrent generation, and retry on rate-limit. "
        "Depends on: FR-20260524-tts-batch-queue."
    )
    assert extract_todo_fr_references(text) == ["FR-20260524-tts-batch-queue"]


# ─────────────────────────────────────────────────────────────────────────────
# Quarterly bucketing

def test_current_quarter():
    assert current_quarter(date(2026, 7, 1)) == "2026-Q3"
    assert current_quarter(date(2026, 1, 15)) == "2026-Q1"
    assert current_quarter(date(2026, 12, 31)) == "2026-Q4"


def test_add_quarters_within_year():
    assert add_quarters("2026-Q3", 1) == "2026-Q4"
    assert add_quarters("2026-Q3", 0) == "2026-Q3"


def test_add_quarters_rolls_into_next_year():
    assert add_quarters("2026-Q4", 1) == "2027-Q1"
    assert add_quarters("2026-Q3", 2) == "2027-Q1"


def test_assign_quarter_manual_override_wins():
    fr = {"id": "FR-1", "risk": "high", "state": "OPEN", "opened_at": "2026-06-30",
          "target_quarter": "2027-Q2"}
    assert assign_quarter(fr, today=date(2026, 6, 30)) == "2027-Q2"


def test_assign_quarter_low_risk_advanced_state_old_age_pulls_earlier():
    fr = {"id": "FR-1", "risk": "low", "state": "FUNCTIONAL_QA",
          "opened_at": "2026-01-01", "target_quarter": None}
    today = date(2026, 6, 30)
    earlier = assign_quarter(fr, today=today)

    fr_high_risk_new = {"id": "FR-2", "risk": "high", "state": "OPEN",
                         "opened_at": "2026-06-25", "target_quarter": None}
    later = assign_quarter(fr_high_risk_new, today=today)

    def _q_index(q):
        year, qn = q.split("-Q")
        return int(year) * 4 + int(qn)

    assert _q_index(earlier) < _q_index(later)


def test_assign_quarter_bucket_clamped_to_range():
    today = date(2026, 6, 30)
    base = current_quarter(today)
    fr = {"id": "FR-1", "risk": "high", "state": "OPEN", "opened_at": "2026-06-29",
          "target_quarter": None}
    result = assign_quarter(fr, today=today)

    def _q_index(q):
        year, qn = q.split("-Q")
        return int(year) * 4 + int(qn)

    assert 0 <= _q_index(result) - _q_index(base) <= 3


# ─────────────────────────────────────────────────────────────────────────────
# Roadmap graph construction

def _fr(id_, title, project="workspace", state="OPEN", risk="medium",
        opened_at="2026-01-01", acceptance_criteria=None, concurrency_notes=None,
        target_quarter=None):
    return {
        "id": id_, "title": title, "projects": project, "state": state, "risk": risk,
        "opened_at": opened_at, "acceptance_criteria": acceptance_criteria,
        "concurrency_notes": concurrency_notes, "target_quarter": target_quarter,
    }


def test_build_roadmap_structure_keys():
    frs = [_fr("FR-1", "First FR")]
    roadmap = build_roadmap(frs, todos=[], today=date(2026, 6, 30))
    assert set(roadmap.keys()) == {
        "generated_at", "nodes", "fr_edges", "project_edges", "todo_refs", "quarters",
    }
    assert len(roadmap["nodes"]) == 1
    node = roadmap["nodes"][0]
    assert node["id"] == "FR-1"
    assert node["project"] == "⊕Workspace"
    assert node["quarter"] in roadmap["quarters"]


def test_build_roadmap_fr_to_fr_and_project_to_project_edges():
    frs = [
        _fr("FR-20260601-music", "Music FR", project="music",
            acceptance_criteria="Depends on: FR-20260601-workspace"),
        _fr("FR-20260601-workspace", "Workspace FR", project="workspace"),
    ]
    roadmap = build_roadmap(frs, todos=[], today=date(2026, 6, 30))
    assert {"from": "FR-20260601-music", "to": "FR-20260601-workspace"} in roadmap["fr_edges"]
    assert {"from": "❤Music", "to": "⊕Workspace"} in roadmap["project_edges"]


def test_build_roadmap_todo_refs_known_case():
    frs = [_fr("FR-20260524-tts-batch-queue", "ElevenLabs TTS Batch Queue Processor",
                project="ai_manifest")]
    todos = [{
        "id": 102, "project": "ai_manifest",
        "text": "... Depends on: FR-20260524-tts-batch-queue.",
    }]
    roadmap = build_roadmap(frs, todos=todos, today=date(2026, 6, 30))
    assert {
        "todo_id": 102, "todo_project": "ai_manifest",
        "fr_id": "FR-20260524-tts-batch-queue", "fr_active": True,
    } in roadmap["todo_refs"]


def test_build_roadmap_todo_ref_marks_inactive_fr():
    frs = []  # FR not present among active FRs
    todos = [{"id": 5, "project": "music", "text": "Depends on: FR-20250101-old"}]
    roadmap = build_roadmap(frs, todos=todos, today=date(2026, 6, 30))
    assert roadmap["todo_refs"][0]["fr_active"] is False


def test_build_roadmap_quarters_section_populated_and_covers_all_nodes():
    frs = [
        _fr("FR-1", "First", state="OPEN"),
        _fr("FR-2", "Second", state="IN_PROGRESS", target_quarter="2026-Q4"),
    ]
    roadmap = build_roadmap(frs, todos=[], today=date(2026, 6, 30))
    assert roadmap["quarters"]
    all_ids_in_quarters = {fr_id for ids in roadmap["quarters"].values() for fr_id in ids}
    assert all_ids_in_quarters == {"FR-1", "FR-2"}
    for node in roadmap["nodes"]:
        assert node["id"] in roadmap["quarters"][node["quarter"]]


# ─────────────────────────────────────────────────────────────────────────────
# Active-state include-list (real-data regression: over-inclusive filter dumped
# 239 mostly-finished nodes because DONE/MERGED/SOAKING weren't excluded)

def test_active_fr_states_excludes_terminal_states():
    terminal = {"DONE", "MERGED", "SOAKING", "SIGNED_OFF", "ARCHIVED", "CLOSED"}
    assert ACTIVE_FR_STATES.isdisjoint(terminal)


def test_active_fr_states_includes_in_flight_states():
    for state in (
        "OPEN", "TRIAGED", "BRANCHED", "IN_PROGRESS", "CHANGES_REQUESTED",
        "FUNCTIONAL_QA", "ARCHITECTURE_REVIEW", "REVIEW_REQUESTED",
        "AUTO_REVIEWED", "TYLER_APPROVED", "BRANCH_CHECKED_OUT",
    ):
        assert state in ACTIVE_FR_STATES


def test_fetch_active_frs_excludes_done_and_merged(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        "CREATE TABLE feature_requests (id TEXT PRIMARY KEY, title TEXT, state TEXT, "
        "projects TEXT, risk TEXT, opened_at TEXT, acceptance_criteria TEXT, concurrency_notes TEXT);"
    )
    conn.executemany(
        "INSERT INTO feature_requests (id, title, state, projects, risk, opened_at) VALUES (?,?,?,?,?,?)",
        [
            ("FR-1", "Done work", "DONE", "workspace", "low", "2026-01-01"),
            ("FR-2", "Merged work", "MERGED", "workspace", "low", "2026-01-01"),
            ("FR-3", "Soaking work", "SOAKING", "workspace", "low", "2026-01-01"),
            ("FR-4", "Active work", "OPEN", "workspace", "low", "2026-01-01"),
            ("FR-5", "Changes requested", "CHANGES_REQUESTED", "workspace", "low", "2026-01-01"),
        ],
    )
    conn.commit()
    active = fetch_active_frs(conn)
    conn.close()
    assert {fr["id"] for fr in active} == {"FR-4", "FR-5"}


# ─────────────────────────────────────────────────────────────────────────────
# Project name canonicalization

@pytest.mark.parametrize("raw,expected", [
    ("∞Life", "∞Life"),
    ("life", "∞Life"),
    ("InfiniteLife", "∞Life"),
    ("infinitelife", "∞Life"),
    ("inflife", "∞Life"),
    ("8Life", "∞Life"),
    ("❤Music", "❤Music"),
    ("music", "❤Music"),
    ("Music", "❤Music"),
    ("HeartMusic", "❤Music"),
    ("heartmusic", "❤Music"),
    ("heart-music", "❤Music"),
    ("heart_music", "❤Music"),
    ("?Music", "❤Music"),
    ("⊕Music", "❤Music"),
    ("⟨ψ⟩Quantum", "⟨ψ⟩Quantum"),
    ("quantum", "⟨ψ⟩Quantum"),
    ("Quantum", "⟨ψ⟩Quantum"),
    ("psi-quantum", "⟨ψ⟩Quantum"),
    ("psi_Quantum", "⟨ψ⟩Quantum"),
    ("???Quantum", "⟨ψ⟩Quantum"),
    ("👁AI-Manifest", "👁AI-Manifest"),
    ("AI-Manifest", "👁AI-Manifest"),
    ("ai_manifest", "👁AI-Manifest"),
    ("aimanifest", "👁AI-Manifest"),
    ("??AI-Manifest", "👁AI-Manifest"),
    ("⊕Workspace", "⊕Workspace"),
    ("workspace", "⊕Workspace"),
    ("Workspace", "⊕Workspace"),
    ("WORKSPACE", "⊕Workspace"),
    ("oplus-workspace", "⊕Workspace"),
    ("?Workspace", "⊕Workspace"),
    ("ΣCapital", "ΣCapital"),
    ("SigmaCapital", "ΣCapital"),
    ("SIGMACapital", "ΣCapital"),
    ("sigmacapital", "ΣCapital"),
    ("capital", "ΣCapital"),
    ("⊕Workspace (primary); indirectly all 5 projects via the workspace file", "⊕Workspace"),
    ("❤Music (primary)", "❤Music"),
])
def test_canonicalize_project_known_aliases(raw, expected):
    assert canonicalize_project(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "  ", "All 5", "All 5 projects", "unknown"])
def test_canonicalize_project_unmappable_goes_to_unmapped_bucket(raw):
    assert canonicalize_project(raw) == UNMAPPED_PROJECT


def test_build_roadmap_canonicalizes_project_names():
    frs = [
        _fr("FR-1", "Music FR", project="heart_music"),
        _fr("FR-2", "Workspace FR", project="?Workspace"),
    ]
    roadmap = build_roadmap(frs, todos=[], today=date(2026, 6, 30))
    projects = {n["id"]: n["project"] for n in roadmap["nodes"]}
    assert projects == {"FR-1": "❤Music", "FR-2": "⊕Workspace"}


def test_build_roadmap_project_edges_use_canonical_names():
    frs = [
        _fr("FR-20260601-music", "Music FR", project="heartmusic",
            acceptance_criteria="Depends on: FR-20260601-workspace"),
        _fr("FR-20260601-workspace", "Workspace FR", project="oplus-workspace"),
    ]
    roadmap = build_roadmap(frs, todos=[], today=date(2026, 6, 30))
    assert {"from": "❤Music", "to": "⊕Workspace"} in roadmap["project_edges"]


# ─────────────────────────────────────────────────────────────────────────────
# End-to-end integration against a seeded fixture DB (not the real, encrypted
# fr_ledgers.db / manifest_todos.db)

@pytest.fixture
def fixture_fr_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        "CREATE TABLE feature_requests ("
        " id TEXT PRIMARY KEY, title TEXT, state TEXT, projects TEXT, risk TEXT,"
        " opened_at TEXT, acceptance_criteria TEXT, concurrency_notes TEXT, target_quarter TEXT"
        ");"
    )
    conn.executemany(
        "INSERT INTO feature_requests "
        "(id, title, state, projects, risk, opened_at, acceptance_criteria, concurrency_notes, target_quarter) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        [
            ("FR-20260101-old-done", "Old finished work", "DONE", "workspace", "low",
             "2026-01-01", None, None, None),
            ("FR-20260201-old-merged", "Old merged work", "MERGED", "music", "low",
             "2026-02-01", None, None, None),
            ("FR-20260301-old-soaking", "Old soaking work", "SOAKING", "quantum", "low",
             "2026-03-01", None, None, None),
            ("FR-20260601-active-music", "Active music work", "IN_PROGRESS", "heart_music", "medium",
             "2026-06-01", "Depends on: FR-20260601-active-workspace", None, None),
            ("FR-20260601-active-workspace", "Active workspace work", "OPEN", "?Workspace", "low",
             "2026-06-15", None, None, "2026-Q4"),
        ],
    )
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def fixture_todos_db(tmp_path):
    db_path = tmp_path / "manifest_todos_fixture.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        "CREATE TABLE todos (id INTEGER PRIMARY KEY, project TEXT, text TEXT, done INTEGER);"
    )
    conn.executemany(
        "INSERT INTO todos (id, project, text, done) VALUES (?,?,?,?)",
        [
            (1, "ai_manifest", "Depends on: FR-20260601-active-music", 0),
            (2, "music", "Old closed-out todo", 1),
        ],
    )
    conn.commit()
    conn.close()
    return db_path


def test_generate_roadmap_end_to_end_against_fixture_db(fixture_fr_conn, fixture_todos_db, tmp_path):
    out_path = tmp_path / "roadmap.json"
    roadmap = generate_roadmap(
        output_path=out_path,
        fr_connection=fixture_fr_conn,
        todos_db_path=fixture_todos_db,
    )

    # Filtering: only the 2 active FRs surface, DONE/MERGED/SOAKING excluded.
    node_ids = {n["id"] for n in roadmap["nodes"]}
    assert node_ids == {"FR-20260601-active-music", "FR-20260601-active-workspace"}

    # Canonicalization: raw aliases collapse to canonical project names.
    projects = {n["id"]: n["project"] for n in roadmap["nodes"]}
    assert projects == {
        "FR-20260601-active-music": "❤Music",
        "FR-20260601-active-workspace": "⊕Workspace",
    }

    # Cross-project dependency edge uses canonical names.
    assert {"from": "❤Music", "to": "⊕Workspace"} in roadmap["project_edges"]


# ─────────────────────────────────────────────────────────────────────────────
# AC1: cross-project subprocess invocation contract (👁AI-Manifest's portal
# pipeline calls this script via subprocess with a fixed path + --out arg —
# see feature-request-flow / BFX-20260701-roadmap-tab-follow-up).

def test_main_cli_invokable_as_subprocess_and_writes_valid_json(tmp_path):
    """Verify the stable subprocess contract:
    C:\\G\\python.exe f:\\⊕Workspace\\src\\utils\\roadmap_generator.py --out <path>
    """
    script = Path(__file__).resolve().parent.parent / "src" / "utils" / "roadmap_generator.py"
    out_path = tmp_path / "roadmap_subprocess.json"

    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    # CI runners don't have FR_LEDGERS_DB_KEY/WORKSPACE_DB_KEY set as system
    # env vars (only Tyler's dev machine does), so generate_roadmap()'s
    # get_connection() would raise RuntimeError. Since fr_ledgers.db is
    # gitignored and won't exist in a fresh checkout, any key value works —
    # sqlcipher3 encrypts a brand-new empty DB with whatever key is supplied
    # on first open. Only inject a dummy key when one isn't already present
    # so this still exercises Tyler's real DB/key locally.
    if not env.get("FR_LEDGERS_DB_KEY") and not env.get("WORKSPACE_DB_KEY"):
        env["FR_LEDGERS_DB_KEY"] = "test-only-dummy-key-for-ci"

    result = subprocess.run(
        [sys.executable, str(script), "--out", str(out_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert out_path.is_file()

    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert set(data.keys()) == {
        "generated_at", "nodes", "fr_edges", "project_edges", "todo_refs", "quarters",
    }
