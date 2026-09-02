"""Machine-checkable budgets for Mermaid diagram sources."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import re


class DiagramCategory(str, Enum):
    OVERVIEW = "overview"
    DETAIL = "detail"
    DATABASE_SCHEMA = "database-schema"
    TECHNOLOGY_STACK = "technology-stack"
    WORKFLOW = "workflow"


@dataclass(frozen=True)
class DiagramMetrics:
    utf8_characters: int
    utf8_bytes: int
    nodes: int
    edges: int
    renderer_url_risk: str
    fallback_risk: str


@dataclass(frozen=True)
class Traceability:
    parent: str | None
    derived_views: tuple[str, ...]


@dataclass(frozen=True)
class DiagramSpec:
    path: str
    category: DiagramCategory
    metrics: DiagramMetrics
    traceability: Traceability
    is_derived_view: bool = False


@dataclass(frozen=True)
class DiagramBudget:
    max_utf8_characters: int
    max_utf8_bytes: int
    max_nodes: int
    max_edges: int
    max_renderer_url_risk: str = "medium"
    max_fallback_risk: str = "medium"
    split_at_nodes: int | None = None
    split_at_edges: int | None = None


@dataclass(frozen=True)
class Finding:
    code: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    findings: tuple[Finding, ...]
    split_required: bool

    @property
    def is_compliant(self) -> bool:
        return not self.findings


RISK_LEVELS = {"low": 0, "medium": 1, "high": 2}

BUDGETS: dict[DiagramCategory, DiagramBudget] = {
    DiagramCategory.OVERVIEW: DiagramBudget(8000, 12000, 40, 60, split_at_nodes=40, split_at_edges=60),
    DiagramCategory.DETAIL: DiagramBudget(8000, 12000, 50, 80, split_at_nodes=50, split_at_edges=80),
    DiagramCategory.DATABASE_SCHEMA: DiagramBudget(8000, 12000, 40, 50, split_at_nodes=40, split_at_edges=50),
    DiagramCategory.TECHNOLOGY_STACK: DiagramBudget(8000, 12000, 30, 40, split_at_nodes=30, split_at_edges=40),
    DiagramCategory.WORKFLOW: DiagramBudget(8000, 12000, 35, 50, split_at_nodes=35, split_at_edges=50),
}


def validate_diagram(spec: DiagramSpec) -> ValidationResult:
    """Validate one diagram against its category budget and lineage rules."""
    budget = BUDGETS[spec.category]
    metrics = spec.metrics
    findings: list[Finding] = []
    limits = (
        ("nodes", metrics.nodes, budget.max_nodes),
        ("edges", metrics.edges, budget.max_edges),
    )
    for code, value, limit in limits:
        if value > limit:
            findings.append(Finding(code, f"{code}={value} exceeds budget {limit}"))
    for code, value, limit in (
        ("renderer_url_risk", metrics.renderer_url_risk, budget.max_renderer_url_risk),
        ("fallback_risk", metrics.fallback_risk, budget.max_fallback_risk),
    ):
        if value not in RISK_LEVELS or RISK_LEVELS[value] > RISK_LEVELS[limit]:
            findings.append(Finding(code, f"{code}={value!r} exceeds allowed risk {limit!r}"))

    split_required = (
        (budget.split_at_nodes is not None and metrics.nodes > budget.split_at_nodes)
        or (budget.split_at_edges is not None and metrics.edges > budget.split_at_edges)
    )
    if split_required:
        findings.append(Finding("split_required", f"{spec.path} exceeds its category split threshold"))

    if spec.is_derived_view and not spec.traceability.parent:
        findings.append(Finding("traceability", "derived views must name their parent diagram"))
    if not spec.is_derived_view and any(not view for view in spec.traceability.derived_views):
        findings.append(Finding("traceability", "parent diagrams must declare non-empty derived view paths"))
    return ValidationResult(tuple(findings), split_required)


def measure_source(path: Path) -> DiagramMetrics:
    """Measure a Mermaid source using the inventory measurement contract."""
    with path.open("r", encoding="utf-8", newline="") as source_file:
        source = source_file.read()
    source = source.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
    lines = source.splitlines()
    node_count = sum(1 for line in lines if _looks_like_node(line))
    edge_count = sum(1 for line in lines if any(operator in line for operator in ("-->", "==>", "-.->", "---", "===", "}|")))
    return DiagramMetrics(
        utf8_characters=len(source),
        utf8_bytes=len(source.encode("utf-8")),
        nodes=node_count,
        edges=edge_count,
        renderer_url_risk="low",
        fallback_risk="medium" if ("%%{init:" in source or not source.isascii()) else "low",
    )


def validate_inventory(
    inventory_path: Path,
    source_root: Path | None = None,
) -> tuple[Finding, ...]:
    """Reconcile the committed inventory measurements with Mermaid sources."""
    source_root = source_root or inventory_path.parent.parent
    inventory_rows = _read_inventory_rows(inventory_path)
    source_paths = {
        path.relative_to(source_root).as_posix(): path
        for path in (source_root / "diagrams").glob("*.mmd")
    }
    findings: list[Finding] = []

    for relative_path in sorted(source_paths):
        expected = inventory_rows.get(relative_path)
        if expected is None:
            findings.append(Finding("inventory_missing", f"{relative_path} is missing from inventory"))
            continue
        actual = measure_source(source_paths[relative_path])
        for code, actual_value, expected_value in (
            ("inventory_nodes", actual.nodes, expected[2]),
            ("inventory_edges", actual.edges, expected[3]),
        ):
            if actual_value != expected_value:
                findings.append(
                    Finding(
                        code,
                        f"{relative_path}: inventory={expected_value}, measured={actual_value}",
                    )
                )

    for relative_path in sorted(set(inventory_rows) - set(source_paths)):
        findings.append(Finding("inventory_extra", f"{relative_path} is not a Mermaid source"))
    return tuple(findings)


def _read_inventory_rows(inventory_path: Path) -> dict[str, tuple[int, int, int, int]]:
    rows: dict[str, tuple[int, int, int, int]] = {}
    with inventory_path.open("r", encoding="utf-8", newline="") as inventory_file:
        for line in inventory_file:
            columns = [column.strip() for column in line.rstrip("\r\n").split("|")]
            if len(columns) < 8 or not columns[1].startswith("diagrams/") or not columns[1].endswith(".mmd"):
                continue
            try:
                rows[columns[1]] = tuple(int(columns[index]) for index in range(4, 8))  # type: ignore[assignment]
            except ValueError:
                continue
    return rows


def _looks_like_node(line: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith(("%%", "subgraph", "classDef", "class ", "style ", "linkStyle")):
        return False
    return re.match(r"^[A-Za-z_][A-Za-z0-9_-]*\s*(?:\[|\(|\{|<|-/|--)", stripped) is not None