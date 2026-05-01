# FR-20260430-vqe-aer-bench — VQE for H₂ + LiH (Aer baseline + dashboard panel)

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260430-vqe-aer-bench
- **Title:** VQE for H₂ + LiH (Aer baseline + dashboard panel)
- **Type:** feature
- **Risk:** medium
- **Projects:** ⟨ψ⟩Quantum
- **State:** BRANCHED
- **Branch:** feature/quantum/vqe-aer-bench
- **PRs:** https://github.com/tylerdrakemusic/Quantum/pull/12 (draft)
- **Cycle timer:** 746313b6-83dd-4a92-a15a-951bd4cdd816
- **Opened:** 2026-04-30
- **Last updated:** 2026-04-30
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. `qiskit-nature` added to ⟨ψ⟩Quantum requirements; **PySCF NOT installed** — use qiskit-nature's prebuilt Hamiltonians for H₂ and LiH
2. New `tools/bench_vqe.py` runs VQE on Aer for both H₂ and LiH and records results to the perf DB following the Shor's bench schema
3. **H₂ ground-state energy within ±1.6e-3 hartree of -1.137 Ha** (chemical accuracy) — test fails if outside threshold
4. **LiH ground-state energy within ±1.6e-3 hartree of -7.882 Ha** — test fails if outside threshold
5. New "🧪 VQE — Molecular Simulation (Aer)" panel added to `reports/benchmark_dashboard.html` showing energy, iteration count, optimizer used, per-molecule
6. `tests/test_vqe.py` exercises the chemical-accuracy thresholds; passes in CI

### Out of Scope
- QPU runs (separate follow-on FR)
- PySCF installation (separate follow-on FR if needed for non-textbook molecules)
- ∞Life molecular-interactions integration (separate follow-on FR)
- Molecules beyond H₂ and LiH

### Concurrency Notes
- Conflicts with: none
- Depends on: none
- Notes: `FR-20260428-shors-monthly-qpu-bench` is in REVIEW_REQUESTED but operates on `bench_shors_v2.py` and the existing dashboard panels — no file overlap with new VQE additions.

### Deliverable Tracker

| #   | Deliverable                                                             | Owner                  | Status      | Proof | Updated    |
| --- | ----------------------------------------------------------------------- | ---------------------- | ----------- | ----- | ---------- |
| AC1 | Add `qiskit-nature` to requirements (no PySCF)                          | ⟨ψ⟩quantum-orchestrator | not-started | —     | —          |
| AC2 | Create `tools/bench_vqe.py` (Shor's-style perf-DB recording)            | ⟨ψ⟩quantum-orchestrator | not-started | —     | —          |
| AC3 | H₂ energy within ±1.6e-3 Ha of -1.137 Ha                                | ⟨ψ⟩quantum-orchestrator | not-started | —     | —          |
| AC4 | LiH energy within ±1.6e-3 Ha of -7.882 Ha                               | ⟨ψ⟩quantum-orchestrator | not-started | —     | —          |
| AC5 | "🧪 VQE — Molecular Simulation (Aer)" panel in `benchmark_dashboard.html` | ⟨ψ⟩quantum-orchestrator | not-started | —     | —          |
| AC6 | `tests/test_vqe.py` enforces chemical-accuracy thresholds; CI green     | ⟨ψ⟩quantum-orchestrator | not-started | —     | —          |

### Tyler's Original Request
> I have a perfect example in mind. I see an AI task Implement VQE for molecular simulation (H₂, LiH) in my executive dashboard, but I need to come to a common understanding of what this is with you before implementing. I think grill me skill would be appropriate for this intake branch fr ledger. My understanding is the impl belongs in the quantum dashboard, we have available QPU band but may want to mock with Aer first

### Intake Decision Tree (grill-me record)

5 questions asked one-at-a-time, 5 answered, 0 sub-branches opened.

| # | Branch | Decision |
|---|--------|----------|
| 1 | Deliverable shape | **B** — Bench-style: `tools/bench_vqe.py` records to perf DB + new VQE panel in dashboard (mirrors Shor's v2 pattern) |
| 2 | Phasing (Aer vs QPU) | **A** — Aer-only this FR; QPU is a separate follow-on FR |
| 3 | PySCF strategy | **B** — Skip PySCF; use qiskit-nature's prebuilt Hamiltonians for H₂/LiH |
| 4 | ∞Life tie-in | **A** — No ∞Life work in this FR; ∞Life integration is a follow-on FR |
| 5 | Correctness criterion | **B** — Hard threshold: chemical accuracy ±1.6e-3 Ha vs literature values |

---

## Event Log

### 2026-04-30T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, grill-me Phase A complete, triage complete → TRIAGED

**Details:**
- Risk = medium (new algorithm + new dependency + new dashboard panel) → grill-me auto-escalation triggered
- 5 grill-me questions resolved; full decision tree closed
- Tyler confirmed scope on 2026-04-30
- Concurrency: clean

**Next:** awaiting Tyler scope approval (confirmed) → handoff to ⊕workspace-ci for branching

### 2026-04-30T00:00:00Z — ⊕workspace-ci

**Event:** state-transition

**Summary:** TRIAGED → BRANCHED

**Details:**
- Branch `feature/quantum/vqe-aer-bench` created off `origin/main` (8df9ac0)
- Worktree at `F:\worktrees\quantum-vqe-aer-bench`
- Seed commit `1e35b53` pushed (empty, opens PR surface)
- Draft PR #12 opened: https://github.com/tylerdrakemusic/Quantum/pull/12

**Next:** handoff to ⟨ψ⟩quantum-orchestrator for AC1–AC6 implementation

---

## Artifacts

- **Perf runs:** 746313b6-83dd-4a92-a15a-951bd4cdd816 — fr-cycle-FR-20260430-vqe-aer-bench
- **Proof artifacts:** —
- **PRs:** https://github.com/tylerdrakemusic/Quantum/pull/12 (draft)
- **Commits:** Quantum@1e35b53 (seed)
- **Reports / dashboards:** —
- **Branch:** feature/quantum/vqe-aer-bench
- **Worktree:** F:\worktrees\quantum-vqe-aer-bench
