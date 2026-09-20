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
2. Run the scheduled backup using the approved inventory manifest. Declared
   SQLCipher databases use the installed driver's online backup API with the
   configured key applied to both connections, preserving encryption at the
   destination. Missing SQLCipher support or key metadata fails closed; it
   never falls back to a raw or plaintext copy. Entries without SQLCipher
   metadata retain the bounded source-stability check and retry up to three
   total attempts.
3. Review the redacted status and `backup-audit.jsonl`; each failed attempt is
   durable evidence identified only by the approved logical database ID.
   Records contain no source paths, filenames, database contents, key names, or
   key values.
4. Validate the manifest authentication, checksums, SQLCipher opening, and
   schema metadata in an isolated restore directory. Never restore into a live
   project root or runtime database.
5. Record a monthly restore drill. Keep the latest 12 evidence records.

Automatic restore, live failover, uploads, provider selection, and key custody
changes are not part of this workflow.