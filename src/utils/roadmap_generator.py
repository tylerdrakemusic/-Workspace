"""Compatibility facade for the modular roadmap generator."""
from __future__ import annotations

import argparse, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from roadmap_db import ACTIVE_FR_STATES, fetch_active_frs, fetch_open_todos
from roadmap_graph import build_roadmap
from roadmap_io import DEFAULT_OUTPUT_PATH, MANIFEST_TODOS_DB_PATH, generate_roadmap
from roadmap_parsing import (
    CANONICAL_PROJECTS,
    UNMAPPED_PROJECT,
    canonicalize_project,
    extract_fr_dependencies,
    extract_todo_fr_references,
    parse_dependencies,
)
from roadmap_quarters import RISK_WEIGHT, STATE_ORDER, add_quarters, assign_quarter, current_quarter


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the cross-project roadmap JSON artifact")
    parser.add_argument("--out", default=None, help="Output path (default: src/data/roadmap.json)")
    args = parser.parse_args()
    out_path = Path(args.out) if args.out else None
    roadmap = generate_roadmap(out_path)
    print(f"[roadmap_generator] Wrote roadmap with {len(roadmap['nodes'])} nodes to "
          f"{out_path or DEFAULT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
