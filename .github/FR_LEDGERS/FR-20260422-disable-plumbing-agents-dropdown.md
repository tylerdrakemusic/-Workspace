# FR-20260422-disable-plumbing-agents-dropdown — Disable Plumbing Agents from VS Code Agent Dropdown

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260422-disable-plumbing-agents-dropdown
- **Title:** Disable Plumbing Agents from VS Code Agent Dropdown
- **Type:** chore
- **Risk:** low
- **Projects:** ⊕Workspace
- **State:** SIGNED_OFF
- **Branch:** superseded by FR-20260423-disable-plumbing-agents-branch
- **PRs:** superseded
- **Cycle timer:** be698f2b-094a-4618-9689-fb2610c81ba4
- **Opened:** 2026-04-22
- **Last updated:** 2026-04-24
- **Merged at:** 2026-04-24T03:10:00Z
- **Signed off at:** 2026-04-24T03:10:00Z
- **Closed:** 2026-04-24
- **Final state:** SIGNED_OFF

### Acceptance Criteria
1. `⊕workspace-doer.agent.md` has `user-invocable: false` in its YAML frontmatter
2. `⊕workspace-alignment.agent.md` has `user-invocable: false` in its YAML frontmatter
3. Both agents no longer appear in the VS Code agent mode picker (dropdown)
4. Both agents remain callable as subagents (invocable by orchestrators)
5. No other agent files are accidentally modified

### Concurrency Notes
- Conflicts with: none
- Depends on: none

### Tyler's Original Request
> "Let's disable agents from being shown in the drop down if they are just plumbing"

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-04-22T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, triage complete → TRIAGED

**Details:**
- Scope: ⊕Workspace only (agent files live in `f:\⊕Workspace\.github\agents\`)
- Affected files: `⊕workspace-doer.agent.md`, `⊕workspace-alignment.agent.md`
- Implementation: add `user-invocable: false` to each file's YAML frontmatter
- Concurrency check: clean (no active FRs touching agent files)
- Risk: low (frontmatter-only change; no code, no DB, no secrets)

**Next:** awaiting Tyler: approve scope

---

## Artifacts

- **Perf runs:** be698f2b-094a-4618-9689-fb2610c81ba4 — FR-intake-disable-plumbing-agents-dropdown cycle timer


### 2026-04-23T18:00:00Z — ⊕workspace-ci (drift-fix)

**Event:** verification

**Summary:** Verified still wanted as of 2026-04-23 per Tyler — state remains TRIAGED

**Details:**
- Tyler confirmed in drift-fix session that this FR is still desired
- No branch cut yet; no code changes; scope unchanged
- State remains TRIAGED; awaiting implementer pickup
- Reconciliation FR: FR-20260423-fr-state-drift-fix

**Next:** awaiting implementer — cut branch chore/workspace/disable-plumbing-agents-dropdown and apply frontmatter changes per ACs
