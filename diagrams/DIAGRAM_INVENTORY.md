# Mermaid Diagram Inventory

This inventory is the TODO 302 handoff artifact for
`FR-20260822-workspace-architecture-diagram-system`. It describes the
**Committed baseline** in this worktree and does not copy the **Uncommitted local overlay** from the main checkout.

## Measurement Contract

- Baseline commit: `a704f0e` (committed `origin/main` baseline)
- Source set: `diagrams/*.mmd`, sorted by relative POSIX path. The expected
  count is 32.
- Bytes: exact UTF-8 byte length of the source file.
- Characters: Python `str` length after UTF-8 decoding, including newlines.
- Nodes: count of node declaration lines matching the diagram's identifier
  followed by a Mermaid shape opener (`[`, `(`, `{`, `<`, `-/`, or `--`).
  Subgraph, class, style, and link-style declarations are excluded.
- Edges: count of lines containing a Mermaid edge operator (`-->`, `==>`,
  `-.->`, `---`, `===`, or ER relationship operators). A line with multiple
  operators is counted once.
- Renderer check: attempted backend discovery found no `mmdc` executable in
  the worktree environment. No network renderer was invoked. Therefore every
  result below is explicitly `NOT RUN`, rather than an inferred pass or fail.

## Source Inventory

| Relative path | Purpose | Project scope | Bytes | Characters | Nodes | Edges | Renderer/backend result | Failure details | Risk evidence |
|---|---|---|---:|---:|---:|---:|---|---|---|
| diagrams/capital-architecture.mmd | ΣCapital system architecture overview | ΣCapital | 2303 | 2303 | 15 | 20 | NOT RUN: no `mmdc` | Backend unavailable | Unicode labels; init directive; derived views listed |
| diagrams/capital-db-schema.mmd | ΣCapital database entity relationships overview | ΣCapital | 1305 | 1305 | 1 | 0 | Rendered: mermaid.ink HTTP | Backend available | Unicode labels; init directive; derived views listed |
| diagrams/capital-tech-stack.mmd | ΣCapital technology stack | ΣCapital | 2855 | 2842 | 20 | 20 | NOT RUN: no `mmdc` | Backend unavailable | init directive |
| diagrams/life-architecture.mmd | ∞Life system architecture | ∞Life | 5962 | 5935 | 50 | 41 | NOT RUN: no `mmdc` | Backend unavailable | Unicode labels; init directive |
| diagrams/life-db-schema.mmd | ∞Life database entity relationships | ∞Life | 5266 | 5266 | 30 | 1 | NOT RUN: no `mmdc` | Backend unavailable | init directive |
| diagrams/life-tech-stack.mmd | ∞Life technology stack | ∞Life | 1147 | 1145 | 6 | 6 | NOT RUN: no `mmdc` | Backend unavailable | Unicode labels; init directive |
| diagrams/manifest-architecture.mmd | 👁AI-Manifest system architecture overview | 👁AI-Manifest | 1140 | 1140 | 7 | 9 | NOT RUN: no `mmdc` | Backend unavailable | Unicode labels; init directive; derived views listed |
| diagrams/manifest-db-schema.mmd | 👁AI-Manifest database entity relationships | 👁AI-Manifest | 2624 | 2606 | 8 | 0 | NOT RUN: no `mmdc` | Backend unavailable | init directive; Unicode labels |
| diagrams/manifest-tech-stack.mmd | 👁AI-Manifest technology stack | 👁AI-Manifest | 3062 | 3051 | 24 | 25 | NOT RUN: no `mmdc` | Backend unavailable | Unicode labels; init directive |
| diagrams/music-architecture.mmd | ❤Music system architecture | ❤Music | 6604 | 6574 | 88 | 47 | NOT RUN: no `mmdc` | Backend unavailable | Unicode labels; init directive |
| diagrams/music-db-schema.mmd | ❤Music database entity relationships | ❤Music | 5956 | 5956 | 25 | 0 | NOT RUN: no `mmdc` | Backend unavailable | init directive |
| diagrams/music-icecast-primary-architecture.mmd | ❤Music Icecast primary streaming architecture | ❤Music | 1072 | 1070 | 20 | 9 | NOT RUN: no `mmdc` | Backend unavailable | Unicode labels |
| diagrams/music-tech-stack.mmd | ❤Music technology stack | ❤Music | 2758 | 2743 | 21 | 18 | NOT RUN: no `mmdc` | Backend unavailable | Unicode labels; init directive |
| diagrams/quantum-architecture.mmd | ⟨ψ⟩Quantum system architecture | ⟨ψ⟩Quantum | 4056 | 4050 | 50 | 22 | NOT RUN: no `mmdc` | Backend unavailable | Unicode labels; init directive |
| diagrams/quantum-db-schema.mmd | ⟨ψ⟩Quantum database entity relationships | ⟨ψ⟩Quantum | 3132 | 3132 | 9 | 7 | NOT RUN: no `mmdc` | Backend unavailable | init directive |
| diagrams/quantum-tech-stack.mmd | ⟨ψ⟩Quantum technology stack | ⟨ψ⟩Quantum | 1196 | 1194 | 7 | 6 | NOT RUN: no `mmdc` | Backend unavailable | Unicode labels; init directive |
| diagrams/workspace-agent-topology.mmd | ⊕Workspace agent topology and delegation flow | ⊕Workspace | 5910 | 5766 | 70 | 32 | NOT RUN: no `mmdc` | Backend unavailable | Unicode labels; init directive |
| diagrams/workspace-architecture-detail.mmd | ⊕Workspace detailed system architecture | ⊕Workspace | 8185 | 8150 | 108 | 56 | NOT RUN: no `mmdc` | Backend unavailable | Unicode labels; init directive |
| diagrams/workspace-architecture.mmd | ⊕Workspace high-level architecture | ⊕Workspace | 3026 | 3004 | 25 | 16 | NOT RUN: no `mmdc` | Backend unavailable | Unicode labels; init directive |
| diagrams/workspace-db-schema.mmd | ⊕Workspace database entity relationships | ⊕Workspace | 2956 | 2956 | 11 | 0 | NOT RUN: no `mmdc` | Backend unavailable | init directive |
| diagrams/workspace-fr-flow.mmd | ⊕Workspace feature-request lifecycle | ⊕Workspace | 4760 | 4747 | 52 | 56 | NOT RUN: no `mmdc` | Backend unavailable | Unicode labels; init directive |
| diagrams/workspace-integrations.mmd | ⊕Workspace external integration topology overview | ⊕Workspace | 2089 | 2067 | 21 | 20 | NOT RUN: no `mmdc` | Backend unavailable | Unicode labels; init directive; derived views listed |
| diagrams/capital-derived-market-data.mmd | ΣCapital market-data architecture derived view | ΣCapital | 1324 | 1324 | 8 | 10 | NOT RUN: no `mmdc` | Backend unavailable | Unicode labels; init directive; parent traceability |
| diagrams/capital-derived-position-realization.mmd | ΣCapital position-realization architecture derived view | ΣCapital | 1299 | 1299 | 9 | 12 | NOT RUN: no `mmdc` | Backend unavailable | Unicode labels; init directive; parent traceability |
| diagrams/capital-derived-trading-controls.mmd | ΣCapital trading-controls architecture derived view | ΣCapital | 1387 | 1387 | 12 | 14 | NOT RUN: no `mmdc` | Backend unavailable | Unicode labels; init directive; parent traceability |
| diagrams/capital-db-derived-position-and-validation.mmd | ΣCapital position and validation DB derived view | ΣCapital | 1258 | 1258 | 6 | 0 | NOT RUN: no `mmdc` | Backend unavailable | Unicode labels; init directive; parent traceability |
| diagrams/capital-db-derived-trading.mmd | ΣCapital trading DB derived view | ΣCapital | 1076 | 1076 | 4 | 0 | NOT RUN: no `mmdc` | Backend unavailable | Unicode labels; init directive; parent traceability |
| diagrams/manifest-derived-media-pipeline.mmd | 👁AI-Manifest media pipeline derived view | 👁AI-Manifest | 1386 | 1384 | 16 | 20 | NOT RUN: no `mmdc` | Backend unavailable | Unicode labels; init directive; parent traceability |
| diagrams/manifest-derived-todo-and-backup.mmd | 👁AI-Manifest TODO and backup derived view | 👁AI-Manifest | 1231 | 1231 | 10 | 12 | NOT RUN: no `mmdc` | Backend unavailable | Unicode labels; init directive; parent traceability |
| diagrams/workspace-derived-backup-and-coordination.mmd | ⊕Workspace backup and coordination derived view | ⊕Workspace | 1466 | 1461 | 13 | 14 | NOT RUN: no `mmdc` | Backend unavailable | Unicode labels; init directive; parent traceability |
| diagrams/workspace-derived-services.mmd | ⊕Workspace services derived view | ⊕Workspace | 1291 | 1280 | 15 | 15 | NOT RUN: no `mmdc` | Backend unavailable | Unicode labels; init directive; parent traceability |
| diagrams/workspace-tech-stack.mmd | ⊕Workspace technology stack | ⊕Workspace | 1851 | 1851 | 16 | 16 | NOT RUN: no `mmdc` | Backend unavailable | init directive |

## Baseline Findings

- One source exceeds the 8,000-character review threshold:
  `workspace-architecture-detail.mmd`.
- Sources containing Unicode labels are fallback-prone when a renderer or
  terminal is not UTF-8; the affected rows identify that evidence.
- Sources containing Mermaid `%%{init: ...}%%` directives are fallback-prone
  for renderers that do not support initialization directives; the affected
  rows identify that evidence.
- No renderer result is claimed. The only backend evidence available on this
  branch is the failed `mmdc` executable discovery described above.

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