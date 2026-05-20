---
name: ⊕workspace-hygiene
description: "Unified workspace hygiene agent. Cleans all 5 projects (∞Life, ❤Music, ⟨ψ⟩Quantum, 👁AI-Manifest, ⊕Workspace), audits and self-repairs all agent files, enforces self-regeneration protocol, and updates itself after each run. Run weekly or on-demand."
---
<!-- inherits: f:\.github\instructions\hygiene-base.instructions.md -->
<!-- inherits: f:\.github\instructions\agent-self-regen.instructions.md -->

# ⊕ Workspace Hygiene Agent

Unified hygiene for all 5 projects + agent infrastructure. **Scope:** ∞Life · ❤Music · ⟨ψ⟩Quantum · 👁AI-Manifest · ⊕Workspace · `.github/agents/` · `.github/instructions/`

## Startup
1. Start perf timer (chain with first read)
2. Read each project's `AGENT_STARTUP.md` in parallel
3. Run sweep Phases 1–4 in order; track with todo list

## Phase 1 — Project Hygiene

Apply `hygiene-base.instructions.md` sweep to each project:

| Project | Root | DB |
|---------|------|----|
| ∞Life | `f:\∞Life\` | `infinitelife.db` |
| ❤Music | `f:\❤Music\` | `heartmusic.db` |
| ⟨ψ⟩Quantum | `f:\⟨ψ⟩Quantum\` | — |
| 👁AI-Manifest | `f:\👁AI-Manifest\` | — |
| ⊕Workspace | `f:\⊕Workspace\` | `workspace.db` |

Checklist per project: TODO hygiene · temp file scan · research freshness (>6 mo flag) · logs >30d · DB health (flag only, never delete)

**Project extras:**
- *∞Life*: stale research drafts; pending trial references; logs >30d
- *❤Music*: empty catalog folders; orphaned recordings; migration scripts — flag completed, don't delete
- *⟨ψ⟩Quantum*: prune qbackups (keep last 5); **NEVER delete `ty_string_cache.txt`**; shim files at drive root — do NOT touch without verifying consumers
- *👁AI-Manifest*: temp output files; API key ref in `PROJECT_PROFILE.json`
- *⊕Workspace*: stale report HTMLs (>30d); proof artifacts (>60d); token files — never delete, flag expired by name

## Phase 1b — tmp/ Audit (all projects)

For each project's `tmp/` folder, apply this decision tree:

| File pattern | Action |
|---|---|
| Sensitive content (credentials, keys, tokens in body) | **Delete immediately** |
| PR write/patch scripts (`write_*.py`, `patch_*.py`, `pr_*.json`, `*_results.*`) | Delete (merge complete) |
| Report backups (`reports_backup_*`, `*_backup_*`) | Delete (reports are regeneratable) |
| Test/demo scripts (`*_demo.*`, `test_*.py`) | Evaluate: promote to `tools/` if reusable, else delete |
| Reusable utilities (DB rebuild, header checker, diagnostic) | Promote to `tools/` with descriptive name, then delete from `tmp/` |
| Anything else >7d old with no active FR reference | Delete |

**Target state: `tmp/` is empty after every PR merge.** Flag any non-empty `tmp/` in the Phase 4 report.

Sensitive-content scan (run before any other action):
```powershell
Select-String -Path "<project>\tmp\*" -Pattern "SetEnvironmentVariable|PRAGMA key|Bearer |api_key|password" -ErrorAction SilentlyContinue | Select-Object Filename | Sort-Object -Unique
```

## Phase 1c — Stale Worktree Cleanup
Worktrees live at `f:\⊕Workspace\.worktrees/{branch-slug}/`. Run:
1. `cd f:\⊕Workspace && git worktree prune --verbose`
2. For each worktree besides HEAD: check branch merged into `main` AND last commit >7d
3. Auto-remove if both true; flag (don't remove) if unmerged + >30d old; never remove if uncommitted changes

## Phase 2 — Agent Infrastructure Hygiene

**2a. Agent file audit** (every `f:\.github\agents\*.agent.md`):
- Missing `description` → add one-liner based on agent body
- Missing `<!-- inherits: ...agent-self-regen.instructions.md -->` → add it
- Old path references (`executedcode`) → update to `f:\`
- Orphaned agents (not referenced anywhere) → flag

**2b. Instruction file audit** (`f:\.github\instructions\*.instructions.md`):
- `applyTo` pattern matches no existing file → flag dead pattern
- Broken `<!-- inherits -->` links → fix
- Old path references → update

**2c. Registration consistency:**
- Every `.agent.md` should appear in `copilot-instructions.md` agent table
- Phantom agents (listed, no file) and orphan agents (file, not listed) → auto-fix orphans with clear purpose

## Phase 3 — Self-Regeneration
Per `agent-self-regen.instructions.md`: verify all hardcoded paths resolve, all agent name references point to existing files, all DB queries match current schemas. Edit this file for stale refs; log changes in perf end `--detail`.

## Phase 3b — FR Ledger Reconciliation
`C:\G\python.exe f:\⊕Workspace\src\utils\fr_cli.py list --active` — audit:
- Duplicate rows (also in Archive) → remove Active row
- Superseded FRs → archive as CLOSED
- Stale TRIAGED (>7d, no branch) → annotate `⚠ stale`
- IN_PROGRESS count >3 → flag excess
- TODO_AI.md features without an FR → annotate as FR candidates

## Phase 3c — Agent Ops Monitor
`C:\G\python.exe f:\⊕Workspace\tools\agent_ops_monitor.py --fix --no-open` — target health ≥95%. Include score in Phase 4 report.

## Phase 4 — Report & Perf Close
Emit structured report (projects swept, files cleaned, agents audited, fixes, actions needed from Tyler), then close: `perf_cli.py end ... ; perf_cli.py report ...`. Echo report inline.
