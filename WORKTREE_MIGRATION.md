# Worktree Migration Plan (FR-20260511)

## Old Strategy (Deprecated)
- **Location:** `f:\worktrees\{project}\{branch}\`
- **Issue:** External paths caused IDE approval friction
- **Status:** Deprecated 2026-05-11

## New Strategy (Active)
- **Location:** `f:\⊕Workspace\.worktrees\{branch-slug}\` (workspace-local)
- **Benefits:** 
  - No IDE approval friction
  - Workspace-local mental model
  - Batch creation (N worktrees = 1 approval gate)
- **Effective:** 2026-05-11 onwards

## Migration for Existing Worktrees
1. For each active worktree in `f:\worktrees\`:
   - Check if associated FR is still IN_PROGRESS or REVIEW_REQUESTED
   - If active: Move to `.worktrees/` location (or recreate from feature branch)
   - If completed: Clean up old worktree (`git worktree remove`)

2. After migration:
   - Delete `f:\worktrees\` directory (no longer used)
   - Update all agent documentation to reference `.worktrees/` only

## Timeline
- **2026-05-11:** New strategy activated (AC1–AC8 complete)
- **2026-05-25:** All existing external worktrees deprecated
- **2026-06-01:** `f:\worktrees\` directory removed from filesystem
