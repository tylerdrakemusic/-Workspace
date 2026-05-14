# FR-20260513-quantum-entropy-sync-panel — ⟨ψ⟩Quantum Benchmark Dashboard — Quantum Entropy Cache Fill + VQE Sync Status Panel

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260513-quantum-entropy-sync-panel
- **Title:** ⟨ψ⟩Quantum Benchmark Dashboard — Quantum Entropy Cache Fill + VQE Sync Status Panel
- **Type:** feature (observability/UI)
- **Risk:** low
- **Projects:** ⟨ψ⟩Quantum
- **State:** BRANCHED
- **Branch:** feature/quantum/fr-20260513-quantum-entropy-sync-panel
- **PRs:** [#18](https://github.com/tylerdrakemusic/Quantum/pull/18)
- **Cycle timer:** f8a1c3e5-b7d9-4f21-9a83-c62e10475d8b
- **Opened:** 2026-05-13
- **Last updated:** 2026-05-13
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria

1. A new collapsible **"Quantum Entropy Cache Fill"** panel renders on the benchmark dashboard, styled after the biomarker dashboard's `Master Sync Observability` block (pills row + events table; NOT the existing 3-card `_build_policy_panel` layout).
2. Panel reads `policy_events` for `policy_id = 'quantum_cache_fill_monthly'` from `quantumpsi.db` — reuses existing `_load_policy_events()`.
3. Pills row shows: Last run start · Next scheduled run (Day 1 @ 01:00 UTC from `execution_policy.json`) · Policy name (`QuantumCacheFill_Monthly`) · QPU cap (180s).
4. Events table columns: Event Time | Event Type | Status badge | Detail — last 6 events, graceful "No events yet" fallback.
5. Overall health badge on the panel header (✓ Healthy / ↷ Degraded / ✗ Failing) derived from latest event status using the same `_status_to_health()` logic as the biomarker dashboard.
6. The existing **VQE execution policy** panel (`vqe_monthly_benchmark`) is also rendered in the same biomarker-style collapsible design — consistent with the new entropy cache fill panel.
7. CSS matches the existing dark-theme variables in `_CSS`; no new CSS framework introduced.
8. Dashboard still generates correctly with `python tools/gen_benchmark_dashboard.py --no-open` (no regressions on Shor's/VQE/QPU table sections).

### Out of Scope

- Changes to the cache fill script itself (`fill_cache.py` or equivalent)
- Changes to the biomarker dashboard (`∞Life`)
- New DB tables or schema changes (`policy_events` table already exists)
- Auto-refresh logic changes
- Redesigning the Shor's policy panel (only Cache Fill + VQE get the new style per Tyler's request)

### Concurrency Notes

- **Related to:** `FR-20260510-quantum-exec-policy-observability` (BRANCHED, appears stalled — auth-blocked PR). This FR is narrower and self-contained to `gen_benchmark_dashboard.py`; no branch overlap if CI creates a clean branch.
- **Depends on:** `FR-20260512-quantum-vqe-execution-policy-card` (MERGED) — VQE `_build_policy_panel` call already in `gen_benchmark_dashboard.py`; this FR converts its rendering style.
- Conflicts with: none (single-file change in `tools/gen_benchmark_dashboard.py`)

### Deliverable Tracker

| #   | Deliverable                                              | Owner                  | Status      | Proof | Updated    |
| --- | -------------------------------------------------------- | ---------------------- | ----------- | ----- | ---------- |
| AC1 | Collapsible entropy cache fill panel (biomarker style)   | ⟨ψ⟩quantum-orchestrator | not-started | —     | 2026-05-13 |
| AC2 | `_load_policy_events("quantum_cache_fill_monthly")` wired | ⟨ψ⟩quantum-orchestrator | not-started | —     | 2026-05-13 |
| AC3 | Pills row: last run · next run · policy · QPU cap        | ⟨ψ⟩quantum-orchestrator | not-started | —     | 2026-05-13 |
| AC4 | Events table (last 6) + graceful fallback                | ⟨ψ⟩quantum-orchestrator | not-started | —     | 2026-05-13 |
| AC5 | Health badge on panel header                             | ⟨ψ⟩quantum-orchestrator | not-started | —     | 2026-05-13 |
| AC6 | VQE panel converted to biomarker-style collapsible       | ⟨ψ⟩quantum-orchestrator | not-started | —     | 2026-05-13 |
| AC7 | CSS consistent with `_CSS` dark theme                    | ⟨ψ⟩quantum-orchestrator | not-started | —     | 2026-05-13 |
| AC8 | Smoke test: `--no-open` generates without error          | ⟨ψ⟩quantum-orchestrator | not-started | —     | 2026-05-13 |

### Tyler's Original Request

> There's also an execution policy for filling bitstring for quantum entropy. I like how the sync display is on the biomarker dashboard, we need the sync of the quantum entropy execution policy on the quantum benchmark dashboard, I'd like the sync status designed after how the biomarker dashboard sync display is setup.
>
> Amendment (confirmed): "for your awareness there is a VQE execution policy that should be with the new display"

### Design Reference

**Biomarker dashboard pattern** (`∞Life/src/dashboard/gen_biomarker_dashboard.py` → `build_master_sync_observability_html`):
- Collapsible `.category` div with header, chevron, and health badge
- Pills row: last run start · last update · scheduler policy · runtime policy · wrapper status
- `<table class="bio-table">` with columns: Subprocess | Health | Status | Sync Timestamp | Step Timestamp | Records | Notes

**Adapt to quantum context:**
- "Subprocess" → "Policy"
- "Sync Timestamp" → "Event Time"
- "Step Timestamp" → "Next Run"
- "Records" → "QPU Cap (s)"
- No "Notes" column needed (use "Detail" from `policy_events`)

---

## Event Log

| Date | Event | Agent |
|------|-------|-------|
| 2026-05-13 | FR opened, triage complete → TRIAGED. Tyler confirmed scope including VQE amendment. | ⊕workspace-intake |
| 2026-05-13 | Branch created, draft PR opened → BRANCHED | ⊕workspace-ci |
