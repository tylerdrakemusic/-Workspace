# Automated Review — FR-20260824-workspace-todo-operational-consolidation

**Decision:** REQUEST_CHANGES
**Exact published head:** `b8966754a97efec743b3a37b9cc3fb39c689b4ba`
**Base:** `origin/main` at `d4238a9f87c9fc78524be9a2c08f6716ef25a56c`

## Findings

### Critical: Telemetry values are not privacy-bounded

`src/utils/todo_operational_runtime.py:37-43` validates telemetry kind and
field names, but accepts arbitrary `todo_id` and values for the allowlisted
`reason` field. The runtime therefore records identifiers or resource names
that can contain medical, genomic, financial, credential, or other sensitive
data. A direct check produced an event containing
`todo_id='medical-record-123'` and `reason='account-number-987654'`.

The runbook and architecture proof claim that telemetry excludes health data
and financial PII, but the implementation does not enforce that claim. Redact
or replace externally supplied identifiers and reason values with bounded,
non-sensitive enums or validated opaque IDs at the telemetry boundary, and add
tests proving sensitive values cannot be emitted or queried.

### Required: The declared policy file is not the runtime source of truth

`src/config/todo_execution_policy.json` declares the operational limits, but
`OperationalConfig` in `src/utils/todo_operational_runtime.py:67-81` hard-codes
the same values and `OperationalRuntime.__init__` uses those defaults directly.
There is no runtime load or validation of the JSON policy. The implementation
can therefore silently diverge from the documented/configured limits whenever
the policy file changes; the current default-value test only proves the
duplication, not configuration wiring.

Load and validate the checked-in policy through one canonical configuration
path, or remove the file and document code defaults as the sole source of
truth. Add a test that changes or supplies policy data and verifies dispatch
uses the configured limits.

## Evidence and checks

- Approved acceptance criteria were read from the canonical FR ledger. The
  ledger is currently `REVIEW_REQUESTED`; no PR is recorded.
- Focused operational/import slice: `10 passed`.
- Full applicable suite at this head: `889 passed, 13 skipped, 11 deselected`.
- `git diff --check origin/main...HEAD`: passed.
- Exact `HEAD` equals the requested published commit and the remote feature
  branch. The latest architecture repair commit contains only the three
  expected diagram files.
- Architecture proof is present and treats the Mermaid HTTP `414` detail
  rendering path as a residual environment limitation after source validation;
  no finding is raised for that fallback.
- No GitHub PR or check-run status is available to verify because the ledger
  records PR creation as blocked and `PRs: None`.
- The worktree has one untracked architecture review artifact from the prior
  architecture gate; no tracked code changes were made by this review.

## Gate outcome

The runtime behavior is otherwise focused and the existing lifecycle, child
coordination, parent-join, direct-script compatibility, documentation, and
diagram evidence are consistent with the tested flow. The two findings above
block `AUTO_REVIEWED` until repaired and revalidated at a new exact published
head.