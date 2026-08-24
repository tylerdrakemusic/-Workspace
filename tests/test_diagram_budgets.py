from __future__ import annotations

from pathlib import Path

from diagram_budgets import (
    DiagramCategory,
    DiagramMetrics,
    DiagramSpec,
    Traceability,
    BUDGETS,
    measure_source,
    validate_inventory,
    validate_diagram,
)


def _spec(category: DiagramCategory, **metrics: int | str) -> DiagramSpec:
    return DiagramSpec(
        path="diagrams/example.mmd",
        category=category,
        metrics=DiagramMetrics(
            utf8_characters=int(metrics.get("utf8_characters", 100)),
            utf8_bytes=int(metrics.get("utf8_bytes", 120)),
            nodes=int(metrics.get("nodes", 8)),
            edges=int(metrics.get("edges", 7)),
            renderer_url_risk=str(metrics.get("renderer_url_risk", "low")),
            fallback_risk=str(metrics.get("fallback_risk", "low")),
        ),
        traceability=Traceability(parent="diagrams/parent.mmd", derived_views=()),
    )


def test_compliant_diagram_has_no_budget_findings() -> None:
    result = validate_diagram(_spec(DiagramCategory.OVERVIEW))

    assert result.is_compliant
    assert result.findings == ()
    assert not result.split_required


def test_oversized_diagram_reports_each_exceeded_machine_budget() -> None:
    result = validate_diagram(
        _spec(
            DiagramCategory.DETAIL,
            utf8_characters=8001,
            utf8_bytes=12001,
            nodes=61,
            edges=101,
            renderer_url_risk="high",
            fallback_risk="high",
        )
    )

    assert not result.is_compliant
    assert {finding.code for finding in result.findings} == {
        "utf8_characters",
        "utf8_bytes",
        "nodes",
        "edges",
        "renderer_url_risk",
        "fallback_risk",
        "split_required",
    }


def test_category_rules_mark_detail_and_schema_as_split_required() -> None:
    detail = validate_diagram(_spec(DiagramCategory.DETAIL, nodes=51))
    schema = validate_diagram(_spec(DiagramCategory.DATABASE_SCHEMA, edges=51))

    assert detail.split_required
    assert "split_required" in {finding.code for finding in detail.findings}
    assert schema.split_required
    assert "split_required" in {finding.code for finding in schema.findings}


def test_derived_view_requires_parent_and_declared_traceability() -> None:
    spec = _spec(DiagramCategory.DETAIL)
    spec = DiagramSpec(
        path=spec.path,
        category=spec.category,
        metrics=spec.metrics,
        traceability=Traceability(parent=None, derived_views=()),
        is_derived_view=True,
    )

    result = validate_diagram(spec)

    assert not result.is_compliant
    assert {finding.code for finding in result.findings} == {"traceability"}


def test_derived_view_with_distinct_parent_path_is_traceable() -> None:
    spec = _spec(DiagramCategory.DETAIL)
    derived = DiagramSpec(
        path=spec.path,
        category=spec.category,
        metrics=spec.metrics,
        traceability=Traceability(parent="diagrams/parent.mmd", derived_views=()),
        is_derived_view=True,
    )

    assert "traceability" not in {finding.code for finding in validate_diagram(derived).findings}


def test_all_documented_categories_have_distinct_machine_budgets() -> None:
    assert set(BUDGETS) == set(DiagramCategory)
    assert BUDGETS[DiagramCategory.TECHNOLOGY_STACK].max_nodes < BUDGETS[DiagramCategory.DETAIL].max_nodes
    assert BUDGETS[DiagramCategory.DATABASE_SCHEMA].max_edges < BUDGETS[DiagramCategory.DETAIL].max_edges


def test_measure_source_uses_todo_302_utf8_contract() -> None:
    path = Path(__file__).parents[1] / "diagrams" / "workspace-tech-stack.mmd"

    metrics = measure_source(path)

    assert metrics.utf8_characters == 1851
    assert metrics.utf8_bytes == 1851
    assert metrics.nodes == 16
    assert metrics.edges == 16
    assert metrics.fallback_risk == "medium"


def test_validate_inventory_reconciles_committed_baseline_measurements() -> None:
    inventory_path = Path(__file__).parents[1] / "diagrams" / "DIAGRAM_INVENTORY.md"

    findings = validate_inventory(inventory_path)

    assert any(
        finding.code == "inventory_utf8_bytes"
        and "diagrams/capital-architecture.mmd" in finding.message
        for finding in findings
    )
    assert any(
        finding.code == "inventory_utf8_characters"
        and "diagrams/capital-architecture.mmd" in finding.message
        for finding in findings
    )
    assert any(
        finding.code == "inventory_nodes"
        and "diagrams/capital-db-schema.mmd" in finding.message
        for finding in findings
    )
    assert any(
        finding.code == "inventory_edges"
        and "diagrams/life-db-schema.mmd" in finding.message
        for finding in findings
    )


def test_validate_inventory_detects_missing_baseline_row(tmp_path: Path) -> None:
    inventory_path = Path(__file__).parents[1] / "diagrams" / "DIAGRAM_INVENTORY.md"
    inventory = inventory_path.read_text(encoding="utf-8")
    inventory = inventory.replace(
        "| diagrams/workspace-tech-stack.mmd |",
        "| diagrams/workspace-tech-stack.removed.mmd |",
    )
    reduced_inventory_path = tmp_path / "DIAGRAM_INVENTORY.md"
    reduced_inventory_path.write_text(inventory, encoding="utf-8")

    findings = validate_inventory(reduced_inventory_path, source_root=inventory_path.parents[1])

    assert any(
        finding.code == "inventory_missing"
        and "diagrams/workspace-tech-stack.mmd" in finding.message
        for finding in findings
    )