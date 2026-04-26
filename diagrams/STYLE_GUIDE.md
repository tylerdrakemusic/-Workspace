# ⊕ Workspace Diagram Style Guide

> Owned by `⊕workspace-architecture-beautifier`. Non-destructive additions
> (new palette tokens, new shape categories, new edge semantics) may be
> auto-committed when tagged `[auto-commit]` in the commit message.
> Destructive changes (renaming tokens, changing existing hex values, removing
> categories) MUST land via FR/PR.

---

## 1. Per-Sigil Palette

Each project gets a **muted/pastel** primary + accent pair. Use these exact hex
values in `classDef` declarations. Never substitute brighter saturated colors —
the muted palette keeps all five sigils visually distinct without competing.

| Project | Sigil | Node fill | Node stroke | Text |
|---------|-------|-----------|-------------|------|
| ∞Life | `∞` | `#1a2e3a` | `#6ab4d4` | `#d0ecf8` |
| ❤Music | `❤` | `#3a1a24` | `#d47a8f` | `#f8d0dc` |
| ⟨ψ⟩Quantum | `⟨ψ⟩` | `#251a3a` | `#a07adf` | `#e8d0f8` |
| 👁AI-Manifest | `👁` | `#3a2e1a` | `#d4a96a` | `#f8ead0` |
| ⊕Workspace | `⊕` | `#1a3a30` | `#6ad4b4` | `#d0f8ee` |

### Supporting role classes

| Class | Purpose | Fill | Stroke | Text |
|-------|---------|------|--------|------|
| `tyler` | The human (Tyler) node | `#2a1a3a` | `#9e4aff` | `#fff` |
| `ext` | External services (GitHub, Suno, ElevenLabs, IBM Quantum, …) | `#3a2020` | `#ff7a7a` | `#ffd0d0` |
| `db` | Databases / persistence (SQLite, SQLCipher) | `#3a3010` | `#d4c050` | `#f8f0c0` |
| `state` | State-machine states | `#1a1a1a` | `#888` | `#ccc` |

### classDef block (copy-paste canonical form)

```mermaid
classDef life     fill:#1a2e3a,stroke:#6ab4d4,color:#d0ecf8
classDef music    fill:#3a1a24,stroke:#d47a8f,color:#f8d0dc
classDef quantum  fill:#251a3a,stroke:#a07adf,color:#e8d0f8
classDef manifest fill:#3a2e1a,stroke:#d4a96a,color:#f8ead0
classDef ws       fill:#1a3a30,stroke:#6ad4b4,color:#d0f8ee
classDef tyler    fill:#2a1a3a,stroke:#9e4aff,color:#fff
classDef ext      fill:#3a2020,stroke:#ff7a7a,color:#ffd0d0
classDef db       fill:#3a3010,stroke:#d4c050,color:#f8f0c0
classDef state    fill:#1a1a1a,stroke:#888888,color:#cccccc
```

---

## 2. Node Shapes by Concept Category

| Category | Mermaid shape syntax | Use for |
|----------|---------------------|---------|
| Agent | `AgentName([label])` | Stadium / pill — all `.agent.md` file instances |
| File / module | `FileName[label]` | Rectangle — Python files, HTML, JSON, config |
| Database | `DBName[(label)]` | Cylinder — SQLite / SQLCipher DBs |
| Integration | `IntName{{label}}` | Hexagon — third-party API integrations |
| External service | `SvcName([label])` | Cloud / stadium for external SaaS nodes |
| Decision | `DecNode{label}` | Diamond — branch / condition |
| Subprocess / tool | `ToolName[/label/]` | Parallelogram — CLI tools, scripts |

---

## 3. Edge Semantics

| Relationship | Syntax | Meaning |
|--------------|--------|---------|
| Synchronous call / direct dependency | `A --> B` | One calls the other; A blocks on B |
| Asynchronous / fire-and-forget | `A -.-> B` | Async, event-driven, or optional |
| Data flow / writes | `A ==> B` | Data is written / transferred |
| Dependency (import / inherits) | `A -- depends --> B` | A requires B to exist |
| Annotated edge | `A -->|label| B` | Use for non-obvious relationships |

---

## 4. Theme Directive

All diagrams use the **neutral** base theme — no forced dark or light. The
viewer's renderer (VS Code, GitHub, browser) decides. Add this comment at the
top of every `.mmd` file:

```
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#1a2e3a', 'primaryTextColor': '#d0ecf8', 'edgeLabelBackground': '#0f1318', 'lineColor': '#4a7a9a'}}}%%
```

---

## 5. Layout Conventions

| Diagram type | Recommended directive |
|---|---|
| Agent topology / call graph | `graph LR` |
| Project architecture | `graph TB` |
| DB schema | `erDiagram` |
| FR / process state machine | `stateDiagram-v2` |
| Sequence between services | `sequenceDiagram` |
| Technology stack layers | `graph TB` with `subgraph` per layer |

### Subgraph usage
- Group nodes by **project sigil** when a diagram spans multiple projects.
- Name subgraphs with the sigil + project short name: `subgraph Life["∞ Life"]`
- Auto-collapse subgraphs over **7 nodes** (use `direction LR` inside large
  subgraphs to keep them compact).

---

## 6. Filename Convention

```
<project-prefix>-<topic>.mmd
```

| Prefix | Project |
|--------|---------|
| `life` | ∞Life |
| `music` | ❤Music |
| `quantum` | ⟨ψ⟩Quantum |
| `manifest` | 👁AI-Manifest |
| `workspace` | ⊕Workspace / cross-project |

Topics: `architecture`, `db-schema`, `tech-stack`, `agent-topology`,
`integrations`, `fr-flow`, `architecture-detail`.

---

## 7. Per-Diagram Legend

Every diagram **should** include a legend subgraph that maps sigils to colors.
Template (trim to only the sigils actually used in that diagram):

```mermaid
subgraph Legend["Legend"]
    direction LR
    L1([∞ Life]):::life
    L2([❤ Music]):::music
    L3([⟨ψ⟩ Quantum]):::quantum
    L4([👁 AI-Manifest]):::manifest
    L5([⊕ Workspace]):::ws
    L6[(DB)]:::db
    L7{{Ext}}:::ext
end
```

---

## 8. Self-Mutation Rules

| Change type | Allowed action |
|---|---|
| Add new palette token (new `classDef` entry) | Auto-commit (`[auto-commit]` tag) |
| Add new shape category row | Auto-commit |
| Add new edge-semantic row | Auto-commit |
| Update existing hex value | FR/PR required |
| Rename existing token | FR/PR required |
| Remove any entry | FR/PR required |

The `--refresh-knowledge` mode in `tools/diagram_beautifier.py` may propose
updates as a unified diff. Tyler or the overseer reviews and applies selectively.

---

*Last updated: 2026-04-26 by ⊕workspace-architecture-beautifier (FR-20260425-architecture-beautifier-styling)*
