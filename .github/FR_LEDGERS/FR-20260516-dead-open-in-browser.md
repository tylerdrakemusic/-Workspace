# FR-20260516-dead-open-in-browser

**Title:** Remove dead "Open in Browser Γåù" button from Live Dashboard header  
**Type:** bugfix  
**State:** TRIAGED ΓåÆ IN_PROGRESS  
**Projects:** ΓèòWorkspace  
**Opened:** 2026-05-16  
**Owner:** Γèòworkspace-intake  

## Problem

The `dashboard_portal.py` portal generator unconditionally renders an  
`<a href="..." target="_blank" class="open-btn">Open in Browser Γåù</a>`  
anchor inside every `flask_app`-type Live Dashboard header pane.  
Affected panels: Γ¥ñMusic dashboard, TJD Radio, Studio dashboard, Executive dashboard.

In the VS Code webview panel, `target="_blank"` links are blocked/dead ΓÇö no  
browser tab opens. Tyler works exclusively within the side panel and does not  
need this button.

## Root Cause

`tools/dashboard_portal.py` ΓÇö `_panes()` function, `flask_app` branch:  
the `<a class="open-btn">Open in Browser Γåù</a>` anchor is always emitted.

## Fix

Remove the single `<a class="open-btn">` f-string fragment from `_panes()`.  
Regenerate the portal HTML.

## Files Changed

- `ΓèòWorkspace/tools/dashboard_portal.py` ΓÇö 1 line removed
- `ΓèòWorkspace/output/portal.html` (or equivalent) ΓÇö regenerated

## Acceptance Criteria

- [ ] Live Dashboard header shows only `ΓùÅ Live Dashboard` label ΓÇö no link/button
- [ ] Portal regenerates cleanly with no errors
- [ ] Guitar Trainer pane (already exempt) unaffected
