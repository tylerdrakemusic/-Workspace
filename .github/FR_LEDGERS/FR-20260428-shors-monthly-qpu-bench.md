# FR-20260428-shors-monthly-qpu-bench — Shor's Monthly QPU Benchmark + Live Dashboard

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260428-shors-monthly-qpu-bench
- **Title:** Shor's Monthly QPU Benchmark + Live Dashboard Redesign
- **Type:** feature
- **Risk:** medium
- **Projects:** ⟨ψ⟩Quantum
- **State:** TRIAGED
- **Branch:** pending
- **PRs:** pending
- **Cycle timer:** 9aa96e41-3111-49ce-bbd9-dddc615a5317
- **Opened:** 2026-04-28
- **Last updated:** 2026-04-28
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria

1. A `bench_shors_monthly.py` (or equivalent) runner selects the **largest N that fits within a 5-min (300s) QPU cap** — logic inspects `shors_v2.py` circuit sizes and available qubit count on the live IBM backend before choosing N, defaulting to N=15 if no larger candidate fits.
2. The monthly runner caps QPU execution at **300 seconds** total (mirroring the fill_cache.py band-aware model). If the cap is hit mid-attempt, the current attempt completes and the run exits gracefully.
3. A **Windows Task Scheduler task** (`ShorsMonthlyBench` or similar) is registered to run the benchmark on the **1st of each month at 02:00 local time** (offset from `QuantumCacheFill_Monthly` to avoid QPU contention).
4. Every run inserts a row into `quantumpsi.db` → `benchmarks` table with correct `algorithm`, `n_value`, `required_qubits`, `backend`, `total_time_sec`, `order_r`, `factor1`, `factor2`, `timestamp` fields.
5. The benchmark dashboard at `reports/benchmark_dashboard.html` is **replaced with a live web panel** served by a local lightweight server (e.g., Python `http.server` or similar) or redesigned as an iframe auto-refresh panel, reading data from `quantumpsi.db` dynamically — no hardcoded benchmark rows in the HTML.
6. The redesigned dashboard clearly displays a **"Last run"** timestamp, hardware vs. simulator split, and a **monthly trend** row/chart showing success rate and average QPU time per month.
7. A **manual one-off run tonight** (2026-04-28) is executed against IBM Quantum hardware (`--backend ibm`), inserts a row into the DB, and the new live dashboard reflects it.
8. The monthly scheduler task survives a system reboot (persisted in Task Scheduler, not just a cron comment).

### Concurrency Notes
- Conflicts with: none (no active FRs touching ⟨ψ⟩Quantum benchmarks)
- Depends on: FR-20260428-quantum-cache-rebuild (DONE — IBM auth via `ibm_quantum_platform` channel is working)

### Deliverable Tracker

| #   | Deliverable                                      | Owner                    | Status      | Proof | Updated    |
| --- | ------------------------------------------------ | ------------------------ | ----------- | ----- | ---------- |
| AC1 | N-selection logic (largest N within 300s QPU)    | ⟨ψ⟩quantum-orchestrator | not-started | —     | 2026-04-28 |
| AC2 | 300s QPU cap + graceful exit in runner           | ⟨ψ⟩quantum-orchestrator | not-started | —     | 2026-04-28 |
| AC3 | Windows Task Scheduler task (monthly, 1st/02:00) | ⟨ψ⟩quantum-orchestrator | not-started | —     | 2026-04-28 |
| AC4 | DB insert verified (all fields correct)          | ⟨ψ⟩quantum-orchestrator | not-started | —     | 2026-04-28 |
| AC5 | Live dashboard (server or iframe auto-refresh)   | ⟨ψ⟩quantum-orchestrator | not-started | —     | 2026-04-28 |
| AC6 | Dashboard: Last-run ts + monthly trend           | ⟨ψ⟩quantum-orchestrator | not-started | —     | 2026-04-28 |
| AC7 | Manual tonight run → DB row + dashboard updated  | ⟨ψ⟩quantum-orchestrator | not-started | —     | 2026-04-28 |
| AC8 | Scheduler task persists after reboot             | ⟨ψ⟩quantum-orchestrator | not-started | —     | 2026-04-28 |

### Tyler's Original Request
> "I want a new run of Shors for the Quantum Benchmark dashboard, I feel like spending some of the QPU band we have on updating that benchmark dashboard with data from quantum hardware, perhaps on a monthly execution policy. I want to be efficient with the QPU usage, perhaps picking an N and qubit number that doesn't exhaust the usage but gives us consistent benchmark results month to month. We may have to redesign that quantum panel, I want to ensure it reflects from the db and not static html, I'd also like to run the benchmark tonight"

---

## Event Log

### 2026-04-28T00:00:00 — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, triage complete → TRIAGED

**Details:**
- Scope: ⟨ψ⟩Quantum (single-project)
- Type: feature | Risk: medium
- Codebase inspected: `tools/bench_shors_v2.py`, `tools/bench_dashboard.py`, `tools/fill_cache.py`, `src/utils/init_db.py`
- Key finding: dashboard already reads from DB (bench_dashboard.py); static HTML is the output format, not data source
- Key finding: N=15 (12 qubits) is the only fully implemented target in shors_v2; larger N requires circuit extension
- Tyler interview answers: N = largest that fits in 300s QPU cap; 300s QPU budget; dashboard redesign = full live panel in same FR; tonight = manual run + first scheduled execution
- Acceptance criteria: 8 items drafted
- Concurrency check: clean (no active Quantum benchmark FRs)
- Depends on: FR-20260428-quantum-cache-rebuild (DONE)
- Cycle timer started: 9aa96e41-3111-49ce-bbd9-dddc615a5317

**Next:** awaiting Tyler scope approval

---

## Artifacts

- **Perf runs:** 9aa96e41-3111-49ce-bbd9-dddc615a5317 — FR cycle timer (intake)
