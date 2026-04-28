# FR-20260427-originals-artwork-ingest — Originals Artwork Ingest

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260427-originals-artwork-ingest
- **Title:** Originals Artwork Ingest — catalog storage + audio embed for all Tyler James Drake songs
- **Type:** chore
- **Risk:** low
- **Projects:** ❤Music
- **State:** CLOSED
- **Branch:** chore/heartmusic/originals-artwork-ingest
- **PRs:** [Music#18](https://github.com/tylerdrakemusic/Music/pull/18)
- **Cycle timer:** 7f04f9ab-ccd7-4e89-b6e3-54b4f8ed6a61
- **Opened:** 2026-04-27
- **Last updated:** 2026-04-28
- **Merged at:** 2026-04-27
- **Signed off at:** 2026-04-28 (Tyler)
- **Closed:** 2026-04-28
- **Final state:** MERGED → CLOSED

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
| AC1 | `catalog/artwork/originals/` folder + canonical copy | ❤music-orchestrator | done | `.gitkeep` present; removed on first `--apply`; canonical `{Title} - Tyler James Drake.{ext}` naming in tool | 2026-04-27 |
| AC2 | `artwork_path` column + DB migration | ❤music-orchestrator | done | Idempotent `ALTER TABLE catalog_songs ADD COLUMN artwork_path TEXT`; populated on `--apply` | 2026-04-27 |
| AC3 | `tools/ingest_artwork.py` dry-run + `--apply` | ❤music-orchestrator | done | `tools/ingest_artwork.py` — `--tmp`, `--apply`, COPY_NEW/SKIP_EXACT_DUP/SKIP_SEMANTIC/MANUAL_REVIEW | 2026-04-27 |
| AC4 | ID3 APIC embed via mutagen | ❤music-orchestrator | done | `embed_cover()` handles MP3/FLAC/MP4/M4A; skips gracefully if mutagen absent or file missing | 2026-04-27 |
| AC5 | MANUAL_REVIEW reporting for unmatched files | ❤music-orchestrator | done | Formatted table to stdout; 4 MANUAL_REVIEW items in Desktop\tmp (brand images + avif) | 2026-04-27 |
| AC6 | Tests: copy logic, DB update, embed, path traversal | ❤music-orchestrator | done | `tests/test_ingest_artwork.py` — 23 tests, 23 passed | 2026-04-27 |

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

### 2026-04-27T00:30:00Z — ❤music-orchestrator

**Event:** state-transition

**Summary:** Implementation started → IN_PROGRESS

**Details:**
- Read AGENT_STARTUP, inspected `ingest_sheet_music.py` pattern, checked `catalog_songs` schema
- Scanned `C:\Users\tyler\Desktop\tmp`: 12 files found (8 song art .jpg + 3 brand images + 1 .avif)
- Song art files: abbey's song art.jpg, bitten song art.jpg, fly away song art.jpg, get out song art.jpg,
  is it real song art.jpg, lighthouse song art.jpg, same thing song art.jpg, what I do song art image.jpg
- Brand/non-song files (will be MANUAL_REVIEW): brand image 1.jpg, brand image 2.jpg,
  tyler in italy social image.jpg, guitar brand image.avif (unsupported ext — not ingested)
- Implementing AC1–AC6

**Next:** commit + push + REVIEW_REQUESTED

---

### 2026-04-27T01:00:00Z — ❤music-orchestrator

**Event:** state-transition

**Summary:** All AC1–AC6 delivered → REVIEW_REQUESTED

**Details:**
- Created `tools/ingest_artwork.py` following `ingest_sheet_music.py` pattern
- Created `tests/test_ingest_artwork.py` — 23 tests, all passing
- DB migration: idempotent `ALTER TABLE catalog_songs ADD COLUMN artwork_path TEXT`
- embed_cover(): MP3 (ID3 APIC), FLAC (Picture block), MP4/M4A (covr atom); graceful skip if mutagen absent
- MANUAL_REVIEW items in Desktop\tmp: brand image 1.jpg, brand image 2.jpg, tyler in italy social image.jpg
  (guitar brand image.avif ignored — not in supported IMAGE_EXTS .jpg/.jpeg/.png/.webp)
- Commit: `fb552b4` on branch `chore/heartmusic/originals-artwork-ingest`
- Pushed to origin; PR Music#18 updated

**Next:** Tyler reviews PR Music#18

---

### 2026-04-27T23:30:00Z — ⊕workspace-ci

**Event:** state-transition

**Summary:** Tyler approved → TYLER_APPROVED; CI gate passed → MERGED

**Details:**
- CI failure diagnosed: Tyler's commit added `.avif` to `IMAGE_EXTS` but `test_non_image_exts_ignored_in_plan` still tested `.avif` as a non-image ext
- Fix: replaced `bloom.avif` with `bloom.mp3` in test (commit `575b04f8`)
- `test` check: green ✓
- PR marked ready for review, squash-merged
- Merge SHA: `dd410156` (squash → main)
- Cycle timer closed: 7f04f9ab-ccd7-4e89-b6e3-54b4f8ed6a61 — 1,900,677ms — ok

**Next:** ledger closeout commit → CLOSED

---

### 2026-04-28T00:00:00Z — Tyler

**Event:** state-transition

**Summary:** Tyler signed off → CLOSED

**Details:**
- Feature exercised and proven on main
- All 6 acceptance criteria satisfied
- State → CLOSED

---

## Artifacts

- **Perf runs:** 7f04f9ab-ccd7-4e89-b6e3-54b4f8ed6a61 — FR cycle timer — 1,900,677ms — ok
- **Branch HEAD:** fb552b4 (implementation commit)
- **Tyler ingest commit:** 2c513681 (8 artworks + fix title discovery)
- **CI fix commit:** 575b04f8 (fix test for .avif now in IMAGE_EXTS)
- **Merge SHA:** dd410156 (squash → main)
- **Scaffold HEAD:** b280657c4c58753090dc0783ab3120c1ecb86dec
- **PR:** https://github.com/tylerdrakemusic/Music/pull/18 (merged)
- **Test result:** 23 passed, 0 failed (`tests/test_ingest_artwork.py`)
- **Deliverables:** `tools/ingest_artwork.py`, `tests/test_ingest_artwork.py`, `catalog/artwork/originals/` (8 JPGs)
