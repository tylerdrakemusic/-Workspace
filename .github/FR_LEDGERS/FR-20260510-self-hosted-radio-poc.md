# FR-20260510-self-hosted-radio-poc — Self-hosted radio POC — Icecast 2 + Liquidsoap on WSL2, streaming Tyler catalog (Phase alpha from IP_STRATEGY.md Section 7)

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260510-self-hosted-radio-poc
- **Title:** Self-hosted radio POC — Icecast 2 + Liquidsoap on WSL2, streaming Tyler catalog (Phase alpha)
- **Type:** feature
- **Risk:** medium
- **Projects:** ❤Music
- **State:** IN_PROGRESS
- **Branch:** feature/music/fr-20260510-self-hosted-radio-poc
- **PRs:** pending
- **Cycle timer:** 1e74e259-ec6e-45c8-8369-225fed989ebe
- **Opened:** 2026-05-10
- **Last updated:** 2026-05-10
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. WSL2 Ubuntu hosts Icecast 2 and Liquidsoap with a working single mount stream for Tyler-owned catalog assets.
2. Stream metadata exposes Now Playing updates and a browser web player can play the mount successfully.
3. Operational docs and scripts exist for start, stop, and restart for the Phase alpha stack.
4. A stability run of at least 2 hours completes without service crash.

### Concurrency Notes
- Conflicts with: none
- Depends on: FR-20260509-tjd-radio-gmusic-playlist (playlist/catalog source behavior baseline)

### Deliverable Tracker

<!-- Mutable table. Agents flip their own row's Status + Proof + Updated in place.
     Status vocab: not-started → in-progress → blocked → done → verified.
     Proof column: proof_artifact id (from proof_cli) or PR comment URL. -->

| #   | Deliverable | Owner | Status | Proof | Updated |
| --- | ----------- | ----- | ------ | ----- | ------- |
| AC1 | WSL2 Icecast + Liquidsoap stream baseline | ❤music-orchestrator | done | commit `aabb5f3` + generated configs | 2026-05-10 |
| AC2 | Metadata + browser playback validation | ❤music-orchestrator | done | commit `aabb5f3` + player + verify script | 2026-05-10 |
| AC3 | Ops scripts and runbook docs | ❤music-orchestrator | done | commit `aabb5f3` | 2026-05-10 |
| AC4 | 2-hour stability proof run | ❤music-orchestrator | in-progress | pending live WSL run evidence | 2026-05-10 |

### Tyler's Original Request
> with interview, can we look at this todo from the exec panel: Self-hosted radio POC — Icecast 2 + Liquidsoap on Windows/WSL, streaming Tyler's catalog (Phase alpha per IP_STRATEGY.md Section 7)

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-05-10T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened and triaged; scope confirmed by Tyler.

**Details:**
- Scope: ❤Music (Phase alpha only)
- Runtime target confirmed: WSL2 Ubuntu
- Catalog policy confirmed: Tyler-owned assets only
- Acceptance criteria drafted (see Header)
- Concurrency check: no direct conflicts; dependency noted on FR-20260509-tjd-radio-gmusic-playlist
- Cycle timer started: 1e74e259-ec6e-45c8-8369-225fed989ebe

**Next:** awaiting Tyler: approve scope for branch cut (BRANCHED)

---

### 2026-05-10T00:10:00Z — ⊕workspace-ci

**Event:** state-transition

**Summary:** Scope approved; FR moved to BRANCHED and implementation branch created.

**Details:**
- Created branch in ❤Music: `feature/music/fr-20260510-self-hosted-radio-poc`
- PR remains pending until implementation kickoff
- Handoff target: ❤music-orchestrator

**Next:** ❤music-orchestrator: begin implementation (IN_PROGRESS) on phase alpha AC1-AC4.

---

### 2026-05-10T00:20:00Z — ❤music-orchestrator

**Event:** state-transition

**Summary:** Implementation started in ❤Music on branch `feature/music/fr-20260510-self-hosted-radio-poc`.

**Details:**
- Entered IN_PROGRESS for phase alpha delivery (WSL2 Icecast2 + Liquidsoap POC)
- Planned deliverables: setup/start/stop/verify scripts, generated playlist/config artifacts, web player page, and runbook

**Next:** ❤music-orchestrator: deliver AC1-AC4 and move to REVIEW_REQUESTED with proof artifacts.

---

### 2026-05-10T00:35:00Z — ❤music-orchestrator

**Event:** artifact

**Summary:** Phase alpha implementation assets committed in ❤Music with passing unit tests.

**Details:**
- Added WSL lifecycle scripts (`setup/start/stop/verify`) and Windows wrappers
- Added generator tool for Tyler-only playlist + Icecast/Liquidsoap configs
- Added static web player page and runbook
- Test result: `5 passed` in `tests/test_radio_phase_alpha_poc.py`

**Next:** ❤music-orchestrator: perform WSL runtime proof run (metadata + 2-hour stability), then prepare REVIEW_REQUESTED.

---

## Artifacts

<!-- APPEND-ONLY. Links to concrete evidence. -->

- **Perf runs:** 1e74e259-ec6e-45c8-8369-225fed989ebe — full FR cycle timer start
- **Proof artifacts:** pending
- **PRs:** pending
- **Commits:** pending
- **Branches:** feature/music/fr-20260510-self-hosted-radio-poc — created for FR implementation
- **Reports / dashboards:** ❤Music/docs/protocols/IP_STRATEGY.md (Section 7)
- **Commits:** `aabb5f3` — feat(radio): add Phase alpha WSL Icecast + Liquidsoap POC assets
- **Tests:** `C:\G\python.exe -m pytest f:\❤Music\tests\test_radio_phase_alpha_poc.py` — 5 passed
- **Generated artifacts:** `f:\❤Music\output\radio_phase_alpha\tyler_catalog_phase_alpha.liqlist`, `f:\❤Music\output\radio_phase_alpha\tjd_radio_phase_alpha.liq`, `f:\❤Music\output\radio_phase_alpha\icecast_phase_alpha.xml`
- **Runbook:** `f:\❤Music\docs\protocols\self-hosted-radio-phase-alpha-runbook.md`
