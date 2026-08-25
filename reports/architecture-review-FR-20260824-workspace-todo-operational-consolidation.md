## ⊕ Architecture Impact Report — FR-20260824-workspace-todo-operational-consolidation
**Decision:** PASS_WITH_UPDATES
**Exact published head:** `b8966754a97efec743b3a37b9cc3fb39c689b4ba`

The cumulative implementation introduces a bounded workspace TODO runtime, an
evidence-backed child/parent coordination surface, policy defaults, and an
allowlisted in-memory telemetry query surface. The three required diagram
repairs are present at this exact head and accurately describe those boundaries.

| File in diff | Impact type | Affected diagram |
|---|---|---|
| `src/utils/todo_operational_runtime.py` | Composes deterministic readiness/capacity scheduling, durable lifecycle claims and leases, child integration, parent join evaluation, and in-memory allowlisted telemetry | `diagrams/workspace-architecture.mmd`, `diagrams/workspace-architecture-detail.mmd`, `diagrams/workspace-fr-flow.mmd` |
| `src/config/todo_execution_policy.json` | Declares bounded defaults: 8 per FR, 16 global, 300-second leases, and 2 retries | `diagrams/workspace-architecture-detail.mmd`, `diagrams/workspace-fr-flow.mmd` |
| `src/utils/init_db.py`, `src/utils/perf_cli.py`, `src/utils/proof_cli.py` | Initializes/reaches the durable lifecycle through package and direct-script-compatible paths | `diagrams/workspace-architecture-detail.mmd` |
| `docs/todo-operational-runbook.md` | Describes recovery, telemetry allowlist/query behavior, child integration, parent join, and gate boundaries | `diagrams/workspace-architecture-detail.mmd`, `diagrams/workspace-fr-flow.mmd` |

| Diagram | Status | Verification |
|---|---|---|
| `diagrams/workspace-architecture.mmd` | PASS | Shows the runtime as a workspace execution/coordination surface connected to the existing FR coordination and ledger boundary. |
| `diagrams/workspace-architecture-detail.mmd` | PASS | Shows policy loading, reuse of durable lifecycle tables, explicit in-memory non-persisted telemetry, FR coordination, and parent-join evaluation. |
| `diagrams/workspace-fr-flow.mmd` | PASS | Shows bounded dispatch, durable claim/lease/retry, allowlisted outcomes, validated child integration, current-parent-head join validation, and the existing QA/review/approval/merge/soak ordering. |
| `diagrams/workspace-db-schema.mmd` | PASS | No new schema is introduced by this cumulative repair; telemetry remains non-durable and lifecycle tables are represented by the existing schema diagram. |
| `diagrams/workspace-agent-topology.mmd` | PASS | Every current `.github/agents/*.agent.md` short name has a corresponding topology node. |
| `diagrams/workspace-integrations.mmd` | PASS | No cross-project integration or external service was added. |
| `diagrams/workspace-tech-stack.mmd` | PASS | No dependency or runtime technology was added. |

## Boundary Checks

- Durable state is limited to the lifecycle tables; telemetry events are held in
	`OperationalTelemetry.events`, filtered through the allowlisted `query()`
	surface, and never written to SQLite.
- Child coordination requires traceable validated claimed/running/completed
	work, isolated branch/worktree identity, serialized integration, and conflict
	preservation. Parent join requires completed validated children, required
	artifacts, integration into the parent branch, and a matching parent head.
- The FR flow retains `PARENT_JOIN -> FUNCTIONAL_QA -> ARCHITECTURE_REVIEW ->
	REVIEW_REQUESTED -> AUTO_REVIEWED -> TYLER_APPROVED -> COST_GATE -> MERGED ->
	SOAKING -> SIGNED_OFF`; no approval, QA, review, or merge bypass is depicted.
- No new agent definition, dependency, persistent telemetry table, cross-project
	import, branch/worktree creation by the runtime, or FR-state mutation by the
	runtime was found.

## Validation

- Focused operational/import/direct-mode slice: `10 passed`.
- Mermaid dashboard: `23/23` diagrams rendered; repaired flow and architecture
	sources rendered directly. The detail source used the known HTTP `414`
	fallback because `mmdc` is unavailable and the encoded diagram exceeds the
	Mermaid HTTP URI limit; this is a renderer/environment limitation, not a
	reported syntax error.
- Exact-head status and published-branch equality verified; repair commit
	changes only the three expected diagram sources.

## Residual Risks

- The detail diagram still needs a local `mmdc` or another non-URI-length parser
	for independent syntax confirmation in this environment.
- Policy values are starting defaults and must be tuned only from the bounded
	telemetry query surface; the architecture review does not establish capacity
	performance claims.