from __future__ import annotations

import pytest

from todo_execution_contracts import (
    ContractValidationError,
    ExecutionState,
    PrerequisiteEdge,
    ResourceDeclaration,
    TodoContract,
)
from todo_readiness_scheduler import SchedulerConfig, schedule_todos


def test_independent_ready_todos_are_priority_ordered_and_parent_is_not_a_dependency() -> None:
    contracts = (
        TodoContract(todo_id="parent"),
        TodoContract(todo_id="high", parent_id="parent"),
        TodoContract(
            todo_id="low",
            prerequisites=(PrerequisiteEdge("low", "setup"),),
        ),
        TodoContract(todo_id="setup"),
    )

    result = schedule_todos(
        contracts,
        execution_states={},
        priorities={"parent": 1, "high": 10, "low": 5, "setup": 2},
        config=SchedulerConfig(global_capacity=10, per_fr_capacity=10, pre_fr_capacity=10),
    )

    assert [item.todo_id for item in result.ready] == ["high", "setup"]
    assert [item.todo_id for item in result.blocked] == ["low"]
    assert [item.todo_id for item in result.queued] == []
    assert [item.todo_id for item in result.join_ineligible] == ["parent"]


def test_edge_specific_terminal_policy_controls_readiness_and_descendants_remain_blocked() -> None:
    contracts = (
        TodoContract(todo_id="failed", fr_id="FR-1"),
        TodoContract(
            todo_id="allowed",
            prerequisites=(
                PrerequisiteEdge(
                    "allowed", "failed", (ExecutionState.FAILED, ExecutionState.CANCELLED)
                ),
            ),
            fr_id="FR-1",
        ),
        TodoContract(
            todo_id="descendant",
            prerequisites=(PrerequisiteEdge("descendant", "allowed"),),
            fr_id="FR-1",
        ),
    )

    result = schedule_todos(
        contracts,
        {"failed": ExecutionState.FAILED},
        priorities={"allowed": 2, "descendant": 1, "failed": 0},
        config=SchedulerConfig(global_capacity=3, per_fr_capacity=3),
    )

    assert [item.todo_id for item in result.ready] == ["allowed"]
    assert [item.todo_id for item in result.blocked] == ["descendant"]
    assert "allowed" in result.blocked[0].reason


def test_global_and_per_fr_capacity_queue_by_priority_and_keep_pre_fr_bucket_explicit() -> None:
    contracts = tuple(TodoContract(todo_id=todo_id, fr_id=fr_id) for todo_id, fr_id in (
        ("fr-high", "FR-1"), ("fr-low", "FR-1"), ("other", "FR-2"), ("pre", None),
    ))

    result = schedule_todos(
        contracts,
        {},
        priorities={"fr-high": 4, "fr-low": 3, "other": 2, "pre": 1},
        config=SchedulerConfig(global_capacity=2, per_fr_capacity=1, pre_fr_capacity=1),
    )

    assert [item.todo_id for item in result.ready] == ["fr-high", "other"]
    assert [item.todo_id for item in result.queued] == ["fr-low", "pre"]
    assert "FR FR-1 capacity exhausted" in result.queued[0].reason


def test_file_and_named_shared_resources_conflict_with_active_and_planned_work() -> None:
    contracts = (
        TodoContract(todo_id="active", resources=(ResourceDeclaration("file", "a.py"),)),
        TodoContract(todo_id="same-file", resources=(ResourceDeclaration("file", "a.py"),)),
        TodoContract(todo_id="same-shared", resources=(ResourceDeclaration("shared", "db"),)),
        TodoContract(todo_id="other-shared", resources=(ResourceDeclaration("shared", "db"),)),
    )

    result = schedule_todos(
        contracts,
        {"active": ExecutionState.RUNNING, "same-shared": ExecutionState.RUNNING},
        priorities={"same-file": 4, "same-shared": 3, "other-shared": 2},
        config=SchedulerConfig(global_capacity=4, per_fr_capacity=4, pre_fr_capacity=4),
        reservations={"active": contracts[0].resources, "same-shared": contracts[2].resources},
    )

    assert [item.todo_id for item in result.ready] == []
    assert [item.todo_id for item in result.queued] == ["same-file", "other-shared"]
    assert "a.py" in result.queued[0].reason
    assert "db" in result.queued[1].reason


def test_invalid_graph_snapshot_and_capacity_inputs_are_rejected() -> None:
    with pytest.raises(ContractValidationError, match="duplicate"):
        schedule_todos((TodoContract(todo_id="one"), TodoContract(todo_id="one")), {})

    with pytest.raises(ContractValidationError, match="unknown TODO"):
        schedule_todos((TodoContract(todo_id="one"),), {"missing": ExecutionState.QUEUED})

    with pytest.raises(ContractValidationError, match="capacity"):
        SchedulerConfig(global_capacity=-1)


def test_pre_fr_lineage_uses_null_bucket_and_inherited_fr_is_preserved() -> None:
    contracts = (
        TodoContract(todo_id="anchor", fr_id=None),
        TodoContract(todo_id="child", parent_id="anchor", inherited_fr_id="FR-7"),
    )

    result = schedule_todos(
        contracts,
        {},
        priorities={"child": 2, "anchor": 1},
        config=SchedulerConfig(global_capacity=2, per_fr_capacity=2, pre_fr_capacity=1),
    )

    assert [item.todo_id for item in result.ready] == ["child"]
    assert [item.todo_id for item in result.queued] == []
    assert [item.todo_id for item in result.join_ineligible] == ["anchor"]


def test_effective_fr_flows_through_inherited_parent_lineage_for_capacity() -> None:
    contracts = (
        TodoContract(todo_id="root"),
        TodoContract(todo_id="parent", parent_id="root", inherited_fr_id="FR-7"),
        TodoContract(todo_id="leaf", parent_id="parent"),
        TodoContract(todo_id="sibling", fr_id="FR-7"),
    )

    result = schedule_todos(
        contracts,
        {},
        priorities={"leaf": 4, "sibling": 3},
        config=SchedulerConfig(global_capacity=3, per_fr_capacity=1, pre_fr_capacity=3),
    )

    assert [item.todo_id for item in result.ready] == ["leaf"]
    assert [item.todo_id for item in result.queued] == ["sibling"]
    assert "FR FR-7 capacity exhausted" in result.queued[0].reason


def test_single_worker_selection_is_deterministic_for_equal_priorities_and_terminal_items_are_omitted() -> None:
    contracts = tuple(TodoContract(todo_id=todo_id, fr_id=f"FR-{todo_id}") for todo_id in ("2", "1", "done"))

    result = schedule_todos(
        contracts,
        {"done": ExecutionState.COMPLETED},
        priorities={"1": 5, "2": 5},
        config=SchedulerConfig(global_capacity=1, per_fr_capacity=1),
    )

    assert [item.todo_id for item in result.ready] == ["1"]
    assert [item.todo_id for item in result.queued] == ["2"]
    assert all(item.todo_id != "done" for item in result.ready + result.queued)


def test_invalid_snapshot_state_and_mixed_todo_id_order_are_deterministic() -> None:
    contracts = tuple(TodoContract(todo_id=todo_id) for todo_id in ("10", "2", "a"))

    with pytest.raises(ContractValidationError, match="execution state"):
        schedule_todos(contracts, {"10": "not-a-state"})

    result = schedule_todos(
        contracts,
        {},
        priorities={"10": 1, "2": 1, "a": 1},
        config=SchedulerConfig(global_capacity=3, per_fr_capacity=3, pre_fr_capacity=3),
    )

    assert [item.todo_id for item in result.ready] == ["10", "2", "a"]