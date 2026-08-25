"""Bounded operational composition for dependency-aware TODO execution."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from todo_execution_contracts import ExecutionState, TodoContract
from todo_execution_lifecycle import ExecutionLifecycle, ExecutionRecord
from parent_join_gates import ChildJoinSnapshot, ParentJoinResult, evaluate_parent_join
from todo_child_coordination import ChildWorktreeCoordinator, IntegrationConflict
from todo_readiness_scheduler import SchedulerConfig, schedule_todos


class TelemetryFieldError(ValueError):
    """Raised when telemetry contains a field outside the operational allowlist."""


_OPAQUE_ID = re.compile(r"^(?:todo|child|parent)-[A-Za-z0-9]+(?:[-_.][A-Za-z0-9]+)*$")
_FORBIDDEN_VALUE = re.compile(
    r"(?:medical|health|genomic|blood|account|routing|password|secret|token|api[-_ ]?key|credential)",
    re.IGNORECASE,
)
_TELEMETRY_REASONS = frozenset(
    {
        "operational retry",
        "capacity limit",
        "resource conflict",
        "child integration conflict",
        "validated child integrated",
    }
)
DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[1] / "config" / "todo_execution_policy.json"


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
        _validate_telemetry_id(todo_id)
        forbidden = set(details) - self.allowed_fields
        if forbidden:
            raise TelemetryFieldError(f"telemetry fields are not allowlisted: {', '.join(sorted(forbidden))}")
        for name, value in details.items():
            _validate_telemetry_value(name, value)
        self.events.append(TelemetryEvent(kind, todo_id, dict(details)))

    def query(
        self,
        *,
        kind: str | None = None,
        todo_id: str | None = None,
        **filters: int | str | bool,
    ) -> tuple[TelemetryEvent, ...]:
        """Return events matching the supplied allowlisted fields in emit order."""
        if kind is not None and kind not in self.allowed_kinds:
            raise TelemetryFieldError(f"telemetry kind is not allowlisted: {kind}")
        _validate_telemetry_id(todo_id)
        forbidden = set(filters) - self.allowed_fields
        if forbidden:
            raise TelemetryFieldError(f"telemetry fields are not allowlisted: {', '.join(sorted(forbidden))}")
        for name, value in filters.items():
            _validate_telemetry_value(name, value)
        return tuple(
            event
            for event in self.events
            if (kind is None or event.kind == kind)
            and (todo_id is None or event.todo_id == todo_id)
            and all(event.details.get(name) == value for name, value in filters.items())
        )


def _validate_telemetry_id(value: str | None) -> None:
    if value is not None and (
        not isinstance(value, str)
        or _FORBIDDEN_VALUE.search(value)
        or not _OPAQUE_ID.fullmatch(value)
    ):
        raise TelemetryFieldError("telemetry todo identity must be an opaque operational identifier")


def _validate_telemetry_value(name: str, value: int | str | bool) -> None:
    if isinstance(value, str):
        if _FORBIDDEN_VALUE.search(value):
            raise TelemetryFieldError(f"telemetry {name} contains a forbidden sensitive value")
        if name == "reason" and value not in _TELEMETRY_REASONS:
            raise TelemetryFieldError("telemetry reason is not an operational enum")
    elif isinstance(value, bool):
        return
    elif not isinstance(value, int) or value < 0:
        raise TelemetryFieldError(f"telemetry {name} must be a bounded non-negative integer")


@dataclass(frozen=True)
class OperationalConfig:
    """Initial evidence-based worker limits for one FR and the workspace."""

    max_parallel_per_fr: int = 8
    global_worker_capacity: int = 16
    lease_seconds: int = 300
    max_retries: int = 2
    pre_fr_capacity: int = 16

    @classmethod
    def from_policy(cls, policy: Mapping[str, object]) -> "OperationalConfig":
        required = {
            "max_parallel_todos_per_fr",
            "max_total_todo_workers",
            "lease_seconds",
            "max_retries",
        }
        allowed = required | {"pre_fr_capacity", "tuning"}
        unknown = set(policy) - allowed
        missing = required - set(policy)
        if unknown:
            raise ValueError(f"unknown execution policy fields: {', '.join(sorted(unknown))}")
        if missing:
            raise ValueError(f"missing execution policy fields: {', '.join(sorted(missing))}")
        values = {key: policy[key] for key in required | {"pre_fr_capacity"} if key in policy}
        invalid_types = sorted(key for key, value in values.items() if type(value) is not int)
        if invalid_types:
            raise ValueError(
                f"execution policy limits must be integers: {', '.join(invalid_types)}"
            )
        return cls(
            max_parallel_per_fr=values["max_parallel_todos_per_fr"],
            global_worker_capacity=values["max_total_todo_workers"],
            lease_seconds=values["lease_seconds"],
            max_retries=values["max_retries"],
            pre_fr_capacity=values.get("pre_fr_capacity", cls.pre_fr_capacity),
        )

    @classmethod
    def from_policy_path(cls, path: str | Path) -> "OperationalConfig":
        with Path(path).open(encoding="utf-8") as policy_file:
            policy = json.load(policy_file)
        if not isinstance(policy, dict):
            raise ValueError("execution policy must be a JSON object")
        return cls.from_policy(policy)

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
        policy: Mapping[str, object] | None = None,
        policy_path: str | Path | None = None,
    ) -> None:
        if config is not None and (policy is not None or policy_path is not None):
            raise ValueError("provide config or policy, not both")
        self.connection = connection
        self.contracts = contracts
        if policy is not None:
            self.config = OperationalConfig.from_policy(policy)
        elif policy_path is not None:
            self.config = OperationalConfig.from_policy_path(policy_path)
        else:
            self.config = config or OperationalConfig.from_policy_path(DEFAULT_POLICY_PATH)
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
            self.telemetry.emit("conflict", item.todo_id, reason=_queue_reason(item.reason))
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


def _queue_reason(reason: str) -> str:
    return "resource conflict" if "resource" in reason else "capacity limit"