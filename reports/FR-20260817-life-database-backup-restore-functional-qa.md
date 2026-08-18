# Functional QA Report - FR-20260817-life-database-backup-restore

**Decision:** PASS
**Tier:** Heavy
**Execution mode:** Synthetic fixtures and read-only source/config inspection only
**Worktrees:** `F:\∞Life\.worktrees\feature-FR-20260817-life-database-backup-restore`; `F:\⊕Workspace\.worktrees\feature-FR-20260817-life-database-backup-restore`

## Acceptance Criteria

| # | Re-derived acceptance criterion | Test type | Result | Evidence |
|---|---|---|---|---|
| 1 | Life inventory identifies the canonical encrypted health store by redacted locator metadata. | focused pytest | PASS | Life inventory suite |
| 2 | The Life inventory keeps the canonical health store default-denied until governed approval is supplied. | focused pytest | PASS | Life inventory suite |
| 3 | Inventory entries are configuration-driven and preserve required classification, encryption, and key-variable metadata without key material. | focused pytest | PASS | Life inventory suite |
| 4 | Life database locators and basenames are project-relative, safe, and database-file constrained. | focused pytest | PASS | Life inventory suite |
| 5 | Workspace approval must identify exactly one approved Life candidate. | focused pytest | PASS | Life inventory suite |
| 6 | A mismatched approved Life locator is rejected even when id and discovery metadata look plausible. | regression pytest | PASS | `test_workspace_approval_rejects_mismatched_approved_path` |
| 7 | Approved Life id, locator, and discovered basename must match the Life inventory before projection. | focused pytest | PASS | Life inventory suite |
| 8 | A valid approval projects only the approved Life entry as backup-allowed and canonical. | focused pytest | PASS | Life inventory suite |
| 9 | The generic scope manifest contains the approved Life entry plus explicit classifications, exclusions, and redacted content boundary. | focused pytest | PASS | Workspace scope suite |
| 10 | Database discovery excludes transient, generated, backup, and worktree locations. | focused pytest | PASS | Workspace scope suite |
| 11 | Discovery rejects ambiguous duplicate project/basename candidates. | focused pytest | PASS | Workspace scope suite |
| 12 | Scope validation rejects malformed paths, unknown fields, incomplete taxonomy, duplicate ids/paths, and unregistered databases. | focused pytest | PASS | Workspace scope suite |
| 13 | Backup fails closed unless the destination identity matches the approved identity. | synthetic pytest | PASS | Workspace backup and operational suites |
| 14 | Backup copies every allowed synthetic entry byte-for-byte and records hashed manifest metadata. | synthetic pytest | PASS | Workspace backup and operational suites |
| 15 | Backup retention prunes old synthetic generations to the configured limit. | synthetic pytest | PASS | Workspace backup suite |
| 16 | Restore requires explicit operator approval and an isolated target. | synthetic pytest | PASS | Workspace backup suite |
| 17 | Restore trusts the observed destination identity and rejects tampered manifest authentication. | synthetic pytest | PASS | Workspace backup suite |
| 18 | Canonical restore and overwrite of existing targets remain separately authorized. | synthetic pytest | PASS | Workspace backup suite |
| 19 | Restore audit and periodic validation expose only redacted locators and use schema metadata validation without emitting database contents. | synthetic pytest | PASS | Workspace backup suite |
| 20 | Scheduler specification is daily at 02:00, uses explicit canonical project roots, excludes Capital, and carries environment names rather than secret values; registration itself is not executed. | pure-spec pytest | PASS | Workspace operational suite |

## Executed Tests

- `∞Life/tests/test_database_backup_inventory.py`: **17 passed in 0.16s**.
- `⊕Workspace/tests/test_database_backup.py tests/test_database_backup_operational.py tests/test_database_backup_scope.py`: **97 passed in 1.59s**.
- The Life result includes the new mismatched approved locator regression.
- No real backup, restore, installed task, scheduler registration, production database query, or scheduler side effect was run.

## Redaction and Safety Audit

- Evidence contains policy metadata and synthetic test outcomes only.
- No health or genomic contents, database bytes, SQLCipher key values, manifest authentication values, sensitive local path contents, or other secret values are included.
- The report uses only the two requested isolated worktrees as implementation/test surfaces and does not reference Capital.
- No source/runtime file was modified by QA; this report is the refreshed proof artifact.

## Playwright

- Triggered: no. The isolated diffs contain no HTML files and no `output/` changes.
- Result: N/A.

## Verdict

All 20 acceptance criteria pass with synthetic/read-only evidence. Advance the FR from `FUNCTIONAL_QA`/`CHANGES_REQUESTED` to `ARCHITECTURE_REVIEW` for the next governed stage.