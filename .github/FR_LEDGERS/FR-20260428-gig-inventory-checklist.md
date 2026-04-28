# FR-20260428-gig-inventory-checklist — Gig Inventory Checklist — Band Management Panel Integration + Print

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260428-gig-inventory-checklist
- **Title:** Gig Inventory Checklist — Band Management Panel Integration + Print
- **Type:** feature
- **Risk:** low
- **Projects:** ❤Music
- **State:** BRANCHED
- **Branch:** feature/heartmusic/gig-inventory-checklist
- **PRs:** [Music#20](https://github.com/tylerdrakemusic/Music/pull/20)
- **Cycle timer:** b3044c39-976a-4387-abb0-c8103f057841
- **Opened:** 2026-04-28
- **Last updated:** 2026-04-28
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria

1. `gig_inventory` table added to `heartmusic.db` via `init_db.py`; seeded from the 11 items in `tools/gig_checklist.py` (Guitar, Guitar Stand, Amp, Amp stand, Trombone, Trombone stand, Music Stand, Gig Bag, Sheet Music, Pedal Board, Lights)
2. Third vtab **📦 Gig Inventory** added to `generate_band_mgmt_panel.py` alongside Active Setlist and Full Catalog
3. Checklist view columns: Item, Category, Going ✓, Returning ✓ — checkboxes interactive in browser
4. `localStorage` persistence for checkbox state (keyed per item); "Reset Checks" button clears all checked state
5. Add Row / Remove Row controls; new rows persisted to `localStorage`; canonical seed from DB/JSON on first load
6. **Print Inventory** button visible only when `currentView === 'inventory'`; triggers `window.print()` with a clean print layout (no sidebar, no controls, white background)
7. `tools/gig_checklist.py` deprecated — replaced by panel print button; file retained with a deprecation notice pointing to the panel
8. Panel regenerated (`reports/band_management_panel.html`); smoke-check passes (panel loads, inventory tab visible, print button present)
9. pytest: `gig_inventory` table has ≥ 11 rows seeded + HTML contains inventory vtab markup
10. Concurrency guard: no modifications to sheet-music-catalog branch files (`generate_band_mgmt_panel.py` edits must be rebased cleanly onto main or coordinated with FR-20260426-sheet-music-catalog)

### Concurrency Notes
- Conflicts with: FR-20260426-sheet-music-catalog (❤Music, active on `chore/heartmusic/sheet-music-catalog`) — both may touch `generate_band_mgmt_panel.py`. Implement on a branch from current main; rebase before PR if sheet-music-catalog merges first.
- Depends on: none

### Deliverable Tracker

| #   | Deliverable | Owner | Status | Proof | Updated |
| --- | --- | --- | --- | --- | --- |
| AC1 | `gig_inventory` DB table + seed in `init_db.py` | ❤music-orchestrator | not-started | — | — |
| AC2 | 📦 Gig Inventory vtab in panel generator | ❤music-orchestrator | not-started | — | — |
| AC3 | Interactive checkboxes: Going / Returning columns | ❤music-orchestrator | not-started | — | — |
| AC4 | localStorage persistence + Reset Checks button | ❤music-orchestrator | not-started | — | — |
| AC5 | Add Row / Remove Row controls | ❤music-orchestrator | not-started | — | — |
| AC6 | Print Inventory button + clean print layout | ❤music-orchestrator | not-started | — | — |
| AC7 | `tools/gig_checklist.py` deprecated with notice | ❤music-orchestrator | not-started | — | — |
| AC8 | Panel regenerated, smoke-check passes | ❤music-orchestrator | not-started | — | — |
| AC9 | pytest: ≥11 rows seeded + vtab HTML marker | ❤music-orchestrator | not-started | — | — |

### Tyler's Original Request

> "I should have somewhere in the music repo a file representing an inventory checklist I use for gigs, it tracks the items I take to the gig and I check before going to the gig and leaving the gig. Basically a gig inventory check list to make sure I don't lose any equipment going in and out. I should already have a data file with what I have. Ideally it would be integrated into the band management panel in a semi persistent way such that I can add or remove rows, but would hold state each time I open the band management panel. Use case I add a new piece of equipment or decide to switch amps I bring to the gig for example. I would also like to be able to print this inventory checklist to take to the gig as a reality copy to manage my gig inventory. The file should be in the music repo already, just need to build on top of that."

**Scope confirmation (Tyler 2026-04-28):** `gig_checklist.py` deprecated; data lives in DB table. Approved.

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-04-28T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened and triage complete → TRIAGED (scope confirmed by Tyler)

**Details:**
- Scope: ❤Music only
- Existing file found: `tools/gig_checklist.py` — standalone fpdf PDF generator with 11 hardcoded items; no DB backing
- No `gig_inventory` table exists in heartmusic.db — this FR creates it
- Band management panel has existing print infrastructure (from FR-20260427-print-setlist-button); inventory tab slots in as third vtab
- Tyler confirmed: `gig_checklist.py` deprecated (data moves to DB); panel print button replaces it
- Concurrency flag: FR-20260426-sheet-music-catalog active on ❤Music (different files expected, low conflict risk)
- Cycle timer started: b3044c39-976a-4387-abb0-c8103f057841

**Next:** ⊕workspace-ci — create branch `feature/heartmusic/gig-inventory-checklist`, open draft PR in ❤Music repo

### 2026-04-28T00:00:00Z — ⊕workspace-ci

**Event:** state-transition

**Summary:** Tyler approved scope → BRANCHED

**Details:**
- Branch created: feature/heartmusic/gig-inventory-checklist
- Scaffold commit: catalog/gig_inventory/.gitkeep (289c23c)
- Draft PR opened: [Music#20](https://github.com/tylerdrakemusic/Music/pull/20)

**Next:** ❤music-orchestrator implements AC1–AC9

---

## Artifacts

- **Perf runs:** b3044c39-976a-4387-abb0-c8103f057841 — FR-20260428-gig-inventory-checklist cycle timer
- **Existing source:** `f:\❤Music\tools\gig_checklist.py` (11-item hardcoded list, to be deprecated)
