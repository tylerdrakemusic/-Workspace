## ⊕ Architecture Impact Report — FR-20260809-cost-merge-gate

**Decision:** PASS_WITH_UPDATES

### Scope reviewed

Compared the feature worktree against `origin/main`, including the committed
handoff plus the current worktree changes. The diff contains:

- `.github/instructions/feature-request-flow.instructions.md`
- `.github/agents/⊕workspace-ci.agent.md`
- `src/utils/fr_cli.py`
- `src/utils/fr_cost_lifecycle.py`
- `tests/test_copilot_cost_tracking.py`
- `tests/test_fr_cli_gate.py`

### Impact assessment

| File in diff | Impact type | Affected diagram |
|---|---|---|
| `.github/instructions/feature-request-flow.instructions.md` | Shared FR protocol change: `MERGED` now requires an explicit `estimated` or `unavailable` cost outcome | `diagrams/workspace-fr-flow.mmd` |
| `.github/agents/⊕workspace-ci.agent.md` | CI merge-agent guidance for the new cost gate; no role or agent identity change | `diagrams/workspace-fr-flow.mmd` |
| `src/utils/fr_cli.py` | Enforcement at the existing FR state-transition boundary; reads existing lifecycle fields and does not add schema objects | None |
| `src/utils/fr_cost_lifecycle.py` | Populates the existing reconciliation-status field during finalization; no new dependency, integration, or schema migration | None |
| `tests/test_copilot_cost_tracking.py`, `tests/test_fr_cli_gate.py` | Regression coverage only | None |

### Diagram checks

- `diagrams/workspace-fr-flow.mmd` now shows `TYLER_APPROVED` entering
  `COST_GATE`, explicit `estimated` and `unavailable + reason/source recorded`
  paths to `MERGED`, and `NULL or pending` returning through `MERGE_BLOCKED`.
- `diagrams/workspace-agent-topology.mmd` is complete: every agent file has a
  corresponding node label, and this FR adds no agent, description change, or
  routing edge.
- No dependency, database schema, external integration, or cross-project
  boundary is introduced by the diff.
- Mermaid rendering completed for all 23 diagrams. The two fallback reports are
  pre-existing unrelated issues in `capital-architecture` (HTTP 414) and
  `music-icecast-primary-architecture` (HTTP 400); the updated FR-flow parsed.

### Review result

The diagram update accurately documents the cost gate. No architectural impact
remains stale or missing.