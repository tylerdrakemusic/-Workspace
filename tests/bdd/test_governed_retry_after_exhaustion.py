from __future__ import annotations

import json
import sqlite3
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from src.utils.coordination_mcp_server import invoke_coordination
from src.utils.todo_execution_lifecycle import ExecutionLifecycle, InvalidTransitionError
from src.utils.todo_operational_runtime import OperationalConfig

scenarios("governed_retry_after_exhaustion.feature")


def _new_context(request: pytest.FixtureRequest) -> dict[str, Any]:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    request.addfinalizer(connection.close)
    return {
        "connection": connection,
        "lifecycle": ExecutionLifecycle(connection),
        "config": OperationalConfig(max_retries=0, lease_seconds=30),
    }


def _fail_first_attempt(context: dict[str, Any], todo_id: str) -> None:
    lifecycle = context["lifecycle"]
    lifecycle.register_queued(
        todo_id=todo_id,
        fr_id="FR-retry-recovery",
        now=90.0,
        max_retries=0,
        idempotency_key=f"dispatch-{todo_id}",
    )
    claimed = lifecycle.claim(
        todo_id=todo_id,
        fr_id="FR-retry-recovery",
        worker_id=f"worker-{todo_id}",
        claim_id=f"claim-{todo_id}-1",
        lease_token=f"fixture-lease-{todo_id}-1",
        now=100.0,
        lease_seconds=30,
        max_retries=0,
        idempotency_key=f"delivery-{todo_id}-1",
    )
    lifecycle.fail(
        todo_id,
        claimed.worker_id,
        claimed.lease_token,
        110.0,
        "attempt failed",
    )


def _grant(
    context: dict[str, Any],
    todo_id: str,
    *,
    actor: str = "operator-1",
    approved: Any = True,
    reason: str = "Recover the blocked deliverable",
) -> dict[str, Any]:
    return json.loads(
        invoke_coordination(
            "todo.grant_retry_attempt",
            {
                "todo_id": todo_id,
                "actor": actor,
                "approved": approved,
                "reason": reason,
            },
            connection=context["connection"],
            config=context["config"],
        )
    )


def _history(context: dict[str, Any], todo_id: str) -> tuple[tuple[Any, ...], ...]:
    connection = context["connection"]
    events = tuple(
        tuple(row)
        for row in connection.execute(
            """SELECT event_id, claim_id, state, reason, error, occurred_at
               FROM todo_execution_events WHERE todo_id = ? ORDER BY event_id""",
            (todo_id,),
        )
    )
    tables = {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    grants = ()
    if "todo_execution_retry_grants" in tables:
        grants = tuple(
            tuple(row)
            for row in connection.execute(
                """SELECT grant_id, actor, reason, attempt_from, attempt_to, granted_at
                   FROM todo_execution_retry_grants WHERE todo_id = ? ORDER BY grant_id""",
                (todo_id,),
            )
        )
    return events + grants


@given("a failed TODO exhausted its retry budget", target_fixture="retry_context")
def exhausted_failed_todo(request: pytest.FixtureRequest) -> dict[str, Any]:
    context = _new_context(request)
    _fail_first_attempt(context, "todo-exhausted")
    context["todo_id"] = "todo-exhausted"
    return context


@given(
    "a failed TODO exhausted its retry budget and has no prior manual grant",
    target_fixture="retry_context",
)
def exhausted_todo_without_grant(request: pytest.FixtureRequest) -> dict[str, Any]:
    return exhausted_failed_todo(request)


@given(
    "the one-time manual grant has been used and the added attempt later fails",
    target_fixture="retry_context",
)
def failed_after_manual_grant(request: pytest.FixtureRequest) -> dict[str, Any]:
    context = exhausted_failed_todo(request)
    todo_id = context["todo_id"]
    assert _grant(context, todo_id)["state"] == "queued"
    claimed = context["lifecycle"].claim(
        todo_id=todo_id,
        fr_id="FR-retry-recovery",
        worker_id="worker-added-attempt",
        claim_id="claim-added-attempt",
        lease_token="fixture-lease-added-attempt",
        now=120.0,
        lease_seconds=30,
        max_retries=0,
        idempotency_key="delivery-added-attempt",
    )
    assert claimed.attempt == 2
    context["lifecycle"].fail(
        todo_id,
        claimed.worker_id,
        claimed.lease_token,
        130.0,
        "added attempt failed",
    )
    return context


@given("a TODO is claimed or running", target_fixture="retry_context")
def active_todos(request: pytest.FixtureRequest) -> dict[str, Any]:
    context = _new_context(request)
    lifecycle = context["lifecycle"]
    active_ids = ("todo-claimed", "todo-running")
    for todo_id in active_ids:
        lifecycle.register_queued(
            todo_id=todo_id,
            fr_id="FR-retry-recovery",
            now=90.0,
            max_retries=0,
            idempotency_key=f"dispatch-{todo_id}",
        )
        claimed = lifecycle.claim(
            todo_id=todo_id,
            fr_id="FR-retry-recovery",
            worker_id=f"worker-{todo_id}",
            claim_id=f"claim-{todo_id}",
            lease_token=f"fixture-lease-{todo_id}",
            now=100.0,
            lease_seconds=30,
            max_retries=0,
            idempotency_key=f"delivery-{todo_id}",
        )
        if todo_id == "todo-running":
            lifecycle.heartbeat(
                todo_id,
                claimed.worker_id,
                claimed.lease_token,
                105.0,
                30,
            )
    context["active_ids"] = active_ids
    context["records_before"] = {todo_id: lifecycle.get(todo_id) for todo_id in active_ids}
    context["history_before"] = {todo_id: _history(context, todo_id) for todo_id in active_ids}
    return context


@when(
    "the operation is called without explicit approval or a reason",
    target_fixture="rejection_context",
)
def call_without_approval_or_reason(
    retry_context: dict[str, Any],
) -> dict[str, Any]:
    todo_id = retry_context["todo_id"]
    retry_context["records_before"] = retry_context["lifecycle"].get(todo_id)
    retry_context["history_before"] = _history(retry_context, todo_id)
    errors = []
    for approved, reason in (
        (False, "Recover the blocked deliverable"),
        (True, "   "),
    ):
        try:
            _grant(retry_context, todo_id, approved=approved, reason=reason)
        except (PermissionError, ValueError) as error:
            errors.append(error)
        else:
            errors.append(None)
    retry_context["errors"] = errors
    return retry_context


@when(
    "an authorized operator approves one extra attempt with a reason",
    target_fixture="grant_context",
)
def call_approved_retry_grant(retry_context: dict[str, Any]) -> dict[str, Any]:
    retry_context["result"] = _grant(retry_context, retry_context["todo_id"])
    return retry_context


@when("another recovery is requested", target_fixture="recovery_context")
def request_repeated_recovery(retry_context: dict[str, Any]) -> dict[str, Any]:
    todo_id = retry_context["todo_id"]
    retry_context["record_before"] = retry_context["lifecycle"].get(todo_id)
    retry_context["history_before"] = _history(retry_context, todo_id)
    try:
        _grant(retry_context, todo_id)
    except InvalidTransitionError as error:
        retry_context["error"] = error
    else:
        retry_context["error"] = None
    return retry_context


@when("recovery is requested", target_fixture="recovery_context")
def request_active_recovery(retry_context: dict[str, Any]) -> dict[str, Any]:
    outcomes = {}
    for todo_id in retry_context["active_ids"]:
        try:
            _grant(retry_context, todo_id)
        except InvalidTransitionError as error:
            outcomes[todo_id] = error
        else:
            outcomes[todo_id] = None
    retry_context["errors"] = outcomes
    return retry_context


@then("it rejects and leaves state and history unchanged")
def rejection_has_no_state_or_history_changes(
    rejection_context: dict[str, Any],
) -> None:
    errors = rejection_context["errors"]
    assert isinstance(errors[0], PermissionError)
    assert isinstance(errors[1], ValueError)
    todo_id = rejection_context["todo_id"]
    assert rejection_context["lifecycle"].get(todo_id) == rejection_context["records_before"]
    assert _history(rejection_context, todo_id) == rejection_context["history_before"]


@then(
    "it transitions to queued and appends an audit event with actor, reason, and attempt transition while preserving the original configured retry policy"
)
def approved_grant_is_queued_and_audited(grant_context: dict[str, Any]) -> None:
    todo_id = grant_context["todo_id"]
    record = grant_context["lifecycle"].get(todo_id)
    assert record.state == "queued"
    assert record.attempt == 1
    assert record.max_retries == 0
    audit = (
        grant_context["connection"]
        .execute(
            "SELECT actor, reason, attempt_from, attempt_to "
            "FROM todo_execution_retry_grants WHERE todo_id = ?",
            (todo_id,),
        )
        .fetchone()
    )
    assert tuple(audit) == (
        "operator-1",
        "Recover the blocked deliverable",
        1,
        2,
    )
    assert grant_context["lifecycle"].events(todo_id)[-1]["state"] == "queued"


@then("it rejects without changing state or history")
def repeated_grant_has_no_state_or_history_changes(
    recovery_context: dict[str, Any],
) -> None:
    todo_id = recovery_context["todo_id"]
    assert isinstance(recovery_context["error"], InvalidTransitionError)
    assert recovery_context["lifecycle"].get(todo_id) == recovery_context["record_before"]
    assert _history(recovery_context, todo_id) == recovery_context["history_before"]


@then("it rejects without changing state or revoking its lease")
def active_lease_is_unchanged(recovery_context: dict[str, Any]) -> None:
    assert all(error is not None for error in recovery_context["errors"].values())
    for todo_id in recovery_context["active_ids"]:
        current = recovery_context["lifecycle"].get(todo_id)
        before = recovery_context["records_before"][todo_id]
        assert current == before
        assert current.lease_token == before.lease_token
        assert _history(recovery_context, todo_id) == recovery_context["history_before"][todo_id]
