# FR-20260426-sheet-music-catalog — Add Original Sheet Music to ❤Music Catalog

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260426-sheet-music-catalog
- **Title:** Add Original Sheet Music to ❤Music Catalog
- **Type:** chore
- **Risk:** low
- **Projects:** ❤Music
- **State:** BRANCHED
- **Branch:** chore/heartmusic/sheet-music-catalog
- **PRs:** pending
- **Cycle timer:** 75c2dd60-a27b-4c9c-a243-17ed4aaeb38f
- **Opened:** 2026-04-26
- **Last updated:** 2026-04-26
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. Directory `f:\❤Music\catalog\sheet_music\originals\` exists and is tracked by git.
2. All 7 `.docx` files are present in the target directory.
3. Files missing the artist name are renamed to the standard format: `{SongName}_Tyler James Drake[_{variant}].docx` — `Bitten.docx` → `Bitten_Tyler James Drake.docx`; `Same Thing.docx` → `Same Thing_Tyler James Drake.docx`.
4. Already-standardized files are copied verbatim (no rename): `Fly Away_Tyler James Drake_Key_C.docx`, `Fly Away_Tyler James Drake_LyricsOnly.docx`, `Lighthouse_Tyler James Drake_Key_Em_Lyrics_Only.docx`, `Lighthouse_Tyler James Drake_Key_Em.docx`, `You Already Know - Rough 1-19-2026_Tyler James Drake_Key_E Major.docx`.
5. A `.gitkeep` or at minimum one tracked file ensures the new directory is committed.
6. PR passes CI (`test` check green).

### Concurrency Notes
- Conflicts with: none
- Depends on: none

### Deliverable Tracker

| #   | Deliverable | Owner | Status | Proof | Updated |
| --- | ----------- | ----- | ------ | ----- | ------- |
| AC1 | Create target directory `catalog/sheet_music/originals/` | ⊕workspace-ci | not-started | — | — |
| AC2 | Copy all 7 files to target directory | ⊕workspace-ci | not-started | — | — |
| AC3 | Rename `Bitten.docx` and `Same Thing.docx` to standardized names | ⊕workspace-ci | not-started | — | — |
| AC4 | Verify 5 already-standardized files are intact | ⊕workspace-ci | not-started | — | — |
| AC5 | Commit + push branch; open draft PR | ⊕workspace-ci | not-started | — | — |
| AC6 | CI test check passes green | ⊕workspace-ci | not-started | — | — |

### Tyler's Original Request
> Tyler has 7 .docx sheet music files for his originals on his desktop at `C:\Users\tyler\Desktop\tmp\`. These need to be:
> 1. Copied to `f:\❤Music\catalog\sheet_music\originals\`
> 2. Renamed to a standard format: `{SongName}_Tyler James Drake_{variant/key info}.docx`
>    - Files missing the artist name in the filename need it added for standardization
>
> Files to move:
> - `Bitten.docx` → `Bitten_Tyler James Drake.docx`
> - `Fly Away_Tyler James Drake_Key_C.docx` → already standardized
> - `Fly Away_Tyler James Drake_LyricsOnly.docx` → already standardized
> - `Lighthouse_Tyler James Drake_Key_Em_Lyrics_Only.docx` → already standardized
> - `Lighthouse_Tyler James Drake_Key_Em.docx` → already standardized
> - `Same Thing.docx` → `Same Thing_Tyler James Drake.docx`
> - `You Already Know - Rough 1-19-2026_Tyler James Drake_Key_E Major.docx` → already standardized

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-04-26T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, scope clear (Tyler pre-approved by submitting with full detail) → BRANCHED (pending CI)

**Details:**
- Scope: ❤Music only
- Risk: low — file copy/rename operation, no code changes
- Acceptance criteria drafted (see Header)
- Concurrency check: no conflicts with active FR `FR-20260426-todo-db-cards-executive-panel` (different repo)
- Tyler scope confirmation: implicit — request submitted with explicit file list, target dir, and rename rules

**Next:** ⊕workspace-ci to create branch `chore/heartmusic/sheet-music-catalog`, copy + rename files, open draft PR

---

## Artifacts

- **Perf runs:** 75c2dd60-a27b-4c9c-a243-17ed4aaeb38f — FR cycle timer started at intake
- **Proof artifacts:** —
- **PRs:** pending
- **Commits:** —
- **Reports / dashboards:** —
