# FR-20260425-intake-interview-driven — Make Intake More Interview-Driven and Less Assumption-Heavy

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260425-intake-interview-driven
- **Title:** Make Intake More Interview-Driven and Less Assumption-Heavy
- **Type:** chore
- **Risk:** low
- **Projects:** ⊕Workspace
- **State:** BRANCHED
- **Branch:** chore/workspace/intake-interview-driven
- **PRs:** https://github.com/tylerdrakemusic/-Workspace/pull/32
- **Cycle timer:** 11ed1327-c2fb-4b29-b1ce-e4ab05be5e97
- **Opened:** 2026-04-25
- **Last updated:** 2026-04-25
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. When given a sparse or ambiguous FR request, the intake agent asks at least 2 targeted clarifying questions before finalizing triage (rather than filling in gaps by assumption).
2. The interview covers: (a) what problem the request solves, (b) the expected outcome/behavior, and (c) what's explicitly out of scope — but only when the answer isn't already clear from the request.
3. The agent does not ask more than 5 questions in any single intake interview — avoids becoming an interrogation.
4. Acceptance criteria written after the interview are derived from Tyler's answers, not agent inference. Each criterion maps back to something Tyler stated.
5. When a request is already sufficiently clear (e.g. contains scope, behavior, and out-of-scope), the interview phase is skipped or abbreviated — the agent is not forced to ask questions for their own sake.
6. The agent explicitly summarizes what it heard before presenting the final scope card, giving Tyler a chance to catch misunderstandings before confirmation.

### Concurrency Notes
- Conflicts with: none
- Depends on: none

### Deliverable Tracker

| #   | Deliverable                                               | Owner              | Status      | Proof | Updated    |
| --- | --------------------------------------------------------- | ------------------ | ----------- | ----- | ---------- |
| AC1 | Interview flow in `.github/agents/⊕workspace-intake.agent.md` | project orchestrator | not-started | —     | —          |
| AC2 | Max-question guard (≤5) in agent instructions            | project orchestrator | not-started | —     | —          |
| AC3 | Summary-before-scope-card step in agent instructions     | project orchestrator | not-started | —     | —          |

### Tyler's Original Request
> "the intake needs to be more interviewish so you aren't making too many assumptions about the feature request and are probing the user for clarity. It shouldn't be too exhaustive but not be too limited either. Enough to give intake the necessary clarity without being an exhaustive interview process"

---

## Event Log

### 2026-04-25T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, triage complete → TRIAGED

**Details:**
- Scope: ⊕Workspace — `.github/agents/⊕workspace-intake.agent.md`
- Type: chore (improvement to existing agent behavior/instructions)
- Risk: low — agent instructions file only, no code/schema/data changes
- Acceptance criteria drafted (6 criteria, see Header)
- Concurrency check: clean — no active FRs touch this file. FR-20260422-playwright-mcp-setup is in REVIEW_REQUESTED on ⊕Workspace but targets Node.js/Playwright setup — no overlap.
- Cycle timer started: run_id 11ed1327-c2fb-4b29-b1ce-e4ab05be5e97

**Next:** awaiting Tyler: approve scope

---

### 2026-04-25T00:00:00Z — ⊕workspace-ci

**Event:** state-transition

**Summary:** Branch created and draft PR opened → BRANCHED

**Details:**
- Branch: `chore/workspace/intake-interview-driven`
- PR: https://github.com/tylerdrakemusic/-Workspace/pull/32 (draft)
- Committed: `.github/agents/⊕workspace-intake.agent.md` + FR ledger
- Changes are in review; awaiting Tyler approval before merge

**Next:** Tyler reviews PR and approves or requests changes

---

## Artifacts

- **Perf runs:** 11ed1327-c2fb-4b29-b1ce-e4ab05be5e97 — FR cycle timer (intake → archive)
