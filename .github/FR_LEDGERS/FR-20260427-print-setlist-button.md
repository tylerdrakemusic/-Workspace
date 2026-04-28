# FR-20260427-print-setlist-button — Add Print Button to Setlist in Band Management Panel

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260427-print-setlist-button
- **Title:** Add Print Button to Setlist in Band Management Panel
- **Type:** feature
- **Risk:** low
- **Projects:** ❤Music
- **State:** CLOSED
- **Branch:** feature/heartmusic/print-setlist-button (deleted)
- **PRs:** [Music#19](https://github.com/tylerdrakemusic/Music/pull/19) ✅ merged
- **Cycle timer:** a1c35e9f-ac0a-4cab-b483-6ae386e4e81a (closed — 11,861,214ms)
- **Opened:** 2026-04-27
- **Last updated:** 2026-04-28
- **Merged at:** 2026-04-28T02:51:37Z
- **Signed off at:** 2026-04-28 (Tyler)
- **Closed:** 2026-04-28
- **Final state:** MERGED → CLOSED

### Acceptance Criteria
1. A "Print Setlist" button is present in the band management panel header/controls area and is only visible when `currentView === 'setlist'`
2. Clicking the button triggers a clean print view (via `window.print()` or a focused print window) — browser print dialog opens
3. The print layout displays: band name, setlist name/date/venue metadata, and songs grouped by set with columns #, Title, Artist, Key, BPM
4. The print layout excludes: audio player controls, sheet music links, search/filter inputs, set-tab controls, dark background, and any nav/sidebar elements
5. `generate_band_mgmt_panel.py` is the sole source of truth — the button, print styles, and print JS are injected there; the static `band_management_panel.html` is regenerated from Python and must NOT be hand-edited
6. The regenerated `band_management_panel.html` reflects all changes and passes a visual smoke-check (panel loads, button appears in setlist view, hidden in catalog view)

### Concurrency Notes
- Conflicts with: FR-20260426-sheet-music-catalog (❤Music, `chore/heartmusic/sheet-music-catalog`) — low risk; that FR targets catalog data, not the band management panel generator. Monitor if it touches `generate_band_mgmt_panel.py`.
- Depends on: none

### Deliverable Tracker

| #   | Deliverable | Owner | Status | Proof | Updated |
| --- | ----------- | ----- | ------ | ----- | ------- |
| AC1 | Print Setlist button in header, hidden in catalog view | ❤music-orchestrator | satisfied | diff confirms button + `bmSwitchView()` visibility logic | 2026-04-27 |
| AC2 | `window.print()` / print window triggered on click | ❤music-orchestrator | satisfied | `bmPrintSetlist()` calls `window.print()` | 2026-04-27 |
| AC3 | Print layout: band name, metadata, grouped songs, correct columns | ❤music-orchestrator | satisfied | HTML builder includes all required fields | 2026-04-27 |
| AC4 | Print layout strips audio, links, controls, dark theme | ❤music-orchestrator | satisfied | `@media print { body > * { display:none }` confirmed | 2026-04-27 |
| AC5 | Python generator (`generate_band_mgmt_panel.py`) is source of truth | ❤music-orchestrator | satisfied | identical diff in generator; HTML regenerated from it | 2026-04-27 |
| AC6 | Regenerated HTML smoke-check passes | ❤music-orchestrator | needs-proof | HTML present in diff but no screenshot/demo artifact | 2026-04-27 |

### Tyler's Original Request
> New feature request intake. Title: "Add print button to pretty-print the setlist in the band management panel"
>
> Affected project: ❤Music
> Primary file (generator): `f:\❤Music\src\band_mgmt\generate_band_mgmt_panel.py`
> Output file (static HTML): `f:\❤Music\reports\band_management_panel.html`
>
> What the feature needs:
> 1. A "Print Setlist" button in the header/controls area (visible only when `currentView === 'setlist'`)
> 2. Clicking it opens a clean print-optimized view (browser `window.print()` or a new window) showing: band name + setlist name/date/venue metadata, songs grouped by set with #, Title, Artist, Key, BPM columns, minimal styling: white background, readable font, no sidebar/buttons/audio controls
> 3. Both the Python generator (`generate_band_mgmt_panel.py`) and the static output HTML need to be updated (the HTML is auto-regenerated from the Python, so the Python is the source of truth).

---

## Event Log

### 2026-04-27T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, triage complete → TRIAGED

**Details:**
- Scope: ❤Music (`generate_band_mgmt_panel.py` + regenerated `band_management_panel.html`)
- Type: feature / Risk: low
- Acceptance criteria drafted (6 ACs — see Header)
- Concurrency check: minor overlap flag on FR-20260426-sheet-music-catalog (❤Music), low risk — different files expected
- Phase A interview: skipped — all three skip conditions met (project explicit, outcome stated, scope boundary clear)

**Next:** awaiting Tyler: approve scope

---

## Artifacts

- **Perf runs:** a1c35e9f-ac0a-4cab-b483-6ae386e4e81a — fr-cycle-FR-20260427-print-setlist-button
- **PR:** [tylerdrakemusic/Music#19](https://github.com/tylerdrakemusic/Music/pull/19)
- **Review:** posted as COMMENT on Music#19 (GitHub blocks REQUEST_CHANGES on own PRs) — 2026-04-27

---

### 2026-04-27T00:00:00Z — ⊕workspace-reviewer

**Event:** auto-review

**Decision:** REQUEST_CHANGES

**Gate results:**

| Gate | Result |
|------|--------|
| Scope conformance | ❌ FAIL |
| Security | ⚠️ WARN |
| Alignment | ✅ PASS |
| Architecture Diagrams | ✅ PASS |
| Tests | ⚠️ WARN |
| Proof-in-the-pudding | ❌ FAIL |
| Demo | ❌ FAIL |

**Required changes:**
1. Remove 10 out-of-scope files from PR — `tools/ingest_artwork.py`, `tests/test_ingest_artwork.py`, and 8 `catalog/artwork/originals/*.jpg` files all belong to FR-20260427-originals-artwork-ingest (MERGED → CLOSED as Music#18). Branch was likely forked from or accidentally merged with the artwork ingest branch.
2. Fix merge conflict (`mergeable_state: dirty`).
3. Mark PR as ready for review (currently Draft).
4. Add proof artifact (screenshot of panel with button visible + print dialog).

**AC assessment:** All 6 ACs are satisfied by the 2 in-scope files. Implementation is correct.

**Review URL:** https://github.com/tylerdrakemusic/Music/pull/19 (comment review)
---

### 2026-04-28T02:51:37Z — ⊕workspace-ci

**Event:** state-transition

**Summary:** Branch rebased onto main (dropped stray artwork-ingest commits), PR #19 un-drafted, CI green, squash-merged → MERGED

**Details:**
- Rebased `feature/heartmusic/print-setlist-button` onto `origin/main` using `--onto main 2c51368` — 3 print-setlist commits cherry-picked cleanly, 3 artwork-ingest commits dropped (already in main via Music#18)
- Diff vs main post-rebase: exactly 2 files (`src/band_mgmt/generate_band_mgmt_panel.py`, `reports/band_management_panel.html`) ✅
- PR #19 marked ready for review (un-drafted)
- CI `test` check: green (completed 2026-04-28T02:51:37Z)
- Squash merge SHA: `850313fcd409b5b3b887f8a61369db1c7da5e734`
- Remote branch deleted (auto-deleted by GitHub on squash merge)
- Cycle timer a1c35e9f closed: 11,861,214ms

**Next:** ledger closeout commit on ⊕Workspace

---

### 2026-04-28T00:00:00Z — Tyler

**Event:** state-transition

**Summary:** Tyler signed off → CLOSED

**Details:**
- Feature exercised and proven on main
- All 6 acceptance criteria satisfied
- State → CLOSED