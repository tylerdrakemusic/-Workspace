# FR-20260430-quantum-dashboard-gitignore — Stop tracking generated dashboard HTML

## Header

- **FR ID:** FR-20260430-quantum-dashboard-gitignore
- **Title:** Stop tracking generated dashboard HTML in ⟨ψ⟩Quantum
- **Type:** chore
- **Risk:** low
- **Projects:** ⟨ψ⟩Quantum
- **State:** TRIAGED
- **Branch:** pending
- **PRs:** pending
- **Cycle timer:** 5ab98ec0-be44-4d1c-8446-a6b878de968e
- **Opened:** 2026-04-30
- **Last updated:** 2026-04-30
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. `reports/benchmark_dashboard.html` added to ⟨ψ⟩Quantum's `.gitignore`
2. `reports/benchmark_dashboard.html` removed from git tracking via `git rm --cached`
3. Local regen produces a populated dashboard (Shor's history + VQE panel both visible)
4. README or `tools/gen_benchmark_dashboard.py` notes that the dashboard is now local-only and must be regenerated to view
5. CI green on the PR

### Out of Scope
- DB schema changes
- Dashboard styling/layout changes
- Gitignoring other generated artifacts (separate FR if needed)

### Concurrency Notes
- Conflicts with: none
- Depends on: PR #12 (FR-20260430-vqe-aer-bench) merged first so VQE panel is on main

### Deliverable Tracker

| #   | Deliverable                                                    | Owner                  | Status      | Proof | Updated    |
| --- | -------------------------------------------------------------- | ---------------------- | ----------- | ----- | ---------- |
| AC1 | Add HTML to `.gitignore`                                       | ⟨ψ⟩quantum-orchestrator | not-started | —     | —          |
| AC2 | `git rm --cached` the HTML                                     | ⟨ψ⟩quantum-orchestrator | not-started | —     | —          |
| AC3 | Local regen shows populated dashboard (Shor's + VQE)           | ⟨ψ⟩quantum-orchestrator | not-started | —     | —          |
| AC4 | Document local-regen requirement                               | ⟨ψ⟩quantum-orchestrator | not-started | —     | —          |
| AC5 | CI green on PR                                                 | ⟨ψ⟩quantum-orchestrator | not-started | —     | —          |

### Tyler's Original Request
> ya let's do that know, I don't want the main board to show an empty shor's history

Reviewer note from PR #12: committed `reports/benchmark_dashboard.html` was regenerated from worktree's empty DB; main shows empty Shor's history until re-regen. Generated artifacts shouldn't live in git.

---

## Event Log

### 2026-04-30T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, triage complete (clear + low-risk → no grill-me) → TRIAGED

**Details:**
- Risk: low (gitignore + cache removal only)
- Tyler approved scope
- Concurrency: clean; depends on PR #12 merging

**Next:** awaiting PR #12 merge → branch creation via ⊕workspace-ci

---

## Artifacts

- **Perf runs:** 5ab98ec0-be44-4d1c-8446-a6b878de968e — FR cycle timer
- **Proof artifacts:** —
- **PRs:** —
- **Commits:** —
- **Reports / dashboards:** —
