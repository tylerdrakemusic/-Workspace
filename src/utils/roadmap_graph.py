"""Roadmap node and dependency graph construction."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from roadmap_parsing import (
    UNMAPPED_PROJECT,
    canonicalize_project,
    extract_fr_dependencies,
    extract_todo_fr_references,
)
from roadmap_quarters import assign_quarter


def _project_by_id(frs: list[dict[str, Any]]) -> dict[str, str]:
    return {
        fr["id"]: canonicalize_project((fr.get("projects") or "").split(",")[0].strip())
        for fr in frs
    }


def _append_fr_data(
    fr: dict[str, Any],
    project_by_id: dict[str, str],
    active_ids: set[str],
    today: date,
    nodes: list[dict[str, Any]],
    fr_edges: list[dict[str, str]],
    project_pairs: set[tuple[str, str]],
    quarters: dict[str, list[str]],
) -> None:
    project = project_by_id[fr["id"]]
    quarter = assign_quarter(fr, today=today)
    deps = extract_fr_dependencies(fr)
    nodes.append({
        "id": fr["id"], "title": fr.get("title"), "project": project,
        "state": fr.get("state"), "risk": fr.get("risk"),
        "quarter": quarter, "depends_on": deps,
    })
    quarters.setdefault(quarter, []).append(fr["id"])
    for dep_id in deps:
        fr_edges.append({"from": fr["id"], "to": dep_id})
        dep_project = project_by_id.get(dep_id, UNMAPPED_PROJECT)
        if dep_id in active_ids and dep_project != project:
            project_pairs.add((project, dep_project))


def _build_todo_refs(
    todos: list[dict[str, Any]], active_ids: set[str]
) -> list[dict[str, Any]]:
    todo_refs: list[dict[str, Any]] = []
    for todo in todos:
        for fr_id in extract_todo_fr_references(todo.get("text")):
            todo_refs.append({
                "todo_id": todo.get("id"), "todo_project": todo.get("project"),
                "fr_id": fr_id, "fr_active": fr_id in active_ids,
            })
    return todo_refs


def build_roadmap(
    frs: list[dict[str, Any]],
    todos: list[dict[str, Any]] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """Build roadmap nodes, dependency edges, todo references, and quarters."""
    todos = todos or []
    today = today or date.today()
    active_ids = {fr["id"] for fr in frs}
    project_by_id = _project_by_id(frs)
    nodes: list[dict[str, Any]] = []
    fr_edges: list[dict[str, str]] = []
    project_pairs: set[tuple[str, str]] = set()
    quarters: dict[str, list[str]] = {}
    for fr in frs:
        _append_fr_data(
            fr, project_by_id, active_ids, today, nodes, fr_edges,
            project_pairs, quarters,
        )
    todo_refs = _build_todo_refs(todos, active_ids)
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "nodes": nodes, "fr_edges": fr_edges,
        "project_edges": [{"from": a, "to": b} for a, b in sorted(project_pairs)],
        "todo_refs": todo_refs, "quarters": quarters,
    }