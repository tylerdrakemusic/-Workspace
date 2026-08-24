"""Pure readiness and capacity planning for TODO execution snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from todo_execution_contracts import (
    ContractValidationError,
    ExecutionState,
    ResourceDeclaration,
    TERMINAL_STATES,
    TodoContract,
    validate_contracts,
)


@dataclass(frozen=True)
class SchedulerConfig:
    """Capacity limits for one deterministic scheduling projection."""

    global_capacity: int = 1
    per_fr_capacity: int = 1
    pre_fr_capacity: int = 1

    def __post_init__(self) -> None:
        if self.global_capacity < 0 or self.per_fr_capacity < 0 or self.pre_fr_capacity < 0:
            raise ContractValidationError("capacity must not be negative")


@dataclass(frozen=True)
class ScheduleItem:
    """A TODO classified by the scheduler with a stable explanation."""

    todo_id: str
    priority: int
    reason: str


@dataclass(frozen=True)
class ReadinessResult:
    """Structured, side-effect-free output of one scheduling projection."""

    blocked: tuple[ScheduleItem, ...] = ()
    queued: tuple[ScheduleItem, ...] = ()
    ready: tuple[ScheduleItem, ...] = ()
    join_ineligible: tuple[ScheduleItem, ...] = ()


def schedule_todos(
    contracts: Sequence[TodoContract],
    execution_states: Mapping[str, ExecutionState | str],
    priorities: Mapping[str, int] | None = None,
    config: SchedulerConfig | None = None,
    reservations: Mapping[str, Sequence[ResourceDeclaration]] | None = None,
) -> ReadinessResult:
    """Classify TODOs without claiming, persisting, or mutating execution state."""
    validate_contracts(contracts)
    config = config or SchedulerConfig()
    priorities = priorities or {}
    reservations = reservations or {}
    by_id = {contract.todo_id: contract for contract in contracts}
    try:
        states = {todo_id: ExecutionState(state) for todo_id, state in execution_states.items()}
    except (TypeError, ValueError) as exc:
        raise ContractValidationError("invalid execution state in snapshot") from exc
    unknown_states = set(states) - set(by_id)
    if unknown_states:
        raise ContractValidationError("execution snapshot has unknown TODO identity")
    unknown_priorities = set(priorities) - set(by_id)
    if unknown_priorities:
        raise ContractValidationError("priority has unknown TODO identity")
    unknown_reservations = set(reservations) - set(by_id)
    if unknown_reservations:
        raise ContractValidationError("reservation has unknown TODO identity")
    for todo_id, resources in reservations.items():
        if len(set(resources)) != len(tuple(resources)):
            raise ContractValidationError(f"duplicate resource reservation for {todo_id}")

    children: dict[str, list[str]] = {todo_id: [] for todo_id in by_id}
    for contract in contracts:
        if contract.parent_id is not None:
            children[contract.parent_id].append(contract.todo_id)

    active_resources = {
        resource
        for todo_id, resources in reservations.items()
        if states.get(todo_id) in {ExecutionState.CLAIMED, ExecutionState.RUNNING}
        for resource in resources
    }
    active_count = sum(
        state in {ExecutionState.CLAIMED, ExecutionState.RUNNING}
        for state in states.values()
    )
    active_by_fr: dict[str | None, int] = {}
    for todo_id, state in states.items():
        if state in {ExecutionState.CLAIMED, ExecutionState.RUNNING}:
            effective_fr = _effective_fr(by_id[todo_id], by_id)
            active_by_fr[effective_fr] = active_by_fr.get(effective_fr, 0) + 1

    def order(todo_id: str) -> tuple[int, str]:
        return (-priorities.get(todo_id, 0), todo_id)

    items: dict[str, list[ScheduleItem]] = {
        "blocked": [], "queued": [], "ready": [], "join_ineligible": []
    }
    planned_resources: set[ResourceDeclaration] = set(active_resources)
    planned_by_fr = dict(active_by_fr)
    planned_count = active_count

    for todo_id in sorted(by_id, key=order):
        state = states.get(todo_id)
        if state in TERMINAL_STATES:
            continue
        if state in {ExecutionState.CLAIMED, ExecutionState.RUNNING}:
            continue
        contract = by_id[todo_id]
        priority = priorities.get(todo_id, 0)
        if children[todo_id]:
            items["join_ineligible"].append(
                ScheduleItem(todo_id, priority, "structural parent is represented by child join state")
            )
            continue
        unmet = _unmet_prerequisites(contract, states)
        if unmet:
            items["blocked"].append(ScheduleItem(todo_id, priority, unmet))
            continue
        effective_fr = _effective_fr(contract, by_id)
        resources = set(contract.resources)
        if (
            planned_count >= config.global_capacity
            or planned_by_fr.get(effective_fr, 0) >= (
                config.pre_fr_capacity if effective_fr is None else config.per_fr_capacity
            )
            or resources & planned_resources
        ):
            reason = _capacity_reason(
                planned_count, effective_fr, planned_by_fr, config, resources, planned_resources
            )
            items["queued"].append(ScheduleItem(todo_id, priority, reason))
            continue
        items["ready"].append(ScheduleItem(todo_id, priority, "all prerequisites satisfied"))
        planned_count += 1
        planned_by_fr[effective_fr] = planned_by_fr.get(effective_fr, 0) + 1
        planned_resources.update(resources)

    return ReadinessResult(*(tuple(sorted(items[name], key=lambda item: order(item.todo_id)))
                             for name in ("blocked", "queued", "ready", "join_ineligible")))


def _unmet_prerequisites(contract: TodoContract, states: Mapping[str, ExecutionState]) -> str:
    unmet = [
        edge.prerequisite_id
        for edge in contract.prerequisites
        if states.get(edge.prerequisite_id) not in edge.allowed_terminal_states
    ]
    return "prerequisites not terminal: " + ", ".join(sorted(unmet)) if unmet else ""


def _effective_fr(contract: TodoContract, by_id: Mapping[str, TodoContract]) -> str | None:
    if contract.fr_id is not None:
        return contract.fr_id
    if contract.inherited_fr_id is not None:
        return contract.inherited_fr_id
    if contract.parent_id is None:
        return None
    return _effective_fr(by_id[contract.parent_id], by_id)


def _capacity_reason(
    planned_count: int,
    effective_fr: str | None,
    planned_by_fr: Mapping[str | None, int],
    config: SchedulerConfig,
    resources: set[ResourceDeclaration],
    planned_resources: set[ResourceDeclaration],
) -> str:
    reasons: list[str] = []
    if planned_count >= config.global_capacity:
        reasons.append("global worker capacity exhausted")
    fr_limit = config.pre_fr_capacity if effective_fr is None else config.per_fr_capacity
    if planned_by_fr.get(effective_fr, 0) >= fr_limit:
        bucket = "pre-FR" if effective_fr is None else f"FR {effective_fr}"
        reasons.append(f"{bucket} capacity exhausted")
    conflicts = sorted(
        resource.name for resource in resources & planned_resources
    )
    if conflicts:
        reasons.append("resource reservation conflict: " + ", ".join(conflicts))
    return "; ".join(reasons)