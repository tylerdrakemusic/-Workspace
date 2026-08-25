"""Bounded operational composition for dependency-aware TODO execution."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Mapping

from todo_execution_contracts import ExecutionState, TodoContract
from todo_execution_lifecycle import ExecutionLifecycle, ExecutionRecord
from parent_join_gates import ChildJoinSnapshot, ParentJoinResult, evaluate_parent_join
from todo_child_coordination import ChildWorktreeCoordinator, IntegrationConflict
from todo_readiness_scheduler import SchedulerConfig, schedule_todos


class TelemetryFieldError(ValueError):
    """Raised when telemetry contains a field outside the operational allowlist."""


@dataclass(frozen=True)
class TelemetryEvent:
    kind: str
    todo_id: str | None
    details: Mapping[str, int | str | bool]


@dataclass
class OperationalTelemetry:
    """In-memory allowlisted telemetry sink for one runtime instance."""

    events: list[TelemetryEvent] = field(default_factory=list)
    allowed_fields: frozenset[str] = frozenset({"depth", "ready", "queued", "attempt", "reason"})
    allowed_kinds: frozenset[str] = frozenset(
        {"queue_depth", "readiness", "claim", "lease", "retry", "stale_recovery", "integration", "conflict", "gate"}
    )

    def emit(self, kind: str, todo_id: str | None = None, **details: int | str | bool) -> None:
        if kind not in self.allowed_kinds:
            raise TelemetryFieldError(f"telemetry kind is not allowlisted: {kind}")
        forbidden = set(details) - self.allowed_fields
        if forbidden:
            raise TelemetryFieldError(f"telemetry fields are not allowlisted: {', '.join(sorted(forbidden))}")
        self.events.append(TelemetryEvent(kind, todo_id, dict(details)))


@dataclass(frozen=True)
class OperationalConfig:
    """Initial evidence-based worker limits for one FR and the workspace."""

    max_parallel_per_fr: int = 8
    global_worker_capacity: int = 16
    lease_seconds: int = 300
    max_retries: int = 2
    pre_fr_capacity: int = 16

    def __post_init__(self) -> None:
        if self.max_parallel_per_fr <= 0 or self.global_worker_capacity <= 0:
            raise ValueError("worker capacities must be positive")
        if self.lease_seconds <= 0 or self.max_retries < 0:
            raise ValueError("lease and retry defaults are invalid")


class OperationalRuntime:
    """Compose scheduling and durable lifecycle without mutating FR gates."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        contracts: tuple[TodoContract, ...],
        *,
        config: OperationalConfig | None = None,
        priorities: Mapping[str, int] | None = None,
    ) -> None:
        self.connection = connection
        self.contracts = contracts
        self.config = config or OperationalConfig()
        self.priorities = priorities or {}
        self.lifecycle = ExecutionLifecycle(connection)
        self.telemetry = OperationalTelemetry()

    def dispatch(self, *, now: float, worker_prefix: str = "worker") -> list[ExecutionRecord]:
        """Project readiness, claim selected work, and return durable leases."""
        states = self._states()
        result = schedule_todos(
            self.contracts,
            states,
            priorities=self.priorities,
            config=SchedulerConfig(
                global_capacity=self.config.global_worker_capacity,
                per_fr_capacity=self.config.max_parallel_per_fr,
                pre_fr_capacity=self.config.pre_fr_capacity,
            ),
        )
        self.telemetry.emit("queue_depth", depth=len(result.ready) + len(result.queued))
        self.telemetry.emit("readiness", ready=len(result.ready), queued=len(result.queued))
        claimed: list[ExecutionRecord] = []
        for index, item in enumerate(result.ready, start=1):
            contract = next(contract for contract in self.contracts if contract.todo_id == item.todo_id)
            record = self.lifecycle.claim(
                todo_id=contract.todo_id,
                fr_id=contract.fr_id or contract.inherited_fr_id,
                worker_id=f"{worker_prefix}-{index}",
                claim_id=f"{worker_prefix}-{index}-{contract.todo_id}",
                lease_token=f"lease-{worker_prefix}-{index}-{contract.todo_id}",
                now=now,
                lease_seconds=self.config.lease_seconds,
                max_retries=self.config.max_retries,
                idempotency_key=f"dispatch-{now}-{contract.todo_id}",
            )
            self.telemetry.emit("claim", record.todo_id, attempt=record.attempt)
            claimed.append(record)
        for item in result.queued:
            self.telemetry.emit("conflict", item.todo_id, reason=item.reason)
        return claimed

    def recover_stale(self, *, now: float) -> list[str]:
        """Recover expired leases and emit only aggregate recovery evidence."""
        recovered = self.lifecycle.recover_stale(now)
        self.telemetry.emit("stale_recovery", depth=len(recovered))
        return recovered

    def heartbeat(self, record: ExecutionRecord, *, now: float) -> ExecutionRecord:
        """Renew a lease through the durable lifecycle and record its outcome."""
        updated = self.lifecycle.heartbeat(
            record.todo_id, record.worker_id, record.lease_token, now, self.config.lease_seconds
        )
        self.telemetry.emit("lease", updated.todo_id, attempt=updated.attempt)
        return updated

    def fail(self, record: ExecutionRecord, *, now: float, error: str) -> ExecutionRecord:
        """Record a failure without copying its error or lease secret to telemetry."""
        updated = self.lifecycle.fail(record.todo_id, record.worker_id, record.lease_token, now, error)
        self.telemetry.emit("retry", updated.todo_id, attempt=updated.attempt)
        return updated

    def retry(self, *, todo_id: str, now: float) -> ExecutionRecord:
        """Return failed or stale work to the bounded retry queue."""
        updated = self.lifecycle.retry(todo_id, now, "operational retry")
        self.telemetry.emit("retry", todo_id, attempt=updated.attempt)
        return updated

    def integrate_child(
        self, coordinator: ChildWorktreeCoordinator, todo_id: str, *, target_head: str
    ) -> None:
        """Integrate only coordinator-admitted validated child work."""
        try:
            coordinator.integrate(todo_id, target_head=target_head)
        except IntegrationConflict:
            self.telemetry.emit("conflict", todo_id, reason="child integration conflict")
            raise
        self.telemetry.emit("integration", todo_id, reason="validated child integrated")

    def evaluate_parent_join(
        self,
        *,
        parent_branch: str,
        parent_head: str,
        required_todos: tuple[str, ...],
        children: tuple[ChildJoinSnapshot, ...],
    ) -> ParentJoinResult:
        """Evaluate the existing FR join gate and expose only its readiness result."""
        result = evaluate_parent_join(
            fr_id=self._fr_id(),
            parent_branch=parent_branch,
            parent_head=parent_head,
            required_todos=required_todos,
            children=children,
        )
        self.telemetry.emit("gate", ready=result.complete, queued=len(result.blockers))
        return result

    def _fr_id(self) -> str:
        fr_ids = {contract.fr_id or contract.inherited_fr_id for contract in self.contracts}
        if len(fr_ids) != 1 or None in fr_ids:
            raise ValueError("runtime parent join requires one FR identity")
        return next(iter(fr_ids))  # type: ignore[return-value]

    def _states(self) -> dict[str, ExecutionState]:
        states: dict[str, ExecutionState] = {}
        for contract in self.contracts:
            try:
                states[contract.todo_id] = ExecutionState(self.lifecycle.get(contract.todo_id).state)
            except KeyError:
                states[contract.todo_id] = ExecutionState.QUEUED
        return states