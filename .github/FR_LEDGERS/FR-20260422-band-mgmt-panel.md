# FR-20260422-band-mgmt-panel — Band Management Panel (Workspace Portal)

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260422-band-mgmt-panel
- **Title:** Band Management Panel (Workspace Portal)
- **Type:** feature
- **Risk:** low
- **Projects:** ❤Music, ⊕Workspace
- **State:** MERGED → CLOSED
- **Branch:** main (inline delivery by other agent)
- **PRs:** delivered inline on main by other agent; confirmed by Tyler 2026-04-22
- **Cycle timer:** 62a7b268-cf8d-406d-b395-8cdb01ef3128
- **Opened:** 2026-04-22
- **Last updated:** 2026-04-22
- **Closed:** 2026-04-22
- **Final state:** MERGED — closure recorded retroactively by ⊕workspace-overseer per Tyler confirmation that implementing agent forgot to flip state.

### Acceptance Criteria

1. `f:\⊕Workspace\reports\portal.html` contains a new "Band Management" panel section
2. The panel displays all 39 setlist songs (SET 1–3) in a table with: #, Title, Artist, Key, BPM columns
3. Artist names are sourced from `G:\Muzic` filename cross-reference — no fabricated data
4. BPM column exists but cells with unknown BPM display a visible `?` marker (data gap, awaiting confirmation)
5. Setlist source file (`Rough CC Prost 05022026.xlsx`) is migrated to `f:\❤Music\` in an agreed path (see Migration Plan below) and committed
6. Two data-gap songs ("Celebrate", "Play That Funky Music") and the Rhiannon key discrepancy are resolved by Tyler before final implementation fills those cells
7. Panel is styled consistently with existing portal.html panels

### Concurrency Notes

- Conflicts with: none detected (portal.html and ❤Music catalog not touched by any active FR)
- Depends on: none

### Tyler's Original Request

> Add a new **Band Management Panel** to `f:\⊕Workspace\reports\portal.html`. The panel should:
> - Display the active gig setlist as the baseline music catalog
> - Include song metadata: title, artist, key, BPM (cross-reference `G:\Muzic` audio files for data; confirm with Tyler if anything is missing — do NOT fabricate)
> - The setlist file is on Tyler's desktop and should be migrated into the `❤Music` repo as part of this feature

---

## Scope Description

**❤Music** — owns the setlist data. The Excel file (`Rough CC Prost 05022026.xlsx` from Tyler's Desktop) will be migrated here. This project's catalog directory will house the canonical setlist going forward.

**⊕Workspace** — owns `reports/portal.html`. A new "Band Management" panel will be appended to the portal with the full setlist table, keyed off the ❤Music data.

---

## Setlist Data — Extracted from `Rough CC Prost 05022026.xlsx` (Sheet: CC Pines 111425)

**Source file:** `C:\Users\tyler\Desktop\Rough CC Prost 05022026.xlsx` (modified 2026-04-19)
**Gig:** Copper Creek Prost 5/2/26

### Full Setlist (39 songs across 3 sets)

| Set | # | Setlist Title (raw) | Key (setlist) | Artist (from G:\Muzic) | BPM | Notes |
|-----|---|---------------------|---------------|------------------------|-----|-------|
| 1 | 1 | Long Train Runnin | Gm | The Doobie Brothers | ? | |
| 1 | 2 | Too Much Time | A | Styx | ? | |
| 1 | 3 | Im Alright | D | Kenny Loggins | ? | |
| 1 | 4 | Bobby McGee | G | Janis Joplin | ? | |
| 1 | 5 | Rhiannon | Am | Fleetwood Mac | ? | ⚠ KEY DISCREPANCY: setlist says Am, G:\Muzic file says "in Bm" |
| 1 | 6 | Gold On Ceiling | G | The Black Keys | ? | |
| 1 | 7 | Call Me | B | Blondie | ? | |
| 1 | 8 | Shaded Jade | Bm | Tamala Cameron and Gene Ngo | ? | File: "Deeper Shade of Jade" |
| 1 | 9 | Reeling In the Yrs | A | Steely Dan | ? | |
| 1 | 10 | I Will Survive | Am | Gloria Gaynor | ? | |
| 1 | 11 | Love Sneaking Up | D | Bonnie Raitt | ? | |
| 1 | 12 | Boots | E | Nancy Sinatra | ? | File: "These Boots Are Made for Walkin'" |
| 1 | 13 | I Can't Go 4 That | F | Daryl Hall and John Oates | ? | |
| 2 | 1 | 25 or 6 to 4 | A | Chicago | ? | |
| 2 | 2 | What You Need | F# | INXS | ? | |
| 2 | 3 | Do It Again | Gm | Steely Dan | ? | |
| 2 | 4 | Baker Street | D | Gerry Rafferty | ? | |
| 2 | 5 | Celebrate | Ab | **UNKNOWN** | ? | ⚠ DATA GAP: no file in G:\Muzic — artist unconfirmed |
| 2 | 6 | Disco Inferno | Ab | Tina Turner | ? | |
| 2 | 7 | Black Magic | Dm | Santana | ? | File: "Black Magic Woman" |
| 2 | 8 | Logical Song | C | Supertramp | ? | |
| 2 | 9 | Jacky | Gm | Jim Mann | ? | File dated 1-7-24 |
| 2 | 10 | Carnival | F#m | Natalie Merchant | ? | |
| 2 | 11 | I Feel the Earth | Cm | Carole King | ? | |
| 2 | 12 | Heart of R&R | C | Huey Lewis and the News | ? | |
| 2 | 13 | Heavy Chevy | C | Alabama Shakes | ? | |
| 3 | 1 | Pick Up the Pieces | Fm | Average White Band | ? | |
| 3 | 2 | Play That Funky M | Em | **UNKNOWN** | ? | ⚠ DATA GAP: no file in G:\Muzic — likely Wild Cherry but unconfirmed |
| 3 | 3 | On the Dark Side | E | John Cafferty | ? | |
| 3 | 4 | What I Like About U | E | The Romantics | ? | |
| 3 | 5 | Smooth Operator | Dm | Sade | ? | |
| 3 | 6 | Smooth | Am | Santana feat. Rob Thomas | ? | |
| 3 | 7 | What I Do | Bm | Tyler James Drake | ? | Original |
| 3 | 8 | Stop Draggin My Hrt | Em | Stevie Nicks | ? | |
| 3 | 9 | The Letter | Bbm | Joe Cocker | ? | |
| 3 | 10 | Blue on Black | C | Kenny Wayne Shepherd | ? | |
| 3 | 11 | Evil Ways | Gm | Santana | ? | |
| 3 | 12 | Peg | G | Steely Dan | ? | |
| 3 | 13 | Roll With Changes | C | REO Speedwagon | ? | |

---

## Data Gaps (Require Tyler's Confirmation)

### GAP-1: BPM — All 39 Songs
The Excel setlist contains no BPM column. BPM is not inferrable from filename alone.
**Resolution needed:** Tyler to provide BPM data, OR accept that BPM column shows `?` as a placeholder in the initial panel build with BPM entry deferred.

### GAP-2: "Celebrate" — Set 2 #5
No audio file matching "Celebrate" found in `G:\Muzic`.
**Resolution needed:** Confirm artist. (Common candidates: Kool & the Gang, or other.)

### GAP-3: "Play That Funky M" — Set 3 #2
No audio file matching "Play That Funky" found in `G:\Muzic`.
**Resolution needed:** Confirm artist. (Likely "Play That Funky Music" by Wild Cherry, but NOT confirmed from files.)

### GAP-4: Rhiannon Key Discrepancy
- Setlist says key = **Am**
- `G:\Muzic` file is named `Rhiannon - Fleetwood Mac (in Bm).wav`
**Resolution needed:** Confirm which key the band actually performs it in.

---

## Migration Plan

**From:** `C:\Users\tyler\Desktop\Rough CC Prost 05022026.xlsx`
**To:** `f:\❤Music\catalog\setlists\Rough CC Prost 05022026.xlsx`

The `catalog/setlists/` directory will be created if it does not exist. The file will be committed to the ❤Music repo as the canonical source of truth for active gig setlists.

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-04-22T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, data extracted, triage complete → TRIAGED

**Details:**
- Scope: ❤Music (setlist data, migration), ⊕Workspace (portal.html panel)
- Excel setlist extracted: 39 songs across 3 sets, Copper Creek Prost 5/2/26
- G:\Muzic cross-reference complete: 36/39 artists confirmed, 3 data gaps identified
- BPM blanket gap: no BPM data in source file
- Concurrency check: clean
- Risk: low

**Next:** awaiting Tyler: approve scope

---

## Artifacts

- **Perf runs:** 62a7b268-cf8d-406d-b395-8cdb01ef3128 — FR cycle timer started at intake
- **Source data:** `C:\Users\tyler\Desktop\Rough CC Prost 05022026.xlsx` (last modified 2026-04-19)
- **Audio catalog:** `G:\Muzic` — 190+ mp3/wav files cross-referenced


---

### 2026-04-22 — ⊕workspace-overseer

**Event:** retroactive-closure

**Summary:** State corrected to MERGED / CLOSED.

**Details:** Implementing agent delivered this FR but did not update the registry or ledger header. Tyler confirmed delivery during session wrap-up. State corrected retroactively; no code changes in this commit — bookkeeping only.

**Next:** none — FR closed.
