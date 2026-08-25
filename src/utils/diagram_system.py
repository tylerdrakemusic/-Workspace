"""Cross-source checks for the workspace architecture diagram system."""

from __future__ import annotations

from pathlib import Path

from diagram_budgets import Finding


_RELATIONSHIP_CONTRACTS: dict[str, tuple[str, ...]] = {
    "capital-db-schema.mmd": (
        "RISK_THRESHOLDS ||--o{ TRADE_CANDIDATES : qualifies",
        "TRADE_CANDIDATES ||--o{ EXITS : creates_entry_exit",
        "EXITS ||--o{ EXITS : supersedes",
    ),
    "manifest-architecture.mmd": ("AudioOut --> Portal",),
    "workspace-integrations.mmd": (
        "Life -->|llm research| OpenAI",
        "Music -->|CI-deployed cloud host: guitartrainer.fly.dev| FlyIO",
        "Quantum -->|qiskit jobs| IBMQ",
    ),
}

_DERIVED_RELATIONSHIP_CONTRACTS: dict[str, tuple[str, ...]] = {
    "capital-db-derived-trading.mmd": _RELATIONSHIP_CONTRACTS["capital-db-schema.mmd"],
    "manifest-derived-media-pipeline.mmd": _RELATIONSHIP_CONTRACTS["manifest-architecture.mmd"],
    "workspace-derived-services.mmd": _RELATIONSHIP_CONTRACTS["workspace-integrations.mmd"],
    "workspace-derived-backup-and-coordination.mmd": ("BackupContract --> BackupInventory",),
}

_DERIVED_PREFIXES = {
    "capital-db-schema.mmd": "capital-db-derived-",
    "manifest-architecture.mmd": "manifest-derived-",
    "workspace-integrations.mmd": "workspace-derived-",
}


def validate_gallery(
    results: dict[str, dict],
    expected_sources: list[str],
    html: str,
) -> tuple[Finding, ...]:
    """Validate source coverage and required dashboard interaction markup."""
    findings: list[Finding] = []
    actual_sources = set(results)
    for stem in sorted(set(expected_sources) - actual_sources):
        findings.append(Finding("gallery_missing", f"{stem} is missing from the generated gallery"))
    for stem in sorted(actual_sources - set(expected_sources)):
        findings.append(Finding("gallery_extra", f"{stem} is not a canonical gallery source"))
    for stem, info in sorted(results.items()):
        if info.get("status") not in {"rendered", "fallback"}:
            findings.append(Finding("gallery_render", f"{stem} has no rendered or explicit fallback result"))
    for marker in ('class="lightbox"', 'class="zoom-btn"', '<details><summary>source</summary>'):
        if marker not in html:
            findings.append(Finding("gallery_interaction_contract", f"dashboard is missing {marker}"))
    return tuple(findings)


def reconcile_architecture_relationships(
    diagrams_dir: Path,
    workspace_root: Path,
) -> tuple[Finding, ...]:
    """Check canonical cross-view edges and the SigmaCapital DB contract."""
    findings: list[Finding] = []
    sources = {
        path.name: path.read_text(encoding="utf-8")
        for path in diagrams_dir.glob("*.mmd")
    }

    for filename, relationships in _RELATIONSHIP_CONTRACTS.items():
        parent = sources.get(filename, "")
        derived_prefix = _DERIVED_PREFIXES[filename]
        related_views = "\n".join(
            source
            for name, source in sources.items()
            if name.startswith(derived_prefix)
        )
        relationship_sources = parent + "\n" + related_views
        for relationship in relationships:
            if relationship not in relationship_sources:
                findings.append(
                    Finding(
                        "relationship_missing",
                        f"{filename}: missing canonical relationship {relationship}",
                    )
                )

    for filename, relationships in _DERIVED_RELATIONSHIP_CONTRACTS.items():
        source = sources.get(filename, "")
        for relationship in relationships:
            if relationship not in source:
                findings.append(
                    Finding(
                        "relationship_missing",
                        f"{filename}: missing derived-view relationship {relationship}",
                    )
                )

    capital_db = workspace_root / "ΣCapital" / "data" / "sigmacapital.db"
    capital_diagram = sources.get("capital-db-schema.mmd", "")
    if capital_db.exists() and "SIGMACAPITAL_DB" not in capital_diagram:
        findings.append(
            Finding(
                "sigma_db_mismatch",
                "capital-db-schema.mmd does not identify canonical ΣCapital database sigmacapital.db",
            )
        )
    return tuple(findings)