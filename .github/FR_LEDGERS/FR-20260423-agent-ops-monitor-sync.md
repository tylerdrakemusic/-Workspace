# FR-20260423-agent-ops-monitor-sync — Reconcile agent ops monitor with current workspace architecture and improve portal visibility

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260423-agent-ops-monitor-sync
- **Title:** Reconcile agent ops monitor with current workspace architecture and improve portal visibility
- **Type:** fix
- **Risk:** medium
- **Projects:** ⊕Workspace
- **State:** BRANCHED
- **Branch:** fix/FR-20260423-agent-ops-monitor-sync (worktree: F:\worktrees\FR-20260423-agent-ops-monitor-sync)
- **PRs:** https://github.com/tylerdrakemusic/-Workspace/pull/7 (draft)
- **Cycle timer:** 2624f477-2cb7-41de-86b3-670330623ef8
- **Opened:** 2026-04-23
- **Last updated:** 2026-04-23
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. A path-remediation migration (in `tools/agent_ops_monitor.py` or new `tools/agent_ops_migrate.py`) rewrites stale `proof_artifacts.artifact_path` entries: `f:/executedcode/<sigil>X/...` → `f:\<sigil>X\...`, `!!security` → `!!☾⛧security`, and normalizes agent names missing sigil prefix (`workspace-*` → `⊕workspace-*`). Re-verification pass runs after rewrites.
2. Legacy run closure is wired into `--fix`: `backfill_legacy` auto-closes pre-proof-system runs with `status=legacy` and a backfilled metric proof noting "predates proof system".
3. `render_dashboard()` shows a top banner with `Live sessions (last 10min) · Recent (24h) · Historical total`, an "Architecture Drift" section listing unverified proofs with bad paths + suggested fix, and a one-click "Apply migration" action in `--serve` mode.
4. `reports/portal.html` surfaces the agent-ops health score prominently with a freshness indicator.
5. `tests/test_agent_ops_monitor.py` covers: path rewriter, legacy backfill wiring into `--fix`, and health score calculation on a fixture DB.
6. After migration runs once on the live DB, the unverified-proof count drops for all path-fixable entries; remaining unverified items are genuinely missing artifacts.
7. `tools/fr_status.py` CLI reads all `.github/FR_LEDGERS/*.md`, parses the Deliverable Tracker + Header, and prints a workspace-wide dashboard of in-flight FRs grouped by owner/agent and state. Supports `--json` and `--agent <name>` filters.

### Concurrency Notes
- Conflicts with: none (playwright-mcp-setup touches `.vscode/mcp.json`; disable-plumbing-agents-dropdown touches agent frontmatter — no file overlap with `tools/agent_ops_monitor.py`, `src/data/workspace.db`, `reports/`, `tests/`).
- Depends on: none.

### Deliverable Tracker

<!-- Mutable table. Agents flip their own row's Status + Proof + Updated in place.
     Status vocab: not-started → in-progress → blocked → done → verified.
     Proof column: proof_artifact id (from proof_cli) or PR comment URL. -->

| #   | Deliverable                                                                        | Owner                 | Status      | Proof | Updated |
| --- | ---------------------------------------------------------------------------------- | --------------------- | ----------- | ----- | ------- |
| AC1 | Path/name migration (rewrite stale `artifact_path`, normalize agent sigils)        | ⊕workspace-doer       | done        | 73dadbf47fdb | 2026-04-23 |
| AC2 | Wire `backfill_legacy` into `--fix` with `status=legacy` + backfilled metric proof | ⊕workspace-doer       | done        | 73dadbf47fdb | 2026-04-23 |
| AC3 | Dashboard: live/recent/historical banner + Architecture Drift + migration button   | ⊕workspace-doer       | done        | 73dadbf47fdb | 2026-04-23 |
| AC4 | Portal surfaces agent-ops health score with freshness indicator                    | ⊕workspace-dashboards | not-started | —     | —       |
| AC5 | `tests/test_agent_ops_monitor.py` fixture coverage                                 | ⊕workspace-doer       | done        | cc6c6f3e439f / e4430386f0c0 | 2026-04-23 |
| AC6 | Post-migration verification — unverified-proof count drops on live DB              | ⊕workspace-reviewer   | not-started | —     | —       |
| AC7 | `tools/fr_status.py` CLI — workspace-wide FR dashboard from ledgers                | ⊕workspace-doer       | done        | d54d2c092e9f | 2026-04-23 |

### 
### Tyler's Original Request
> "let's shore up the agent ops monitor through portal. I see 48 runs in session inventory but only 2 including yourself in session view in vscode, what is the existing gap and unverified agent, we need to sync it to current project architecture"

### Out of Scope (deferred to future FRs)
- Real-time websocket/SSE to the portal
- VS Code extension integration to detect live chat sessions
- Cross-project proof schema changes

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-04-23T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, triage complete → TRIAGED

**Details:**
- Scope: ⊕Workspace only (tools, src/data, reports, tests)
- Acceptance criteria drafted (see Header)
- Concurrency check: clean — no file overlap with in-flight FRs (FR-20260422-playwright-mcp-setup, FR-20260422-disable-plumbing-agents-dropdown)
- Root-cause analysis gathered via `agent_ops_monitor.py --json`:
  - Stale artifact paths (`f:/executedcode/❤Music/...`) predate flat project layout
  - Stale folder references (`!!security` → `!!☾⛧security` rename not propagated)
  - Agent name drift (legacy rows missing sigil prefix)
  - `backfill_legacy` function exists but not wired into `--fix`
  - Dashboard conflates historical DB rows with live VS Code sessions
- Cycle timer started: 2624f477-2cb7-41de-86b3-670330623ef8

**Next:** awaiting Tyler: approve scope

---

### 2026-04-23T00:30:00Z — ⊕workspace-overseer

**Event:** state-transition

**Summary:** Tyler approved scope + AC7 addition → SCOPE_APPROVED

**Details:**
- Tyler approved the Deliverable Tracker revision and requested AC7 (`fr_status.py` CLI) as more scalable than per-FR tracker maintenance alone.
- Added AC7 to acceptance criteria and tracker table.
- Amended `.github/FR_LEDGERS/_TEMPLATE.md` so every future FR gets a Deliverable Tracker section.
- State: TRIAGED → SCOPE_APPROVED.

**Next:** handoff to ⊕workspace-ci to cut `fix/FR-20260423-agent-ops-monitor-sync` branch + worktree + draft PR.

---

### 2026-04-23T01:00:00Z — ⊕workspace-ci

**Event:** state-transition

**Summary:** Branch + worktree + draft PR cut → BRANCHED

**Details:**
- Created worktree `F:\worktrees\FR-20260423-agent-ops-monitor-sync` on new branch `fix/FR-20260423-agent-ops-monitor-sync` off `main` (preserves in-flight chore branches in the primary worktree).
- Copied FR-20260423 ledger and amended `_TEMPLATE.md` from primary worktree onto the branch.
- Initial commit `1f0cac0`: `chore(FR-20260423): intake scope approval + deliverable tracker`.
- Pushed `origin/fix/FR-20260423-agent-ops-monitor-sync`.
- Opened draft PR #7: https://github.com/tylerdrakemusic/-Workspace/pull/7
- State: SCOPE_APPROVED → BRANCHED.

**Next:** handoff to ⊕workspace-doer to start AC1 (path-remediation migration).

---

### 2026-04-23T02:30:00Z — ⊕workspace-doer

**Event:** implementation

**Summary:** AC1, AC2, AC3, AC5, AC7 delivered

**Details:**
- **AC1** — Added `rewrite_artifact_path()`, `normalize_agent()`, `migrate_architecture()`, `_backup_db()`, `drift_candidates()` to `tools/agent_ops_monitor.py`. New CLI flags `--migrate` and `--migrate --dry-run`. Backup dir: `src/data/backups/workspace.db.<ts>.bak` (auto-created). Post-migration verification pass re-runs the `Path.exists()` loop so fixable proofs flip to `verified=1`.
- **AC2** — Rewrote `backfill_legacy()` to use the legacy heuristic (orphan + `ended_at` earlier than earliest `proof_artifacts.created_at`). Backfilled proof has `description="predates proof system"`, `proof_type=metric`, `verified=1`. Run status flips to `legacy`. Wired into `fix_gaps()` so `--fix` now auto-backfills legacy orphans and reports `fixed_legacy` in the summary.
- **AC3** — Added top `live-banner` with three cells (Live 10min / Recent 24h / Historical total) driven by new `live_count`/`recent_count`/`historical_total` keys on `collect_health()`. Added "Architecture Drift" section listing unverified proofs matching migration patterns with current vs suggested values side-by-side. Added POST `/apply-migration` endpoint to the `OpsHandler` returning `{status, fixed_paths, fixed_agents, verified_after, backup_path}`. Dry-run + live buttons wired via `applyMigration(dryRun)` JS.
- **AC5** — `tests/test_agent_ops_monitor.py` + `tests/conftest.py` with in-memory sqlite schema mirror. 12 tests covering path rewriter (3 patterns), agent sigil normalization, `backfill_legacy` wiring into `fix_gaps`, legacy-predates-proof heuristic, health score math on known mix, and live/recent/historical counts. `monkeypatch` stubs `_backup_db` to keep tests isolated from live DB.
- **AC7** — `tools/fr_status.py` stdlib-only CLI. Parses Header via `- **Key:** value` regex, tracker rows from `### Deliverable Tracker` (or bare header) markdown table. Flags `--json`, `--agent`, `--state`. `sys.stdout.reconfigure(encoding='utf-8')` for sigil safety.
- Dry-run migration against live DB reports 16 paths to rewrite + 3 agents to rename (no mutation).
- `pytest tests/test_agent_ops_monitor.py -v` → **12 passed in 0.16s**.

**Perf run:** 730b9c00-679a-4deb-8734-f3b9ca417764 (doer implementation).

**Next:** handoff to ⊕workspace-reviewer for AC6 (post-migration verification on live DB) and AC4 (portal freshness indicator — ⊕workspace-dashboards owner).

---

## Artifacts

<!-- APPEND-ONLY. Links to concrete evidence. -->

- **Perf runs:** 2624f477-2cb7-41de-86b3-670330623ef8 — FR cycle timer (intake → merge)
- **Perf runs:** 730b9c00-679a-4deb-8734-f3b9ca417764 — ⊕workspace-doer implementation dispatch
- **Proof artifacts:** 73dadbf47fdb — AC1+AC2+AC3 agent_ops_monitor.py modifications
- **Proof artifacts:** cc6c6f3e439f — AC5 tests/test_agent_ops_monitor.py
- **Proof artifacts:** e6f27aa76706 — AC5 tests/conftest.py
- **Proof artifacts:** d54d2c092e9f — AC7 tools/fr_status.py
- **Proof artifacts:** e4430386f0c0 — AC5 test_pass (12/12)
