---
applyTo: ".github/agents/*-hygiene.agent.md"
---

# Hygiene Base Instructions

Shared sweep procedure for all `*-hygiene` agents. Apply these principles and checklist to the target project's specific paths.

---

## Core Principles

1. **Completed = archived.** Done tasks don't belong in active TODO files. Move to archive, keep only a summary line.
2. **Low priority = removed.** Task untouched for 2+ weeks and marked low priority → delete. If it matters, it'll come back.
3. **One source of truth.** Duplicate information across files creates drift. Pick canonical location and delete the rest.
4. **Research files decay.** Research older than 6 months should be flagged for re-review or archived.
5. **Temp files die.** Any `_test_*`, `_temp_*`, `_debug_*`, `tmp_*` file is garbage unless actively referenced.

---

## Sweep Checklist

### 1. TODO Hygiene
- Move all `[DONE]` / `[x]` items to `docs/archive/completed_tasks.md` with date
- Leave at most a "Phase N complete" summary line in the active file
- Remove any task that is both low-priority AND older than 14 days with no progress
- Collapse verbose task descriptions to single lines (< 120 chars)

### 2. Completed Log Maintenance
- Keep only the last 5 entries in active TODO files
- Move older completed entries to `docs/archive/completed_tasks.md`
- Keep Architecture Decisions / conventions tables in active files (reference, not clutter)

### 3. File Tree Scan
- `tools/` — `_test_*`, `_temp_*`, `_debug_*`, `tmp_*` files
- `src/` — unused imports, dead code files
- `research/` — empty folders, stale drafts (> 6 months)
- `docs/` — orphaned docs not referenced anywhere
- `logs/` — logs older than 30 days
- Project root — temp files, scratch scripts

### 4. Research Freshness
- Flag research files with no updates in > 6 months
- Flag research files referencing "pending" trials — check if results are available
- Remove research files fully superseded by newer ones (after archiving key findings)

### 5. Database Hygiene
- Report empty tables (do NOT drop without confirmation)
- Report orphaned records (records referencing deleted parent rows)
- Flag duplicate entries by key fields
- Do NOT delete any records — flag only

### 6. Agent/Instruction File Consistency
- Verify every `*-hygiene.agent.md` is referenced in the project's AGENT_STARTUP.md
- Verify instructions files have valid `applyTo` patterns
- Flag agents referencing deleted files or stale paths

### 7. Cross-Repo Agent Link Audit

Scan ALL known agent/skill locations — not just the current project:

| Location | Contains |
|---|---|
| `f:\.github\agents\` | ∞Life + ❤Music agents |
| `f:\.github\instructions\` | Shared instructions |
| `f:\superpowers\agents\` | Superpowers agents |
| `f:\superpowers\skills\` | Superpowers skills |

**Checks:**
- Every agent file has a valid `description` in frontmatter
- Every `<!-- inherits: ... -->` comment points to a file that exists
- Every agent listed in a "Known specialists" table has a matching `.agent.md` file
- Every `.agent.md` file is listed in at least one "Known specialists" table or `AGENTS.md`
- Every instruction with `applyTo` matches at least one existing file
- Flag orphaned agents (exist on disk but never referenced anywhere)
- Flag phantom agents (referenced in tables/docs but no `.agent.md` file exists)
- Run `f:\.github\tools\validate_agent_links.py` if available for automated check

### 8. Scope Creep Audit

**Trigger:** Any time integration work has been performed recently, or `src/integrations/` exists in any project.

Load and follow the `scope-creep` skill (`f:\.github\skills\scope-creep\SKILL.md`) to:

1. **Detect misplaced files** — scan `src/integrations/`, `src/utils/`, and project root for artifacts whose domain belongs to a different project
2. **Apply the Integration Boundary Rule:**
   - Core algorithm → stays in ⟨ψ⟩Quantum (e.g. `qaoa.py`, `circuit_*.py`)
   - Data adapter → belongs to the project that OWNS the data (e.g. `setlist_optimizer.py` → ❤Music, `supplement_scheduler.py` → ∞Life)
3. **Assess impact** before any move (consumers, imports, tests, hardcoded paths)
4. **Move + fix** with the 7-step procedure in the skill
5. **Report** all moves, import updates, and test results

**Common signals to trigger this check:**
- Recently completed cross-project integration (quantum + health, quantum + music, etc.)
- File names containing another project's domain terms (setlist, supplement, gig, biomarker, budget)
- Files in this project that import from another project's DB (`heartmusic.db`, `infinitelife.db`)
- Files that answer "yes" to: *"Would this file still make sense if ⟨ψ⟩Quantum were deleted?"*

---

## Archive Format

`docs/archive/completed_tasks.md`:

```markdown
## Phase N — Completed YYYY-MM-DD
| Task | Date | Notes |
|------|------|-------|
| Task description | YYYY-MM-DD | One-line notes |
```

---

## Output Report Format

```
HYGIENE REPORT — <date>
─────────────────────────
Archived:    X completed tasks
Removed:     X low-priority/stale items
Cleaned:     X temp/dead files
Flagged:     X items needing review
DB orphans:  X records
```

---

## Safety Rules

- **Never delete research files without archiving key findings first**
- **Never delete DB records** — flag them, let the project owner decide
- **Never remove items marked `[IN PROGRESS]`**
- **Ask before deleting anything recently modified or that looks like in-progress work**
- Prefer moving over deleting — `docs/archive/` is the graveyard
