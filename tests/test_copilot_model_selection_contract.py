from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.utils.copilot_model_selection import (
    BenchmarkEvidence,
    CachedInventory,
    ContractValidationError,
    DelegationManifest,
    InventorySnapshot,
    ModelRecord,
    SelectionCandidate,
    dispatch,
    ingest_benchmark,
    observed_cost_per_accepted,
    persist_telemetry,
    select_model,
    TelemetryRecord,
    telemetry_from_usage,
)


def test_inventory_contract_is_versioned_and_metadata_only() -> None:
    inventory = InventorySnapshot(
        captured_at=datetime.now(timezone.utc),
        source="supported-copilot-enumeration",
        models=(
            ModelRecord(
                model_id="gpt-5.3-codex",
                provider="openai",
                roles=("tdd", "qa"),
                tiers=("standard", "heavy"),
                available=True,
            ),
        ),
    )

    payload = inventory.to_dict()

    assert payload["schema_version"] == 1
    assert payload["models"][0]["provider"] == "openai"
    assert "prompt" not in str(payload).lower()


def test_contract_rejects_prompt_or_task_payloads() -> None:
    with pytest.raises(ContractValidationError, match="metadata-only"):
        InventorySnapshot.from_dict(
            {
                "schema_version": 1,
                "captured_at": "2026-08-30T00:00:00Z",
                "source": "supported-copilot-enumeration",
                "models": [
                    {
                        "model_id": "gpt-5.3-codex",
                        "provider": "openai",
                        "roles": ["qa"],
                        "tiers": ["standard"],
                        "available": True,
                        "prompt": "secret task payload",
                    }
                ],
            }
        )


def _model(model_id: str, provider: str, *, quality: float = 0.9, cost: str = "1") -> ModelRecord:
    return ModelRecord(model_id, provider, ("tdd",), ("standard",), True, quality, 0.9, 0.9)


def test_stale_inventory_is_explicit_when_enumeration_is_unavailable(tmp_path) -> None:
    path = tmp_path / "inventory.json"
    snapshot = InventorySnapshot(
        datetime(2026, 8, 29, tzinfo=timezone.utc),
        "supported-copilot-enumeration",
        (_model("a", "anthropic"),),
        freshness_seconds=60,
    )
    path.write_text(__import__("json").dumps(snapshot.to_dict()), encoding="utf-8")

    current = CachedInventory(path).current(datetime(2026, 8, 30, tzinfo=timezone.utc))

    assert current.status == "stale-fallback"
    assert current.models[0].model_id == "a"


def test_unverifiable_benchmark_evidence_is_rejected() -> None:
    class Adapter:
        def ingest(self, record):
            return BenchmarkEvidence(
                source_url="",
                benchmark_name="bench",
                benchmark_version="1",
                methodology="method",
                retrieved_at=datetime.now(timezone.utc),
                model_id="a",
                role="tdd",
                raw_score=0.9,
                comparable=True,
                provenance="",
            )

    with pytest.raises(ContractValidationError, match="unverifiable"):
        ingest_benchmark(Adapter(), {})


def test_selector_applies_quality_gate_before_deterministic_cost_ranking() -> None:
    candidates = [
        SelectionCandidate(_model("cheap", "openai", quality=0.69), "tdd", "standard", __import__("decimal").Decimal("1")),
        SelectionCandidate(_model("best", "anthropic", quality=0.9), "tdd", "standard", __import__("decimal").Decimal("2")),
    ]

    decision = select_model(candidates, "tdd", "standard")

    assert decision.model_id == "best"
    assert decision.status == "selected"


def test_dispatch_fails_closed_without_supported_consumer() -> None:
    manifest = DelegationManifest("FR-1", "tdd", "standard", "best", "anthropic", "available", "test")

    result, fallback = dispatch(manifest, None, preflight=lambda _: True)

    assert result is None
    assert fallback.fallback_model is None
    assert "unavailable" in fallback.reason


def test_dispatch_requires_live_preflight_before_activation() -> None:
    manifest = DelegationManifest("FR-1", "tdd", "standard", "best", "anthropic", "available", "test")

    result, fallback = dispatch(manifest, object())

    assert result is None
    assert "preflight" in fallback.reason


def test_dispatch_retries_then_fails_over_deterministically() -> None:
    class Consumer:
        def __init__(self):
            self.calls = []

        def delegate(self, manifest):
            self.calls.append(manifest.model_id)
            if manifest.model_id == "first":
                raise RuntimeError("temporary")
            return {"accepted": True, "model_id": manifest.model_id}

    first = DelegationManifest("FR-1", "tdd", "standard", "first", "openai", "available", "selected")
    second = DelegationManifest("FR-1", "tdd", "standard", "second", "anthropic", "available", "failover")
    consumer = Consumer()

    result, fallback = dispatch(first, consumer, failover=(second,), preflight=lambda _: True, retry_limit=1)

    assert result["model_id"] == "second"
    assert consumer.calls == ["first", "first", "second"]
    assert fallback.attempted_models == ("first", "second")


def test_telemetry_cost_is_per_accepted_outcome() -> None:
    records = [
        TelemetryRecord("FR-1", "qa", "standard", "a", "openai", 100, 0, False, True, __import__("decimal").Decimal("2")),
        TelemetryRecord("FR-1", "qa", "standard", "a", "openai", 150, 1, False, False, __import__("decimal").Decimal("1")),
    ]

    assert observed_cost_per_accepted(records, "a") == __import__("decimal").Decimal("3")


def test_telemetry_uses_existing_cost_calculator_and_writes_metadata_only(tmp_path) -> None:
    record = telemetry_from_usage(
        fr_id="FR-1", role="qa", tier="standard", model_id="claude-sonnet-4-6",
        provider="anthropic", usage={"input_tokens": 100}, latency_ms=12,
        retries=0, failed=False, accepted=True,
    )
    destination = tmp_path / "telemetry.jsonl"

    persist_telemetry(destination, record)

    saved = destination.read_text(encoding="utf-8")
    assert '"schema_version": 1' in saved
    assert '"usd_cost":' in saved
    assert "input_tokens" not in saved


def test_operations_documentation_declares_fail_closed_activation_and_shadow_mode() -> None:
    root = __import__("pathlib").Path(__file__).parents[1]
    flow = (root / ".github" / "instructions" / "feature-request-flow.instructions.md").read_text(encoding="utf-8")
    docs = (root / "docs" / "copilot-model-selection.md").read_text(encoding="utf-8")

    assert "shadow replay" in flow.lower()
    assert "fail-closed" in docs.lower()
    assert "agent yaml" in docs.lower()