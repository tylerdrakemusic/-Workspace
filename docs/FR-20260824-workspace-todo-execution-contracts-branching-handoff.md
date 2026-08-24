# FR-20260824 Workspace Todo Execution Contracts

## Branching Handoff

- FR: `FR-20260824-workspace-todo-execution-contracts`
- Branch: `feature/FR-20260824-workspace-todo-execution-contracts`
- Worktree: isolated feature worktree for the branch above (local path omitted)
- Repository: `tylerdrakemusic/-Workspace`
- Base: `main`
- Phase: contract implementation and regression repair
- PR state: open with automated review `REQUEST_CHANGES`; follow-up changes are pending validation

This document records the isolated implementation location for the approved
TRIAGED scope and its current implementation state. The branch contains the
domain-neutral TODO contract, execution lease helpers, state-aware retry
eligibility, and focused regression tests. Retry eligibility now rejects
active `CLAIMED` and `RUNNING` leases, and accepts only failed or stale prior
attempts while retry budget remains.

The implementation remains deliberately pure: it does not add execution-state
persistence, scheduling, or worker coordination. The focused contract suite
covers identity/dependency validation, lease lifecycle behavior, active retry
rejection, failed/stale retry eligibility, and retry-limit enforcement.