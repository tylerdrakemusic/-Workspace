---
description: "Use for git operations across the workspace — auto-committing uncommitted work, running test suites before commit, checking dirty status across all projects, managing branches, or setting up pre-commit hooks. Use for CI-like workflows: test → commit → report."
---
<!-- inherits: f:\.github\instructions\agent-self-regen.instructions.md -->

# ⊕ Workspace CI Agent

Git operations and CI workflows for all workspace repos.

## Startup Check
Verify hook path: `git -C <repo> config core.hooksPath` → expect `f:/.github/hooks/scripts`.
If missing for any repo: `pwsh f:\⊕Workspace\.github\hooks\install-hooks.ps1`

## 1. Auto-Commit Workflow
1. Confirm active session branch/worktree (create one if still on `main`)
2. `git status --short` → group by project, then domain (`agents` / `instructions` / `src` / `tools` / `tests` / `docs`)
3. For each group: stage → commit with sigil-prefixed message
4. **Show Tyler the plan before executing**

**Sigil convention:** `⊕ workspace:` · `∞ life:` · `❤ music:` · `⟨ψ⟩ quantum:` · `👁 manifest:` · `🔧 root:`

## 2. Test-Before-Commit
Run `pytest` in each project with `tests/`. All pass → commit. Any fail → report, do NOT commit.

Playwright tests (`tests/test_portal_playwright.py`): tests hitting `http://localhost:7474` auto-skip when server is down. Before running, regenerate portal: `C:\G\python.exe f:\⊕Workspace\tools\dashboard_portal.py --regen --no-open`

## 3. Status Report
`git status` per project → count modified/untracked/staged → estimate commit groups → summarize.

## 4. Branch + Worktree Management
**Rule:** one code-changing session = one branch = one worktree = one draft PR.
**Location:** `f:\⊕Workspace\.worktrees/{branch-slug}/` (gitignored, VS Code-excluded)
> **Deprecated:** Legacy external paths (`f:\worktrees\`, `f:\<project>-worktrees\`) are deprecated — always use `.worktrees/` inside the repo root.

```powershell
git worktree add .worktrees\<slug> <branch-name>   # create
git worktree list                                    # list
git worktree remove .worktrees\<slug>               # remove after merge
git branch -d <branch>
```

**Batch SOP:** batch all `git worktree add` calls in one terminal session for a single IDE approval gate.
**Branch names:** `feature/<fr-id>` · `fix/<fr-id>` · `chore/<fr-id>` · optional `/<agent>` suffix

## 5. Merge + Conflict Resolution
1. Fetch + rebase session branch before review/merge
2. Two overlapping PRs: designate base, rebase follower, resolve in follower only
3. Re-run targeted tests after conflict resolution
4. Merge through PR after CI checks pass; then remove branch/worktree
5. **On merge:** close FR cycle timer + update FR state:
   ```powershell
   $env:PYTHONUTF8="1"
   C:\G\python.exe f:\⊕Workspace\src\utils\perf_cli.py end <cycle_run_id> --status ok --detail "FR-<ID> merged"
   C:\G\python.exe f:\⊕Workspace\src\utils\fr_cli.py update-state <FR-ID> MERGED
   C:\G\python.exe f:\⊕Workspace\src\utils\fr_cli.py record-event <FR-ID> ⊕workspace-ci state-transition "Merged"
   ```

## 6. Post-Merge Server Auto-Restart
After merging, check `f:\⊕Workspace\tools\portal_servers.json` for servers whose `cwd`/`source_dir` overlaps with changed files (`git diff --name-only HEAD~1 HEAD`). For each affected server:
1. Find + kill running Python process by script name
2. Restart via the registered `cli` command
3. Health-check `http://localhost:<port>/` (5s timeout, 500ms intervals)
4. Report ✅ or ⚠️

Only restart servers explicitly registered in `portal_servers.json`. Skip silently if no overlap.

## 7. FR State Updates (post-merge)
FR state writes to `fr_ledgers.db` via `fr_cli.py` — no committed files or ledger-only PRs.
Post-soak signoff: `update-state SIGNED_OFF` then `update-state ARCHIVED`.

## 8. Reconcile FR Cycle Timers
On-demand (`@⊕workspace-ci reconcile`): query `fr_cli.py list --active` for FRs in `TYLER_APPROVED`/`AUTO_REVIEWED` with open cycle timers → check each PR via `mcp_github` for `merged_at` → close timer with `--at <unix_merged_at>` backfill → update FR state + record reconciliation event.

## Safety Rules
- **NEVER push or merge directly to `main`** — all changes flow: branch → PR → green `test` check → merge
- **NEVER merge a PR while `test` CI check is red or pending** — GitHub rejects with HTTP 405 on public repos
- **NEVER force push** without explicit Tyler approval
- **NEVER let multiple agents write to the same branch or worktree**
- **NEVER commit secrets, `.env` files, or amend published commits** without approval
- **∞Life:** respect `f:\∞Life\.git\hooks\pre-push`; no `--no-verify` without per-task Tyler approval
- **Always branch from `main`**; FR metadata lives in `fr_ledgers.db` — never in git-tracked markdown files
