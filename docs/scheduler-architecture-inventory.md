# Scheduler Architecture Inventory

**Owner:** `⊕Workspace` architecture documentation
**Scope:** architecture and documentation only. This is not a live scheduler,
monitor, schedule editor, or database schedule registry.

## Classification Contract

- `documented`: a repository source documents an intended external scheduled task.
- `deployed`: deployment evidence explicitly confirms the task is registered in
  the target environment. No current record is promoted to this status without
  that evidence.
- `unverified`: a scheduler claim or candidate exists, but registration or
  deployment cannot be confirmed.
- `no-entry`: discovery found no verified external scheduled job. In-process
  timers, queue polling, browser timing, and database schedule fields are
  excluded from this classification.

The evidence column is always a repository-relative path in the project named
by the row. Discovery reads the six canonical worktrees, records one row per
project, and preserves `unverified` or `no-entry` results instead of inferring
an active schedule. Re-run the deterministic validator after changing a row or
the diagram. A new external scheduler requires a new evidence path and a
review of the diagram and this inventory.

## Current Results

| Project | Trigger | Command | Owner | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| ∞Life | Daily Windows Task Scheduler task, timing documented in scripts | `tools/nightly_master_sync.ps1` | ∞Life maintenance | documented | `tools/Register-NightlySync.ps1` |
| ❤Music | None verified for an external project scheduler | None verified | None identified | no-entry | `AGENT_STARTUP.md` |
| ⟨ψ⟩Quantum | Monthly cache and benchmark task, cadence documented in project startup/config | `tools/fill_cache.py` | ⟨ψ⟩Quantum maintenance | documented | `src/config/execution_policy.json` |
| 👁AI-Manifest | Daily database backup task, cadence documented | `tools/register_database_backup_task.ps1` | 👁AI-Manifest maintenance | documented | `docs/scheduled_tasks.md` |
| ⊕Workspace | External task registration scripts document maintenance tasks | `tools/run_hygiene.py` | ⊕Workspace maintenance | documented | `tools/register_hygiene_task.ps1` |
| ΣCapital | Daily review-only position realization task | `tools/run_position_realization.py` | ΣCapital maintenance | documented | `tools/schedule_position_realization.xml` |

## Diagram and Maintenance

The companion view is [../diagrams/workspace-scheduler-architecture.mmd](../diagrams/workspace-scheduler-architecture.mmd).
The Mermaid view links each inventory record to its project and command node;
its legend retains the documented, deployed, unverified, and no-entry states.
Architecture review checks this document, the evidence paths, the diagram
coverage, and the measured row in [../diagrams/DIAGRAM_INVENTORY.md](../diagrams/DIAGRAM_INVENTORY.md).
Architecture beautification may change layout or styling, but must preserve
the inventory relationships and classifications.

This reference intentionally does not describe in-process schedulers, add DB
schedule fields, enable live monitoring, or provide schedule editing.