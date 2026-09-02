from pathlib import Path

from diagram_budgets import DiagramCategory, DiagramSpec, Traceability, measure_source, validate_diagram

AGENTS_DIR = Path(__file__).parents[1] / ".github" / "agents"


def test_architecture_agents_reference_approved_budget_lineage_and_renderer_contract() -> None:
    reviewer = (AGENTS_DIR / "⊕workspace-architecture-reviewer.agent.md").read_text(encoding="utf-8")
    beautifier = (AGENTS_DIR / "⊕workspace-architecture-beautifier.agent.md").read_text(encoding="utf-8")
    combined = f"{reviewer}\n{beautifier}"

    for required_text in (
        "diagrams/DIAGRAM_BUDGETS.md",
        "diagrams/STYLE_GUIDE.md",
        "nodes",
        "edges",
        "UTF-8 byte and character counts are diagnostic only",
        "split_required",
        "is_derived_view=true",
        "Traceability.parent",
        "Traceability.derived_views",
        "renderer",
        "NOT RUN",
        "repository-local manifests",
        "generated aggregate registry",
    ):
        assert required_text in combined


def test_architecture_agents_preserve_relationships_when_splitting() -> None:
    reviewer = (AGENTS_DIR / "⊕workspace-architecture-reviewer.agent.md").read_text(encoding="utf-8")
    beautifier = (AGENTS_DIR / "⊕workspace-architecture-beautifier.agent.md").read_text(encoding="utf-8")

    assert "preserve" in reviewer.lower()
    assert "parent" in beautifier.lower()
    assert "derived" in beautifier.lower()
    assert "relationship" in beautifier.lower()


def test_oversized_parent_diagrams_are_replaced_by_bounded_views() -> None:
    diagrams_dir = Path(__file__).parents[1] / "diagrams"
    categories = {
        "workspace-architecture.mmd": DiagramCategory.OVERVIEW,
        "workspace-integrations.mmd": DiagramCategory.OVERVIEW,
    }

    for filename, category in categories.items():
        path = diagrams_dir / filename
        metrics = measure_source(path)
        result = validate_diagram(
            DiagramSpec(
                path=f"diagrams/{filename}",
                category=category,
                metrics=metrics,
                traceability=Traceability(parent=None, derived_views=()),
            )
        )
        assert result.is_compliant, (filename, result.findings)

    derived = sorted(diagrams_dir.glob("workspace-derived-*.mmd"))
    assert derived
    assert all("Traceability.parent" in path.read_text(encoding="utf-8") for path in derived)