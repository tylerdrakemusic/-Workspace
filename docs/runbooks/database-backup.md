# Workspace Database Backup Runbook

This runbook covers the approved, provider-neutral local backup workflow. Only
inventory entries with `backup_allowed=true` are copied. Worktrees, legacy,
temporary, generated, unclassified, plaintext key material, and excluded
directories remain outside the scope.

## Objectives

- Recovery point objective: 24 hours.
- Recovery time objective: 4 hours.
- Retain 30 generations and preserve the newest valid recovery point when
  pruning.

## Operator Workflow

1. Confirm the destination identity marker and required environment variables.
2. Run the scheduled backup using the approved inventory manifest.
3. Review the redacted status and `backup-audit.jsonl`; failures contain no
   source paths, database contents, or key values.
4. Validate the manifest authentication, checksums, SQLCipher opening, and
   schema metadata in an isolated restore directory. Never restore into a live
   project root or runtime database.
5. Record a monthly restore drill. Keep the latest 12 evidence records.

Automatic restore, live failover, uploads, provider selection, and key custody
changes are not part of this workflow.