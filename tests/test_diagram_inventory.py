from pathlib import Path

from src.utils.diagram_budgets import measure_source


REPO_ROOT = Path(__file__).parents[1]
DIAGRAMS_DIR = REPO_ROOT / "diagrams"
INVENTORY_PATH = DIAGRAMS_DIR / "DIAGRAM_INVENTORY.md"


def test_diagram_inventory_covers_all_mermaid_sources_with_required_evidence() -> None:
    inventory = INVENTORY_PATH.read_text(encoding="utf-8")
    source_paths = sorted(path.relative_to(REPO_ROOT).as_posix() for path in DIAGRAMS_DIR.glob("*.mmd"))
    assert len(source_paths) == 11
    assert "| Relative path | Purpose | Project scope | Bytes | Characters | Nodes | Edges | Renderer/backend result | Failure details |" in inventory
    assert all(f"| {source_path} |" in inventory for source_path in source_paths)
    for source_path in source_paths:
        assert f"| {source_path} |" in inventory
    for source_path in source_paths:
        inventory_row = next(row for row in inventory.splitlines() if f"| {source_path} |" in row)
        assert measure_source(REPO_ROOT / source_path).utf8_characters == int(inventory_row.split("|")[5].strip())
    assert "Committed baseline" in inventory
    assert "Baseline commit: `4ee4f6e` (FR worktree diagram baseline)" in inventory
    assert "seven approved" in inventory

def test_workspace_architecture_documents_federated_registry_boundary() -> None:
    for filename in ("workspace-architecture.mmd", "workspace-integrations.mmd"):
        source = (DIAGRAMS_DIR / filename).read_text(encoding="utf-8")
        assert "repository-local manifests" in source
        assert "generated aggregate registry" in source
