# ❤Music Agentic Chord Sheet Flow Prompt

Use this prompt to invoke the agentic chord-sheet generation workflow for ❤Music.

## Context
- This replaces the disabled Ollama-based Chord Sheets dashboard tab (`BFX-20260630-chord-sheet-ollama-timeout`, closed — llama3.1:8b proved unreliable for verbatim long-context JSON transcription).
- The canonical procedure lives in the skill: `f:\⊕Workspace\.github\skills\❤music-chord-sheets\SKILL.md`. Read and follow it in full before doing any parsing/generation work.
- Do not use Ollama or any local LLM for this flow — this is an in-chat Copilot-driven procedure.

## Invocation
When Tyler hands you one or more inputs (PDF, raw text, URL, image, or any document with song structure) and asks for chord sheets, invoke the `❤music-chord-sheets` skill:

1. Parse each input into the `song_template.json` schema.
2. Route each song to `catalog/sheet_music/covers/` (any artist other than Tyler James Drake) or `catalog/sheet_music/originals/` (Tyler James Drake originals), per the skill's `is_tyler_original` logic.
3. Generate the `.docx` via `tools/make_chord_sheet.py`.
4. Validate the generated `.docx` against the source input with Playwright before presenting results.
5. Batch mode: process all inputs handed to you in the session before presenting the full batch for review.
6. Present all generated files to Tyler for review at the end of the batch.
7. Only git-commit approved `.docx` files, JSON templates, and any process logs after Tyler's explicit sign-off — never commit automatically.

## Notes
- BPM values are currently entered manually (e.g. sourced from getsongbpm.com) — see the pending FR for automating this via the GetSongBPM API once Tyler provides an API key.
