# FR-20260509-tjd-radio-gmusic-playlist

**Title:** TJD Radio — G:\Muzic playlist source + artist display + filter engine  
**Type:** feature  
**Project:** ❤Music  
**Owner:** ⊕workspace-overseer  
**State:** AUTO_REVIEWED
**Opened:** 2026-05-09
**Branch:** feature/music/fr-20260509-tjd-radio-gmusic-playlist
**PR:** [Music#36](https://github.com/tylerdrakemusic/Music/pull/36)

---

## Motivation

The radio currently only plays 3 hardcoded EP subdirs from `f:\❤Music\catalog\ep\`
(~dozen tracks). `G:\Muzic` has 200+ files — covers + TJD originals — making it a
real radio station. The web player also displays "Muzic" as the album name for every
track, which is meaningless; artist name should be extracted from the filename pattern.

---

## Acceptance Criteria

| # | AC | Done |
|---|----|------|
| AC1 | `main()` scans `G:\Muzic` (flat) and `f:\❤Music\catalog\masters` (recursive) as primary playlist sources. The 3 hardcoded `CATALOG_ROOT / "ep" / ...` entries are **removed from the `scan_dirs` list in code** (the `catalog/ep/` directory itself is not deleted from the repo). | ☐ |
| AC2 | Graceful fallback: if `G:\Muzic` is unavailable, log a warning and fall back to `catalog/masters` + `catalog/ep/Marigold`, `catalog/ep/Get Out`, `catalog/ep/What I do` so the radio still starts. | ☐ |
| AC3 | Filter engine excludes pitch-shifted tracks (`(+/-N step(s))`, `(Backing Track +/-)`) and rough/intermediate tracks (`(Rough`, `Rough)`, `(Tuned Vox`, `PreMaster`, `Vox Down`). Applied to all sources. | ☐ |
| AC4 | Dedup: when the same TJD original appears in both `G:\Muzic` and `catalog/masters`, the `catalog/masters` version wins. Dedup by normalized title (lowercase, strip extra whitespace). | ☐ |
| AC5 | When both `.mp3` and `.wav` exist for the same file stem, prefer `.mp3` (existing behavior preserved). | ☐ |
| AC6 | Artist field extracted from filename pattern `Song Title - Artist Name.ext`; web player panel displays `Artist` instead of parent folder name. TJD originals without a ` - Artist` suffix show `Tyler James Drake`. | ☐ |
| AC7 | All existing tests pass; new unit tests added for the filter engine (`is_filtered`) and artist-extraction (`extract_artist`) functions. | ☐ |

---

## Out of Scope

- No changes to streaming engine, crossfade, bumpers, or Flask routes
- No changes to `catalog/ep/` directory contents
- No portal dashboard changes
- No changes to `start_studio_panel.ps1` or other launchers
- `start_tjd_radio.ps1` may get a minor comment update (no functional change)

---

## Risk Assessment

**Low** — playlist-only change; no DB, no auth, no secrets, no shared infrastructure.

---

## Event Log

| Timestamp | Event | Actor |
|-----------|-------|-------|
| 2026-05-09 | OPEN: FR filed by Tyler | Tyler |
| 2026-05-09 | TRIAGED: grill-me scope interview complete, all 6 AC confirmed | ⊕workspace-intake |
| 2026-05-09 | BRANCHED: branch + draft PR #36 created | ⊕workspace-ci |
| 2026-05-09 | IN_PROGRESS → REVIEW_REQUESTED: 27/27 tests pass, commit 9e43e8b | ❤music-orchestrator |
| 2026-05-09 | AUTO_REVIEWED: APPROVE — 7/7 ACs verified, 27 tests pass in 0.27s | ⊕workspace-reviewer |
| 2026-05-09 | MERGED: squash merge d3310b0 to main | ⊕workspace-ci |
| 2026-05-09 | BRANCHED: branch + draft PR #36 created | ⊕workspace-ci |
| 2026-05-09 | IN_PROGRESS → REVIEW_REQUESTED: 27/27 tests pass, commit 9e43e8b | ❤music-orchestrator |
| 2026-05-09 | AUTO_REVIEWED: APPROVE — 7/7 ACs verified, 27 tests pass in 0.27s | ⊕workspace-reviewer |
| 2026-05-09 | MERGED: squash merge d3310b0 to main | ⊕workspace-ci |
| 2026-05-09 | BRANCHED: branch + draft PR created | ⊕workspace-ci |
| 2026-05-09 | AUTO_REVIEWED: APPROVE — 7/7 ACs satisfied, 27/27 tests pass, no security blockers. One minor XSS nit (low-risk, optional). Review posted to Music#36 as COMMENT (GitHub blocks self-review APPROVE). | ⊕workspace-reviewer |
