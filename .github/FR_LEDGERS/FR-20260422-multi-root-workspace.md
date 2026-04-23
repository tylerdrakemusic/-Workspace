# FR-20260422-multi-root-workspace — Adopt Multi-Root VS Code Workspace

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260422-multi-root-workspace
- **Title:** Adopt Multi-Root VS Code Workspace (`.code-workspace`)
- **Type:** chore (tooling / editor config)
- **Risk:** medium (changes how Tyler opens the workspace; affects all agent-file discovery)
- **Projects:** ⊕Workspace (primary); indirectly all 5 projects via the workspace file
- **State:** REVIEW_REQUESTED
- **Branch:** `chore/FR-20260422-multi-root-workspace` (worktree: `f:\⊕Workspace-worktrees\FR-20260422-multi-root-workspace\`)
- **PRs:** [#3](https://github.com/tylerdrakemusic/-Workspace/pull/3) (draft, commit `4e0d5b6`)
- **Cycle timer:** a430da3a-6590-4318-8c37-843d8f146a78
- **Opened:** 2026-04-22
- **Last updated:** 2026-04-22
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. A `.code-workspace` file exists that, when opened in VS Code, yields the same multi-project view Tyler currently gets by opening `f:\`.
2. When opened via the `.code-workspace` file, VS Code auto-loads `copilot-instructions.md`, `instructions/*.instructions.md`, `agents/*.agent.md`, and `skills/*/SKILL.md` from the git-tracked `f:\⊕Workspace\.github\` tree (NOT from `f:\.github\`).
3. There is only one canonical, git-tracked `.github/` tree in use after migration.
4. `f:\.github\` is either deleted or archived to `f:\.github.deprecated\` — it is no longer a live discovery path.
5. The `.code-workspace` file works identically when the workspace is cloned onto macOS (no Windows-specific paths, no reparse points, no platform-specific glue required).
6. All 5 project folders (`∞Life`, `❤Music`, `⟨ψ⟩Quantum`, `👁AI-Manifest`, `⊕Workspace`) are visible as roots in the VS Code Explorer.
7. FR registry/ledger reads and agent-discovery smoke tests pass from a fresh VS Code session opened via the workspace file.

### Concurrency Notes
- Conflicts with: none (editor config only).
- Depends on: FR-20260422-github-dir-reconcile (MERGED_PARTIAL — tracked copy is current).
- **Blocks:** FR-20260422-sigil-encoding-map.

### Supersedes
- FR-20260422-github-dir-reconcile Phase 2 (junction swap) + Phase 3 (README cross-platform docs). Those phases were infeasible because F: is exFAT (NTFS reparse points unsupported). Multi-root workspace achieves the same goal (single canonical `.github/` that VS Code auto-loads and git tracks) without any filesystem reparse points.

### Open Scope Questions for Tyler
1. **Post-migration disposition of `f:\.github\`:** delete outright, or archive to `f:\.github.deprecated\` for a grace period?
2. **Workspace file location:** `f:\workspace.code-workspace` (sits at drive root alongside project folders) or `f:\⊕Workspace\workspace.code-workspace` (lives inside the tracked repo)?
3. **Commit to git:** should the `.code-workspace` file be committed to the ⊕Workspace repo (portable, shareable across machines — e.g. when cloned on macOS) or kept local/untracked?

### Tyler's Original Intent
> Adopt a multi-root VS Code workspace so `⊕Workspace/.github/` becomes the auto-loaded agent tree. Eliminates the dual-dir problem without needing filesystem junctions. Works on exFAT and on macOS out of the box. Replaces the failed junction-swap approach from FR-20260422-github-dir-reconcile.

---

## Event Log

### 2026-04-22 — ⊕workspace-overseer

**Event:** state-transition

**Summary:** FR opened → TRIAGED. Succeeds FR-20260422-github-dir-reconcile Phase 2/3.

**Details:**
- Created to unblock FR-20260422-sigil-encoding-map after the junction-based reconcile approach was killed by exFAT.
- Scope drafted; 3 scope questions queued for Tyler (see Header).
- No branch yet; awaiting scope confirmation before CI handoff.

**Next:** Tyler answers the 3 scope questions → hand off to ⊕workspace-ci for branching.

---

### 2026-04-22 — ⊕workspace-overseer

**Event:** state-transition

**Summary:** TRIAGED → BRANCHED → IN_PROGRESS → REVIEW_REQUESTED.

**Details:**
- Tyler approved scope: (1) dispose of `f:\.github\` outright, (2) workspace file inside tracked repo at `⊕Workspace/workspace.code-workspace`, (3) commit to git.
- Worktree created: `f:\⊕Workspace-worktrees\FR-20260422-multi-root-workspace\`. Branch `chore/FR-20260422-multi-root-workspace` from `origin/main` (`2b9e612`).
- Implemented Phase 1: created `workspace.code-workspace` with 5 folders (⊕Workspace primary; ∞Life, ❤Music, ⟨ψ⟩Quantum, 👁AI-Manifest as siblings via `../` relative paths — cross-platform).
- Added minimal settings: `files.encoding: utf8`, `files.autoGuessEncoding: false` to preempt sigil encoding issues.
- Committed `4e0d5b6`, pushed to origin.
- Draft PR #3 opened: https://github.com/tylerdrakemusic/-Workspace/pull/3

**Security note:** during PR creation, git credential helper printed a GitHub token to terminal output (token value REDACTED; rotated by Tyler 2026-04-22). Root cause: no `gh` CLI available, no `GITHUB_TOKEN` env var, fell back to `git credential fill` which prints the password line to stdout. Recommend: install `gh` CLI or set `GITHUB_TOKEN` env var to avoid this path in future FRs.

**Next:** reviewer agent / Tyler gateway #3 → approve + merge → Phase 2 manual migration by Tyler.

---

## Artifacts

- **Perf runs:**
  - `a430da3a-6590-4318-8c37-843d8f146a78` — FR cycle timer (active)
- **PRs:** [#3](https://github.com/tylerdrakemusic/-Workspace/pull/3) (draft)
- **Commits:** `4e0d5b6` (Phase 1)
- **Reports / dashboards:** N/A
