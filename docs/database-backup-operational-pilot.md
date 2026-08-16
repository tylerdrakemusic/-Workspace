# Local Database Backup Operational Pilot

This pilot runs the approved database backup manifest once per day at 02:00
local time. It writes versioned generations only to the trusted external
volume; it never falls back to another drive and it never overwrites canonical
source databases.

## Provisioning

Provision the destination marker after the external volume is mounted:

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
C:\G\python.exe tools\provision_backup_volume.py `
  --volume-root 'E:\WorkspaceBackup' `
  --volume-identity 'workspace-backup-volume-2026'
```

The command creates `E:\WorkspaceBackup` and the non-secret
`.backup-volume-identity` marker when they do not exist. An existing marker
with a different value is an error and is never replaced.

Expected layout:

```text
E:\WorkspaceBackup\
  .backup-volume-identity
  generations\
    <generation>\
      manifest.json
      ⊕Workspace\src\data\workspace.db
      ...
  backup-audit.jsonl
```

## Environment

Persist these environment variables in the account or system environment
visible to Task Scheduler. Temporary process variables are not sufficient for
the scheduled task. The manifest authentication key is not written to a file
or included in task arguments.

- `WORKSPACE_BACKUP_VOLUME=E:\WorkspaceBackup`
- `WORKSPACE_BACKUP_VOLUME_ID=<the exact marker value>`
- `WORKSPACE_BACKUP_MANIFEST_KEY=<the existing manifest signing key>`

## Registration

After provisioning and setting the environment, registration is explicit and
does not install a task during tests:

```powershell
.\tools\register_database_backup_task.ps1
```

The task is named `⊕Workspace-DatabaseBackup`, runs daily at 02:00 local time,
and invokes `tools\run_database_backup.ps1` with the explicit `C:\G\python.exe`
path, the reviewed manifest, and the workspace source root. Registration uses
`-Force`, so an existing task with the same name is replaced. The launcher
verifies that the
configured destination is exactly `E:\WorkspaceBackup`, that the directory is
mounted, and that the marker matches before invoking the generic Python runner.

## Unplugged-drive behavior

If E: is unplugged, unavailable, or missing its marker, the launcher exits with
an error before loading the manifest or copying any database. A mismatched
marker has the same fail-closed behavior. There is no alternate-drive or
canonical-database fallback.

## Adding future databases

Future entries join the same job by being added to the reviewed
`src\config\database_backup_scope.json` manifest with `backup_allowed: true`.
The source must be discoverable under the task's source root and must pass the
manifest validation rules. No task, launcher, or backup lifecycle code changes
are needed for another approved non-sensitive database.

The operational pilot implementation does not provision E: or install the
real scheduled task. Those actions remain a post-test, post-QA deployment step.