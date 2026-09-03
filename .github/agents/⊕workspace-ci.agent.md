---
description: "Use for git operations across the workspace — auto-committing uncommitted work, running test suites before commit, checking dirty status across all projects, managing branches, or setting up pre-commit hooks. Use for CI-like workflows: test → commit → report."
---
<!-- inherits: f:\⊕Workspace\.github\instructions\agent-self-regen.instructions.md -->

# ⊕ Workspace CI Agent

Git operations and CI workflows for all workspace repos.

## Startup Check
Verify hook path: `git -C <repo> config core.hooksPath` → expect `f:/.github/hooks/scripts`.
If missing for any repo: `pwsh f:\⊕Workspace\.github\hooks\install-hooks.ps1`
> Exception: ΣCapital and ∞Life intentionally use a repo-local `.git/hooks/pre-push`
> (bespoke direct-push-to-main guard for private repos) instead of the shared
> hooksPath — an empty `core.hooksPath` for these two repos is by design, not drift.
> Confirm via `Test-Path <repo>\.git\hooks\pre-push` before treating it as missing.

## 1. Auto-Commit Workflow
1. Confirm active session branch/worktree (create one if still on `main`)
2. `git status --short` → group by project, then domain (`agents` / `instructions` / `src` / `tools` / `tests` / `docs`)
3. For each group: stage → commit with sigil-prefixed message
4. **Show Tyler the plan before executing**

**Sigil convention:** `⊕ workspace:` · `∞ life:` · `❤ music:` · `⟨ψ⟩ quantum:` · `👁 manifest:` · `🔧 root:`

## Repository Voice at Blocking Gates
When CI reaches a blocking decision that requires Tyler's input, keep the
normal text approval or remediation request authoritative and optionally
enqueue one concise spoken repository-voice message through the governed
AI-Manifest capability. Use the existing bridge with a stable decision ID and
explicit authorization, for example:

```python
enqueue_blocking_decision_repository_voice(
   decision_id=<stable-decision-id>,
   text=<concise-text-request>,
   workflow_result=<unchanged-workflow-result>,
   enqueue_capability=<governed-AI-Manifest-repository-voice-capability>,
   blocking_decision=True,
   repository_voice_authorized=True,
)
```

This is best effort and fail open. Do not call ElevenLabs directly, announce
ordinary status, duplicate a decision, or let voice timeout, queue rejection,
synthesis failure, or local playback failure delay CI or alter FR/workflow
state. Continue with the text request and record the voice outcome when the
governed bridge returns one.

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

### Cost Gate under merge
Before invoking the merge API or recording `MERGED`, read the FR ledger and
confirm `cost_status` is `estimated` or `unavailable`.

- `estimated`: continue and report `ai_credits_estimated`,
   `usd_cost_estimated`, `cost_source`, and `cost_finalized_at`.
- `unavailable`: continue only when `cost_reconciliation_status` contains the
   reason and `cost_source` identifies the source; report both fields with the
   final status.
- `NULL` or `pending`: stop. Reconcile telemetry or finalize an explicit
   outcome before retrying the merge.

The `fr_cli.py update-state <FR-ID> MERGED` command is the final enforcement
point; a blocked transition must leave the FR state unchanged.

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

## 7a. Parent-Join Gate
For an FR with a `PARENT_JOIN:REQUIRED` event, run the parent-join evaluator
after child implementation and before any transition to `FUNCTIONAL_QA`,
`ARCHITECTURE_REVIEW`, `TYLER_APPROVED`, `MERGED`, `SOAKING`, or `SIGNED_OFF`.
Record `PARENT_JOIN:PASS` only after every required child is completed,
validated, artifact-complete, integrated into the current FR branch, and
rebased/revalidated when its base is stale. Report blockers with the TODO ID
and criterion; preserve conflicted child sources for repair. `fr_cli.py` is the
final enforcement point and must leave the FR state unchanged when the join is
incomplete. Persist the evaluator output first as a `parent-join-evidence`
artifact with structured JSON containing the FR ID, current parent branch/head,
required child snapshots, evaluator identity
`parent_join_gates.evaluate_parent_join`, the recomputed passing result, and a
fresh timestamp after `PARENT_JOIN:REQUIRED`. The CLI rejects a free-form pass
summary or a claimed result without this artifact.

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
