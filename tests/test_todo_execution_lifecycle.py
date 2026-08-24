from __future__ import annotations

import sqlite3

import pytest

from todo_execution_lifecycle import (
    DuplicateClaimError,
    ExecutionLifecycle,
    InvalidTransitionError,
    LeaseOwnershipError,
    RetryExhaustedError,
)


def make_lifecycle() -> ExecutionLifecycle:
    connection = sqlite3.connect(":memory:")
    return ExecutionLifecycle(connection)


def test_active_claim_is_unique_but_repeated_delivery_is_idempotent() -> None:
    lifecycle = make_lifecycle()

    first = lifecycle.claim(
        todo_id="todo-1",
        fr_id="FR-1",
        worker_id="worker-a",
        claim_id="claim-1",
        lease_token="token-1",
        now=100.0,
        lease_seconds=30,
        max_retries=2,
        idempotency_key="delivery-1",
    )

    assert lifecycle.claim(
        todo_id="todo-1",
        fr_id="FR-1",
        worker_id="worker-a",
        claim_id="claim-1",
        lease_token="token-1",
        now=101.0,
        lease_seconds=30,
        max_retries=2,
        idempotency_key="delivery-1",
    ) == first

    with pytest.raises(DuplicateClaimError):
        lifecycle.claim(
            todo_id="todo-1",
            fr_id="FR-1",
            worker_id="worker-b",
            claim_id="claim-2",
            lease_token="token-2",
            now=102.0,
            lease_seconds=30,
            max_retries=2,
            idempotency_key="delivery-2",
        )


def claim(lifecycle: ExecutionLifecycle, *, now: float = 100.0, retries: int = 1):
    return lifecycle.claim(
        todo_id="todo-1", fr_id="FR-1", worker_id="worker-a",
        claim_id=f"claim-{now}", lease_token=f"token-{now}", now=now,
        lease_seconds=30, max_retries=retries, idempotency_key=f"delivery-{now}",
    )


def test_heartbeat_requires_owner_and_live_lease() -> None:
    lifecycle = make_lifecycle()
    claim(lifecycle)

    with pytest.raises(LeaseOwnershipError):
        lifecycle.heartbeat("todo-1", "worker-b", "token-100.0", 110.0, 30)
    with pytest.raises(LeaseOwnershipError):
        lifecycle.heartbeat("todo-1", "worker-a", "wrong", 110.0, 30)
    with pytest.raises(InvalidTransitionError):
        lifecycle.heartbeat("todo-1", "worker-a", "token-100.0", 130.0, 30)


def test_completion_and_failure_are_single_winner_terminal_races() -> None:
    lifecycle = make_lifecycle()
    claim(lifecycle)
    lifecycle.heartbeat("todo-1", "worker-a", "token-100.0", 105.0, 30)

    lifecycle.complete("todo-1", "worker-a", "token-100.0", 110.0, "done")
    with pytest.raises(InvalidTransitionError):
        lifecycle.fail("todo-1", "worker-a", "token-100.0", 111.0, "late failure")
    assert lifecycle.get("todo-1").state == "completed"


def test_failure_retry_and_exhaustion_preserve_terminal_failure() -> None:
    lifecycle = make_lifecycle()
    claim(lifecycle, retries=1)
    lifecycle.fail("todo-1", "worker-a", "token-100.0", 110.0, "transient")
    retry = lifecycle.retry("todo-1", 111.0, "transient retry")
    assert retry.state == "queued"
    claim(lifecycle, now=120.0, retries=1)
    lifecycle.fail("todo-1", "worker-a", "token-120.0", 130.0, "permanent")
    with pytest.raises(RetryExhaustedError):
        lifecycle.retry("todo-1", 131.0, "budget exhausted")
    assert lifecycle.get("todo-1").state == "failed"


def test_cancellation_stale_recovery_and_restart_recovery_are_auditable() -> None:
    lifecycle = make_lifecycle()
    claim(lifecycle, retries=1)
    lifecycle.cancel("todo-1", "worker-a", "token-100.0", 105.0, "operator request")
    with pytest.raises(InvalidTransitionError):
        lifecycle.retry("todo-1", 106.0, "cancelled work")

    recovered = make_lifecycle()
    claim(recovered, now=200.0, retries=1)
    assert recovered.recover_stale(231.0) == ["todo-1"]
    restarted = ExecutionLifecycle(recovered.connection)
    assert restarted.recover_stale(232.0) == []
    events = restarted.events("todo-1")
    assert any(event["state"] == "stale" and event["error"] for event in events)


def test_invalid_transition_has_structured_reason_and_error() -> None:
    lifecycle = make_lifecycle()
    claim(lifecycle)
    with pytest.raises(InvalidTransitionError):
        lifecycle.complete("todo-1", "worker-a", "token-100.0", 105.0, "not running")
    event = lifecycle.events("todo-1")[-1]
    assert event["reason"] == "invalid transition"
    assert event["error"]