---
name: ❤music-chord-sheets
description: 'Agentic chord-sheet generation for ❤Music. Use when Tyler hands Copilot one or more input files/links in chat (PDF, raw text, URL, image, or any parseable song structure) and asks to turn them into chord sheets. Covers parsing unconstrained input into the song_template.json schema, routing output to covers/ vs originals/ (Tyler James Drake = original, all other artists = cover), generating the .docx via tools/make_chord_sheet.py, Playwright-based accuracy validation against the source, batch review, and git commit on Tyler''s approval. Triggers: "make a chord sheet", "chord sheet for <song>", "process these songs into chord sheets", "generate sheet music from this PDF/text/link". Replaces the disabled Ollama-based Chord Sheets dashboard tab (BFX-20260630).'
---

# ❤music-chord-sheets

Turns raw song input Tyler pastes/attaches in chat into reviewed, catalog-ready
chord sheet `.docx` files — entirely in-session, no CLI or dashboard automation.

## Why a skill, not a new agent

This is a single repeatable procedure with no need for context isolation or
per-stage tool restrictions — every step (parse → template → docx → validate →
log) runs in the same conversation with the same tool access. It is invoked
directly by Tyler in chat, or as a capability of the existing `❤music-catalog`
/ `❤music-production` agents. A dedicated `.agent.md` would add a persona and
subagent-delegation overhead this workflow doesn't need.

## When to Use
- Tyler pastes or attaches one or more chord charts / lead sheets / lyric+chord
  PDFs / URLs / images in chat and asks for a chord sheet, sheet music, or
  "process this song".
- Batch requests ("do these 5 songs") — process sequentially, one at a time,
  within this session.

## Procedure

For **each** input file, in order:

### 1. Extract song structure
Read the input (PDF text, raw paste, fetched URL, or described image) and
parse it into the `song_template.json` schema used by
[`tools/make_chord_sheet.py`](../../../../❤Music/tools/make_chord_sheet.py):

```json
{
  "title": "...", "artist": "...", "key": "...", "bpm": "...",
  "sections": [
    { "name": "Verse 1", "lines": [ { "chords": "Dm F Am Dm", "lyrics": "..." } ] }
  ]
}
```
- Preserve chord/lyric line pairing exactly as they appear in the source.
- Use `[Section]` markers in raw text as section boundaries.
- Best-effort `key`/`bpm` if not explicit in the source (mark `"?"` if unknown — do not fabricate).
- If input is genuinely unparseable, stop and tell Tyler rather than guessing content.

### 2. Resolve output paths
Call [`resolve_chord_sheet_paths`](../../../../❤Music/src/utils/chord_sheet_output.py)
with the parsed `title`/`artist` and the ❤Music repo root. This returns:
- `sheet_music_path` — `catalog/sheet_music/originals/` if artist is Tyler
  James Drake, else `catalog/sheet_music/covers/` — named
  `{Artist} - {Title}.docx`.
- `template_path` — `studio_master/song_templates/{Artist} - {Title}.json`.
- `log_path` — `catalog/sheet_music/_process_logs/chord_sheets_runs.jsonl`
  (new directory; this is the workspace convention for this skill's process
  logs — one JSONL file, one line per processed input).

### 3. Save JSON template
Write the parsed song JSON to `template_path` (create parent dirs as needed).

### 4. Generate the .docx
Import `build_docx` and `load_song` from `tools/make_chord_sheet.py` and call
`build_docx(song, sheet_music_path)`.

### 5. Validate with Playwright
Extract text back out of the generated `.docx` (python-docx paragraph text)
and call
[`render_validation_html`](../../../../❤Music/src/utils/chord_sheet_output.py)
with the original source lines vs. the extracted generated lines. Open the
resulting HTML report with a Playwright browser tool and inspect the
rendered mismatch count/rows before presenting the song to Tyler. Report any
mismatches — do not silently accept them.

### 6. Log the run
Call `log_chord_sheet_run(log_path, {...})` with `title`, `artist`,
`sheet_music_path`, `template_path`, `is_original`, and the mismatch count
from step 5.

### 7. Batch review + commit
After all inputs in the batch are processed, present the full list (docx
paths + validation summaries) to Tyler for review. On his approval, `git add`
the approved `.docx` / `.json` files and commit to the current branch. Do not
push — that is `⊕workspace-ci`'s job.

## Constraints
- Do NOT touch `music_dashboard.py`'s disabled Chord Sheets tab code
  (`ENABLE_CHORD_SHEETS = False`).
- Do NOT fabricate lyrics, chords, or metadata not present in the source input.
- Do NOT push commits — stage and commit locally only.
