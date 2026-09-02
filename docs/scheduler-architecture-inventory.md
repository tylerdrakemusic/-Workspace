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
by the row, or the shared Workspace audit file when the evidence is the
cross-project live audit. Discovery reads the six canonical repositories and
records one row per externally scheduled job. Live Task Scheduler discovery is
deployment evidence; repository-only source references remain `documented` or
`unverified`. Re-run the deterministic validator after changing a row or the
diagram. A new external scheduler requires a new evidence path and a review of
the diagram and this inventory.

## Current Results

| Project | Task Name | Task Path | Trigger / Cadence | Action / Command | Owner | Status | Evidence | Last Observed Result | Operational Findings |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ∞Life | InfiniteLife-NightlySync | `\∞Life\InfiniteLife-NightlySync` | Daily | `tools/nightly_master_sync.ps1` | ∞Life maintenance | deployed | `docs/scheduler-live-audit-2026-09-01.md` | Audit found task; result not collected | Live registration observed; encoding/path defect tracked by TODO 452. |
| ∞Life | InfiniteLife_Withings_Token_Watcher | `\∞Life\InfiniteLife_Withings_Token_Watcher` | Daily | `tools/withings_token_watcher.py` | ∞Life maintenance | deployed | `docs/scheduler-live-audit-2026-09-01.md` | Audit found task; result not collected | Live registration observed; token values intentionally omitted. |
| ❤Music | No verified external job | None | None verified | None verified | None identified | no-entry | `AGENT_STARTUP.md` | No live job found | In-process timing is out of scope. |
| ⟨ψ⟩Quantum | QuantumCacheDepletionGuard_Daily | `\⟨ψ⟩Quantum\QuantumCacheDepletionGuard_Daily` | Daily | `tools/cache_depletion_guard.py` | ⟨ψ⟩Quantum maintenance | deployed | `docs/scheduler-live-audit-2026-09-01.md` | Audit found task; result not collected | Live registration observed; path encoding issue tracked by TODO 452. |
| ⟨ψ⟩Quantum | QuantumCacheFill_Monthly | `\⟨ψ⟩Quantum\QuantumCacheFill_Monthly` | Monthly | `tools/fill_cache.py` | ⟨ψ⟩Quantum maintenance | deployed | `docs/scheduler-live-audit-2026-09-01.md` | Audit found task; result not collected | Live registration observed. |
| ⟨ψ⟩Quantum | ShorsMonthlyBench | `\⟨ψ⟩Quantum\ShorsMonthlyBench` | Monthly | `tools/run_shors_monthly.py` | ⟨ψ⟩Quantum maintenance | deployed | `docs/scheduler-live-audit-2026-09-01.md` | Audit found task; result not collected | Live registration observed. |
| ⟨ψ⟩Quantum | VQEMonthlyBench | `\⟨ψ⟩Quantum\VQEMonthlyBench` | Monthly | `tools/run_vqe_monthly.py` | ⟨ψ⟩Quantum maintenance | deployed | `docs/scheduler-live-audit-2026-09-01.md` | Audit found task; result not collected | Live registration observed. |
| ⟨ψ⟩Quantum | PolicyComplianceAudit_Daily | `\⟨ψ⟩Quantum\PolicyComplianceAudit_Daily` | Daily | `tools/policy_compliance_audit.py` | ⟨ψ⟩Quantum maintenance | deployed | `docs/scheduler-live-audit-2026-09-01.md` | Audit found task; result not collected | Live registration observed. |
| 👁AI-Manifest | AI_Manifest_Priority_Rescore | `\👁AI-Manifest\AI_Manifest_Priority_Rescore` | Daily | `tools/priority_rescore.py` | 👁AI-Manifest maintenance | deployed | `docs/scheduler-live-audit-2026-09-01.md` | Audit found task; result not collected | Live registration observed; no service credentials recorded. |
| ⊕Workspace | ⊕Workspace-DatabaseBackup | `\⊕Workspace\⊕Workspace-DatabaseBackup` | Daily | `tools/backup_database.py` | ⊕Workspace maintenance | deployed | `docs/scheduler-live-audit-2026-09-01.md` | Audit found task; result not collected | Live registration observed; safe audit metadata only. |
| ⊕Workspace | ⊕Workspace-SecurityScan | `\⊕Workspace\⊕Workspace-SecurityScan` | Daily | `tools/run_security_scan.py` | ⊕Workspace maintenance | deployed | `docs/scheduler-live-audit-2026-09-01.md` | Audit found task; result not collected | Live registration observed. |
| ⊕Workspace | WorkspaceHygiene | `\⊕Workspace\WorkspaceHygiene` | Weekly | `tools/run_hygiene.py` | ⊕Workspace maintenance | deployed | `docs/scheduler-live-audit-2026-09-01.md` | Audit found task; result not collected | Live registration observed. |
| ⊕Workspace | Workspace-PerfRegressionAlerter | `\⊕Workspace\Workspace-PerfRegressionAlerter` | Daily | `tools/perf_regression_alerter.py` | ⊕Workspace maintenance | deployed | `docs/scheduler-live-audit-2026-09-01.md` | Audit found task; result not collected | Live registration observed. |
| ⊕Workspace | ProofHealthVerifier | `\⊕Workspace\ProofHealthVerifier` | Daily | `tools/verify_proof_health.py` | ⊕Workspace maintenance | deployed | `docs/scheduler-live-audit-2026-09-01.md` | Audit found task; result not collected | Live registration observed. |
| ⊕Workspace | SkillSyncNightly | `\⊕Workspace\SkillSyncNightly` | Nightly | `tools/sync_skills.ps1` | ⊕Workspace maintenance | deployed | `docs/scheduler-live-audit-2026-09-01.md` | Audit found task; result not collected | Live registration observed; external skill files remain governed. |
| ΣCapital | PositionRealization | `\ΣCapital\PositionRealization` | Daily | `tools/run_position_realization.py` | ΣCapital maintenance | deployed | `docs/scheduler-live-audit-2026-09-01.md` | Audit found task; result not collected | Live registration observed; account data intentionally omitted. |
| ΣCapital | ProductionFillReconciliation | `\ΣCapital\ProductionFillReconciliation` | Daily | `tools/reconcile_production_fills.py` | ΣCapital maintenance | deployed | `docs/scheduler-live-audit-2026-09-01.md` | Audit found task; result not collected | Live registration observed; account data intentionally omitted. |
| ΣCapital | ReconcileOrders | `\ΣCapital\ReconcileOrders` | Daily | `tools/reconcile_orders.py` | ΣCapital maintenance | deployed | `docs/scheduler-live-audit-2026-09-01.md` | Audit found task; result not collected | Live registration observed; account data intentionally omitted. |

## Diagram and Maintenance

The companion view is [../diagrams/workspace-scheduler-architecture.mmd](../diagrams/workspace-scheduler-architecture.mmd).
The Mermaid view links each inventory record to its project and command node;
its legend retains the documented, deployed, unverified, and no-entry states.
Architecture review checks this document, the evidence paths, the diagram
coverage, and the generated discovery contract in [../diagrams/DIAGRAM_DISCOVERY.md](../diagrams/DIAGRAM_DISCOVERY.md).
Architecture beautification may change layout or styling, but must preserve
the inventory relationships and classifications.

This reference intentionally does not describe in-process schedulers, add DB
schedule fields, enable live monitoring, or provide schedule editing.