from pathlib import Path

from src.utils.diagram_budgets import measure_source


REPO_ROOT = Path(__file__).parents[1]
DIAGRAMS_DIR = REPO_ROOT / "diagrams"
INVENTORY_PATH = DIAGRAMS_DIR / "DIAGRAM_INVENTORY.md"


def test_diagram_inventory_covers_all_mermaid_sources_with_required_evidence() -> None:
    inventory = INVENTORY_PATH.read_text(encoding="utf-8")
    source_paths = sorted(path.relative_to(REPO_ROOT).as_posix() for path in DIAGRAMS_DIR.glob("*.mmd"))
    expected_character_counts = {
        "diagrams/capital-architecture.mmd": 1943,
        "diagrams/capital-db-schema.mmd": 822,
        "diagrams/manifest-architecture.mmd": 1140,
        "diagrams/workspace-agent-topology.mmd": 5766,
        "diagrams/workspace-architecture-detail.mmd": 8150,
        "diagrams/workspace-architecture.mmd": 3004,
        "diagrams/workspace-integrations.mmd": 1392,
        "diagrams/capital-derived-market-data.mmd": 1324,
        "diagrams/workspace-derived-services.mmd": 1280,
    }

    assert len(source_paths) == 32
    assert "| Relative path | Purpose | Project scope | Bytes | Characters | Nodes | Edges | Renderer/backend result | Failure details |" in inventory
    assert inventory.count("| diagrams/") == len(source_paths)
    for source_path in source_paths:
        assert f"| {source_path} |" in inventory
    for source_path, character_count in expected_character_counts.items():
        inventory_row = next(row for row in inventory.splitlines() if f"| {source_path} |" in row)
        assert measure_source(REPO_ROOT / source_path).utf8_characters == character_count
        assert int(inventory_row.split("|")[5].strip()) == character_count
    assert "Committed baseline" in inventory
    assert "Baseline commit: `a704f0e` (committed `origin/main` baseline)" in inventory
    assert "Uncommitted local overlay" in inventory