# Automated Review - FR-20260808-copilot-cost-tracking

**Decision:** REQUEST_CHANGES

## Gate Results

| Gate | Result | Notes |
| --- | --- | --- |
| Scope conformance | PASS | Changes stay within the FR ledger CLI, migration, and cost helpers. |

## Findings

1. **High: empty and malformed telemetry bypass the confirmation gate.**
   `src/utils/fr_cost_lifecycle.py` returns `("github", await github_usage())` for any successful coroutine result, including `{}` and non-numeric token values. A direct check reproduced both cases. This violates the requirement to label missing telemetry and require explicit operator confirmation when authoritative telemetry is unavailable or unusable. Validate the returned object and token fields before accepting the GitHub source; otherwise return an explicit unavailable/unconfirmed result and do not finalize a cost.

2. **High: merge finalization does not enforce async reconciliation confirmation.**
   `src/utils/fr_cli.py` finalizes cost during `MERGED` whenever `--cost-model` and `--cost-usage-json` are present. It does not call `reconcile_cost`, require a confirmed GitHub result, or require an explicit operator confirmation for fallback data. The caller can supply arbitrary usage and `--cost-source` and still persist an estimated cost during the merge transition. Wire the merge path to the reconciliation result and block or mark the cost unconfirmed unless the required confirmation state is present.

3. **Medium: published pricing is not represented with provenance.**
   `src/utils/copilot_cost.py` embeds one model's rates in `_RATES_PER_MILLION` without a published source URL, retrieval/version identifier, effective date, currency, or a persisted rate snapshot. This makes the resulting dollar estimate difficult to audit and unsafe to silently carry across pricing changes. Store or expose the rate provenance with the estimate, and keep unknown/unpublished models explicitly unavailable.

## Validation Evidence


## Required Changes

# Automated Review - FR-20260808-copilot-cost-tracking

**Decision:** APPROVE

## Gate Results

| Gate | Result | Notes |
| --- | --- | --- |
| Scope conformance | PASS | Changes remain within the FR ledger CLI, migration, cost helpers, tests, and review artifacts. |
| Security and privacy | PASS | Malformed or empty GitHub telemetry is rejected; unconfirmed reconciliation does not finalize cost. |
| Alignment and maintainability | PASS | Published pricing includes source URL, version, effective date, currency, and persisted rate snapshot. |
| Migration safety | PASS | The additive nullable migration is idempotent and preserves legacy rows. |
| Tests | PASS | Focused cost suite and adjacent FR CLI/server/migration suites: 38 passed. |
| Functional QA | PASS | Ledger records QA PASS for all six acceptance criteria after repair. |
| Architecture | PASS | Re-review records additive FR-ledger impact with no dependency, integration, or diagram change. |
| Proof artifacts | PASS | Reviewer proof run `19e9c217-0a89-4e6f-86a0-661763b6be59`: 3 recorded, 3 verified, 100% coverage. |
| Worktree and tmp hygiene | PASS | No committed `.worktrees/` paths or forbidden ephemeral `tmp/` artifacts found. |
| UI validation | N/A | No HTML or UI surface changed. |

## Acceptance Criteria Check

1. Cost calculation, cache handling, and unknown models: PASS, covered by the focused suite.
2. Idempotent nullable schema migration: PASS, covered by focused migration tests.
3. Baseline and final cost persistence: PASS, covered by lifecycle and CLI tests.
4. Auditable pricing provenance: PASS, source/version/effective date/currency/rate snapshot are persisted.
5. Async telemetry reconciliation and explicit confirmation: PASS, malformed telemetry and merge confirmation cases are covered.
6. Chat-facing reporting and regression safety: PASS, 38 focused and adjacent tests passed.

## Findings

No remaining blocking findings. The prior telemetry validation, merge confirmation, pricing provenance, negative-test, and proof-artifact findings are repaired and verified.

## Approval State

Automated review is approved. Tyler approval is not present in the ledger, so the FR must remain at the branch-checked-out / awaiting-approval gateway and must not advance to `TYLER_APPROVED` or merge.