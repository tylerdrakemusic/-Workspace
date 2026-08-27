from __future__ import annotations

import sqlite3

import pytest

from todo_decision_metadata import (
    DecisionMetadataError,
    DecisionMetadataStore,
    priority_guidance,
    validate_decision_metadata,
)


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