"""Evaluate whether required child TODO work has joined its parent FR branch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

PARENT_JOIN_EVALUATOR_IDENTITY = "parent_join_gates.evaluate_parent_join"


@dataclass(frozen=True)
class ChildJoinSnapshot:
    """Evidence needed to admit one completed child into a parent FR."""

    todo_id: str
    fr_id: str
    state: str
    validated: bool
    required_artifacts: tuple[str, ...]
    artifacts: tuple[str, ...]
    integrated_branch: str | None
    parent_head: str
    child_base: str


@dataclass(frozen=True)
class ParentJoinResult:
    """Deterministic parent-join outcome and human-actionable blockers."""

    complete: bool
    blockers: tuple[str, ...] = ()


def evaluate_parent_join(
    *,
    fr_id: str,
    parent_branch: str,
    parent_head: str,
    required_todos: Iterable[str],
    children: Iterable[ChildJoinSnapshot],
) -> ParentJoinResult:
    """Return whether every required child is complete, valid, and integrated."""
    required_input = tuple(required_todos)
    required = tuple(dict.fromkeys(required_input))
    snapshots = tuple(children)
    if not fr_id.strip() or not parent_branch.strip() or not parent_head.strip():
        raise ValueError("parent join identities are required")
    if len(required) != len(required_input):
        raise ValueError("duplicate required TODO identity")
    by_id: dict[str, ChildJoinSnapshot] = {}
    for child in snapshots:
        if not child.todo_id.strip():
            raise ValueError("child TODO identity is required")
        if child.todo_id in by_id:
            raise ValueError("duplicate child TODO identity")
        if child.fr_id != fr_id:
            raise ValueError("child FR identity does not match parent FR")
        by_id[child.todo_id] = child

    blockers: list[str] = []
    for todo_id in required:
        child = by_id.get(todo_id)
        if child is None:
            blockers.append(f"{todo_id}: required child is missing")
            continue
        if child.state != "completed":
            blockers.append(f"{todo_id}: terminal state must be completed")
        if not child.validated:
            blockers.append(f"{todo_id}: validation is required")
        for artifact in child.required_artifacts:
            if artifact not in child.artifacts:
                blockers.append(f"{todo_id}: required artifact missing: {artifact}")
        if child.integrated_branch != parent_branch:
            blockers.append(f"{todo_id}: child is not integrated into parent branch")
        if child.child_base != parent_head:
            blockers.append(
                f"{todo_id}: child base {child.child_base} conflicts with parent head {parent_head}"
            )
    return ParentJoinResult(not blockers, tuple(blockers))