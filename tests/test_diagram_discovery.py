from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]
DIAGRAMS_DIR = REPO_ROOT / "diagrams"
DISCOVERY_PATH = DIAGRAMS_DIR / "DIAGRAM_DISCOVERY.md"


def test_diagram_discovery_is_a_generated_federation_contract() -> None:
    discovery = DISCOVERY_PATH.read_text(encoding="utf-8")

    for heading in (
        "Six local manifests",
        "Workspace-owned cross-project sources",
        "Generated aggregate discovery",
        "Validation dimensions",
        "structure",
        "nodes/edges",
        "renderer/fallback risk",
        "split",
        "lineage",
        "duplicate/orphan",
    ):
        assert heading in discovery

    for legacy_claim in (
        "Source Inventory",
        "Committed baseline",
        "Baseline commit",
        "UTF-8 byte",
        "Characters:",
        "seven approved",
        "architecture changes require editing",
    ):
        assert legacy_claim not in discovery

def test_workspace_architecture_documents_federated_registry_boundary() -> None:
    for filename in ("workspace-architecture.mmd", "workspace-integrations.mmd"):
        source = (DIAGRAMS_DIR / filename).read_text(encoding="utf-8")
        assert "repository-local manifests" in source
        assert "generated aggregate registry" in source
