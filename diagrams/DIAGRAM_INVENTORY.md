# Mermaid Diagram Inventory

This inventory is refreshed under the umbrella attribution of
`FR-20260830-workspace-xdist-diagram-reconciliation` for the confirmed
Workspace-owned documentation scope. It describes the current six-project
diagram set and the four reconciled technology-stack sources:
`diagrams/life-tech-stack.mmd`, `diagrams/music-tech-stack.mmd`,
`diagrams/quantum-tech-stack.mmd`, and `diagrams/manifest-tech-stack.mmd`.
Their xdist claims reflect merged project behavior: Life parallel CI with a
Playwright exclusion and no invented worker count; Music bounded two-worker
paired parallel/serial lanes with exclusions; Quantum bounded two workers with
`ci_long_running` excluded; and AI-Manifest controlled parallel workers with
Playwright/live exclusions plus a serial debugging fallback. This is the
Committed baseline inventory for current branch evidence. The prior baseline's
seven approved decision-metadata edits remain historical context; unrelated
fallback and NOT RUN rows remain preserved as documented evidence.

## Measurement Contract

- Current baseline commit: `a4bf3b6` (existing Quantum cache lifecycle PR baseline)
- Evidence head: current `feature/FR-20260830-quantum-cache-integrity-lifecycle-diagram` worktree
- Baseline commit: `4ee4f6e` (FR worktree diagram baseline)
- Source set: `diagrams/*.mmd`, sorted by relative POSIX path. The expected
  count is 34.
- Bytes: exact UTF-8 byte length of the source file.
- Characters: Python `str` length after UTF-8 decoding, including newlines.
- Nodes: count of node declaration lines matching the diagram's identifier
  followed by a Mermaid shape opener (`[`, `(`, `{`, `<`, `-/`, or `--`).
  Subgraph, class, style, and link-style declarations are excluded.
- Edges: count of lines containing a Mermaid edge operator (`-->`, `==>`,
  `-.->`, `---`, `===`, or ER relationship operators). A line with multiple
  operators is counted once.
- Renderer check: 32 of 34 sources were rendered through mermaid.ink and
  returned HTTP 200. The two unrelated fallback rows remain documented with
  their HTTP 414 and HTTP 400 results.

## Source Inventory

| Relative path | Purpose | Project scope | Bytes | Characters | Nodes | Edges | Renderer/backend result | Failure details | Risk evidence |
|---|---|---|---:|---:|---:|---:|---|---|---|
| diagrams/capital-architecture.mmd | ΣCapital system architecture overview | ΣCapital | 2957 | 2957 | 21 | 27 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | Unicode labels; init directive; derived views listed |
| diagrams/capital-db-schema.mmd | ΣCapital database entity relationships overview | ΣCapital | 2388 | 2388 | 3 | 0 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | Unicode labels; init directive; derived views listed |
| diagrams/capital-tech-stack.mmd | ΣCapital technology stack | ΣCapital | 3271 | 3257 | 22 | 25 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | init directive |
| diagrams/life-architecture.mmd | ∞Life system architecture | ∞Life | 5962 | 5935 | 50 | 41 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | Unicode labels; init directive |
| diagrams/life-db-schema.mmd | ∞Life database entity relationships | ∞Life | 5266 | 5266 | 30 | 1 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | init directive |
| diagrams/life-tech-stack.mmd | ∞Life technology stack | ∞Life | 1638 | 1633 | 8 | 11 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | Unicode labels; init directive; FR-20260830 xdist reconciliation |
| diagrams/manifest-architecture.mmd | 👁AI-Manifest system architecture overview | 👁AI-Manifest | 2269 | 2262 | 12 | 15 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | Unicode labels; init directive; derived views listed |
| diagrams/manifest-db-schema.mmd | 👁AI-Manifest database entity relationships | 👁AI-Manifest | 4270 | 4252 | 10 | 0 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | init directive; Unicode labels |
| diagrams/manifest-tech-stack.mmd | 👁AI-Manifest technology stack | 👁AI-Manifest | 3604 | 3591 | 26 | 30 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | Unicode labels; init directive; FR-20260830 xdist reconciliation |
| diagrams/music-architecture.mmd | ❤Music system architecture | ❤Music | 6604 | 6574 | 88 | 47 | Fallback: mermaid.ink HTTP 414 | URI Too Long | Unicode labels; init directive |
| diagrams/music-db-schema.mmd | ❤Music database entity relationships | ❤Music | 5956 | 5956 | 25 | 0 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | init directive |
| diagrams/music-icecast-primary-architecture.mmd | ❤Music Icecast primary streaming architecture | ❤Music | 1072 | 1070 | 20 | 9 | Fallback: mermaid.ink HTTP 400 | Bad Request | Unicode labels |
| diagrams/music-tech-stack.mmd | ❤Music technology stack | ❤Music | 3280 | 3262 | 23 | 23 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | Unicode labels; init directive; FR-20260830 xdist reconciliation |
| diagrams/quantum-architecture.mmd | ⟨ψ⟩Quantum system architecture overview | ⟨ψ⟩Quantum | 2557 | 2555 | 30 | 16 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | Unicode labels; init directive; derived view: diagrams/quantum-derived-cache-integrity.mmd; split_required=false |
| diagrams/quantum-derived-cache-integrity.mmd | ⟨ψ⟩Quantum cache integrity lifecycle derived detail | ⟨ψ⟩Quantum | 2743 | 2743 | 28 | 14 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | Unicode labels; init directive; parent: diagrams/quantum-architecture.mmd; split_required=false |
| diagrams/quantum-db-schema.mmd | ⟨ψ⟩Quantum database entity relationships | ⟨ψ⟩Quantum | 3132 | 3132 | 9 | 7 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | init directive |
| diagrams/quantum-tech-stack.mmd | ⟨ψ⟩Quantum technology stack | ⟨ψ⟩Quantum | 1729 | 1723 | 9 | 11 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | Unicode labels; init directive; FR-20260830 xdist reconciliation |
| diagrams/workspace-agent-topology.mmd | ⊕Workspace agent topology and delegation flow | ⊕Workspace | 5910 | 5766 | 70 | 32 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | Unicode labels; init directive |
| diagrams/workspace-architecture-detail.mmd | ⊕Workspace decision-metadata ownership and persistence detail | ⊕Workspace | 2935 | 2930 | 23 | 15 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | Unicode labels; init directive; derived companion listed; measured under detail budget |
| diagrams/workspace-architecture.mmd | ⊕Workspace high-level architecture | ⊕Workspace | 3431 | 3409 | 29 | 19 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | Unicode labels; init directive |
| diagrams/workspace-db-schema.mmd | ⊕Workspace database entity relationships | ⊕Workspace | 4006 | 4006 | 13 | 0 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | init directive |
| diagrams/workspace-fr-flow.mmd | ⊕Workspace feature-request lifecycle | ⊕Workspace | 4878 | 4865 | 51 | 55 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | Unicode labels; init directive |
| diagrams/workspace-integrations.mmd | ⊕Workspace external integration topology overview | ⊕Workspace | 3187 | 3162 | 27 | 27 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | Unicode labels; init directive; derived views listed |
| diagrams/capital-derived-market-data.mmd | ΣCapital market-data architecture derived view | ΣCapital | 1324 | 1324 | 8 | 10 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | Unicode labels; init directive; parent traceability |
| diagrams/capital-derived-position-realization.mmd | ΣCapital position-realization architecture derived view | ΣCapital | 1299 | 1299 | 9 | 12 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | Unicode labels; init directive; parent traceability |
| diagrams/capital-derived-trading-controls.mmd | ΣCapital trading-controls architecture derived view | ΣCapital | 1976 | 1976 | 18 | 21 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | Unicode labels; init directive; parent traceability |
| diagrams/capital-db-derived-position-and-validation.mmd | ΣCapital position and validation DB derived view | ΣCapital | 1258 | 1258 | 6 | 0 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | Unicode labels; init directive; parent traceability |
| diagrams/capital-db-derived-trading.mmd | ΣCapital trading DB derived view | ΣCapital | 1880 | 1880 | 6 | 0 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | Unicode labels; init directive; parent traceability |
| diagrams/manifest-derived-media-pipeline.mmd | 👁AI-Manifest media pipeline derived view | 👁AI-Manifest | 1937 | 1935 | 25 | 29 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | Unicode labels; init directive; parent traceability |
| diagrams/manifest-derived-todo-and-backup.mmd | 👁AI-Manifest TODO and backup derived view | 👁AI-Manifest | 2158 | 2153 | 13 | 16 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | Unicode labels; init directive; parent traceability |
| diagrams/workspace-derived-backup-and-coordination.mmd | ⊕Workspace backup and coordination derived view | ⊕Workspace | 1466 | 1461 | 13 | 14 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | Unicode labels; init directive; parent traceability |
| diagrams/workspace-derived-decision-metadata-implementation.mmd | ⊕Workspace decision-metadata implementation derived view | ⊕Workspace | 3994 | 3979 | 45 | 28 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | Unicode labels; init directive; parent traceability; under detail budget |
| diagrams/workspace-derived-services.mmd | ⊕Workspace services derived view | ⊕Workspace | 1291 | 1280 | 15 | 15 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | Unicode labels; init directive; parent traceability |
| diagrams/workspace-tech-stack.mmd | ⊕Workspace technology stack | ⊕Workspace | 2730 | 2725 | 22 | 25 | Rendered: mermaid.ink HTTP 200 | HTTP 200 | init directive |

## Baseline Findings

- All current source measurements are within their category character, byte,
  node, and edge budgets, including `workspace-architecture-detail.mmd` at
  2,930 characters and 2,935 UTF-8 bytes.
- Sources containing Unicode labels are fallback-prone when a renderer or
  terminal is not UTF-8; the affected rows identify that evidence.
- Sources containing Mermaid `%%{init: ...}%%` directives are fallback-prone
  for renderers that do not support initialization directives; the affected
  rows identify that evidence.
- The renderer probe used mermaid.ink directly: 32 sources returned HTTP 200;
  `music-architecture.mmd` returned HTTP 414 (URI Too Long), and
  `music-icecast-primary-architecture.mmd` returned HTTP 400 (Bad Request).

## Main-Checkout Overlay Evidence

This is discovery evidence from the separate main checkout, not part of the
committed baseline and not copied into this branch. At discovery time,
`git diff --stat -- diagrams` reported four modified sources, with 188 added
and 4 deleted lines total:

- `diagrams/capital-architecture.mmd` (+68/-1)
- `diagrams/capital-db-schema.mmd` (+98/-0)
- `diagrams/life-architecture.mmd` (+19/-2)
- `diagrams/quantum-architecture.mmd` (+3/-1)

The overlay was intentionally not inspected for content or included in the
metrics above. Re-run the measurement contract after those edits are either
committed or intentionally discarded to produce a new baseline inventory.