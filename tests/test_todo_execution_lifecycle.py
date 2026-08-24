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


def test_failed_attempt_cannot_be_reclaimed_when_retry_budget_is_exhausted() -> None:
    lifecycle = make_lifecycle()
    claim(lifecycle, retries=0)
    lifecycle.fail("todo-1", "worker-a", "token-100.0", 110.0, "permanent")

    with pytest.raises(InvalidTransitionError):
        lifecycle.claim(
            todo_id="todo-1", fr_id="FR-1", worker_id="worker-b",
            claim_id="claim-2", lease_token="token-2", now=111.0,
            lease_seconds=30, max_retries=0, idempotency_key="delivery-2",
        )

    assert lifecycle.get("todo-1").state == "failed"


def test_stale_attempt_requires_explicit_retry_before_claim() -> None:
    lifecycle = make_lifecycle()
    claim(lifecycle, retries=1)
    assert lifecycle.recover_stale(130.0) == ["todo-1"]

    with pytest.raises(InvalidTransitionError):
        lifecycle.claim(
            todo_id="todo-1", fr_id="FR-1", worker_id="worker-b",
            claim_id="claim-2", lease_token="token-2", now=131.0,
            lease_seconds=30, max_retries=1, idempotency_key="delivery-2",
        )

    assert lifecycle.get("todo-1").state == "stale"
    assert lifecycle.retry("todo-1", 132.0, "recover stale attempt").state == "queued"
    assert lifecycle.claim(
        todo_id="todo-1", fr_id="FR-1", worker_id="worker-b",
        claim_id="claim-2", lease_token="token-2", now=133.0,
        lease_seconds=30, max_retries=1, idempotency_key="delivery-2",
    ).state == "claimed"


def test_expired_cancellation_rejects_and_allows_stale_recovery() -> None:
    lifecycle = make_lifecycle()
    claim(lifecycle, retries=1)

    with pytest.raises(InvalidTransitionError, match="expired"):
        lifecycle.cancel("todo-1", "worker-a", "token-100.0", 130.0, "operator request")

    assert lifecycle.get("todo-1").state == "claimed"
    assert lifecycle.recover_stale(131.0) == ["todo-1"]
    assert lifecycle.get("todo-1").state == "stale"
    assert any(
        event["state"] == "stale" and event["error"] == "lease expired"
        for event in lifecycle.events("todo-1")
    )
    recovery = lifecycle.connection.execute(
        "SELECT reason, error FROM todo_execution_stale_recoveries WHERE todo_id = ?",
        ("todo-1",),
    ).fetchone()
    assert recovery["reason"] == "lease expired; worker recovered"
    assert recovery["error"] == "lease expired"


def test_cancellation_preserves_ownership_and_terminal_idempotency() -> None:
    lifecycle = make_lifecycle()
    claim(lifecycle)

    with pytest.raises(LeaseOwnershipError):
        lifecycle.cancel("todo-1", "worker-b", "token-100.0", 105.0, "operator request")
    with pytest.raises(LeaseOwnershipError):
        lifecycle.cancel("todo-1", "worker-a", "wrong-token", 105.0, "operator request")

    cancelled = lifecycle.cancel(
        "todo-1", "worker-a", "token-100.0", 105.0, "operator request"
    )
    assert cancelled.state == "cancelled"
    with pytest.raises(InvalidTransitionError, match="active lease"):
        lifecycle.cancel("todo-1", "worker-a", "token-100.0", 106.0, "repeat request")
    assert lifecycle.get("todo-1").state == "cancelled"


@pytest.mark.parametrize("terminal_state", ["completed", "cancelled"])
def test_terminal_execution_cannot_be_claimed_again(terminal_state: str) -> None:
    lifecycle = make_lifecycle()
    claim(lifecycle)
    if terminal_state == "completed":
        lifecycle.heartbeat("todo-1", "worker-a", "token-100.0", 105.0, 30)
        lifecycle.complete("todo-1", "worker-a", "token-100.0", 110.0, "done")
    else:
        lifecycle.cancel("todo-1", "worker-a", "token-100.0", 105.0, "operator request")

    with pytest.raises(InvalidTransitionError):
        lifecycle.claim(
            todo_id="todo-1", fr_id="FR-1", worker_id="worker-b",
            claim_id="claim-2", lease_token="token-2", now=111.0,
            lease_seconds=30, max_retries=1, idempotency_key="delivery-2",
        )

    assert lifecycle.get("todo-1").state == terminal_state


def test_new_and_queued_claims_remain_valid_after_admission_fix() -> None:
    lifecycle = make_lifecycle()
    first = claim(lifecycle, retries=1)
    lifecycle.fail("todo-1", "worker-a", "token-100.0", 110.0, "transient")
    assert lifecycle.retry("todo-1", 111.0, "retry transient attempt").state == "queued"

    second = lifecycle.claim(
        todo_id="todo-1", fr_id="FR-1", worker_id="worker-a",
        claim_id="claim-120.0", lease_token="token-120.0", now=120.0,
        lease_seconds=30, max_retries=1, idempotency_key="delivery-120.0",
    )
    assert second.state == "claimed"
    assert second.attempt == first.attempt + 1
    assert lifecycle.claim(
        todo_id="todo-1", fr_id="FR-1", worker_id="worker-a",
        claim_id="claim-120.0", lease_token="token-120.0", now=121.0,
        lease_seconds=30, max_retries=1, idempotency_key="delivery-120.0",
    ) == second


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