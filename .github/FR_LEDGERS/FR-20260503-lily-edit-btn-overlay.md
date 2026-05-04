# FR-20260503-lily-edit-btn-overlay — Lily edit-prompt button: portrait overlay (top-right), matching Nova bio-panel

## Metadata
- **FR ID:** FR-20260503-lily-edit-btn-overlay
- **Title:** Lily edit-prompt button — portrait overlay top-right, matching Nova bio-panel
- **Type:** fix / UX
- **Projects:** 👁AI-Manifest
- **State:** MERGED → CLOSED
- **Owner:** ⊕workspace-overseer
- **Opened:** 2026-05-03
- **Updated:** 2026-05-03

## Problem Statement

The Lily edit-prompt button in the Executive Audio Brief portal was a labelled pill button (`✏️ Edit Prompt`) rendered **below** the portrait image. The ∞Life bio-panel uses a more refined pattern: a small circular icon overlaid at `top:4px; right:4px` on the portrait, with subtle opacity and no visible text label. Tyler wanted Lily's button to match the Nova pattern.

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| AC1 | `.lily-portrait` wrapper gains `position: relative` so the absolute child positions correctly |
| AC2 | `.lily-edit-btn` CSS changed to `position:absolute; top:4px; right:4px; border-radius:50%; width:22px; height:22px; padding:0; display:flex; align-items:center; justify-content:center; font-size:12px; background:rgba(0,0,0,0.55); border:none; cursor:pointer; opacity:0.35; transition:opacity 0.2s; color:#fff` |
| AC3 | `.lily-edit-btn:hover { opacity: 0.9; }` |
| AC4 | Button HTML text changes from `✏️ Edit Prompt` to `✏` only; `title` attribute retained |
| AC5 | `onmouseenter`/`onmouseleave` inline handlers added matching Nova pattern |
| AC6 | Modal open / save / regen logic is **unchanged** |
| AC7 | Regenerated `executive_brief_portal.html` reflects the new overlay layout |

## Out of Scope
- Modal internals (two-step save+regen flow)
- Server endpoints
- Any other panel

## Reference
- **Nova pattern source:** `f:\∞Life\src\dashboard\gen_biomarker_dashboard.py` — `.nova-portrait-wrap` + `.nova-edit-btn`
- **Target file:** `f:\👁AI-Manifest\tools\executive_audio_brief.py`

## Branch / PR
- **Branch:** `feature/ai-manifest/lily-edit-btn-overlay`
- **Repo:** `tylerdrakemusic/AI-Manifest`
- **PR:** [AI-Manifest#19](https://github.com/tylerdrakemusic/AI-Manifest/pull/19) (merged)

## Proof Artifacts
- `file_modified` — `f:\👁AI-Manifest\tools\executive_audio_brief.py`
- `file_modified` — `f:\👁AI-Manifest\output\executive_brief_portal.html`
- Perf run: `bdf3d94c-a0d4-45cf-94a0-4f7106d2715c` — 186.9s — ok
