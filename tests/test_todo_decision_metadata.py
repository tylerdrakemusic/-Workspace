from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest

from todo_decision_metadata import (
    DecisionMetadataError,
    DecisionMetadataStore,
    priority_guidance,
    validate_decision_metadata,
)


CONTRACT_PATH = Path(__file__).parents[1] / "src" / "contracts" / "todo_decision_metadata.v1.json"


def _peer_contract_path() -> Path:
    configured_path = os.environ.get("AI_MANIFEST_CONTRACT_PATH")
    if configured_path:
        return Path(configured_path)

    repo_root = Path(__file__).parents[1]
    return repo_root.parents[2] / "👁AI-Manifest" / ".worktrees" / repo_root.name / "src" / "contracts" / "todo_decision_metadata.v1.json"


def test_workspace_validator_is_derived_from_versioned_contract() -> None:
    from todo_decision_metadata import (
        BENEFIT_CATEGORIES,
        EVIDENCE_POLICY,
        REQUIRED_FIELDS,
        SCALE_ANCHORS,
        SCORE_FIELDS,
    )

    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    assert tuple(contract["score_fields"]) == SCORE_FIELDS
    assert frozenset(contract["required_fields"]) == REQUIRED_FIELDS
    assert tuple(contract["benefit_categories"]) == tuple(BENEFIT_CATEGORIES)
    assert contract["scale"] == {
        "min": SCALE_ANCHORS["min"],
        "max": SCALE_ANCHORS["max"],
        "anchors": {str(key): value for key, value in SCALE_ANCHORS["anchors"].items()},
    }
    assert contract["evidence_policy"] == EVIDENCE_POLICY


def test_workspace_and_ai_manifest_contract_artifacts_are_identical() -> None:
    assert json.loads(CONTRACT_PATH.read_text(encoding="utf-8")) == json.loads(
        _peer_contract_path().read_text(encoding="utf-8")
    )


def test_peer_contract_path_honors_ci_contract_location(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    contract_path = tmp_path / "peer-contract.json"
    monkeypatch.setenv("AI_MANIFEST_CONTRACT_PATH", str(contract_path))

    assert _peer_contract_path() == contract_path


def valid_metadata() -> dict:
    return {
        "expected_value": 8,
        "user_or_system_benefit": 7,
        "strategic_alignment": 6,
        "confidence": 7,
        "cost_of_delay": 8,
        "primary_benefit_category": "risk_reduction",
        "secondary_benefit_category": "maintenance",
        "benefit_summary": "Reduces repeated operational failures.",
        "justification": "The failure rate is measurable and the proposed work addresses it.",
        "evidence": ["test: failure rate is measurable"],
    }


def test_validator_accepts_canonical_metadata_and_preserves_scale_anchors() -> None:
    metadata = validate_decision_metadata(valid_metadata())

    assert set(metadata) == {
        "expected_value", "user_or_system_benefit", "strategic_alignment",
        "confidence", "cost_of_delay", "primary_benefit_category",
        "secondary_benefit_category", "benefit_summary", "justification",
        "evidence", "scale",
    }
    assert metadata["primary_benefit_category"] == "risk_reduction"
    assert metadata["scale"]["min"] == 1
    assert metadata["scale"]["max"] == 10
    assert metadata["scale"]["anchors"][1] == "minimal"
    assert metadata["scale"]["anchors"][10] == "exceptional"


@pytest.mark.parametrize(
    "field,value",
    [
        ("expected_value", 0),
        ("confidence", 11),
        ("primary_benefit_category", "invented"),
        ("secondary_benefit_category", "invented"),
    ],
)
def test_validator_rejects_invalid_scores_and_categories(field: str, value: object) -> None:
    metadata = valid_metadata()
    metadata[field] = value

    with pytest.raises(DecisionMetadataError, match=field):
        validate_decision_metadata(metadata)


def test_validator_rejects_legacy_vocabulary_without_fabricating_values() -> None:
    metadata = valid_metadata()
    metadata["benefit_score"] = 8

    with pytest.raises(DecisionMetadataError, match="unsupported fields"):
        validate_decision_metadata(metadata)


def test_validator_rejects_malformed_evidence() -> None:
    metadata = valid_metadata()
    metadata["evidence"] = [""]

    with pytest.raises(DecisionMetadataError, match="evidence"):
        validate_decision_metadata(metadata)


def test_high_impact_requires_progressively_complete_evidence() -> None:
    metadata = valid_metadata()
    metadata["evidence"] = []

    with pytest.raises(DecisionMetadataError, match="high-impact.*evidence"):
        validate_decision_metadata(metadata)

    metadata = valid_metadata()
    metadata["expected_value"] = 9
    metadata["evidence"] = ["test: one source"]

    with pytest.raises(DecisionMetadataError, match="two evidence"):
        validate_decision_metadata(metadata)


def test_store_migration_is_idempotent_and_does_not_backfill_legacy_rows() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE todos (id INTEGER PRIMARY KEY, text TEXT NOT NULL)")
    conn.execute("INSERT INTO todos (id, text) VALUES (1, 'legacy todo')")
    store = DecisionMetadataStore(conn)

    store.migrate()
    store.migrate()

    assert conn.execute("SELECT decision_metadata FROM todos WHERE id = 1").fetchone()[0] is None
    assert conn.execute("SELECT COUNT(*) FROM todo_decision_metadata_history").fetchone()[0] == 0


def test_store_persists_current_and_append_only_history_transactionally() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE todos (id INTEGER PRIMARY KEY, text TEXT NOT NULL)")
    conn.execute("INSERT INTO todos (id, text) VALUES (1, 'todo')")
    store = DecisionMetadataStore(conn)
    store.migrate()

    first = validate_decision_metadata(valid_metadata())
    second = {**first, "expected_value": 9, "evidence": [*first["evidence"], "test: confirmed"]}
    store.save(1, first)
    store.save(1, second)

    assert store.read_current(1)["expected_value"] == 9
    assert len(store.read_history(1)) == 2


def test_priority_guidance_is_advisory_and_does_not_mutate_priority() -> None:
    metadata = validate_decision_metadata(valid_metadata())

    guidance = priority_guidance(metadata, current_priority=4)

    assert guidance["current_priority"] == 4
    assert guidance["recommended_priority"] > 4
    assert "priority" not in metadata