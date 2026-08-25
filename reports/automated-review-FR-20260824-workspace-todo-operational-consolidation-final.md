# Heavy Automated Review — FR-20260824-workspace-todo-operational-consolidation

**Decision:** REQUEST_CHANGES
**Exact published head:** `aa18ff3a3022da3b10836be047fca1a1e1828d23`
**Base:** `origin/main`
**PR/status:** unavailable; the ledger records PR creation blocked and no PR is recorded

## Gate Results

| Gate | Result | Notes |
|------|--------|-------|
| Scope conformance | PASS | Cumulative diff is limited to the operational runtime, policy, lifecycle import compatibility, focused tests, runbook, and three related diagrams. |
| Security/privacy | PASS | Telemetry validates opaque operational IDs, rejects sensitive/free-form values before append, allowlists fields/kinds, and never persists telemetry. Focused tests cover sensitive values, secret fields, and query boundaries. |
| Alignment | PASS | Existing lifecycle, scheduler, child coordination, parent join, SQLite, pytest, and direct/package import conventions are preserved. |
| Architecture diagrams | PASS | Latest architecture rerun records `PASS_WITH_UPDATES` at the requested head; affected sources and topology/schema/integration checks are consistent. |
| Worktree path audit | PASS | No `.worktrees/` path is present in the cumulative diff. |
| `tmp/` cleanliness | PASS | No forbidden ephemeral PR artifacts are present in the branch `tmp/` directory. |
| Tests | PASS | Focused runtime/import/direct-mode slice: 19 passed. Full applicable suite: 898 passed, 13 skipped, 11 deselected. |
| Functional QA | PASS | Latest QA proof records PASS at `aa18ff3` and covers all approved acceptance areas, including both prior blockers. |
| Proof-in-the-pudding | PASS | Latest QA and architecture proof artifacts exist and match the requested published head. |
| Demo | PASS | CLI/runtime operational evidence and runbook are present; no browser UI is in scope. |
| UI validation | N/A | No HTML or dashboard output is changed by this FR. |

## Prior Blocker Verification

1. **Telemetry privacy-bounded before storage — PASS.** `_validate_telemetry_id()` requires the opaque operational ID format and rejects sensitive terms. `_validate_telemetry_value()` rejects sensitive strings and restricts `reason` to operational enum values. `emit()` performs validation before appending to the in-memory event list. Tests prove rejected values do not become stored events.
2. **JSON policy canonical runtime configuration — FAIL.** `OperationalConfig.from_policy()` and `from_policy_path()` correctly validate and apply supplied policy data, and tests cover injected/path policies. However, `OperationalRuntime.__init__()` still selects `config or OperationalConfig()` when neither `policy` nor `policy_path` is supplied. The checked-in `src/config/todo_execution_policy.json` is therefore duplicated configuration, not the canonical default runtime source. A change to that JSON would not change `OperationalRuntime(connection, contracts)` behavior. The default-value test only confirms duplicated values match today; it does not prove default runtime loading.

## Acceptance Criteria

The ledger’s approved criteria for DAG scheduling, deterministic waves/capacity/resource conflicts, durable claim and lease lifecycle, child coordination and parent join, bounded telemetry, operational CLI compatibility, documentation, and diagram accuracy are otherwise supported by the final QA and architecture evidence. The canonical-policy criterion remains unsatisfied until the no-argument runtime loads and validates the checked-in JSON (or the JSON is removed and code defaults are explicitly made the sole source of truth).

## Required Change

- [ ] Make `src/config/todo_execution_policy.json` the canonical default runtime configuration, with a stable package/worktree-relative path and validation at runtime construction; retain or add a behavior test that changes the policy data and proves default dispatch/lease/retry behavior follows it. Alternatively remove the JSON policy and revise the acceptance evidence/runbook/diagrams to declare code defaults as the sole source of truth.

## Residual, Non-Blocking Notes

- Mermaid detail-diagram rendering still uses the known HTTP 414 fallback because `mmdc` is unavailable and the encoded source exceeds the Mermaid HTTP URI limit. Source validation remains valid, so this is not a gate failure.
- The shared absolute-path direct `perf_cli.py start` invocation remains environment-sensitive due to package-relative imports; worktree-local direct and package-compatible paths pass and the direct-mode tests pass.
- The worktree contains untracked review reports preserved from prior gates plus this report. They are not in the published diff; no production or test code was modified by this review.
- No GitHub CI/check status could be inspected because no PR is available. This does not waive the local test gates.

_Tyler: automated review only. Tyler approval, branch checkout, merge, and post-merge signoff remain separate lifecycle gates._