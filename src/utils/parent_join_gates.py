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
    repository: str | None = None
    project: str | None = None
    parent_branch: str | None = None


@dataclass(frozen=True)
class ParentRepositorySnapshot:
    """Trusted current branch and head for one parent repository."""

    repository: str
    project: str
    parent_branch: str
    parent_head: str


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
    parent_repositories: Iterable[ParentRepositorySnapshot] = (),
) -> ParentJoinResult:
    """Return whether every required child is complete, valid, and integrated."""
    required_input = tuple(required_todos)
    required = tuple(dict.fromkeys(required_input))
    snapshots = tuple(children)
    repositories = tuple(parent_repositories)
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

    repository_heads: dict[tuple[str, str], ParentRepositorySnapshot] = {}
    for repository in repositories:
        if not all(
            value.strip()
            for value in (
                repository.repository,
                repository.project,
                repository.parent_branch,
                repository.parent_head,
            )
        ):
            raise ValueError("parent repository identities are required")
        key = (repository.repository, repository.project)
        if key in repository_heads:
            raise ValueError("duplicate parent repository identity")
        repository_heads[key] = repository

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
        expected_repository = None
        if repositories:
            if not child.repository or not child.project:
                blockers.append(f"{todo_id}: repository/project identity is required")
                continue
            else:
                expected_repository = repository_heads.get((child.repository, child.project))
                if expected_repository is None:
                    blockers.append(
                        f"{todo_id}: repository/project is not declared: "
                        f"{child.repository}/{child.project}"
                    )
                elif child.parent_branch and child.parent_branch != expected_repository.parent_branch:
                    blockers.append(
                        f"{todo_id}: child parent branch {child.parent_branch} conflicts with "
                        f"{child.repository}/{child.project} branch {expected_repository.parent_branch}"
                    )
        expected_branch = expected_repository.parent_branch if expected_repository else parent_branch
        expected_head = expected_repository.parent_head if expected_repository else parent_head
        repository_label = (
            f"{child.repository}/{child.project} " if expected_repository else ""
        )
        if child.integrated_branch != expected_branch:
            blockers.append(f"{todo_id}: child is not integrated into parent branch")
        if repositories and expected_repository and child.parent_head != expected_head:
            blockers.append(
                f"{todo_id}: child parent head {child.parent_head} conflicts with "
                f"{repository_label}head {expected_head}"
            )
        if child.child_base != expected_head:
            blockers.append(
                f"{todo_id}: child base {child.child_base} conflicts with "
                f"{repository_label}parent head {expected_head}"
            )
    return ParentJoinResult(not blockers, tuple(blockers))