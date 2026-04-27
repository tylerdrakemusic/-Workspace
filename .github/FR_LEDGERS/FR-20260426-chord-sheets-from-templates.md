# FR-20260426-chord-sheets-from-templates — Generate Chord Sheet DOCX Files from All Song Templates

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260426-chord-sheets-from-templates
- **Title:** Generate Chord Sheet DOCX Files from All Song Templates
- **Type:** chore
- **Risk:** low
- **Projects:** ❤Music
- **State:** MERGED → CLOSED
- **Branch:** chore/heartmusic/sheet-music-from-templates (merged)
- **PRs:** https://github.com/tylerdrakemusic/Music/pull/15 (merged)
- **Cycle timer:** 671c9098-9b69-4d5c-ad90-5adb1ab98a83 (closed)
- **Opened:** 2026-04-26
- **Last updated:** 2026-04-26
- **Merged at:** 2026-04-26
- **Signed off at:** 2026-04-26
- **Closed:** 2026-04-26
- **Final state:** completed

### Acceptance Criteria
1. Branch `chore/heartmusic/sheet-music-from-templates` created off ❤Music `main`.
2. All 31 DOCX files generated using `C:\G\python.exe f:\❤Music\tools\make_chord_sheet.py --input <template> --out <outdir>`.
3. 4 originals (artist = Tyler James Drake) land in `f:\❤Music\catalog\sheet_music\originals\`: Abbey's Song (Bm), Fly Away (C), Lighthouse (Em), You Already Know (E Major).
4. 27 covers land in `f:\❤Music\catalog\sheet_music\covers\`.
5. Tyler visually reviews all generated DOCX files in the catalog folders before commit.
6. All 31 files staged, committed, and pushed; draft PR opened with CI green.

### Concurrency Notes
- Conflicts with: FR-20260426-sheet-music-catalog (overlapping path `catalog/sheet_music/originals/` — that FR copies 7 pre-existing DOCX files; this FR generates 4 originals via tool). Recommend serializing: complete FR-20260426-sheet-music-catalog first, then rebase this branch on top. Or handle both in same session on same branch — Tyler's call.
- Depends on: none (tool `make_chord_sheet.py` and all 31 templates already exist)

### Deliverable Tracker

<!-- Mutable table. Agents flip their own row's Status + Proof + Updated in place. -->

| #   | Deliverable | Owner | Status | Proof | Updated |
| --- | ----------- | ----- | ------ | ----- | ------- |
| AC1 | Create branch `chore/heartmusic/sheet-music-from-templates` off ❤Music `main` | ⊕workspace-ci | not-started | — | — |
| AC2 | Run `make_chord_sheet.py` for all 31 templates | ❤music-orchestrator | not-started | — | — |
| AC3 | Verify 4 originals in `catalog/sheet_music/originals/` | ❤music-orchestrator | not-started | — | — |
| AC4 | Verify 27 covers in `catalog/sheet_music/covers/` | ❤music-orchestrator | not-started | — | — |
| AC5 | Tyler visual review of generated files | Tyler | not-started | — | — |
| AC6 | Stage, commit, push + open draft PR; CI `test` check passes green | ⊕workspace-ci | not-started | — | — |

### Song Template Inventory

**Originals (4) → `catalog/sheet_music/originals/`**
| Template | Title | Key |
|----------|-------|-----|
| `abbeys_song.json` | Abbey's Song | Bm |
| `flyWayTylerJamesDrake.json` | Fly Away | C |
| `Lighthouse_Tyler_James_Drake.json` | Lighthouse | Em |
| `you_already_know_backup_2026-01-01.json` | You Already Know | E Major |

**Covers (27) → `catalog/sheet_music/covers/`**
| Template | Title | Artist | Key |
|----------|-------|--------|-----|
| (remaining 27 templates) | Ain't It Fun | Paramore | C |
| | Beaches | Beabadoobee | Dm |
| | Beaches (var 2) | Beabadoobee | Em |
| | Creep | Alba Reche | E |
| | Diamonds | Sam Smith | Bbm |
| | Fake Plastic Trees | Radiohead | A |
| | Genie in a Bottle | Christina Aguilera | Fm |
| | Go Your Own Way | Fleetwood Mac | F |
| | I Want Something That I Want | Grace Potter | Eb |
| | Imagine | Eva Cassidy | F# |
| | Killing Me Softly | Fugees | Em |
| | La Vida Es Fria | Jason Joshua | Fm |
| | Let It Fade | Ada Schmidt | Bm |
| | Lose Control | Teddy Swims | F#m |
| | Love on the Brain | Rihanna | G |
| | Lovefool | Cardigans | Am |
| | Missed Call | Treaty Oak Revival | Db |
| | Parachute | Chris Stapleton | D#m |
| | Paul | Big Thief | B |
| | Rise Up | Andra Day | Db |
| | Star Crossed | Scary Kids Scaring Kids | G#m |
| | Sweet Home Alabama | Lynyrd Skynyrd | G |
| | Take It Easy | Eagles | G |
| | Think | Aretha Franklin | G |
| | Undressed | Sombr | Bm |
| | Wicked Games | Chris Isaak | Bm |
| | You Can Leave Your Hat On | Joe Cocker | C |

### Tyler's Original Request
> Tyler has 31 song template JSON files in `f:\❤Music\studio_master\song_templates\`. A Python tool (`f:\❤Music\tools\make_chord_sheet.py`) generates formatted DOCX chord sheets from these templates. All 31 need to be generated and routed to the correct catalog location: Originals → `f:\❤Music\catalog\sheet_music\originals\`, Covers → `f:\❤Music\catalog\sheet_music\covers\`. After generation Tyler wants to visually review each generated DOCX before the branch is committed — so generation happens to the catalog path first, the folder is opened for review, then commit happens after Tyler signs off.

---

## Event Log

### 2026-04-26T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR registered at BRANCHED (Tyler pre-approved scope by direct specification of all details)

**Details:**
- Scope: ❤Music only
- Type: chore, Risk: low
- 31 templates → 4 originals + 27 covers
- Acceptance criteria: 6 ACs drafted
- Concurrency: path overlap with FR-20260426-sheet-music-catalog on `catalog/sheet_music/originals/`; recommend serializing or merging branches
- Cycle timer: 671c9098-9b69-4d5c-ad90-5adb1ab98a83

**Next:** ⊕workspace-ci — create branch `chore/heartmusic/sheet-music-from-templates` off ❤Music `main`; then ❤music-orchestrator for generation

---

## Artifacts

- **Perf runs:** 671c9098-9b69-4d5c-ad90-5adb1ab98a83 — fr-cycle-FR-20260426-chord-sheets-from-templates (closed: ok)
- **PRs:** https://github.com/tylerdrakemusic/Music/pull/15 (merged)
- **Commits:** 52755cf74d1c58f1963962800524a28551124a2c (branch), f0796b3241fc4d87b28317d643901c0a14cb4bfe (merge)

---

### Event Log

| Timestamp | Agent | Event |
|-----------|-------|-------|
| 2026-04-26 | ⊕workspace-ci | PR #15 marked ready for review (was draft) |
| 2026-04-26 | ⊕workspace-ci | PR #15 merged via merge commit f0796b3 into main (tylerdrakemusic/Music) |
| 2026-04-26 | ⊕workspace-ci | Local f:\❤Music pulled, fast-forwarded to f0796b3 |
| 2026-04-26 | ⊕workspace-ci | Cycle timer 671c9098 closed — status ok — FR-20260426-chord-sheets-from-templates complete |
