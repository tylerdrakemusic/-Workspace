# Architecture Review — FR-20260816-quantum-database-backup-restore

**Decision:** `PASS`

## Diff Scope

The Workspace worktree is based on `origin/main` at `9492e72` and has the
implementation and repair commits at review time. Its actual diff contains:

| File | Change |
| --- | --- |
| `tools/register_database_backup_task.py` | Canonicalizes an active `.worktrees` path before building the existing daily Task Scheduler specification while preserving configured roots on foreign platforms. |
| `tests/test_database_backup_operational.py` | Adds regression coverage for canonical roots, exclusion of `.worktrees` paths from scheduler arguments, and cross-platform preservation of non-worktree roots. |
| `reports/architecture-review-FR-20260816-quantum-database-backup-restore.md` | Records this architecture review as a reviewable FR proof artifact. |

The Quantum worktree is clean and `HEAD` equals its `origin/main` at `d1fbbc2`;
there is no unreviewed Quantum-side diff.

## Architectural Checks

- The change extends the merged provider-neutral backup lifecycle and scheduler
  from the Workspace pilot. It does not create a competing backup system.
- Canonical-root resolution is owned by `build_task_spec`, immediately before
  the existing launcher, manifest, and explicit project-root arguments are
  constructed.
- The active manifest preserves the explicit `quantum-quantumpsi` mapping to
  `⟨ψ⟩Quantum/src/data/quantumpsi.db` with `classification: canonical` and
  `backup_allowed: true`. `quantum-orion-config` remains derived and excluded.
- The diff adds no dependency, integration, database schema, or runtime
  database mutation.
- The Workspace architecture diagrams already model the provider-neutral
  backup contract, Task Scheduler, launcher, manifest scope, trusted
  destination, authenticated generations, and the Quantum database edge to
  that contract. The Quantum architecture diagram already models
  `quantumpsi.db`. The root-resolution correction adds no node, edge, or
  ownership boundary, so no diagram update is required.
- The mandatory Workspace agent-topology completeness check found no agent file
  without a corresponding topology node.
- The required GitHub `test` check failed in pytest because the initial
  implementation resolved every configured root with the host platform's
  `Path.resolve()`. The focused regression reproduced this portability defect;
  the final implementation resolves only paths containing `.worktrees` and
  preserves other configured roots.

## Verification

- `git diff --check origin/main...HEAD`: passed.
- `py_compile tools/register_database_backup_task.py`: passed.
- Focused scheduler tests: 11 passed, including the cross-platform root
  regression.
- Quantum inventory test: `tests/test_database_backup_inventory.py`, 10 passed
  in the clean Quantum worktree; no Quantum-side implementation diff was
  required.
- FR ledger confirms explicit `quantum-quantumpsi` scope, Todo #249 linkage,
  and prior QA PASS; this review does not advance the FR state or modify Todo
  #249.