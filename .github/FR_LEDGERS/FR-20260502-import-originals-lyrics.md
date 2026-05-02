# FR-20260502-import-originals-lyrics — Import Originals Lyrics from `❤Music/lyrics/` into Catalog

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260502-import-originals-lyrics
- **Title:** Import Originals Lyrics from `❤Music/lyrics/` into Catalog (+ relocate People*.pdf to covers/)
- **Type:** feature
- **Risk:** low
- **Projects:** ❤Music
- **State:** BRANCHED
- **Branch:** feature/❤music/import-originals-lyrics
- **Worktree:** F:\worktrees\FR-20260502-import-originals-lyrics\heartmusic
- **PRs:** [Music#25](https://github.com/tylerdrakemusic/Music/pull/25) (draft)
- **Cycle timer:** 60938f97-9352-4758-b786-e2b3a200db3e
- **Opened:** 2026-05-02
- **Last updated:** 2026-05-02
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. New import capability ingests `.txt` lyric files from `f:\❤Music\lyrics\` into the ❤Music catalog as **originals** lyrics, attributed to Tyler James Drake, with title derived from filename.
2. Capability supports `--dry-run` (preview, no writes) and `--apply` (perform writes) modes.
3. As part of `--apply`, the following files are **moved** from `f:\❤Music\catalog\sheet_music\originals\` to `f:\❤Music\catalog\sheet_music\covers\` (target dir created if missing): `People.pdf`, `People Bass.pdf`, `People Tab.pdf`. These files are **not** imported as originals lyrics.
4. The PDF move is logged (source path → destination path) and is idempotent (running `--apply` again with the files already moved is a no-op, not an error).
5. Existing lyrics rows for the same originals are not duplicated — re-running `--apply` is idempotent.
6. Pytest test(s) cover: dry-run yields no DB or filesystem writes; apply imports expected count of originals; apply moves the 3 People PDFs to covers/; re-running apply is idempotent for both lyrics and PDF moves.
7. Audit log / output summary lists imported lyric files, skipped files, and moved PDFs.

### Concurrency Notes
- Conflicts with: none (no other in-flight ❤Music FR touches `catalog/sheet_music/originals/` or `lyrics/`)
- Depends on: none

### Deliverable Tracker

| #   | Deliverable                                                              | Owner               | Status      | Proof | Updated |
| --- | ------------------------------------------------------------------------ | ------------------- | ----------- | ----- | ------- |
| AC1 | Import tool ingests `❤Music/lyrics/*.txt` as originals                   | ❤music-orchestrator | not-started | —     | —       |
| AC2 | `--dry-run` / `--apply` modes                                            | ❤music-orchestrator | not-started | —     | —       |
| AC3 | People*.pdf moved to `catalog/sheet_music/covers/` during `--apply`      | ❤music-orchestrator | not-started | —     | —       |
| AC4 | PDF move logged + idempotent                                             | ❤music-orchestrator | not-started | —     | —       |
| AC5 | Lyric import idempotent (no duplicate rows)                              | ❤music-orchestrator | not-started | —     | —       |
| AC6 | Pytest coverage for dry-run, apply, idempotency, PDF move                | ❤music-orchestrator | not-started | —     | —       |
| AC7 | Audit/summary output lists imported, skipped, and moved files            | ❤music-orchestrator | not-started | —     | —       |

### Tyler's Original Request
> Import the lyrics in `f:\❤Music\lyrics\` as originals lyrics into the ❤Music catalog. Also move `People*.pdf` files from `F:\❤Music\catalog\sheet_music\originals\` to `F:\❤Music\catalog\sheet_music\covers\` (creating that directory if needed) — folded into this FR. The import capability should perform the move as part of `--apply`, log the move, and not import them as originals lyrics.

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-05-02T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, triage complete → TRIAGED

**Details:**
- Scope: ❤Music (single-project)
- Type: feature; Risk: low (file I/O + DB inserts; no auth, secrets, agent framework, DB schema changes, or health interventions)
- Source data: `f:\❤Music\lyrics\` contains 9 `.txt` lyric files (A Second Flight, Abbey's Song, Fata Morgana, Fly, My Bond, NFT, Nebula Blue, Reflection, Whole) + 1 PDF (Abbey's Song.pdf — out of scope for this FR)
- People PDFs to relocate: `People.pdf`, `People Bass.pdf`, `People Tab.pdf` confirmed present in `catalog/sheet_music/originals/`
- Concurrency check: clean — no in-flight FRs touch the affected paths
- Cycle timer started: run_id 60938f97-9352-4758-b786-e2b3a200db3e

**Next:** awaiting Tyler: approve scope

### 2026-05-02T00:00:01Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** Tyler confirmed scope (with PDF-move folded in) → BRANCHED (pending CI)

**Details:**
- Tyler approved the scope and explicitly requested folding the People*.pdf relocation into THIS FR rather than spinning a separate one. Acceptance criteria updated accordingly (AC3, AC4, AC6, AC7).
- Open clarification removed.

**Next:** delegating to ⊕workspace-ci to create branch `feature/❤music/import-originals-lyrics` + draft PR.

### 2026-05-02T00:00:02Z — ⊕workspace-intake

**Event:** delegation

**Summary:** Handing off to ⊕workspace-ci for branch + draft PR creation.

**Details:**
Payload:
```
{
  "fr_id": "FR-20260502-import-originals-lyrics",
  "type": "feature",
  "repos": ["❤Music"],
  "branch": "feature/❤music/import-originals-lyrics",
  "base_branch": "main",
  "draft_pr": true
}
```

**Next:** ⊕workspace-ci to create branch + worktree + draft PR; return PR URL; transition to BRANCHED.

---

## Artifacts

<!-- APPEND-ONLY. Links to concrete evidence. -->

- **Perf runs:** 60938f97-9352-4758-b786-e2b3a200db3e — FR cycle timer (intake → merge)

---

### 2026-05-02T15:55:00Z — ⊕workspace-ci

**Event:** state-transition

**Summary:** Branch + worktree + draft PR created → BRANCHED

**Details:**
- Branch `feature/❤music/import-originals-lyrics` created from `tylerdrakemusic/Music@main` (`60a57c4`) and pushed to origin.
- Worktree provisioned at `F:\worktrees\FR-20260502-import-originals-lyrics\heartmusic`.
- Empty commit `6d6c591` opened the branch ahead of `main` so a draft PR could be filed.
- Draft PR opened: [tylerdrakemusic/Music#25](https://github.com/tylerdrakemusic/Music/pull/25).
- Registry row flipped from `BRANCHED (pending CI)` → `BRANCHED` and PR URL recorded.

**Next:** ❤music-orchestrator picks up the worktree to implement AC1–AC7.
