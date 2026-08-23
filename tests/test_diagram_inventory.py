from pathlib import Path


REPO_ROOT = Path(__file__).parents[1]
DIAGRAMS_DIR = REPO_ROOT / "diagrams"
INVENTORY_PATH = DIAGRAMS_DIR / "DIAGRAM_INVENTORY.md"


def test_diagram_inventory_covers_all_mermaid_sources_with_required_evidence() -> None:
    inventory = INVENTORY_PATH.read_text(encoding="utf-8")
    source_paths = sorted(path.relative_to(REPO_ROOT).as_posix() for path in DIAGRAMS_DIR.glob("*.mmd"))

    assert len(source_paths) == 23
    assert "| Relative path | Purpose | Project scope | Bytes | Characters | Nodes | Edges | Renderer/backend result | Failure details |" in inventory
    assert inventory.count("| diagrams/") == len(source_paths)
    for source_path in source_paths:
        assert f"| {source_path} |" in inventory
    assert "Committed baseline" in inventory
    assert "Uncommitted local overlay" in inventory