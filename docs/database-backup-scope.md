# Workspace Database Backup Scope

This policy prepares the workspace for local disaster recovery. It is the
inventory and approval boundary for the provider-neutral backup engine; it does
not authorize cloud delivery or manage database encryption keys.

## Source Of Truth

The versioned machine-readable manifest at
`src/config/database_backup_scope.json` is authoritative. The Markdown report
is a deterministic human-readable projection of that manifest and must not be
edited as the policy source.

The manifest root contains these fields:

- `schema_version` — manifest format version.
- `fr` — feature-request identifier that owns the policy.
- `policy_status` — review state for the manifest.
- `purpose` — the disaster-recovery preparation purpose.
- `content_boundary` — the path-and-policy-only boundary.
- `classifications` — the complete classification taxonomy.
- `databases` — registered database entries.
- `exclusions` — excluded path patterns and their reasons.
- `not_implemented` — explicitly out-of-scope capabilities.
- `separate_todos` — follow-up work tracked outside this policy.

Each `databases` entry contains `id`, `path`, `classification`,
`backup_allowed`, and `reason`. The versioned `path` is a redacted,
project-scoped POSIX locator such as `life/health-store`, not a local
filesystem path. Sensitive entries may also contain a `discovery` object with
the safe project key and database basename. Live discovery uses that key to
classify local candidates without storing their directory paths in public
artifacts. Absolute paths, drive-relative paths, colons, backslashes, and
control characters are not part of the manifest contract.

## Discovery Boundary

Discovery is bounded to these six project roots:

- `∞Life/`
- `❤Music/`
- `⟨ψ⟩Quantum/`
- `👁AI-Manifest/`
- `⊕Workspace/`
- `ΣCapital/`

The registered inventory also covers known shared coordination paths within
those roots, including the manifest-service stores and the shared
`⊕Workspace` coordination databases. A database candidate is not in approved
scope merely because it is found under one of the roots: it must be registered
in the manifest.

The default exclusions are:

- `.git/`
- virtual environments (`.venv/` and `venv/`)
This policy prepares the workspace for local disaster recovery. It is the
inventory and approval boundary for the provider-neutral backup engine; it does
not authorize cloud delivery or manage database encryption keys.
- backup artifacts (`backups/`)
- transient areas (`tmp/`, `logs/`, and `qbackups/`)
- root-level temporary database files such as `tmp*.db`, `tmp*.sqlite`, and
  `tmp*.sqlite3`

Excluded areas remain out of scope unless a path is separately and explicitly
registered in the manifest.

## Classification And Validation

The taxonomy is:

`canonical`, `coordination`, `derived`, `temporary`, `legacy`, `unknown`, and
`approval-required`.

An unclassified database, or a discovered database path that is not registered
in the manifest, is a validation failure. `unknown` is allowed only when it is
an explicit classification in a manifest entry; it is not an implicit default
and it does not authorize backup. Entries classified as `unknown`,
`temporary`, `legacy`, or `derived` remain denied unless the policy is
deliberately revised.

The health/genomic and financial stores are visible through redacted
project-scoped locators so their presence is auditable, but they are
classified `approval-required` and default-denied. They must retain
`backup_allowed: false` until explicit approval changes the policy.

## Generate The Report

From the repository root, run this exact PowerShell command:

```powershell
$env:PYTHONUTF8 = "1"
& "C:\G\python.exe" "tools\generate_database_backup_scope_report.py" `
  --manifest "src\config\database_backup_scope.json" `
  --report "reports\database_backup_scope.md"
```

The generator produces deterministic output at
`reports/database_backup_scope.md`. It reads and validates the manifest, then
renders the report in manifest order. The current limitation is important:
report generation does not itself perform a live discovery drift check. A
separate validation run must discover current files and compare them with the
registered paths before treating the inventory as current.

## Local Backup Contract

`src/utils/database_backup.py` is the provider-neutral implementation. A
`BackupDestination` must positively verify its stable identity before any
source file is read or copied. `LocalVolumeDestination` uses a pre-provisioned
`.backup-volume-identity` marker for local external volumes.

`DatabaseBackup.run()` copies only manifest entries with `backup_allowed: true`
into a temporary generation directory, atomically commits the generation, and
writes a JSON manifest with SHA-256 hashes. It retains the newest 30 generations
and appends backup and restore events to `backup-audit.jsonl`.
`validate_recent_backups()` is the periodic restore-validation hook; it checks
every retained manifest without modifying source databases.

Restore is isolated by target directory and requires `operator_approved=True`.
It verifies generation hashes before copying, preserving encrypted bytes and
leaving environment-backed database keys untouched. Discovery remains
fail-closed through `discover_and_validate_manifest()`.

The daily entry point is:

```powershell
$env:WORKSPACE_BACKUP_VOLUME = "E:\WorkspaceBackup"
$env:WORKSPACE_BACKUP_VOLUME_ID = "approved-volume-id"
& "C:\G\python.exe" "tools\run_database_backup.py" `
  --manifest "src\config\database_backup_scope.json" `
  --source-root "F:\"
```

The destination identity and paths are supplied by the operator/environment;
no provider SDK, cloud upload, or key material is embedded in the contract.