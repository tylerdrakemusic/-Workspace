---
name: ui-baseline-capture
description: "Capture a Playwright screenshot and page structure snapshot of UI surfaces before scope-clarification interview questions during FR/BFX intake. Store the screenshot as a fr_artifact baseline. QA agent uses the baseline for before/after comparison in its report. Invoked by ⊕workspace-intake (capture step) and ⊕workspace-qa (diff hook)."
user-invocable: false
applyTo: ".github/agents/⊕workspace-intake.agent.md, .github/agents/⊕workspace-qa.agent.md"
---

# UI Baseline Capture Skill

Two entry points: **intake capture** (runs before Phase A interview) and **QA diff hook**
(runs during `FUNCTIONAL_QA` when a baseline exists). Procedure for each is below.

---

## 1 — Intake: Capture Step

### 1.1 Trigger Detection

Fire this skill when **either** condition is met:

**File-impact heuristics** — FR title, notes, or any file path mentioned contains:
- Extension: `.html`, `.css`, `.js` (frontend only — not backend scripts)
- Directory: `output/`, `reports/`, `src/static/`, `templates/`

**Keyword match** — FR title or notes contain (case-insensitive):
`dashboard`, `portal`, `UI`, `UX`, `layout`, `page`, `panel`, `chart`, `table`,
`button`, `form`, `modal`, `sidebar`, `tab`, `nav`, `style`, `design`, `display`

If neither condition is met: skip this skill entirely.

---

### 1.2 Surface Discovery

Collect capture targets in this order (deduplicate by URL/path):

**Step A — project `dashboard.json`**
For each affected project, read `<project-root>/dashboard.json`.
Look for fields: `url`, `local_url`, `path`, `file`. Collect all non-null values.

Example fields to check:
```json
{ "url": "http://localhost:7474", "local_path": "output/portal.html" }
```

**Step B — FR title and notes**
Extract any file path (`.html`, `output/...`, `reports/...`) or URL (`http://...`)
mentioned by Tyler. Add to the target list.

**Step C — fallback**
If zero targets found after A+B: log "No UI surfaces found — skipping capture"
in the scope card. Do NOT block. Proceed to Phase A interview questions.

---

### 1.3 Capture Procedure

For each surface in the target list:

1. **Serve local files if needed** — if the target is a local `.html` path (not
   a running server URL), open it directly via `file://` URL in the browser:
   ```
   file:///f:/path/to/dashboard.html
   ```
   No server spin-up required for static HTML files.

2. **Navigate**: `mcp_playwright_browser_navigate` to the URL/path.

3. **Screenshot**: `mcp_playwright_browser_take_screenshot` — full page.

4. **Page structure snapshot**: `mcp_playwright_browser_snapshot`
   This returns the accessible elements tree (visible text, headings, button
   labels, form fields, link text). Trim to the first 120 lines if verbose.

5. **Handle failures gracefully**: if navigation times out or page is
   unreachable, record a warning: "Surface `<url>` unreachable — skipped."
   Continue with remaining surfaces. Do NOT abort Phase A.

---

### 1.4 Output

**Inline in scope card (Phase B):**

```markdown
### 📸 UI Baseline — <surface name>
[Screenshot attached]

**Page structure (key elements):**
- <heading 1>
- <button label / link text>
- <table/chart caption>
...
```

Include one block per captured surface.

**Store as fr_artifact:**
```powershell
$env:PYTHONUTF8="1"
# Save screenshot to proof folder first
$screenshotPath = "f:\⊕Workspace\proof\<FR-ID>-ui-baseline-<slug>.png"
# Then record artifact
C:\G\python.exe f:\⊕Workspace\src\utils\fr_cli.py record-artifact <FR-ID> screenshot "ui-baseline" --path $screenshotPath
```

Artifact key is always `"ui-baseline"`. If multiple surfaces, append a slug:
`"ui-baseline-portal"`, `"ui-baseline-dashboard"`, etc.

---

## 2 — QA: Diff Hook

### 2.1 Trigger

Run this hook when **both** are true:
- The FR has a `screenshot` artifact with label matching `ui-baseline*`
- The FR diff contains at least one `.html` file or `output/` path

Retrieve baseline artifact path:
```powershell
$env:PYTHONUTF8="1"
C:\G\python.exe f:\⊕Workspace\src\utils\fr_cli.py get <FR-ID>
# Look for artifact_type=screenshot, label starting with 'ui-baseline'
```

---

### 2.2 After-State Capture

Repeat the surface discovery and capture procedure from §1.2–1.3 on the
**currently-implemented** surfaces (post-implementation state). This is the
"after" screenshot.

---

### 2.3 Diff Report

Include the following block in the QA report under the `## Playwright` section:

```markdown
## UI Before/After Comparison

| Surface | Before (baseline) | After (post-impl) |
|---|---|---|
| <surface name> | [screenshot: fr_artifact ui-baseline] | [screenshot: captured now] |

**Changes observed:**
- <list visible changes: new element, removed element, layout shift, text change>
- OR: "No visible differences detected."

**Assessment:** PASS — changes match acceptance criteria / FAIL — unexpected regressions
```

Record the after screenshot as a proof artifact:
```powershell
$env:PYTHONUTF8="1"
C:\G\python.exe f:\⊕Workspace\src\utils\proof_cli.py record <run_id> "⊕workspace-qa" screenshot "UI after-state: <surface>" --path <after-screenshot-path>
```

If the baseline artifact is missing or the path is no longer readable: note
"Baseline unavailable — before/after diff skipped" and proceed. Do NOT fail QA
solely because the baseline is missing.
