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
| AC1 | WSL2 Icecast + Liquidsoap stream baseline | ❤music-orchestrator | not-started | — | — |
| AC2 | Metadata + browser playback validation | ❤music-orchestrator | not-started | — | — |
| AC3 | Ops scripts and runbook docs | ❤music-orchestrator | not-started | — | — |
| AC4 | 2-hour stability proof run | ❤music-orchestrator | not-started | — | — |

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

## Artifacts

<!-- APPEND-ONLY. Links to concrete evidence. -->

- **Perf runs:** 1e74e259-ec6e-45c8-8369-225fed989ebe — full FR cycle timer start
- **Proof artifacts:** pending
- **PRs:** pending
- **Commits:** pending
- **Branches:** feature/music/fr-20260510-self-hosted-radio-poc — created for FR implementation
- **Reports / dashboards:** ❤Music/docs/protocols/IP_STRATEGY.md (Section 7)
