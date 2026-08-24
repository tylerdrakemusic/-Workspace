from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from todo_execution_contracts import (
    ExecutionLease,
    ContractValidationError,
    ExecutionState,
    ResourceDeclaration,
    PrerequisiteEdge,
    TodoContract,
    associate_fr,
    cancellation_state,
    claim_execution,
    expire_execution,
    heartbeat_execution,
    parent_join_state,
    retry_allowed,
    validate_contracts,
)


def test_contract_keeps_parent_and_prerequisite_identity_distinct() -> None:
    contract = TodoContract(
        todo_id="child-1",
        parent_id="parent-1",
        fr_id=None,
        prerequisites=(PrerequisiteEdge("child-1", "setup-1"),),
    )

    assert contract.parent_id == "parent-1"
    assert contract.prerequisites[0].prerequisite_id == "setup-1"


def test_contract_rejects_prerequisite_cycles() -> None:
    with pytest.raises(ContractValidationError, match="cycle"):
        validate_contracts((
            TodoContract(todo_id="todo-1", prerequisites=(PrerequisiteEdge("todo-1", "todo-2"),)),
            TodoContract(todo_id="todo-2", prerequisites=(PrerequisiteEdge("todo-2", "todo-1"),)),
        ))


def test_execution_states_include_terminal_and_stale_states() -> None:
    assert {ExecutionState.COMPLETED, ExecutionState.FAILED,
            ExecutionState.CANCELLED, ExecutionState.STALE} <= set(ExecutionState)


def test_registry_rejects_duplicate_ids_invalid_parentage_and_duplicate_edges() -> None:
    contracts = (
        TodoContract(todo_id="parent"),
        TodoContract(
            todo_id="child",
            parent_id="missing",
            prerequisites=(PrerequisiteEdge("child", "setup"),
                           PrerequisiteEdge("child", "setup")),
        ),
        TodoContract(todo_id="parent"),
    )

    with pytest.raises(ContractValidationError, match="duplicate"):
        validate_contracts(contracts)


def test_registry_rejects_parent_and_prerequisite_cycles() -> None:
    with pytest.raises(ContractValidationError, match="parent cycle"):
        validate_contracts((
            TodoContract(todo_id="a", parent_id="b"),
            TodoContract(todo_id="b", parent_id="a"),
        ))


def test_registry_rejects_unsupported_resources_and_invalid_terminal_policy() -> None:
    with pytest.raises(ContractValidationError, match="resource"):
        TodoContract(todo_id="todo", resources=(ResourceDeclaration("socket", "x"),))

    with pytest.raises(ContractValidationError, match="terminal"):
        PrerequisiteEdge("todo", "setup", allowed_terminal_states=(ExecutionState.RUNNING,))


def test_refined_anchor_can_associate_only_with_its_inherited_fr() -> None:
    anchor = TodoContract(todo_id="anchor", fr_id=None, inherited_fr_id="FR-1")
    assert associate_fr(anchor, "FR-1").fr_id == "FR-1"

    with pytest.raises(ContractValidationError, match="FR"):
        associate_fr(anchor, "FR-2")


def test_registry_rejects_descendant_inherited_fr_mismatch_with_parent() -> None:
    with pytest.raises(ContractValidationError, match="inherited FR"):
        validate_contracts((
            TodoContract(todo_id="parent", fr_id="FR-1"),
            TodoContract(todo_id="child", parent_id="parent", inherited_fr_id="FR-2"),
        ))


def test_registry_checks_inherited_fr_against_the_effective_parent_chain() -> None:
    with pytest.raises(ContractValidationError, match="inherited FR"):
        validate_contracts((
            TodoContract(todo_id="root", fr_id="FR-1"),
            TodoContract(todo_id="parent", parent_id="root"),
            TodoContract(todo_id="child", parent_id="parent", inherited_fr_id="FR-2"),
        ))


def test_registry_preserves_pre_fr_null_anchors_until_association() -> None:
    validate_contracts((
        TodoContract(todo_id="anchor", fr_id=None),
        TodoContract(todo_id="child", parent_id="anchor", inherited_fr_id="FR-1"),
    ))


def test_execution_lease_exposes_claim_heartbeat_expiration_retry_and_cancellation_contract() -> None:
    now = datetime.now(timezone.utc)
    lease = ExecutionLease(
        todo_id="todo",
        state=ExecutionState.CLAIMED,
        worker_id="worker",
        claim_id="claim",
        lease_expires_at=now + timedelta(minutes=5),
        heartbeat_at=now,
        attempt=1,
        max_retries=2,
        cancellation_requested=False,
    )

    assert lease.worker_id == "worker"
    assert lease.attempt == 1
    assert lease.max_retries == 2


def test_parent_join_waits_for_children_and_propagates_terminal_failure() -> None:
    assert parent_join_state((ExecutionState.COMPLETED, ExecutionState.RUNNING)) == ExecutionState.RUNNING
    assert parent_join_state((ExecutionState.COMPLETED, ExecutionState.COMPLETED)) == ExecutionState.COMPLETED
    assert parent_join_state((ExecutionState.COMPLETED, ExecutionState.FAILED)) == ExecutionState.FAILED


def test_contract_preserves_one_branch_one_worktree_traceability() -> None:
    contract = TodoContract(todo_id="todo", branch="feature/todo", worktree=".worktrees/todo")
    assert (contract.branch, contract.worktree) == ("feature/todo", ".worktrees/todo")

    with pytest.raises(ContractValidationError, match="traceability"):
        TodoContract(todo_id="todo", branch="feature/todo")


def test_lease_helpers_cover_heartbeat_expiration_retry_and_cancellation() -> None:
    now = datetime.now(timezone.utc)
    lease = claim_execution("todo", "worker", "claim", 60, now)
    running = heartbeat_execution(lease, now + timedelta(seconds=10), 60)

    assert running.state is ExecutionState.RUNNING
    assert expire_execution(running, now + timedelta(seconds=20)) is ExecutionState.RUNNING
    assert expire_execution(running, now + timedelta(seconds=70)) is ExecutionState.STALE
    assert cancellation_state(running.state) is ExecutionState.CANCELLED
    assert retry_allowed(running) is False