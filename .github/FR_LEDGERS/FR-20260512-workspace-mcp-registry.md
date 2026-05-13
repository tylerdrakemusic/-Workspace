# FR-20260512-workspace-mcp-registry — Gold-Standard MCP Registry: evaluate and document 5-10 production MCP servers

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260512-workspace-mcp-registry
- **Title:** Gold-Standard MCP Registry: evaluate and document 5-10 production MCP servers
- **Type:** chore + research
- **Risk:** low
- **Projects:** ⊕Workspace
- **State:** REVIEW_REQUESTED
- **Branch:** chore/workspace/fr-20260512-workspace-mcp-registry
- **PRs:** [⊕Workspace draft-create](https://github.com/tylerdrakemusic/-Workspace/pull/new/chore/workspace/fr-20260512-workspace-mcp-registry)
- **Cycle timer:** c5bfdd2e-3c71-478c-81f8-ed610e4f505f
- **Opened:** 2026-05-12
- **Last updated:** 2026-05-12
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. Create a registry artifact listing 5-10 MCP servers with links and rationale.
2. Include a weighted scoring rubric covering security, performance, code quality, and maintenance.
3. Provide ranked top-3 recommendations tagged as adopt now / later / avoid.
4. Document guardrails for private vs public repos and safe usage boundaries.

### Concurrency Notes
- Conflicts with: none
- Depends on: none

### Deliverable Tracker

| #   | Deliverable | Owner | Status | Proof | Updated |
| --- | ----------- | ----- | ------ | ----- | ------- |
| AC1 | MCP registry candidate list + rationale | ⊕workspace-overseer | done | file_created 055861fb76fe | 2026-05-12 |
| AC2 | Weighted scoring rubric | ⊕workspace-overseer | done | file_created 055861fb76fe | 2026-05-12 |
| AC3 | Ranked top-3 recommendations | ⊕workspace-overseer | done | file_created 055861fb76fe | 2026-05-12 |
| AC4 | Repo-visibility guardrails section | ⊕workspace-overseer | done | file_created 055861fb76fe | 2026-05-12 |

### Tyler's Original Request
> "pick one of the higher priority todo's that's lowest risk and short and sweet to implement. I have concurrency running"

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-05-12 20:31 UTC — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened and triaged from approved candidate selection

**Details:**
- Candidate source: open todo `[81] workspace SCAN P9`
- Selection rationale: highest-priority item with low implementation risk and minimal merge conflict probability under concurrent sessions
- Scope: research/documentation-first delivery in ⊕Workspace
- Out of scope: runtime MCP installation and cross-project code changes in this FR
- Branching deferred until Tyler requests implementation handoff

### 2026-05-12 21:00 UTC — ⊕workspace-overseer

**Event:** implementation-complete

**Summary:** Registry artifact implemented and FR advanced to REVIEW_REQUESTED

**Details:**
- Created `f:\⊕Workspace\MCP_REGISTRY.md` with 8 MCP candidates, links/rationale, weighted rubric, and ranked recommendations.
- Included top-3 decisions explicitly tagged as adopt now / later / avoid.
- Added repo-visibility guardrails aligned with `REPO_VISIBILITY.md` for private vs public repo handling.
- Marked MCP research todo completed in `f:\⊕Workspace\TODO_AI.md`.
- No runtime MCP installation or config mutations performed in this FR.
