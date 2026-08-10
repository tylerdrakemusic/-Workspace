## ⊕ Architecture Impact Report — FR-20260810-architecture-diagram-html-artifacts
**Decision:** PASS_WITH_UPDATES

| File in diff | Impact type | Affected diagram |
|---|---|---|
| `tools/diagrams_dashboard.py` | Stable HTML artifact ownership and dashboard consumption | All canonical `diagrams/*.mmd` sources; no Mermaid source change required |
| `tools/diagram_beautifier.py` | HTML publication command and migration path | All canonical `diagrams/*.mmd` sources; no Mermaid source change required |
| `.github/agents/⊕workspace-architecture-beautifier.agent.md` | Beautifier contract now requires HTML, provenance, proof, and idempotent migration | `workspace-agent-topology.mmd` agent contract node already present |
| `.github/instructions/feature-request-flow.instructions.md` | FR-flow publication protocol | `workspace-fr-flow.mmd` already represents the architecture-review handoff |
| `dashboard.json` | Standalone top-level dashboard registration | No architecture diagram node change required |

### Verification

- `23` canonical Mermaid sources have `23` matching `reports/diagrams/<stem>.html` artifacts.
- Each HTML artifact contains escaped source and `diagrams/<stem>.mmd` provenance metadata.
- `--no-render` consumes existing HTML artifacts; SVG output remains a compatibility preview/fallback.
- Workspace topology contains labels for all `39` `.github/agents/*.agent.md` files.
- Focused tests: `25 passed` (`tests/test_diagrams_dashboard.py`, `tests/test_architecture_agents.py`).
- Static checks: `py_compile` passed for both touched tools; `git diff --check` passed.
- Dashboard registration is a standalone `static_html` top-level dashboard and does not add a feature page to the portal left navigation.

### Residual note

`diagrams/music-icecast-primary-architecture.mmd` predates this FR and lacks the theme directive, but it has a matching HTML artifact and is not stale or missing as a result of this change.