# FR-20260513-hooks-setup — Better hooks setup for all workspace repos

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260513-hooks-setup
- **Title:** Better hooks setup for all workspace repos
- **Type:** chore (security infrastructure)
- **Risk:** medium — touches security-critical commit path; ∞Life health data gate
- **Projects:** ⊕Workspace, ∞Life, ❤Music, ⟨ψ⟩Quantum, 👁AI-Manifest (all 5)
- **State:** BRANCHED
- **Branch:** chore/workspace/fr-20260513-hooks-setup
- **PRs:** https://github.com/tylerdrakemusic/-Workspace/pull/139
- **Cycle timer:** d57751a9-e842-4cc7-8d70-5a3d2ca1f46e (started at intake 2026-05-13)
- **Opened:** 2026-05-13
- **Last updated:** 2026-05-13
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria

1. `core.hooksPath` is set to `f:\.github\hooks\scripts\` in all 5 repos via `git config`
2. A single `pre-commit` bash entry point exists in `.github\hooks\scripts\` and runs the following checks:
   - **Worktree guard** — blocks staging of `.worktrees/` paths (refactored from `pre-commit-worktree-guard.sh`)
   - **Secret scanner** — custom regex scanner detects API keys, tokens, JWT headers, and env var leaks in staged diffs
   - **∞Life health data audit** — when running in the ∞Life repo, blocks `*.db`, `SUBJECT_PROFILE.json`, `data/bloodwork/`, `data/genomics/`, `data/medical_records/`, `logs/`, `tmp/` from staging
   - **Smoke test gate** — runs `pytest -k smoke` (or `test_smoke.py`) for the current repo; commit blocked if tests fail
3. `f:\.github\hooks\install-hooks.ps1` PowerShell script sets `core.hooksPath` in all 5 repos in one shot
4. `⊕workspace-ci.agent.md` updated to verify `core.hooksPath` is set at the start of any commit workflow
5. `pre-commit-worktree-guard.sh` is preserved (backward compat) but superseded by the unified `pre-commit` entry point

### Concurrency Notes

- Conflicts with: none
- Depends on: none

### Deliverable Tracker

| #   | Deliverable | Owner | Status | Proof | Updated |
|-----|-------------|-------|--------|-------|---------|
| AC1 | `pre-commit` bash entry point (unified hook) | ⊕workspace-ci | done | c14047c | 2026-05-13 |
| AC2 | `secret_scan.py` — custom regex scanner | ⊕workspace-ci | done | c14047c | 2026-05-13 |
| AC3 | `health_data_audit.py` — ∞Life gitignore audit | ⊕workspace-ci | done | c14047c | 2026-05-13 |
| AC4 | `smoke_test_gate.py` — smoke test runner | ⊕workspace-ci | done | c14047c | 2026-05-13 |
| AC5 | `install-hooks.ps1` — sets core.hooksPath in all 5 repos | ⊕workspace-ci | done | c14047c | 2026-05-13 |
| AC6 | `⊕workspace-ci.agent.md` updated — hooksPath startup verification | ⊕workspace-ci | done | c14047c | 2026-05-13 |

### Tyler's Original Request

> "we need better hooks setup for the repos, grill me"

---

## Event Log

### 2026-05-13T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, grill-me interview completed, scope confirmed by Tyler → TRIAGED

**Details:**
- Audit revealed: ⊕Workspace has `pre-commit`+`post-commit` installed; ∞Life has `pre-push` only; ❤Music, ⟨ψ⟩Quantum, 👁AI-Manifest have zero active hooks
- Worktree guard script exists in `.github/hooks/scripts/pre-commit-worktree-guard.sh` but is not installed in 4 of 5 repos
- No secret scanning hook exists anywhere (gap flagged in `encryption-recommendations.md` L332)
- ∞Life has real genomic/medical data with no pre-commit audit gate
- Grill-me decisions: core.hooksPath approach, hybrid bash+Python scripts, smoke test gate only, both PS1 install script + CI agent verification
- Anchors: `∞Life/research/security/encryption-recommendations.md` L332, `⊕Workspace/.github/instructions/repo-visibility.instructions.md`
- Concurrency check: no conflicts detected
- Out of scope: lint/format hooks, commit message enforcement, pre-commit framework, GitHub Actions CI

**Next:** ⊕workspace-ci — create branch, implement deliverables

---

---

### 2026-05-13T00:00:00Z — ⊕workspace-ci

**Event:** branched + implemented

**Summary:** All 6 deliverables implemented, committed on `chore/workspace/fr-20260513-hooks-setup`, draft PR opened → BRANCHED

**Details:**
- Created `pre-commit` bash entry point with worktree guard, secret scan, ∞Life health data audit, smoke test gate
- Created `secret_scan.py`, `health_data_audit.py`, `smoke_test_gate.py` Python hook scripts
- Created `install-hooks.ps1` — sets `core.hooksPath = f:/.github/hooks/scripts` in all 5 repos
- Updated `⊕workspace-ci.agent.md` to document core.hooksPath approach and CI startup check
- Ran `install-hooks.ps1` — all 5 repos confirmed [OK]
- Syntax checks: `bash -n pre-commit` → 0, `py_compile` on all 3 Python scripts → 0
- Commit: `c14047c` on branch `chore/workspace/fr-20260513-hooks-setup`
- Draft PR: https://github.com/tylerdrakemusic/-Workspace/pull/139

**Next:** Tyler review → approve → merge

---

## Artifacts

- **Perf runs:** d57751a9-e842-4cc7-8d70-5a3d2ca1f46e — FR-intake-hooks-setup
- **Proof artifacts:** —
- **PRs:** pending
- **Commits:** —
- **Reports / dashboards:** —
