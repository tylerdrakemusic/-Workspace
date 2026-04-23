# FR-20260422-github-dir-reconcile — Reconcile Divergent `.github/` Directory Trees

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260422-github-dir-reconcile
- **Title:** Reconcile Divergent `.github/` Directory Trees (workspace root vs ⊕Workspace repo)
- **Type:** chore (infrastructure / source-of-truth reconciliation)
- **Risk:** high (touches agent framework discovery path + git tracking of the entire agent surface)
- **Projects:** ⊕Workspace (tracked repo) + workspace-root `.github/` (VS Code discovery path)
- **State:** BRANCHED
- **Branch:** `chore/FR-20260422-github-dir-reconcile` (worktree: `f:\⊕Workspace-worktrees\FR-20260422-github-dir-reconcile\`)
- **PRs:** [#2](https://github.com/tylerdrakemusic/-Workspace/pull/2) (draft)
- **Cycle timer:** 4a30bc0e-fe8e-48bd-b8ca-448115fede0d
- **Opened:** 2026-04-22
- **Last updated:** 2026-04-22
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. There is exactly ONE canonical `.github/` tree on disk. All edits land in the same place VS Code reads from.
2. The canonical tree is git-tracked in the `⊕Workspace` repo (`tylerdrakemusic/-Workspace`) so history is preserved.
3. VS Code continues to auto-load `copilot-instructions.md`, `instructions/*.instructions.md`, `agents/*.agent.md`, and `skills/*/SKILL.md` from `f:\.github\` without behavior change.
4. All divergent content is reconciled with `f:\.github\` as the winner (it is the live-edited tree that agents have been running against).
5. Stale artifacts removed: per-project hygiene agents in `⊕Workspace\.github\agents\` (`∞life-hygiene`, `❤music-hygiene`, `⟨ψ⟩quantum-hygiene`, `👁ai-manifest-hygiene`) are superseded by the unified `⊕workspace-hygiene.agent.md` and must not reappear after reconciliation.
6. New content present only in `f:\.github\` is preserved: `FEATURE_REQUESTS.md`, `FR_LEDGERS/`, `workflow-templates/`, `agent-self-regen.instructions.md`, `feature-request-flow.instructions.md`, `⊕workspace-hygiene.agent.md`, `⊕workspace-intake.agent.md`, `⊕workspace-reviewer.agent.md`.
7. macOS / cross-platform note documented: how a fresh clone reproduces the layout (symlink on \*nix, directory junction on Windows, or a post-clone script).
8. After reconciliation, editing any file under the canonical path appears as an unstaged change in `git status` run inside `f:\⊕Workspace\`.
9. All 5 project orchestrators + ⊕workspace agents still load successfully (smoke test: VS Code reload + one agent invocation).
10. FR-20260422-sigil-encoding-map is unblocked and its target path (`f:\.github\instructions\sigil-encoding.instructions.md`) resolves to a path inside the ⊕Workspace repo.

### Concurrency Notes
- **Conflicts with:** FR-20260422-remove-service-label-field (touches `⊕Workspace/src/` only — no `.github/` overlap, but shares the ⊕Workspace repo; should serialize the merge to avoid branch rebase pain on top of a tree-move). FR-20260422-band-mgmt-panel is REVIEW_REQUESTED inline on main and also touches ⊕Workspace — wait for it to close before cutting this branch.
- **Blocks:** FR-20260422-sigil-encoding-map (cannot create tracked instruction file until canonical path is git-tracked).
- **Depends on:** none.

### Tyler's Original Request
> Reconcile the divergent `.github/` directory trees in the workspace.
>
> - `f:\.github\` exists and is what VS Code actually loads for copilot-instructions, instructions files, agent definitions, and skills. It is NOT inside any git repo.
> - `f:\⊕Workspace\.github\` exists and IS git-tracked (remote: `tylerdrakemusic/-Workspace`).
> - The two directories are genuinely divergent — not a symlink, not a junction.
> - Changes made to `f:\.github\` are invisible to git; changes committed to `f:\⊕Workspace\.github\` are invisible to VS Code. Any workspace-level agent/instructions/skills work is at risk of drift.
>
> This is a BLOCKER for FR-20260422-sigil-encoding-map.

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-04-22 — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, triage complete → TRIAGED. Marked as BLOCKER for FR-20260422-sigil-encoding-map.

**Details:**
- **Divergence confirmed.** `f:\.github\` is a plain directory (no reparse point); `f:\⊕Workspace\.github\` is a plain tracked directory in the ⊕Workspace repo. Genuinely two independent trees.
- **High-level diff (count-level, not content-level — full diff deferred to implementation):**
  - **Files only in `f:\.github\`:** `FEATURE_REQUESTS.md`, `FR_LEDGERS/` (entire dir, 8 files), `workflow-templates/` (entire dir), `instructions/agent-self-regen.instructions.md`, `instructions/feature-request-flow.instructions.md`, `agents/⊕workspace-hygiene.agent.md`, `agents/⊕workspace-intake.agent.md`, `agents/⊕workspace-reviewer.agent.md`.
  - **Files only in `f:\⊕Workspace\.github\`:** `agents/∞life-hygiene.agent.md`, `agents/❤music-hygiene.agent.md`, `agents/⟨ψ⟩quantum-hygiene.agent.md`, `agents/👁ai-manifest-hygiene.agent.md` (all superseded by unified `⊕workspace-hygiene.agent.md` per `copilot-instructions.md`).
  - **Files differing in content (SHA-256 mismatch):** `copilot-instructions.md` + **25 agents** + **4 instructions** (`∞life-base`, `∞life-python`, `❤music-base`, `⟨ψ⟩quantum-base`).
  - **Identical:** `skills/scope-creep/`, remaining agents/instructions, `hooks/`, `tools/`, `!!☾⛧security/` (not individually hashed but top-level structure matches).
- **Winner for conflicts:** `f:\.github\` — it is the tree VS Code actually reads, it contains the FR-flow infrastructure (registry + ledgers + templates) referenced throughout `copilot-instructions.md`, and its agents reference instructions files (`agent-self-regen`, `feature-request-flow`) that don't exist in the ⊕Workspace tracked copy. The tracked copy is stale.
- **Concurrency:** active FRs in `⊕Workspace` repo: `FR-20260422-remove-service-label-field` (TRIAGED, no .github/ overlap), `FR-20260422-band-mgmt-panel` (REVIEW_REQUESTED inline on main — completes before this FR branches). Serialization plan: this FR waits until band-mgmt-panel closes, then cuts branch; remove-service-label-field can rebase onto it if needed.
- Proposed reconciliation options presented to Tyler below.

**Next:** awaiting Tyler: **approve scope + pick reconciliation option**

---

### 2026-04-22 — ⊕workspace-ci

**Event:** state-transition

**Summary:** Scope approved by Tyler (Option A, all 5 questions answered). Branch + worktree + draft PR opened. TRIAGED → BRANCHED.

**Details:**
- Branch `chore/FR-20260422-github-dir-reconcile` cut from `origin/main` @ `2e29eba`.
- Dedicated worktree: `f:\⊕Workspace-worktrees\FR-20260422-github-dir-reconcile\` (isolates from concurrent `chore/workspace/remove-service-label-field` worktree at the main ⊕Workspace checkout).
- Scaffold commit `308d032` (empty, allows draft PR creation before implementation begins).
- Draft PR #2 opened: https://github.com/tylerdrakemusic/-Workspace/pull/2
- Perf run (ci-branch): `a6d1e47a-a306-4845-b8f2-bf840a72424e`.
- Handoff: overseer takes implementation inside the worktree.

**Next:** ⊕workspace-overseer to execute Phase 1 (sync + git rm + adds) in the worktree.

---

## Artifacts

- **Perf runs:**
  - `4a30bc0e-fe8e-48bd-b8ca-448115fede0d` — FR cycle timer (intake → close)
  - `a6d1e47a-a306-4845-b8f2-bf840a72424e` — ci-branch-fr-github-dir-reconcile
- **Proof artifacts:** pending
- **PRs:** [#2](https://github.com/tylerdrakemusic/-Workspace/pull/2) (draft)
- **Commits:** `308d032` (scaffold, empty)
- **Reports / dashboards:** pending

---

## Reconciliation Strategy Options (for Tyler)

### Option A — **Canonicalize on `f:\⊕Workspace\.github\` via directory junction** ⭐ RECOMMENDED

**Steps (executed by implementation agent on a branch):**
1. On branch `chore/FR-20260422-github-dir-reconcile` in ⊕Workspace worktree:
   - Copy every file from `f:\.github\` → `f:\⊕Workspace\.github\` where `f:\.github\` wins (all 25 divergent agents, 4 instructions, copilot-instructions.md).
   - Add net-new files: `FEATURE_REQUESTS.md`, `FR_LEDGERS/**`, `workflow-templates/**`, 2 new instructions, 3 new agents.
   - `git rm` the 4 superseded per-project hygiene agents.
   - Commit, open draft PR.
2. Tyler approves PR + merges.
3. Post-merge (⊕workspace-ci final step):
   - Back up `f:\.github\` → `f:\.github.backup-FR-github-dir-reconcile\`.
   - Delete `f:\.github\`.
   - Create directory junction: `cmd /c mklink /J "f:\.github" "f:\⊕Workspace\.github"`.
   - Smoke test: open VS Code, verify `copilot-instructions.md` loads, verify one agent invocation works.
   - Delete backup after 24h soak.
4. Document in ⊕Workspace `README.md`: post-clone setup step for Windows (junction) and macOS/Linux (symlink: `ln -s ./⊕Workspace/.github ./.github`). Optionally add a bootstrap script.

**Pros:** single source of truth, git-tracked, zero changes to VS Code config, preserves ⊕Workspace history.
**Cons:** requires one-time OS-specific bootstrap step on fresh clones (junction on Windows, symlink on \*nix). Script makes this trivial.

### Option B — **Canonicalize on `f:\.github\` by init'ing a new repo or moving `.github/` out of ⊕Workspace**

Either (B1) init a new workspace-root repo that owns `f:\.github\`, or (B2) `git mv` `.github/` out of ⊕Workspace to a different tracked location that VS Code can still find.

**Pros:** no symlink/junction needed.
**Cons:** B1 introduces a 6th repo to maintain (doesn't match the "5 projects" model documented everywhere). B2 breaks ⊕Workspace history for the `.github/` tree and VS Code only auto-discovers `.github/` at the workspace root — moving it breaks discovery. Larger blast radius either way. **Not recommended.**

### Option C — **Keep both dirs, add a sync mechanism (git hook / file watcher / rsync)** — REJECTED

Fragile, doubles the surface area, creates a race condition on every edit, and violates "one source of truth." Tyler already flagged this as reject-worthy. **Do not pursue.**

---

## Scope Questions for Tyler

Before I route this to `⊕workspace-ci` for branch creation, confirm:

1. **Pick option:** A (recommended), B, or reject B/C only and stick with A?
2. **Winner confirmed:** `f:\.github\` is the conflict winner for all 29 divergent files and the 4 stale per-project hygiene agents in ⊕Workspace are deleted. Correct? (If you want to preserve any of those 4 as archive, say so now.)
3. **Serialize or concurrent:** do you want this to wait for `FR-20260422-band-mgmt-panel` (REVIEW_REQUESTED) and `FR-20260422-remove-service-label-field` (TRIAGED) to merge first, or should it run concurrently with them (both only touch `⊕Workspace/src/`, no `.github/` overlap, but rebase pain is possible)?
4. **Backup retention:** keep `f:\.github.backup-*\` for 24h post-switch, or delete immediately after smoke test?
5. **Cross-platform bootstrap:** want a committed `⊕Workspace/tools/bootstrap-github-link.{ps1,sh}` script, or plain README instructions?
