"""Coordinate isolated child TODO work and serialized FR integration."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Callable


class CoordinationError(ValueError):
    """Raised when child work cannot be admitted or integrated."""


@dataclass(frozen=True)
class ChildWorktree:
    """Traceable child branch/worktree work associated with one FR claim."""

    todo_id: str
    fr_id: str
    worker_id: str
    claim_id: str
    branch: str
    worktree: str
    state: str
    validated: bool
    source_base: str


class IntegrationConflict(CoordinationError):
    """Raised when a child cannot be rebased onto the current FR branch."""

    def __init__(self, child: ChildWorktree, target_branch: str, target_head: str) -> None:
        super().__init__(f"child integration conflict: {child.todo_id}")
        self.child = child
        self.target_branch = target_branch
        self.target_head = target_head


Rebase = Callable[[ChildWorktree, str], bool]
Integrate = Callable[[ChildWorktree], None]


class ChildWorktreeCoordinator:
    """Admit and serialize validated child work into one FR feature branch."""

    def __init__(
        self,
        *,
        fr_id: str,
        target_branch: str,
        capacity: int,
        rebase: Rebase | None = None,
        integrate: Integrate | None = None,
    ) -> None:
        if not fr_id.strip() or not target_branch.strip() or capacity <= 0:
            raise CoordinationError("invalid FR integration configuration")
        self.fr_id = fr_id
        self.target_branch = target_branch
        self.capacity = capacity
        self._rebase = rebase or (lambda child, target_head: True)
        self._integrate = integrate or (lambda child: None)
        self._children: dict[str, ChildWorktree] = {}
        self._lock = Lock()

    def admit(self, child: ChildWorktree) -> None:
        """Admit one claimed, live, validated child within coordinator capacity."""
        if child.fr_id != self.fr_id:
            raise CoordinationError("child FR does not match coordinator")
        if not all((child.todo_id.strip(), child.worker_id.strip(), child.claim_id.strip(), child.branch.strip(), child.worktree.strip())):
            raise CoordinationError("child traceability identities are required")
        if child.todo_id not in child.branch or child.todo_id not in child.worktree:
            raise CoordinationError("branch/worktree must identify the TODO")
        if child.state not in {"claimed", "running", "completed"}:
            raise CoordinationError("child is not admitted for execution")
        if not child.validated:
            raise CoordinationError("child work has not been validated")
        with self._lock:
            if child.todo_id in self._children:
                raise CoordinationError("TODO already has admitted child work")
            if len(self._children) >= self.capacity:
                raise CoordinationError("child execution capacity exhausted")
            if any(existing.branch == child.branch or existing.worktree == child.worktree for existing in self._children.values()):
                raise CoordinationError("branch/worktree is already assigned")
            self._children[child.todo_id] = child

    def integrate(self, todo_id: str, *, target_head: str) -> None:
        """Rebase stale child work and integrate it while holding the FR lock."""
        with self._lock:
            child = self._children.get(todo_id)
            if child is None:
                raise CoordinationError("child work is not admitted")
            if child.state != "completed" or not child.validated:
                raise CoordinationError("only validated completed child work may integrate")
            if child.source_base != target_head and not self._rebase(child, target_head):
                raise IntegrationConflict(child, self.target_branch, target_head)
            self._integrate(child)
            del self._children[todo_id]

    def source(self, todo_id: str) -> ChildWorktree:
        """Return the preserved source assignment for a pending child."""
        try:
            return self._children[todo_id]
        except KeyError as error:
            raise CoordinationError("child work is not admitted") from error