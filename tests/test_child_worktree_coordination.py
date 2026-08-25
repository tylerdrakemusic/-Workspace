from __future__ import annotations

import pytest

from src.utils.todo_child_coordination import (
    ChildWorktree,
    ChildWorktreeCoordinator,
    CoordinationError,
    IntegrationConflict,
)


def _child(*, state: str = "completed", validated: bool = True, base: str = "base-1") -> ChildWorktree:
    return ChildWorktree(
        todo_id="333-1",
        fr_id="FR-20260824-workspace-todo-child-branch-worktree-coordination",
        worker_id="worker-1",
        claim_id="claim-1",
        branch="feature/todo-333-1",
        worktree="child-worktree/todo-333-1",
        state=state,
        validated=validated,
        source_base=base,
    )


def test_admission_rejects_unclaimed_expired_failed_or_unvalidated_children() -> None:
    coordinator = ChildWorktreeCoordinator(
        fr_id="FR-20260824-workspace-todo-child-branch-worktree-coordination",
        target_branch="feature/fr-333",
        capacity=1,
    )

    coordinator.admit(_child())

    for state, validated in (("queued", True), ("stale", True), ("failed", True), ("completed", False)):
        with pytest.raises(CoordinationError):
            coordinator.admit(_child(state=state, validated=validated))


def test_integration_rebases_stale_child_and_preserves_sources_on_conflict() -> None:
    calls: list[tuple[str, str]] = []

    def rebase(child: ChildWorktree, target_head: str) -> bool:
        calls.append(("rebase", target_head))
        return True

    def integrate(child: ChildWorktree) -> None:
        calls.append(("integrate", child.branch))

    coordinator = ChildWorktreeCoordinator(
        fr_id="FR-20260824-workspace-todo-child-branch-worktree-coordination",
        target_branch="feature/fr-333",
        capacity=2,
        rebase=rebase,
        integrate=integrate,
    )
    child = _child(base="old-head")
    coordinator.admit(child)
    coordinator.integrate(child.todo_id, target_head="new-head")

    assert calls == [("rebase", "new-head"), ("integrate", child.branch)]

    def conflicting_rebase(child: ChildWorktree, target_head: str) -> bool:
        return False

    conflicted = ChildWorktreeCoordinator(
        fr_id="FR-20260824-workspace-todo-child-branch-worktree-coordination",
        target_branch="feature/fr-333",
        capacity=1,
        rebase=conflicting_rebase,
    )
    conflicted.admit(child)
    with pytest.raises(IntegrationConflict) as error:
        conflicted.integrate(child.todo_id, target_head="new-head")

    assert error.value.child == child
    assert (error.value.target_branch, error.value.target_head) == (
        "feature/fr-333",
        "new-head",
    )
    assert conflicted.source(child.todo_id) == child


def test_admission_requires_lifecycle_owner_and_unique_isolated_worktree() -> None:
    coordinator = ChildWorktreeCoordinator(
        fr_id="FR-20260824-workspace-todo-child-branch-worktree-coordination",
        target_branch="feature/fr-333",
        capacity=2,
    )
    coordinator.admit(_child())

    with pytest.raises(CoordinationError):
        coordinator.admit(
            ChildWorktree(
                todo_id="333-2",
                fr_id="FR-20260824-workspace-todo-child-branch-worktree-coordination",
                worker_id="worker-2",
                claim_id="claim-2",
                branch="feature/todo-333-1",
                worktree="child-worktree/todo-333-1",
                state="completed",
                validated=True,
                source_base="base-1",
            )
        )