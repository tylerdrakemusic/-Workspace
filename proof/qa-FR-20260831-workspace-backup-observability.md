# QA Report - FR-20260831-workspace-backup-observability

**Decision:** FUNCTIONAL_QA PASS
**Validated:** 2026-08-31
**Worktree:** `feature-FR-20260831-workspace-backup-observability`
**Published head:** `84ce8e60c15fbed54b942cfa4a532a47d42bb922`

The published feature ref and the current worktree resolve to the same commit.
The exact focused suite used by the published review was rerun in the current
worktree with the result `23 passed in 1.64s`.

| # | Acceptance criterion | Test / check | Result | Evidence |
|---|---|---|---|---|
| 1 | Failure observations are structured and redact source paths, database names, and key values. | `test_failure_details_are_redacted_and_structured`; `test_scheduled_failure_exposes_redacted_observation` | PASS | 23-test focused suite; both assertions passed. |
| 2 | Retention keeps 30 generations and preserves the newest valid recovery point. | `test_retention_preserves_latest_valid_recovery_point`; runbook contract check | PASS | Temporary-generation test passed; runbook declares 30 generations and newest-valid preservation. |
| 3 | Restore-drill evidence is bounded to the latest 12 records and uses isolated validation. | `test_restore_drill_records_latest_twelve_evidence_entries`; runbook contract check | PASS | Temporary JSONL test passed with exactly 12 newest records; runbook requires isolated restore validation. |
| 4 | Recovery-objective reporting declares RPO 24 hours and RTO 4 hours. | `test_recovery_objectives_report_declared_rpo_and_rto`; runbook contract check | PASS | Report returned `{'rpo_hours': 24, 'rto_hours': 4, 'status': 'defined'}`. |
| 5 | Only approved backup inventory entries are operationally in scope, with operator boundaries documented. | `test_workspace_runbooks_document_the_operational_contract`; operational and scope test suite | PASS | Runbook documents approved `backup_allowed=true` entries and exclusions; 99/99 operational, scope, inventory, and diagram checks passed. |
| 6 | Architecture evidence matches the updated diagrams and implementation responsibilities. | Diagram inventory and budget tests; current source/inventory inspection | PASS | 99/99 checks passed; affected diagrams are current, rendered HTTP 200, and inventory metrics are recorded in the architecture proof. |

## Focused test execution

Command:

```text
C:\G\python.exe -m pytest -q tests/test_backup_observability.py tests/test_database_backup.py --disable-warnings
```

Result: **23 passed in 1.64s**.

The wider related check was also run:

```text
C:\G\python.exe -m pytest -q tests/test_database_backup_operational.py tests/test_database_backup_scope.py tests/test_diagram_inventory.py tests/test_diagram_budgets.py --disable-warnings
```

Result: **99 passed in 0.76s**.

The required published-branch CI check for head `84ce8e6...` is green:
GitHub Actions `test`, conclusion `success`.

## Negative paths

The focused and related checks passed the fail-closed boundaries for unverified
destinations, tampered metadata, traversal paths, existing restore targets,
canonical restore prohibition, unredacted audit locators, denied inventory
classifications, and invalid manifest fields. Scheduled failure output was
verified to exclude the temporary source path and sensitive locator values.

## Database safety

QA made no live database mutation. Tests used temporary directories and
runtime-generated or isolated test data. The feature diff contains no `*.db`
files and no database write was executed during this QA run. The runbook also
requires restore validation in an isolated directory and excludes live project
roots and runtime databases.

## Unrelated baseline failures

The two independently confirmed baseline failures remain unrelated to this FR:

1. Humanizer validation reported a declared SHA mismatch, `14fc8a...` versus
   checked-out `5fd504...`.
2. The AI-Manifest worktree contract artifact is missing.

Neither failure occurs in the focused backup tests or explains the evidence
blockers repaired by this report.

## Verdict

All six acceptance criteria have passing executable or contract evidence.
FUNCTIONAL_QA PASS. The FR is ready to advance to `ARCHITECTURE_REVIEW`.