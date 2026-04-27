# FR-20260427-originals-artwork-ingest — Originals Artwork Ingest

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260427-originals-artwork-ingest
- **Title:** Originals Artwork Ingest — catalog storage + audio embed for all Tyler James Drake songs
- **Type:** chore
- **Risk:** low
- **Projects:** ❤Music
- **State:** BRANCHED
- **Branch:** chore/heartmusic/originals-artwork-ingest
- **PRs:** [Music#18](https://github.com/tylerdrakemusic/Music/pull/18)
- **Cycle timer:** 7f04f9ab-ccd7-4e89-b6e3-54b4f8ed6a61
- **Opened:** 2026-04-27
- **Last updated:** 2026-04-27T00:01:00Z
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria

1. `catalog/artwork/originals/` folder exists; images copied there with canonical names `{Title} - Tyler James Drake.{ext}`
2. `catalog_songs` gains a nullable `artwork_path` TEXT column; all matched originals get it populated
3. `tools/ingest_artwork.py` reads from `C:\Users\tyler\Desktop\tmp`, matches files by song title to catalog rows, copies to `catalog/artwork/originals/`, and updates the DB — dry-run by default, `--apply` to execute
4. Tool also embeds the matched image as an ID3 APIC (cover) tag directly into the audio file when `source_file` is set on the catalog row
5. Unmatched tmp files (no catalog row found) are reported as `MANUAL_REVIEW`
6. Tests cover ingest copy logic, DB update, embed path, and traversal-safe path handling

### Concurrency Notes

- Conflicts with: none
- Depends on: none

### Deliverable Tracker

| #   | Deliverable | Owner | Status | Proof | Updated |
| --- | ----------- | ----- | ------ | ----- | ------- |
| AC1 | `catalog/artwork/originals/` folder + canonical copy | ❤music-orchestrator | not-started | — | — |
| AC2 | `artwork_path` column + DB migration | ❤music-orchestrator | not-started | — | — |
| AC3 | `tools/ingest_artwork.py` dry-run + `--apply` | ❤music-orchestrator | not-started | — | — |
| AC4 | ID3 APIC embed via mutagen | ❤music-orchestrator | not-started | — | — |
| AC5 | MANUAL_REVIEW reporting for unmatched files | ❤music-orchestrator | not-started | — | — |
| AC6 | Tests: copy logic, DB update, embed, path traversal | ❤music-orchestrator | not-started | — | — |

### Tyler's Original Request

> I want to address **Artwork** — Album art for Bloom? File path if exists. in music project. each of my original songs as artwork, I've placed artwork and brand images in /tmp on desktop

---

## Event Log

### 2026-04-27T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened via `new-fr` prompt template, triage complete → TRIAGED

**Details:**
- Scope: ❤Music only
- Drop folder: `C:\Users\tyler\Desktop\tmp` (established pattern, matches `ingest_sheet_music.py`)
- Images named by song title (e.g. `Bloom.png`)
- Deliverable confirmed: copy to `catalog/artwork/originals/` + `artwork_path` DB column + ID3 APIC embed
- No `catalog/artwork/` folder exists yet; no `artwork_path` column in `catalog_songs` yet
- Originals in scope: all Tyler James Drake songs in catalog (Bloom album + EPs: Marigold, Get Out, What I Do)
- Concurrency check: no conflicts with active FRs
- Cycle timer started: 7f04f9ab-ccd7-4e89-b6e3-54b4f8ed6a61

**Next:** awaiting Tyler: approve scope → ⊕workspace-ci branches

---

### 2026-04-27T00:01:00Z — ⊕workspace-ci

**Event:** state-transition

**Summary:** Gate 2 approved by Tyler → BRANCHED

**Details:**
- Created branch `chore/heartmusic/originals-artwork-ingest` from `main` (HEAD `b280657c`)
- Scaffold commit: `catalog/artwork/originals/.gitkeep` pushed to origin
- Draft PR opened: [Music#18](https://github.com/tylerdrakemusic/Music/pull/18)

**Next:** ❤music-orchestrator implements AC1–AC6

---

## Artifacts

- **Perf runs:** 7f04f9ab-ccd7-4e89-b6e3-54b4f8ed6a61 — FR cycle timer
- **Branch HEAD:** b280657c4c58753090dc0783ab3120c1ecb86dec
- **Draft PR:** https://github.com/tylerdrakemusic/Music/pull/18
