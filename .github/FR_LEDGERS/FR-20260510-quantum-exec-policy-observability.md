# FR-20260510-quantum-exec-policy-observability — Quantum Execution Policy Observability and Benchmark Schedule Visibility

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260510-quantum-exec-policy-observability
- **Title:** Quantum Execution Policy Observability and Benchmark Schedule Visibility
- **Type:** feature
- **Risk:** medium
- **Projects:** ⟨ψ⟩Quantum, ⊕Workspace
- **State:** BRANCHED
- **Branch:** feature/quantum/fr-20260510-quantum-exec-policy-observability; feature/workspace/fr-20260510-quantum-exec-policy-observability
- **PRs:** https://github.com/tylerdrakemusic/Quantum/pull/new/feature/quantum/fr-20260510-quantum-exec-policy-observability (draft create); https://github.com/tylerdrakemusic/-Workspace/pull/new/feature/workspace/fr-20260510-quantum-exec-policy-observability (draft create)
- **Cycle timer:** 1fc82c9c-6027-4015-bd25-b53a1c85e6a1
- **Opened:** 2026-05-10
- **Last updated:** 2026-05-10
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. Quantum benchmark panel shows execution policy status signals for benchmark jobs: started, succeeded, failed.
2. Quantum benchmark panel shows next scheduled run for the benchmark policy near existing schedule/alert context.
3. Quantum benchmark panel surfaces skip/defer outcomes for scheduled benchmark attempts when they occur.
4. Quantum benchmark panel surfaces manual override/exception events relevant to benchmark policy execution.
5. Policy observability information is integrated into the existing quantum benchmark panel flow (not a detached panel).
6. Alerting context in the quantum benchmark panel reflects the new execution policy observability signals.
7. Benchmark schedule policy is normalized to the canonical schedule: cache fill at 01:00 and benchmark at 02:00.
8. Schedule policy values are defined in one canonical config file, and schedule-consuming scripts and documentation read from that source rather than duplicating hardcoded schedule times.
9. Schedule policy rollout for this FR is forward-only from merge; no historical backfill is performed.

### Concurrency Notes
- Conflicts with: FR-20260428-shors-monthly-qpu-bench (active quantum benchmark panel ownership)
- Depends on: FR-20260428-shors-monthly-qpu-bench

### Deliverable Tracker

| #   | Deliverable | Owner | Status | Proof | Updated |
| --- | ----------- | ----- | ------ | ----- | ------- |
| AC1 | Execution status signals (started/succeeded/failed) visible in quantum benchmark panel | ⟨ψ⟩quantum-orchestrator | not-started | — | — |
| AC2 | Next scheduled run visible near benchmark schedule context | ⟨ψ⟩quantum-orchestrator | not-started | — | — |
| AC3 | Skipped/deferred outcomes surfaced in panel | ⟨ψ⟩quantum-orchestrator | not-started | — | — |
| AC4 | Manual override/exception events surfaced in panel | ⟨ψ⟩quantum-orchestrator | not-started | — | — |
| AC5 | Panel integration in ⊕Workspace dashboard/UI path | ⊕workspace-overseer | not-started | — | — |
| AC6 | Branch/worktree/draft PR orchestration for both repos | ⊕workspace-ci | in-progress | Branches/worktrees created; draft-create URLs recorded | 2026-05-10 |
| AC7 | Canonical schedule normalization implemented (cache fill 01:00, benchmark 02:00) | ⟨ψ⟩quantum-orchestrator | not-started | — | — |
| AC8 | Single-source schedule policy config consumed by scripts/docs | ⟨ψ⟩quantum-orchestrator | not-started | — | — |
| AC9 | Forward-only rollout with no schedule backfill | ⟨ψ⟩quantum-orchestrator | not-started | — | — |

### Tyler's Original Request
> Title: Quantum Execution Policy Observability and Benchmark Schedule Visibility. Type: feature. Scope: ⟨ψ⟩Quantum + ⊕Workspace dashboard/UI. Signals: started/succeeded/failed, next scheduled run, skipped/deferred, manual override/exceptions. UI: integrate in quantum benchmark panel near next scheduled run and alerting there.

---

## Event Log

### 2026-05-11T03:30:01Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened from confirmed draft; triage complete and marked BRANCHED (pending CI branch creation).

**Details:**
- Scope: ⟨ψ⟩Quantum benchmark execution policy telemetry + ⊕Workspace benchmark panel visibility.
- Risk: medium (cross-repo UI + benchmark execution observability changes).
- Out of scope for this FR: changing QPU budget caps, changing PowerShell launcher execution policy behavior.
- Acceptance criteria drafted (see Header).
- Concurrency check: conflict/dependency flagged against FR-20260428-shors-monthly-qpu-bench.
- Cycle timer started: 1fc82c9c-6027-4015-bd25-b53a1c85e6a1.

**Next:** awaiting ⊕workspace-ci: create branches/worktrees/draft PRs for Quantum and -Workspace.

### 2026-05-11T04:10:00Z — ⊕workspace-intake

**Event:** scope-amendment

**Summary:** Absorbed schedule consistency into FR scope per Tyler confirmation; acceptance criteria expanded to include policy normalization and source-of-truth requirements.

**Details:**
- In-scope amendment: schedule policy normalization is now part of this FR.
- Canonical schedule confirmed: cache fill 01:00, benchmark 02:00.
- Policy source confirmed: one config file is authoritative; scripts/docs must read from it.
- Rollout policy confirmed: no backfill; forward-only behavior from merge.
- Branch/PR status unchanged: pending.

**Next:** awaiting ⊕workspace-ci branch/worktree/draft PR handling under unchanged pending status.

### 2026-05-10T00:00:00Z — ⊕workspace-ci

**Event:** state-transition

**Summary:** Created isolated FR branches and worktrees for ⟨ψ⟩Quantum and ⊕Workspace; pushed both branches; draft-create URLs recorded.

**Details:**
- Quantum branch: feature/quantum/fr-20260510-quantum-exec-policy-observability.
- Quantum worktree: f:\worktrees\fr-20260510-quantum-exec-policy-observability-quantum.
- Workspace branch: feature/workspace/fr-20260510-quantum-exec-policy-observability.
- Workspace worktree: f:\worktrees\fr-20260510-quantum-exec-policy-observability-workspace.
- Draft PR creation attempted via GitHub API and web flow; environment auth prevented direct draft submission in-session.
- Draft-create URLs are now captured in Header and Artifacts for immediate manual finalize.

**Next:** create draft PRs from recorded URLs once authenticated session is available; then replace URLs with concrete PR numbers.

---

## Artifacts

- **Perf runs:** 1fc82c9c-6027-4015-bd25-b53a1c85e6a1 — fr-cycle-FR-20260510-quantum-exec-policy-observability
- **Proof artifacts:** —
- **PRs:** https://github.com/tylerdrakemusic/Quantum/pull/new/feature/quantum/fr-20260510-quantum-exec-policy-observability (draft create); https://github.com/tylerdrakemusic/-Workspace/pull/new/feature/workspace/fr-20260510-quantum-exec-policy-observability (draft create)
- **Commits:** 2784d34 (Quantum bootstrap), 261eb21 (Workspace bootstrap)
- **Reports / dashboards:** —
