from __future__ import annotations

import sqlite3
import json
from pathlib import Path

import pytest

import todo_operational_runtime
from todo_execution_contracts import ResourceDeclaration, TodoContract
from parent_join_gates import ChildJoinSnapshot
from todo_child_coordination import ChildWorktree, ChildWorktreeCoordinator, IntegrationConflict
from todo_operational_runtime import (
    OperationalConfig,
    OperationalRuntime,
    TelemetryFieldError,
)


@pytest.mark.parametrize(
    "value",
    [
        "medical-record-123",
        "account-number-987654",
        "password=secret-token",
        "lease-token-abc123",
        "operator supplied reason",
    ],
)
def test_telemetry_rejects_non_opaque_or_unbounded_values(value: str) -> None:
    runtime = OperationalRuntime(sqlite3.connect(":memory:"), (TodoContract(todo_id="todo-1"),))

    with pytest.raises(TelemetryFieldError):
        runtime.telemetry.emit("retry", value, reason=value)


def test_telemetry_accepts_bounded_operational_reason() -> None:
    telemetry = OperationalRuntime(sqlite3.connect(":memory:"), ()).telemetry

    telemetry.emit("retry", "todo-1", reason="operational retry")

    assert telemetry.events[0].details["reason"] == "operational retry"


def test_runtime_loads_injected_policy_and_applies_capacity_lease_and_retry_limits() -> None:
    policy = {
        "max_parallel_todos_per_fr": 1,
        "max_total_todo_workers": 1,
        "lease_seconds": 42,
        "max_retries": 0,
    }
    contracts = tuple(TodoContract(todo_id=f"todo-{index}", fr_id="FR-1") for index in range(2))
    runtime = OperationalRuntime(sqlite3.connect(":memory:"), contracts, policy=policy)

    claimed = runtime.dispatch(now=100.0)

    assert len(claimed) == 1
    assert claimed[0].lease_expires_at == 142.0
    assert runtime.lifecycle.get("todo-0").max_retries == 0


def test_runtime_rejects_invalid_injected_policy() -> None:
    with pytest.raises(ValueError, match="max_total_todo_workers"):
        OperationalRuntime(
            sqlite3.connect(":memory:"),
            (),
            policy={
                "max_parallel_todos_per_fr": 1,
                "max_total_todo_workers": "unbounded",
                "lease_seconds": 1,
                "max_retries": 0,
            },
        )


def test_runtime_loads_policy_from_explicit_json_path(tmp_path) -> None:
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        '{"max_parallel_todos_per_fr": 1, "max_total_todo_workers": 1, '
        '"lease_seconds": 17, "max_retries": 1}',
        encoding="utf-8",
    )

    runtime = OperationalRuntime(sqlite3.connect(":memory:"), (), policy_path=policy_path)

    assert runtime.config.lease_seconds == 17


def test_default_runtime_loads_checked_in_policy_and_tracks_policy_changes(tmp_path, monkeypatch) -> None:
    policy_path = Path(todo_operational_runtime.__file__).resolve().parents[1] / "config" / "todo_execution_policy.json"
    checked_in_policy = json.loads(policy_path.read_text(encoding="utf-8"))
    default_runtime = OperationalRuntime(sqlite3.connect(":memory:"), ())

    assert default_runtime.config == OperationalConfig.from_policy(checked_in_policy)

    changed_policy_path = tmp_path / "changed-policy.json"
    changed_policy_path.write_text(
        '{"max_parallel_todos_per_fr": 1, "max_total_todo_workers": 1, '
        '"lease_seconds": 17, "max_retries": 0}',
        encoding="utf-8",
    )
    monkeypatch.setattr(todo_operational_runtime, "DEFAULT_POLICY_PATH", changed_policy_path)
    contracts = tuple(TodoContract(todo_id=f"todo-{index}", fr_id="FR-1") for index in range(2))

    changed_runtime = OperationalRuntime(sqlite3.connect(":memory:"), contracts)
    claimed = changed_runtime.dispatch(now=100.0)

    assert len(claimed) == 1
    assert claimed[0].lease_expires_at == 117.0
    assert changed_runtime.lifecycle.get("todo-0").max_retries == 0


def test_operational_defaults_bound_dispatch_and_allowlisted_telemetry() -> None:
    config = OperationalConfig()
    assert config.max_parallel_per_fr == 8
    assert config.global_worker_capacity == 16

    contracts = tuple(
        TodoContract(
            todo_id=f"todo-{index}",
            fr_id="FR-1",
            resources=(ResourceDeclaration("file", f"file-{index}.py"),),
        )
        for index in range(10)
    )
    runtime = OperationalRuntime(sqlite3.connect(":memory:"), contracts, config=config)

    claimed = runtime.dispatch(now=100.0, worker_prefix="worker")

    assert [record.todo_id for record in claimed] == [f"todo-{index}" for index in range(8)]
    assert [event.kind for event in runtime.telemetry.events[:10]] == [
        "queue_depth",
        "readiness",
        *(["claim"] * 8),
    ]
    assert [event.kind for event in runtime.telemetry.events[10:]] == ["conflict", "conflict"]
    assert all(set(event.details) <= {"depth", "ready", "queued", "attempt", "reason"} for event in runtime.telemetry.events)


def test_operational_runtime_rejects_secret_bearing_telemetry() -> None:
    runtime = OperationalRuntime(sqlite3.connect(":memory:"), (TodoContract(todo_id="todo-1"),))

    with pytest.raises(TelemetryFieldError, match="token"):
        runtime.telemetry.emit("claim", "todo-1", token="must-not-be-recorded")


def test_telemetry_query_filters_allowlisted_events_deterministically() -> None:
    runtime = OperationalRuntime(sqlite3.connect(":memory:"), (TodoContract(todo_id="todo-1"),))
    runtime.telemetry.emit("claim", "todo-1", attempt=1)
    runtime.telemetry.emit("retry", "todo-1", attempt=2)
    runtime.telemetry.emit("claim", "todo-2", attempt=1)

    assert runtime.telemetry.query(kind="claim", todo_id="todo-1") == (
        runtime.telemetry.events[0],
    )
    assert runtime.telemetry.query(attempt=2) == (runtime.telemetry.events[1],)

    with pytest.raises(TelemetryFieldError, match="token"):
        runtime.telemetry.query(token="must-not-be-queryable")


def test_dispatch_is_deterministic_and_resource_conflicts_are_observable() -> None:
    contracts = (
        TodoContract(todo_id="todo-b", fr_id="FR-1", resources=(ResourceDeclaration("shared", "db"),)),
        TodoContract(todo_id="todo-a", fr_id="FR-1", resources=(ResourceDeclaration("shared", "db"),)),
    )
    runtime = OperationalRuntime(sqlite3.connect(":memory:"), contracts)

    claimed = runtime.dispatch(now=100.0, worker_prefix="worker")

    assert [record.todo_id for record in claimed] == ["todo-a"]
    assert any(event.kind == "conflict" and event.todo_id == "todo-b" for event in runtime.telemetry.events)


def test_runtime_tracks_lease_retry_and_stale_recovery_without_exposing_tokens() -> None:
    runtime = OperationalRuntime(sqlite3.connect(":memory:"), (TodoContract(todo_id="todo-1", fr_id="FR-1"),))
    record = runtime.dispatch(now=100.0)[0]

    runtime.heartbeat(record, now=110.0)
    runtime.fail(record, now=120.0, error="transient")
    runtime.retry(todo_id="todo-1", now=121.0)
    record = runtime.dispatch(now=122.0)[0]
    runtime.recover_stale(now=423.0)

    kinds = [event.kind for event in runtime.telemetry.events]
    assert "lease" in kinds
    assert "retry" in kinds
    assert "stale_recovery" in kinds
    assert all("token" not in event.details and "error" not in event.details for event in runtime.telemetry.events)


def test_runtime_requires_validated_integrated_children_before_parent_gate() -> None:
    fr_id = "FR-1"
    coordinator = ChildWorktreeCoordinator(fr_id=fr_id, target_branch="feature/fr-1", capacity=1)
    runtime = OperationalRuntime(sqlite3.connect(":memory:"), (TodoContract(todo_id="child-1", fr_id=fr_id),))
    child = ChildWorktree("child-1", fr_id, "worker-1", "claim-1", "feature/child-1", "worktree/child-1", "completed", True, "parent-1")
    coordinator.admit(child)
    runtime.integrate_child(coordinator, "child-1", target_head="parent-1")

    result = runtime.evaluate_parent_join(
        parent_branch="feature/fr-1",
        parent_head="parent-1",
        required_todos=("child-1",),
        children=(ChildJoinSnapshot("child-1", fr_id, "completed", True, (), (), "feature/fr-1", "parent-1", "parent-1"),),
    )

    assert result.complete is True
    assert any(event.kind == "integration" for event in runtime.telemetry.events)
    assert any(event.kind == "gate" and event.details["ready"] is True for event in runtime.telemetry.events)


def test_runtime_preserves_conflicting_child_and_blocks_failed_join() -> None:
    fr_id = "FR-1"
    coordinator = ChildWorktreeCoordinator(
        fr_id=fr_id,
        target_branch="feature/fr-1",
        capacity=1,
        rebase=lambda child, target_head: False,
    )
    runtime = OperationalRuntime(sqlite3.connect(":memory:"), (TodoContract(todo_id="child-1", fr_id=fr_id),))
    coordinator.admit(ChildWorktree("child-1", fr_id, "worker-1", "claim-1", "feature/child-1", "worktree/child-1", "completed", True, "old-head"))

    with pytest.raises(IntegrationConflict):
        runtime.integrate_child(coordinator, "child-1", target_head="new-head")

    blocked = runtime.evaluate_parent_join(
        parent_branch="feature/fr-1",
        parent_head="new-head",
        required_todos=("child-1",),
        children=(ChildJoinSnapshot("child-1", fr_id, "failed", False, ("proof",), (), None, "new-head", "old-head"),),
    )

    assert blocked.complete is False
    assert len(blocked.blockers) == 5
    assert coordinator.source("child-1").todo_id == "child-1"