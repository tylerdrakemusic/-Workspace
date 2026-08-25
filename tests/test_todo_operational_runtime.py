from __future__ import annotations

import sqlite3

import pytest

from todo_execution_contracts import ResourceDeclaration, TodoContract
from parent_join_gates import ChildJoinSnapshot
from todo_child_coordination import ChildWorktree, ChildWorktreeCoordinator, IntegrationConflict
from todo_operational_runtime import (
    OperationalConfig,
    OperationalRuntime,
    TelemetryFieldError,
)


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