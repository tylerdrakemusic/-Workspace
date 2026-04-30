# FR-20260430-grill-me-intake — Integrate grill-me skill into intake Phase A

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260430-grill-me-intake
- **Title:** Integrate grill-me skill into intake Phase A
- **Type:** feature
- **Risk:** low
- **Projects:** ⊕Workspace
- **State:** TRIAGED
- **Branch:** pending
- **PRs:** pending
- **Cycle timer:** 5e822672-712c-4125-b748-ec77718e05b7
- **Opened:** 2026-04-30
- **Last updated:** 2026-04-30
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. `f:\⊕Workspace\.github\skills\grill-me\SKILL.md` exists with the skill definition mirroring Matt Pocock's grill-me source
2. Intake agent Phase A includes a vagueness + risk check that chooses batch vs. grill-me mode
3. Grill-me mode: one question at a time, recommended answer provided, explores codebase before asking if codebase can resolve it
4. Batch mode (2–5 questions, single `vscode_askQuestions` call) is preserved for clear, low-risk FRs
5. Skill is listed in `copilot-instructions.md` `<skills>` section with correct description

### Concurrency Notes
- Conflicts with: none
- Depends on: none

### Deliverable Tracker

| #   | Deliverable                                     | Owner                  | Status      | Proof | Updated    |
| --- | ----------------------------------------------- | ---------------------- | ----------- | ----- | ---------- |
| AC1 | Create `grill-me/SKILL.md`                      | ⊕workspace-intake      | not-started | —     | —          |
| AC2 | Update intake agent Phase A (vagueness/risk gate) | ⊕workspace-intake    | not-started | —     | —          |
| AC3 | Grill-me mode: one-at-a-time + recommended answer | ⊕workspace-intake    | not-started | —     | —          |
| AC4 | Batch mode preserved for clear/low-risk FRs    | ⊕workspace-intake      | not-started | —     | —          |
| AC5 | Register skill in `copilot-instructions.md`    | ⊕workspace-intake      | not-started | —     | —          |

### Tyler's Original Request
> integrate this skill into our intake procedure https://github.com/mattpocock/skills/blob/main/skills/productivity/grill-me/SKILL.md

---

## Event Log

### 2026-04-30T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, triage complete → TRIAGED

**Details:**
- Scope: ⊕Workspace (intake agent + new grill-me skill file)
- Risk: low
- Tyler confirmed scope on 2026-04-30
- Integration mode: auto-escalate on vague or medium/high-risk FRs
- Concurrency check: clean

**Next:** awaiting Tyler: approve scope (confirmed — proceed to BRANCHED)

---

## Artifacts

- **Perf runs:** 5e822672-712c-4125-b748-ec77718e05b7 — fr-cycle-FR-20260430-grill-me-intake
- **Proof artifacts:** —
- **PRs:** —
- **Commits:** —
- **Reports / dashboards:** —
