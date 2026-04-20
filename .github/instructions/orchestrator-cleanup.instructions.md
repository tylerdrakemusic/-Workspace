---
description: "Use when any orchestrator agent finishes a multi-step workflow or todo list. Covers cleanup, TODO sync, and session hygiene."
applyTo: ".github/agents/*-orchestrator.agent.md"
---

# Orchestrator Cleanup Protocol

**After completing a set of todos or multi-step workflow, ALWAYS run this cleanup before reporting final results.**

## Cleanup Checklist

1. **Mark all todos complete** — No orphaned in-progress or not-started items from the current batch
2. **Update project TODO files** — Sync completed work into `TODO_AI.md` and `TODO_TYLER.md`:
   - Move completed items from Active → Completed Log with date and agent name
   - Add any new follow-up tasks discovered during the work
   - Remove or update items that are no longer relevant
3. **Update PROJECT_PROFILE.json** (or equivalent) if project state changed materially (new capabilities, status changes, new dependencies)
4. **Clean up temp files** — Delete any scratch/temp files created during the workflow
5. **Verify no secrets exposed** — Quick grep for API tokens, passwords, or keys in any files touched
6. **Final status summary** — Report to the user:
   - What was completed (concise list)
   - What's next (top 2-3 remaining items from TODO)
   - Any blockers or items needing Tyler's input
