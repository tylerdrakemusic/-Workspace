# Workspace Database Backup Scope

This policy prepares the workspace for future disaster recovery. It is an
inventory and approval boundary only; it does not implement backup, restore,
retention, encryption-key management, or delivery to a backup service.

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
- worktrees (`.worktrees/`)
- caches (`cache/`, `caches/`, `.cache/`)
- generated output (`output/`)
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

This feature request authorizes no cloud upload and no transfer of database
contents. It records database paths and policy metadata only; it does not read,
copy, upload, or restore database contents.