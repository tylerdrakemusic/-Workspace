# Architecture Impact Report - FR-20260824-workspace-todo-execution-lifecycle

Decision: ARCHITECTURE_REVIEW:PASS

## Change surface

- `src/utils/todo_execution_lifecycle.py` adds durable lifecycle coordination for TODO claims, leases, heartbeats, retries, cancellation, stale recovery, and audit events.
- `src/utils/init_db.py` invokes `ExecutionLifecycle(conn)` after existing schema migrations, using the existing `workspace.db` connection.
- The lifecycle module creates these durable tables:
  - `todo_execution_lifecycle`
  - `todo_execution_events`
  - `todo_execution_stale_recoveries`
- `docs/todo-execution-contracts.md` documents the lifecycle state machine and hands successful claim consumption to TODO 333 without creating branches, worktrees, child FRs, or workers.

## Diagram assessment

| Diagram | Status | Required delta |
|---|---|---|
| `diagrams/workspace-db-schema.mmd` | PASS | The diagram now includes `TODO_EXECUTION_LIFECYCLE`, `TODO_EXECUTION_EVENTS`, and `TODO_EXECUTION_STALE_RECOVERIES`, their lifecycle relationships, source traceability, and every implementation column. `PK`/`UK` markers match the SQLite primary-key and unique constraints. |
| `diagrams/workspace-architecture.mmd` | No direct delta required | The change remains inside the existing Workspace database boundary and introduces no cross-project integration. |
| `diagrams/workspace-architecture-detail.mmd` | No direct delta required | No new runtime process, worker, branch, or worktree is created by this implementation. |
| `diagrams/workspace-integrations.mmd` | No direct delta required | No cross-project import or external integration was added. |
| `diagrams/workspace-tech-stack.mmd` | No direct delta required | No dependency or runtime technology was added. |
| `diagrams/workspace-agent-topology.mmd` | PASS | Mandatory topology completeness check found no agent file without a corresponding topology entry. |

## Boundary and residual-risk findings

- Claim admission matches the lifecycle state machine: new executions and queued retries may be claimed; claimed/running executions retain duplicate-claim protection; failed and stale executions require an explicit retry transition.
- Retry ownership is explicit: `retry` is the only transition from failed/stale to queued, and it rejects exhausted budgets without changing the failed/stale state.
- Completed and cancelled executions are terminal and cannot be claimed or retried.
- The initializer imports the lifecycle through the sibling package boundary (`from .todo_execution_lifecycle import ExecutionLifecycle`); the regression test removes the direct `utils` path and verifies temporary database initialization through `src.utils`.
- The three diagram entities and all implementation fields match the SQL schema; the two declared lifecycle relationships match the persisted event and stale-recovery rows keyed by `todo_id`/`claim_id`.
- The claim-admission repair changes no schema or diagram content, so `diagrams/workspace-db-schema.mmd` remains accurate for the cumulative implementation.
- No requirements change, cross-project import, agent definition, integration, scope-creep artifact, branch/worktree creation, FR creation, approval bypass, QA bypass, review bypass, or merge bypass was found.
- TODO 333 handoff remains accurate: it may consume a successful claim and FR anchor later, but this change creates no branches, worktrees, child FRs, workers, or background execution and does not bypass lifecycle ownership or FR gates.
- Residual risk: callers must continue to supply valid lease credentials and use the explicit retry/recovery transitions; scheduler/worker orchestration remains outside this TODO 332 scope.

## Verification

- Mandatory topology completeness check: PASS; all workspace agent files have matching topology nodes.
- Focused lifecycle and package-import tests: `12 passed`.
- Full workspace suite: `862 passed, 13 skipped, 11 deselected`.
- FR history confirms TRIAGED, implementation delegation, FUNCTIONAL_QA, QA PASS, prior ARCHITECTURE_REVIEW STALE, architecture repair, and post-repair QA PASS in order. No approval, review, or merge transition was bypassed.
