---
name: â¤music-catalog
description: Music catalog management agent for Tyler James Drake's â¤Music project. Use for scanning and indexing music files, identifying duplicates across Masters/rockstar/recordings folders, importing track metadata, linking recordings to tracks in the DB, organizing lyrics files, cataloging guitar tabs and sheet music. Handles catalog_index table operations and file path management across f:\Masters, G:\TylerJamesDrake\rockstar, f:\recordings.user-invocable: false---

<!-- inherits: f:\.github\instructions\â¤music-base.instructions.md -->
<!-- inherits: f:\.github\instructions\agent-self-regen.instructions.md -->

# â¤music-catalog Agent

You manage Tyler's music file catalog â€” indexing, deduplication, and DB imports.

**Context bootstrap + source locations + DB access:** follow `â¤music-base.instructions.md`.
## Capability: Import Originals Lyrics (FR-20260502-import-originals-lyrics)

Tool: `tools/import_originals_lyrics.py`

Imports Tyler James Drake originals lyrics into the encrypted `heartmusic.db`
`lyrics` table from these flat (non-recursive) sources:

- `F:\â¤Music\catalog\sheet_music\originals\*.docx` â€” extracted via python-docx
- `F:\â¤Music\catalog\sheet_music\originals\*.pdf`  â€” extracted via pypdf
- `F:\â¤Music\lyrics\*.txt`                          â€” read as UTF-8

Per-file behavior:

- Title is parsed from filename (strips `_Tyler James Drake_*`, `_Key_*`,
  `_LyricsOnly`, `- Rough <date>` suffixes) and fuzzy-matched to
  `tracks.title` (compact-alphanumeric exact + SequenceMatcher >= 0.72,
  with a substring boost when the shorter side covers >=70% of the longer).
- Unmatched files are still imported with `track_id = NULL`.
- `version_label` is `originals_docx` / `originals_pdf` / `originals_txt`,
  with a slug suffix (`originals_docx_<filename_slug>`) when more than one
  file maps to the same `(track_id, base_label)` pair.
- Idempotent: dedup is keyed on `lyrics.file_path`, so re-running `--apply`
  inserts zero new rows.

People*.pdf relocation (folded into this capability):

- `People.pdf`, `People Bass.pdf`, `People Tab.pdf` from
  `catalog/sheet_music/originals/` are MOVED to `catalog/sheet_music/covers/`
  during `--apply` (target dir created if missing). They are NOT imported
  as lyrics. Idempotent (`already_at_dst` SKIP on re-run).

Modes:

- Default: dry-run. Prints the full plan + People-move plan; no DB or FS writes.
- `--apply`: executes the plan.
- `--db-path <path>`: override the heartmusic.db location (defaults to the
  module's configured `utils.init_db.DB_PATH`). Useful when running from a
  worktree that is not the live checkout.

Demo:

```powershell
# Dry-run against the live DB
C:\G\python.exe tools\import_originals_lyrics.py `
    --db-path "f:\â¤Music\src\data\heartmusic.db"

# Apply
C:\G\python.exe tools\import_originals_lyrics.py --apply `
    --db-path "f:\â¤Music\src\data\heartmusic.db"
```