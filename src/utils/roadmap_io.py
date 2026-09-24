"""Roadmap generation and JSON output orchestration."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from roadmap_db import fetch_active_frs, fetch_open_todos
from roadmap_graph import build_roadmap

MANIFEST_TODOS_DB_PATH = (
    Path(__file__).resolve().parents[3] / "👁AI-Manifest" / "src" / "data" / "manifest_todos.db"
)
DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "roadmap.json"


def generate_roadmap(
    output_path: Path | None = None,
    fr_connection: sqlite3.Connection | None = None,
    todos_db_path: Path | None = None,
) -> dict[str, Any]:
    """Generate the roadmap JSON artifact."""
    owns_fr_conn = False
    if fr_connection is None:
        from init_fr_db import get_connection, init_db
        init_db()
        fr_connection = get_connection()
        owns_fr_conn = True
    try:
        frs = fetch_active_frs(fr_connection)
    finally:
        if owns_fr_conn:
            fr_connection.close()
    todos_path = todos_db_path if todos_db_path is not None else MANIFEST_TODOS_DB_PATH
    todos: list[dict[str, object]] = []
    if todos_path.is_file():
        todo_conn = sqlite3.connect(str(todos_path))
        todo_conn.row_factory = sqlite3.Row
        try:
            todos = fetch_open_todos(todo_conn)
        finally:
            todo_conn.close()
    roadmap = build_roadmap(frs, todos)
    output_path = output_path or DEFAULT_OUTPUT_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(roadmap, indent=2, ensure_ascii=False), encoding="utf-8")
    return roadmap