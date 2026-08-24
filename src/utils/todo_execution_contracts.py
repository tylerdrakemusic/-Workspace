"""Domain-neutral contracts for TODO relationships and execution leases."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Iterable


class ContractValidationError(ValueError):
    """Raised when a TODO execution contract is not structurally valid."""


class ExecutionState(str, Enum):
    QUEUED = "queued"
    CLAIMED = "claimed"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    STALE = "stale"


TERMINAL_STATES = frozenset({
    ExecutionState.COMPLETED,
    ExecutionState.FAILED,
    ExecutionState.CANCELLED,
    ExecutionState.STALE,
})
SUPPORTED_RESOURCES = frozenset({"file", "shared"})


def _identity(value: str | None, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"missing {label} identity")
    return value.strip()


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ContractValidationError("timestamps must include a timezone")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class ResourceDeclaration:
    """A file path or named shared resource required by a TODO."""

    kind: str
    name: str

    def __post_init__(self) -> None:
        if self.kind not in SUPPORTED_RESOURCES:
            raise ContractValidationError(f"unsupported resource kind: {self.kind}")
        _identity(self.name, "resource")


@dataclass(frozen=True)
class PrerequisiteEdge:
    """A directional edge from ``todo_id`` to its prerequisite."""

    todo_id: str
    prerequisite_id: str
    allowed_terminal_states: tuple[ExecutionState, ...] = (ExecutionState.COMPLETED,)

    def __post_init__(self) -> None:
        todo_id = _identity(self.todo_id, "todo")
        prerequisite_id = _identity(self.prerequisite_id, "prerequisite")
        if todo_id == prerequisite_id:
            raise ContractValidationError("prerequisite cycle: a TODO cannot require itself")
        states = tuple(ExecutionState(state) for state in self.allowed_terminal_states)
        if not states or any(state not in TERMINAL_STATES for state in states):
            raise ContractValidationError("invalid terminal-state policy")
        if len(set(states)) != len(states):
            raise ContractValidationError("duplicate terminal-state policy")
        object.__setattr__(self, "todo_id", todo_id)
        object.__setattr__(self, "prerequisite_id", prerequisite_id)
        object.__setattr__(self, "allowed_terminal_states", states)


@dataclass(frozen=True)
class TodoContract:
    """Normalized identity and dependency declarations for one TODO."""

    todo_id: str
    parent_id: str | None = None
    fr_id: str | None = None
    inherited_fr_id: str | None = None
    branch: str | None = None
    worktree: str | None = None
    prerequisites: tuple[PrerequisiteEdge, ...] = ()
    resources: tuple[ResourceDeclaration, ...] = ()

    def __post_init__(self) -> None:
        todo_id = _identity(self.todo_id, "todo")
        parent_id = _identity(self.parent_id, "parent") if self.parent_id is not None else None
        fr_id = _identity(self.fr_id, "FR") if self.fr_id is not None else None
        inherited = (
            _identity(self.inherited_fr_id, "inherited FR")
            if self.inherited_fr_id is not None else None
        )
        if fr_id is not None and inherited is not None and fr_id != inherited:
            raise ContractValidationError("mismatched inherited FR link")
        branch = _identity(self.branch, "branch") if self.branch is not None else None
        worktree = _identity(self.worktree, "worktree") if self.worktree is not None else None
        if (branch is None) != (worktree is None):
            raise ContractValidationError("branch/worktree traceability requires both identities")
        edges = tuple(self.prerequisites)
        if any(edge.todo_id != todo_id for edge in edges):
            raise ContractValidationError("prerequisite edge has mismatched TODO identity")
        resources = tuple(self.resources)
        if len(set(resources)) != len(resources):
            raise ContractValidationError("duplicate resource declaration")
        object.__setattr__(self, "todo_id", todo_id)
        object.__setattr__(self, "parent_id", parent_id)
        object.__setattr__(self, "fr_id", fr_id)
        object.__setattr__(self, "inherited_fr_id", inherited)
        object.__setattr__(self, "branch", branch)
        object.__setattr__(self, "worktree", worktree)
        object.__setattr__(self, "prerequisites", edges)
        object.__setattr__(self, "resources", resources)


@dataclass(frozen=True)
class ExecutionLease:
    """Claim and lease metadata; mutation is represented by new values."""

    todo_id: str
    state: ExecutionState
    worker_id: str
    claim_id: str
    lease_expires_at: datetime
    heartbeat_at: datetime
    attempt: int = 1
    max_retries: int = 0
    cancellation_requested: bool = False

    def __post_init__(self) -> None:
        _identity(self.todo_id, "todo")
        _identity(self.worker_id, "worker")
        _identity(self.claim_id, "claim")
        if self.state not in {ExecutionState.CLAIMED, ExecutionState.RUNNING}:
            raise ContractValidationError("lease must be claimed or running")
        if self.attempt < 1 or self.max_retries < 0:
            raise ContractValidationError("invalid retry policy")
        expires = _utc(self.lease_expires_at)
        heartbeat = _utc(self.heartbeat_at)
        if expires <= heartbeat:
            raise ContractValidationError("lease expiration must follow heartbeat")
        object.__setattr__(self, "todo_id", self.todo_id.strip())
        object.__setattr__(self, "worker_id", self.worker_id.strip())
        object.__setattr__(self, "claim_id", self.claim_id.strip())
        object.__setattr__(self, "lease_expires_at", expires)
        object.__setattr__(self, "heartbeat_at", heartbeat)


def associate_fr(contract: TodoContract, fr_id: str) -> TodoContract:
    """Associate a refined anchor with its inherited FR, once established."""
    fr_id = _identity(fr_id, "FR")
    if contract.inherited_fr_id is not None and contract.inherited_fr_id != fr_id:
        raise ContractValidationError("mismatched inherited FR link")
    return replace(contract, fr_id=fr_id, inherited_fr_id=contract.inherited_fr_id or fr_id)


def validate_contracts(contracts: Iterable[TodoContract]) -> None:
    """Validate identities, parentage, dependency direction, and cycles."""
    items = tuple(contracts)
    by_id: dict[str, TodoContract] = {}
    for contract in items:
        if contract.todo_id in by_id:
            raise ContractValidationError(f"duplicate TODO identity: {contract.todo_id}")
        by_id[contract.todo_id] = contract
    parent_graph: dict[str, str] = {}
    prerequisite_graph: dict[str, tuple[str, ...]] = {}
    for contract in items:
        if contract.parent_id is not None:
            if contract.parent_id == contract.todo_id:
                raise ContractValidationError("invalid parentage: TODO cannot parent itself")
            if contract.parent_id not in by_id:
                raise ContractValidationError("invalid parentage: parent identity is missing")
            parent_graph[contract.todo_id] = contract.parent_id
        targets = tuple(edge.prerequisite_id for edge in contract.prerequisites)
        if len(set(targets)) != len(targets):
            raise ContractValidationError(f"ambiguous dependency for {contract.todo_id}")
        if any(target not in by_id for target in targets):
            raise ContractValidationError("ambiguous dependency: prerequisite identity is missing")
        prerequisite_graph[contract.todo_id] = targets
    _reject_cycles(parent_graph, "parent cycle")
    _reject_cycles(prerequisite_graph, "prerequisite cycle")

    effective_fr: dict[str, str | None] = {}

    def resolve_effective_fr(todo_id: str) -> str | None:
        if todo_id in effective_fr:
            return effective_fr[todo_id]
        contract = by_id[todo_id]
        parent_fr = (
            resolve_effective_fr(contract.parent_id)
            if contract.parent_id is not None else None
        )
        if contract.inherited_fr_id is not None and parent_fr is not None:
            if contract.inherited_fr_id != parent_fr:
                raise ContractValidationError(
                    f"inherited FR mismatch for {todo_id}: parent effective FR is {parent_fr}"
                )
        resolved = contract.fr_id or contract.inherited_fr_id or parent_fr
        effective_fr[todo_id] = resolved
        return resolved

    for contract in items:
        resolve_effective_fr(contract.todo_id)


def _reject_cycles(graph: dict[str, Iterable[str]], label: str) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise ContractValidationError(label)
        if node in visited:
            return
        visiting.add(node)
        for target in graph.get(node, ()):
            visit(target)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)


def claim_execution(todo_id: str, worker_id: str, claim_id: str,
                    lease_seconds: int, now: datetime) -> ExecutionLease:
    """Create a claimed lease with explicit claim and worker identities."""
    if lease_seconds <= 0:
        raise ContractValidationError("lease duration must be positive")
    now = _utc(now)
    return ExecutionLease(todo_id, ExecutionState.CLAIMED, worker_id, claim_id,
                          now + timedelta(seconds=lease_seconds), now)


def heartbeat_execution(lease: ExecutionLease, now: datetime, lease_seconds: int) -> ExecutionLease:
    """Renew a live lease and mark its execution as running."""
    now = _utc(now)
    if now >= lease.lease_expires_at:
        raise ContractValidationError("cannot heartbeat an expired lease")
    if lease_seconds <= 0:
        raise ContractValidationError("lease duration must be positive")
    return replace(lease, state=ExecutionState.RUNNING, heartbeat_at=now,
                   lease_expires_at=now + timedelta(seconds=lease_seconds))


def expire_execution(lease: ExecutionLease, now: datetime) -> ExecutionState:
    """Return stale when the lease has expired, otherwise preserve its state."""
    return ExecutionState.STALE if _utc(now) >= lease.lease_expires_at else lease.state


def retry_allowed(lease: ExecutionLease) -> bool:
    """Return whether another attempt is permitted after a stale/failed attempt."""
    return lease.attempt <= lease.max_retries


def cancellation_state(state: ExecutionState) -> ExecutionState:
    """Map cancellable execution states to the terminal cancelled state."""
    if state in TERMINAL_STATES:
        return state
    return ExecutionState.CANCELLED


def parent_join_state(child_states: Iterable[ExecutionState]) -> ExecutionState:
    """Derive a parent state after joining child executions."""
    states = tuple(child_states)
    if not states or any(state not in TERMINAL_STATES for state in states):
        return ExecutionState.RUNNING
    if ExecutionState.FAILED in states:
        return ExecutionState.FAILED
    if ExecutionState.CANCELLED in states:
        return ExecutionState.CANCELLED
    if ExecutionState.STALE in states:
        return ExecutionState.STALE
    return ExecutionState.COMPLETED