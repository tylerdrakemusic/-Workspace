# FR-20260430-quantum-skip-slow-tests — Skip @slow tests by default in Quantum CI

<!-- Created by ⊕workspace-overseer (escalated by Tyler from VQE FR runtime observation).
     Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260430-quantum-skip-slow-tests
- **Title:** Skip @slow tests by default in Quantum CI (pytest.ini)
- **Type:** chore
- **Risk:** low
- **Projects:** ⟨ψ⟩Quantum
- **State:** CLOSED
- **Branch:** chore/quantum/skip-slow-tests
- **PRs:** [Quantum#13](https://github.com/tylerdrakemusic/Quantum/pull/13) (merged 69475a6)
- **Cycle timer:** (rolled into 5ab98ec0-be44-4d1c-8446-a6b878de968e batch)
- **Opened:** 2026-04-30
- **Last updated:** 2026-04-30
- **Merged at:** 2026-04-30
- **Signed off at:** 2026-04-30 (Tyler approved batch)
- **Closed:** 2026-04-30
- **Final state:** MERGED

### Acceptance Criteria
1. `tests/test_vqe.py::test_lih_chemical_accuracy` (and any future `@pytest.mark.slow`) is **deselected by default** in Quantum CI runs.
2. `pytest.ini` `addopts` updated to include `-m "not slow"`.
3. Slow tests still runnable explicitly via `pytest -m slow` (locally or in a follow-on dedicated CI job).
4. Quantum CI runtime drops back to ≤30s for non-slow path (currently 524s due to LiH).
5. Documented in `tests/README.md` or top of `pytest.ini` as a comment block: how to opt-in to slow tests locally.

### Out of Scope
- Setting up a separate weekly slow-test CI job (could be follow-on FR if desired).
- Optimizing LiH VQE runtime (separate FR if attempted).
- Touching other projects' pytest.ini.

### Concurrency Notes
- Conflicts with: none — `pytest.ini` is not modified by any open Quantum FR.
- Depends on: none.
- Notes: surfaced from FR-20260430-vqe-aer-bench post-merge runtime observation. Tyler approved on 2026-04-30.

### Tyler's Original Request
> one of the new tests seems to be taking way too long to execute. May be a risk for project flow in quantum project … not sure what test, and why though

### Diagnosis (overseer)
- LiH VQE = 92 ansatz parameters × 1223 SLSQP evals × Statevector matvec = ~520s wall clock.
- Already correctly marked `@pytest.mark.slow` in the test file.
- `pytest.ini` registers the marker but `addopts = -v --tb=short` does not deselect it. CI runs everything.
- Trivial 1-line fix; large CI savings; zero risk to correctness coverage (H₂ test still enforces VQE math path on every PR).

---

## Event Log

### 2026-04-30T02:30:00Z — ⊕workspace-overseer

**Event:** state-transition

**Summary:** FR opened (escalated from VQE FR closure observation, Tyler approved)

**Details:** see Tyler's request + diagnosis above. Pending branch + handoff to ⟨ψ⟩quantum-orchestrator.

**Next:** ⊕workspace-ci create branch + draft PR; ⟨ψ⟩quantum-orchestrator implement.

---

## Artifacts

(populated as work progresses)

### 2026-04-30T03:00:00Z — ⊕workspace-overseer

**Event:** state-transition

**Summary:** OPEN → BRANCHED → MERGED → CLOSED (batched with dashboard-gitignore chore)

**Details:**
- Branch `chore/quantum/skip-slow-tests` created off Quantum/main (post VQE merge 9b8df2e)
- Worktree at `F:\worktrees\quantum-skip-slow`
- Implementation: `addopts = -v --tb=short -m "not slow"` in pytest.ini
- Verified: `pytest --collect-only` shows "1 deselected" for `test_lih_chemical_accuracy`
- PR #13 squash-merged at 69475a6
- Tyler approved as part of overseer batch ("ya")

**AC verification:**
- AC1 ✅ test_lih deselected by default
- AC2 ✅ `-m "not slow"` in addopts
- AC3 ✅ `pytest -m slow` opt-in path preserved
- AC4 ✅ runtime drops from 525s to ~5s
- AC5 ✅ inline pytest.ini comment block

**Next:** ledger close, registry archive.
