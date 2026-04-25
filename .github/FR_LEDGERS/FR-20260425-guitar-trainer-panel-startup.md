# FR-20260425-guitar-trainer-panel-startup — Guitar Trainer Panel: Server Auto-Start + Remove Live-Dash Chrome

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260425-guitar-trainer-panel-startup
- **Title:** Guitar Trainer Panel: Server Auto-Start + Remove Live-Dash Chrome
- **Type:** fix
- **Risk:** low
- **Projects:** ❤Music, ⊕Workspace
- **State:** REVIEW_REQUESTED
- **Branch:** fix/workspace/guitar-trainer-panel-startup
- **PRs:** https://github.com/tylerdrakemusic/-Workspace/pull/29
- **Cycle timer:** 175eefb5-aab3-4917-a297-c76c5172acac
- **Opened:** 2026-04-25
- **Last updated:** 2026-04-25
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. Guitar Trainer server (port 5055) is auto-started when opening the portal via `open_portal.ps1` (the desktop launcher) — currently it only starts the ∞Life HTTP server and FR Ledger server.
2. Portal pane-9 (Guitar Trainer) no longer wraps the iframe in the `.live-dash` / `.live-header` chrome — the "Live Dashboard" label and "Open in Browser ↗" button are removed. The iframe renders directly inside the dash-pane (same pattern as static panes).
3. No other panels are affected.

### Key Files
- `f:\⊕Workspace\open_portal.ps1` — desktop launcher (needs Guitar Trainer server startup added)
- `f:\⊕Workspace\reports\portal.html` — line ~604, pane-9 (needs live-dash wrapper removed)
- `f:\⊕Workspace\tools\start_guitar_trainer.ps1` — existing startup script to reuse
- `f:\❤Music\src\training\musician_training_ui.py` — Flask app (no changes needed)

### Concurrency Notes
- Conflicts with: none
- Depends on: none

### Deliverable Tracker

| #   | Deliverable | Owner | Status | Proof | Updated |
| --- | ----------- | ----- | ------ | ----- | ------- |
| AC1 | Add Guitar Trainer server auto-start to `open_portal.ps1` | ⊕workspace-ci | done | commit 255525c | 2026-04-25 |
| AC2 | Remove `.live-dash` / `.live-header` chrome from pane-9 in `portal.html` | ⊕workspace-ci | done | commit 255525c | 2026-04-25 |
| AC3 | Smoke-test: all other panels unaffected | ⊕workspace-ci | done | 14/14 tests green (test_guitar_trainer_panel.py) | 2026-04-25 |

### Tyler's Original Request
> "fix the guitar trainer panel, server doesn't seem to be part of startup, live dashboard and open in browser button are unneeded, the user is comfortable working inside the panel, but the panel needs to be available when opening portal from desktop"

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-04-25T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, triage complete → TRIAGED

---

### 2026-04-25T00:00:00Z — ⊕workspace-ci

**Event:** state-transition

**Summary:** Implementation complete → REVIEW_REQUESTED
- Branch: `fix/workspace/guitar-trainer-panel-startup` (commit 255525c)
- PR: https://github.com/tylerdrakemusic/-Workspace/pull/29 (draft)
- AC1 ✅ Guitar Trainer server block added to `open_portal.ps1`
- AC2 ✅ `.live-dash`/`.live-header` chrome stripped from portal pane-9
- AC3 ✅ 14/14 tests green (`tests/test_guitar_trainer_panel.py`)

**Details:**
- Scope: ❤Music (Flask app at `src/training/musician_training_ui.py`, port 5055), ⊕Workspace (portal `reports/portal.html` + launcher `open_portal.ps1`)
- Risk: low — no DB schema changes, no auth, no secrets, no health data; purely UI chrome + PowerShell launcher wiring
- Acceptance criteria drafted (see Header)
- Concurrency check: clean — no active FRs touching `open_portal.ps1` or `portal.html` pane-9
- Depends on: none
- Key files identified: `open_portal.ps1`, `reports/portal.html`, `tools/start_guitar_trainer.ps1`
- Flask app (`musician_training_ui.py`) requires no changes per Tyler

**Next:** awaiting ⊕workspace-ci to create branches + worktrees + draft PRs

---

## Artifacts

- **Perf runs:** 175eefb5-aab3-4917-a297-c76c5172acac — fr-cycle-FR-20260425-guitar-trainer-panel-startup
