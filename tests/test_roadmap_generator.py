"""Tests for roadmap_generator.py — dependency parsing, quarter bucketing, graph build."""
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "utils"))

from roadmap_generator import (  # noqa: E402
    add_quarters,
    assign_quarter,
    build_roadmap,
    current_quarter,
    extract_fr_dependencies,
    extract_todo_fr_references,
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
    assert node["project"] == "workspace"
    assert node["quarter"] in roadmap["quarters"]


def test_build_roadmap_fr_to_fr_and_project_to_project_edges():
    frs = [
        _fr("FR-20260601-music", "Music FR", project="music",
            acceptance_criteria="Depends on: FR-20260601-workspace"),
        _fr("FR-20260601-workspace", "Workspace FR", project="workspace"),
    ]
    roadmap = build_roadmap(frs, todos=[], today=date(2026, 6, 30))
    assert {"from": "FR-20260601-music", "to": "FR-20260601-workspace"} in roadmap["fr_edges"]
    assert {"from": "music", "to": "workspace"} in roadmap["project_edges"]


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
