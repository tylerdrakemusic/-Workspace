# FR-20260423-agent-ops-live-session-fix — Fix agent ops monitor live session detection — stale closed sessions appearing, active sessions not shown

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260423-agent-ops-live-session-fix
- **Title:** Fix agent ops monitor live session detection — stale closed sessions appearing, active sessions not shown
- **Type:** fix
- **Risk:** medium
- **Projects:** ⊕Workspace
- **State:** CLOSED
- **Branch:** fix/workspace/agent-ops-live-session-fix
- **PRs:** https://github.com/tylerdrakemusic/-Workspace/pull/10
- **Cycle timer:** e1488e85-5257-47b3-aa81-13facb35b8e3
- **Opened:** 2026-04-23
- **Last updated:** 2026-04-23 (CLOSED — retroactive reconciliation)
- **Merged at:** 2026-04-23 (merge SHA 921b891f43d3)
- **Closed:** 2026-04-23
- **Final state:** CLOSED

### Acceptance Criteria

1. **Stale session closed:** Running `agent_ops_monitor.py --fix` (or equivalent auto-heal) marks any session whose `last_heartbeat` is older than the zombie threshold as `ended`; the stale closed session no longer appears in "Live sessions (last 10 min)".
2. **Active sessions visible:** The 2 currently active VS Code Copilot chat sessions (or any session with a `last_heartbeat` within the live window) appear in the "Live sessions" section of the dashboard after a refresh.
3. **Live window query uses `last_heartbeat`:** The "live (last 10 min)" query is confirmed to filter on `last_heartbeat` (not `started_at` or a missing `ended_at` check), and that column is being updated by the heartbeat mechanism.
4. **Zombie threshold documented and correct:** The zombie-close threshold (e.g., no heartbeat for N minutes → session closed) is explicit in code, matches the live window, and is applied *before* the live-count query runs.
5. **Dashboard auto-refreshes correctly:** After the fix, a hard reload of `reports/agent_ops_dashboard.html` shows live session count ≥ 2 (or the true active count) without manual DB surgery.
6. **No regressions:** Existing tests in `tests/` pass; no previously-closed sessions are re-opened by the fix.
7. **Phantom agent purged:** The "ops-monitor" agent name (or any agent name) that appears in proof coverage but has no corresponding `.agent.md` file in `f:\.github\agents\` is identified, its DB rows are either reassigned to the correct agent name or flagged as orphaned, and the proof coverage dashboard no longer shows it as an active agent.

### Concurrency Notes

- Conflicts with: none (FR-20260422-playwright-mcp-setup is BRANCHED on unrelated files; FR-20260423-agent-ops-monitor-sync is MERGED and closed)
- Depends on: none

### Deliverable Tracker

| #   | Deliverable | Owner | Status | Proof | Updated |
| --- | ----------- | ----- | ------ | ----- | ------- |
| AC1 | Audit + fix zombie/stale detection logic in `agent_ops_monitor.py` | ⊕workspace-doer | done | 130b305fee5e | 2026-04-23 |
| AC2 | Verify `last_heartbeat` is the live-window filter column; fix query if not | ⊕workspace-doer | done | 130b305fee5e | 2026-04-23 |
| AC3 | Run `--fix` or equivalent to close stale session in `workspace.db` | ⊕workspace-doer | done | ee5f9c6dfad4 | 2026-04-23 |
| AC4 | Confirm 2 active sessions appear in dashboard after reload | ⊕workspace-doer | done | c1f5b54f8c4b | 2026-04-23 |
| AC5 | Document zombie threshold inline in code | ⊕workspace-doer | done | 130b305fee5e | 2026-04-23 |
| AC6 | All existing tests pass | ⊕workspace-doer | done | 95973d9de180 | 2026-04-23 |
| AC7 | Identify + purge phantom "ops-monitor" agent from proof coverage; no ghost agents in dashboard | ⊕workspace-doer | done | 95973d9de180 | 2026-04-23 |

### Tyler's Original Request

> "The live agents section in the agent ops dashboard isn't working — it's showing an old agent I closed. I have 2 other agents running besides you right now."
>
> "Also noticed agent proof coverage has an ops-monitor agent that doesn't exist in our repo."

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-04-23T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, triage complete → TRIAGED

**Details:**
- Scope: ⊕Workspace (`tools/agent_ops_monitor.py`, `src/data/workspace.db`, `reports/agent_ops_dashboard.html`)
- Type: fix | Risk: medium
- Acceptance criteria drafted (6 criteria, see Header)
- Concurrency check: clean — FR-20260422-playwright-mcp-setup touches unrelated files; FR-20260423-agent-ops-monitor-sync is MERGED/archived
- Cycle timer started: e1488e85-5257-47b3-aa81-13facb35b8e3

**Next:** awaiting Tyler: approve scope

---

## Artifacts

- **Perf runs:** e1488e85-5257-47b3-aa81-13facb35b8e3 — FR cycle timer (fr-cycle-FR-20260423-agent-ops-live-session-fix)

---

### 2026-04-23T00:00:00Z — ⊕workspace-ci

**Event:** state-transition

**Summary:** TRIAGED → BRANCHED — scope approved by Tyler, branch and draft PR created

**Details:**
- Branch created: `fix/workspace/agent-ops-live-session-fix` (from `main`)
- Intake commit: `34d4a14` — `chore(FR-20260423-live): intake scope approval + deliverable tracker`
- Draft PR opened: https://github.com/tylerdrakemusic/-Workspace/pull/10
- State set to BRANCHED

**Next:** implementation agent to work AC1–AC7

---

### 2026-04-23T00:00:00Z — ⊕workspace-doer

**Event:** implementation-complete

**Summary:** All 7 ACs implemented on branch `fix/workspace/agent-ops-live-session-fix`

**Details:**
- **AC1+AC5:** Added `ZOMBIE_THRESHOLD_MIN = 10` and `LIVE_WINDOW_MIN = 10` named constants. Zombie detection now uses `last_heartbeat` (fallback `started_at`) instead of hardcoded 2h threshold.
- **AC2:** Fixed `live_count` query to filter `ended_at IS NULL` and use `last_heartbeat` fallback. Added `_ensure_last_heartbeat_column()` to migrate schema on startup.
- **AC3:** Ran `--fix` on live DB: closed 2 zombie sessions.
- **AC4:** Dashboard regenerated; live_count reflects `last_heartbeat`-based window with `ended_at IS NULL` filter.
- **AC6:** All 17 tests pass (5 new tests added: `test_zombie_uses_last_heartbeat_not_started_at`, `test_zombie_triggered_by_stale_last_heartbeat`, `test_fix_closes_zombie_before_live_count`, `test_validate_agent_names_detects_phantom`, `test_validate_agent_names_fix_renames_known_alias`).
- **AC7:** Added `validate_agent_names()` function. `--fix` renamed 44 `⊕ops-monitor` phantom rows to `⊕workspace-overseer`. Fixed `backfill_legacy()` to use canonical `⊕workspace-overseer` going forward. Fixed `.agent.md` stem extraction bug (double extension).

**Perf run:** 38985359-e419-4bb3-a57a-e4050274ee95 (status: ok)

**Proof IDs:**
- `130b305fee5e` — tools/agent_ops_monitor.py modified (AC1+AC2+AC5+AC7)
- `95973d9de180` — tests/test_agent_ops_monitor.py modified (AC6+AC7)
- `06c294a66501` — tests/conftest.py modified (AC6 fixture)
- `c1f5b54f8c4b` — reports/agent_ops_dashboard.html regenerated (AC4)
- `ee5f9c6dfad4` — command_output: --fix ran successfully (AC3)

**Next:** PR review + merge


### 2026-04-23T18:00:00Z — ⊕workspace-ci (drift-fix)

**Event:** state-transition

**Summary:** Stale ledger header reconciled — no remote branch → CLOSED

**Details:**
- Remote branch ix/workspace/agent-ops-live-session-fix no longer exists on origin (deleted post-merge)
- Commit 921b891 (`FR-20260423: Fix agent ops live session detection + phantom agent purge`) is already on main
- Registry archive already lists this FR as MERGED @ 921b891f43d3; ledger header was stale at BRANCHED
- Transition: BRANCHED → CLOSED (reason: stale — no active work, no remote branch; merged to main @ 921b891f43d3 per archive entry and verified via git log)
- All 7 ACs already marked done in Deliverable Tracker
- Reconciliation FR: FR-20260423-fr-state-drift-fix

**Next:** none — terminal state
