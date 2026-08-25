from __future__ import annotations

import pytest

from src.utils.parent_join_gates import ChildJoinSnapshot, evaluate_parent_join


def _child(**overrides: object) -> ChildJoinSnapshot:
    values: dict[str, object] = {
        "todo_id": "333-1",
        "fr_id": "FR-20260824-workspace-parent-join-gates",
        "state": "completed",
        "validated": True,
        "required_artifacts": ("test-proof",),
        "artifacts": ("test-proof",),
        "integrated_branch": "feature/FR-20260824-workspace-parent-join-gates",
        "parent_head": "parent-head-2",
        "child_base": "parent-head-2",
    }
    values.update(overrides)
    return ChildJoinSnapshot(**values)


def test_parent_join_reports_each_incomplete_child_criterion() -> None:
    result = evaluate_parent_join(
        fr_id="FR-20260824-workspace-parent-join-gates",
        parent_branch="feature/FR-20260824-workspace-parent-join-gates",
        parent_head="parent-head-2",
        required_todos=("333-1",),
        children=(
            _child(
                state="stale",
                validated=False,
                artifacts=(),
                integrated_branch=None,
                child_base="old-head",
            ),
        ),
    )

    assert result.complete is False
    assert result.blockers == (
        "333-1: terminal state must be completed",
        "333-1: validation is required",
        "333-1: required artifact missing: test-proof",
        "333-1: child is not integrated into parent branch",
        "333-1: child base old-head conflicts with parent head parent-head-2",
    )


def test_parent_join_requires_all_required_children_and_accepts_complete_join() -> None:
    complete = evaluate_parent_join(
        fr_id="FR-20260824-workspace-parent-join-gates",
        parent_branch="feature/FR-20260824-workspace-parent-join-gates",
        parent_head="parent-head-2",
        required_todos=("333-1", "333-2"),
        children=(_child(), _child(todo_id="333-2")),
    )

    assert complete.complete is True
    assert complete.blockers == ()


def test_parent_join_rejects_child_from_another_fr() -> None:
    with pytest.raises(ValueError, match="FR identity"):
        evaluate_parent_join(
            fr_id="FR-20260824-workspace-parent-join-gates",
            parent_branch="feature/FR-20260824-workspace-parent-join-gates",
            parent_head="parent-head-2",
            required_todos=("333-1",),
            children=(_child(fr_id="FR-other"),),
        )