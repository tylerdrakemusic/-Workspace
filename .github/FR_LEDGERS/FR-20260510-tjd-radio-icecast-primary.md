# FR-20260510-tjd-radio-icecast-primary — Replace local TJD radio with Icecast default, Muzic primary + Tyler-owned fallback

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260510-tjd-radio-icecast-primary
- **Title:** Replace local TJD radio with Icecast default, Muzic primary + Tyler-owned fallback
- **Type:** feature + migration
- **Risk:** medium
- **Projects:** ❤Music
- **State:** REVIEW_REQUESTED
- **Branch:** feature/music/fr-20260510-tjd-radio-icecast-primary
- **PRs:** pending
- **Cycle timer:** d5c06499-2b3c-455e-b973-84af0ae825ec
- **Opened:** 2026-05-10
- **Last updated:** 2026-05-10
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. Local TJD radio panel uses Icecast as the default backend for playback and now-playing data.
2. Source priority is enforced as: Muzic primary, Tyler-owned catalog roots fallback.
3. Legacy local broadcaster path remains available as explicit fallback (not default).
4. Architecture review report and one updated radio architecture diagram explain runtime boundaries and public-facing exposure options.
5. Runbook and verification scripts document and validate the new default path and fallback behavior.

### Concurrency Notes
- Conflicts with: none
- Depends on: FR-20260510-self-hosted-radio-poc, FR-20260509-tjd-radio-gmusic-playlist

### Deliverable Tracker

<!-- Mutable table. Agents flip their own row's Status + Proof + Updated in place.
     Status vocab: not-started → in-progress → blocked → done → verified.
     Proof column: proof_artifact id (from proof_cli) or PR comment URL. -->

| #   | Deliverable | Owner | Status | Proof | Updated |
| --- | ----------- | ----- | ------ | ----- | ------- |
| AC1 | Panel default routed to Icecast backend | ❤music-orchestrator | verified | `src/radio/tjd_radio.py` smoke: `GET /api/now_playing` (icecast mode) + `GET /stream` → 302 to Icecast | 2026-05-10 |
| AC2 | Catalog priority logic (Muzic primary, Tyler fallback) | ❤music-orchestrator | verified | `prioritized_radio_roots` + `build_deduped_playlist` flow; tests passed (`test_tjd_radio.py`) | 2026-05-10 |
| AC3 | Legacy local broadcaster kept as explicit fallback only | ❤music-orchestrator | verified | explicit `--backend local` smoke on :8111 with live `/api/now_playing` payload | 2026-05-10 |
| AC4 | Architecture impact review + updated diagram | ⊕workspace-architecture-reviewer | done | 221708ccebe9 | 2026-05-10 |
| AC5 | Runbook and verification updates | ❤music-orchestrator | verified | runbook + architecture docs updated; WSL verify/stability helpers validated | 2026-05-10 |

### Tyler's Original Request
> I don't think we need 2 hosted radio stations. I think we need to replace the TJD local radio with TJD icecast radio, Muzic should be the primary source and Tyler-owned catalog roots as fallback. I have purchased all the music in the primary from Amazon music.

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-05-10T20:50:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened and triaged; scope and constraints confirmed by Tyler.

**Details:**
- Scope: ❤Music radio stack consolidation
- Default mode confirmed: Icecast primary path for local TJD panel
- Fallback mode confirmed: keep legacy local broadcaster available but non-default
- Source policy confirmed: Muzic primary, Tyler-owned catalog roots fallback
- Acceptance criteria drafted (see Header)
- Concurrency check: no direct conflicts; depends on existing radio FR baselines
- Cycle timer started: d5c06499-2b3c-455e-b973-84af0ae825ec

**Next:** awaiting Tyler: approve scope for branch cut (BRANCHED).

---

### 2026-05-10T20:58:00Z — ⊕workspace-intake

**Event:** decision

**Summary:** Tyler approved the triaged scope and requested architecture clarity on public interfacing.

**Details:**
- Tyler confirmed FR draft: approved
- Requested architecture review and diagram to clarify what public Icecast interfacing means
- AC4 explicitly tracks architecture review + diagram update

**Next:** ⊕workspace-ci: create BRANCHED state for FR-20260510-tjd-radio-icecast-primary.

---

### 2026-05-10T23:46:26Z — ⊕workspace-ci

**Event:** state-transition

**Summary:** BRANCHED transition completed; ❤Music feature branch created.

**Details:**
- Branch created in ❤Music: feature/music/fr-20260510-tjd-radio-icecast-primary
- Draft PR creation attempted immediately
- Blocker: GitHub CLI is unavailable on this machine (`gh` command not found)
- PR status remains pending until CLI is installed or PR is opened via alternate path

**Next:** open draft PR for this branch, then transition to IN_PROGRESS when implementation starts.

---

### 2026-05-10T23:58:00Z — ❤music-orchestrator

**Event:** state-transition

**Summary:** Implementation started on feature branch for Icecast-primary local radio migration.

**Details:**
- Entered IN_PROGRESS on `feature/music/fr-20260510-tjd-radio-icecast-primary`
- Initial work focus: route local panel/runtime defaults to Icecast path, enforce source priority (Muzic primary, Tyler fallback), preserve legacy local broadcaster as explicit fallback
- Architecture clarity deliverable (AC4) scheduled early in implementation so public interface boundaries are documented before final review

**Next:** ❤music-orchestrator: deliver AC1-AC5 and move FR to REVIEW_REQUESTED with proof artifacts.

---

### 2026-05-10T17:52:44Z — ⊕workspace-architecture-reviewer

**Event:** architecture-review

**Summary:** Architectural impact review completed for Icecast-primary radio migration.

**Details:**
- Decision: PASS_WITH_UPDATES
- Architectural impact confirmed in runtime boundary changes in `src/radio/tjd_radio.py` (Icecast default backend, explicit local fallback)
- Source-of-truth policy confirmed (Muzic primary, Tyler-owned catalog fallback)
- Diagram coverage verified: `diagrams/music-icecast-primary-architecture.mmd` updated and aligned with detected impacts
- No additional diagrams required for this FR scope

**Next:** ❤music-orchestrator may proceed toward REVIEW_REQUESTED after remaining AC checks.

---

### 2026-05-11T00:02:00Z — ❤music-orchestrator

**Event:** state-transition + artifact

**Summary:** Implementation complete for Icecast-primary migration; FR moved to REVIEW_REQUESTED.

**Details:**
- Implemented Icecast-first local panel backend with explicit fallback mode in `src/radio/tjd_radio.py`
- Added source-priority helpers (Muzic primary, Tyler-owned fallback) and metadata normalization for combined ICY song fields
- Updated runbook and added architecture explainer doc + diagram
- Validation: `45 passed` on targeted radio test suite (`tests/test_tjd_radio.py`, `tests/test_radio_phase_alpha_poc.py`)
- Smoke (icecast default): `GET /api/now_playing` returned normalized artist/title; `GET /stream` redirected to `http://127.0.0.1:8000/stream`
- Smoke (legacy fallback): `--backend local` served live now-playing API payload on `:8111`

**Next:** await architecture review closeout state handling and Tyler review on feature branch.

---

## Artifacts

<!-- APPEND-ONLY. Links to concrete evidence. -->

- **Perf runs:** d5c06499-2b3c-455e-b973-84af0ae825ec — FR cycle timer start (intake)
- **Reports / dashboards:** f:\⊕Workspace\diagrams\ — architecture update target for AC4
- **Architecture review report:** f:\⊕Workspace\reports\architecture-review-FR-20260510-tjd-radio-icecast-primary.md
- **Proof artifact:** 221708ccebe9 (`⊕workspace-architecture-reviewer`, `file_created`)
- **Tests:** `C:\G\python.exe -m pytest f:\❤Music\tests\test_tjd_radio.py f:\❤Music\tests\test_radio_phase_alpha_poc.py` (`45 passed`)
- **Smoke evidence:** panel icecast mode on `:8110` (`/api/now_playing`, `/stream`), panel local fallback mode on `:8111` (`/api/now_playing`)
