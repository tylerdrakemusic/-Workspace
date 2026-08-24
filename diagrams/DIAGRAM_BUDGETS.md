# Diagram Budgets

The validator in `src/utils/diagram_budgets.py` applies these budgets to each
Mermaid source. Measurements follow `DIAGRAM_INVENTORY.md`: source text is
decoded as UTF-8, line endings are normalized to the inventory's canonical
CRLF representation, characters are Python string length, and bytes are exact
UTF-8 length of that canonical representation. This keeps measurements stable
across Windows and Linux checkouts.

## Machine-Checked Limits

| Category | UTF-8 characters | UTF-8 bytes | Nodes | Edges | Renderer URL risk | Fallback risk |
|---|---:|---:|---:|---:|---|---|
| overview | 8,000 | 12,000 | 40 | 60 | low-medium | low-medium |
| detail | 8,000 | 12,000 | 50 | 80 | low-medium | low-medium |
| database-schema | 8,000 | 12,000 | 40 | 50 | low-medium | low-medium |
| technology-stack | 8,000 | 12,000 | 30 | 40 | low-medium | low-medium |
| workflow | 8,000 | 12,000 | 35 | 50 | low-medium | low-medium |

Risk values are ordered `low < medium < high`. A `high` renderer URL or
fallback risk is non-compliant. URL risk covers renderer transport limits and
encoding hazards; fallback risk covers unsupported Mermaid directives,
non-UTF-8 labels, and unavailable renderer backends.

## Category Rules

- **overview**: one project or cross-project orientation; keep the main path
  legible and split when the node or edge limit is exceeded.
- **detail**: implementation-level architecture; split by subsystem when a
  node, edge, character, or byte limit is exceeded.
- **database-schema**: entities and relationships only; split by bounded data
  domain when the node or edge limit is exceeded.
- **technology-stack**: technology layers and their dependencies; split by
  project or layer when the node or edge limit is exceeded.
- **workflow**: states, actors, and transitions; split by phase or lifecycle
  when the node or edge limit is exceeded.

Any source over its character, node, or edge split threshold is marked
`split_required`. Byte and risk findings still make a source non-compliant,
even when they do not independently trigger a split recommendation.

## Traceability

Every derived view must set `is_derived_view=true` and name its parent path in
`Traceability.parent`. Every parent that has derived views must list their
non-empty paths in `Traceability.derived_views`. A derived view should retain
the parent scope and explain its narrower category in the owning diagram
inventory entry. Missing lineage is a `traceability` finding.

The validator intentionally does not render Mermaid or fetch renderer URLs.
Renderer availability remains an explicit inventory result (`NOT RUN` when no
backend is installed), so budget validation is deterministic and offline.