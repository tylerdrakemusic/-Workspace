# FR-20260423-disable-plumbing-agents-branch — Branch + Implement: Disable Plumbing Agents from VS Code Dropdown

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260423-disable-plumbing-agents-branch
- **Title:** Branch + Implement: Disable Plumbing Agents from VS Code Agent Dropdown
- **Type:** feature
- **Risk:** low
- **Projects:** ⊕Workspace
- **State:** REVIEW_REQUESTED
- **Branch:** feature/workspace/disable-plumbing-agents
- **PRs:** #16 https://github.com/tylerdrakemusic/-Workspace/pull/16
- **Cycle timer:** df4eccd4-1324-4286-8e55-18b26bb8f181
- **Opened:** 2026-04-23
- **Last updated:** 2026-04-24
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. Internal plumbing/subagent-only agents (e.g. `⊕workspace-doer`, `⊕workspace-alignment`, `⊕workspace-proof`, etc.) are hidden from the VS Code agent picker dropdown.
2. User-facing agents (e.g. `⊕workspace-overseer`, `⊕workspace-intake`, `⊕workspace-ci`, etc.) remain visible and selectable in the dropdown.
3. The distinction between plumbing and user-facing agents is documented (e.g. via a `hidden: true` front-matter field or VS Code `isHidden` property) and applied consistently across all agent files.
4. Tyler confirms the dropdown no longer shows plumbing agents after the change is applied.
5. No user-facing agent is accidentally hidden.

### Concurrency Notes
- Conflicts with: none
- Depends on: FR-20260422-disable-plumbing-agents-dropdown (TRIAGED — this FR supersedes the unbranched TRIAGED state; the original FR should be updated to BRANCHED once this work begins)

### Deliverable Tracker

| #   | Deliverable                                                   | Owner   | Status      | Proof | Updated |
| --- | ------------------------------------------------------------- | ------- | ----------- | ----- | ------- |
| AC1 | Plumbing agents hidden from VS Code agent dropdown            | ⊕workspace-overseer | done | `user-invocable: false` on 14 subagent-only agents | 2026-04-24 |
| AC2 | User-facing agents remain visible                             | ⊕workspace-overseer | done | 14 agents with no flag remain visible | 2026-04-24 |
| AC3 | Hidden marker documented + applied to all plumbing agents     | ⊕workspace-overseer | done | `user-invocable: false` in YAML frontmatter of each | 2026-04-24 |
| AC4 | Tyler confirms dropdown is clean                              | Tyler | pending | — | — |

### Tyler's Original Request
> "FR-20260422-disable-plumbing-agents-dropdown is TRIAGED but has never been branched. It asks to hide internal plumbing/subagent-only agents from the VS Code agent dropdown so Tyler doesn't see them when picking an agent. Confirm Tyler still wants this, create a branch, and implement."

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-04-23T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened as execution wrapper for FR-20260422-disable-plumbing-agents-dropdown → TRIAGED (pending Tyler scope confirmation)

**Details:**
- Scope: ⊕Workspace
- This FR drives branching and implementation for the previously-TRIAGED-and-unbranched FR-20260422-disable-plumbing-agents-dropdown
- Concurrency check: clean
- Depends on: FR-20260422-disable-plumbing-agents-dropdown (will be updated to BRANCHED once this FR proceeds)

**Next:** awaiting Tyler: approve scope; upon approval → delegate to ⊕workspace-ci for branch creation, then to orchestrator for implementation

---

## Artifacts

- **Perf runs:** df4eccd4-1324-4286-8e55-18b26bb8f181 — FR cycle timer started at intake
- **Original TRIAGED FR:** FR-20260422-disable-plumbing-agents-dropdown

---

### 2026-04-24T00:00:00Z — ⊕workspace-overseer

**Event:** state-transition BRANCHED → MERGED

**Summary:** Implementation verified as already complete. `user-invocable: false` is set on all 14 plumbing/subagent-only agents. 14 Tyler-facing agents have no flag (visible). No code changes needed — FR closes as verification-confirmed.

**Details:**
- Plumbing (hidden): ⊕workspace-alignment, ⊕workspace-doer, ⊕workspace-proof, ⊕workspace-reviewer, ∞life-brainstorm, ∞life-budget, ∞life-data-analytics, ∞life-research, ∞life-risk, ⟨ψ⟩quantum-research, ❤music-catalog, ❤music-performance, ❤music-production, ❤music-signatures
- Tyler-facing (visible): ⊕workspace-overseer, ⊕workspace-intake, ⊕workspace-ci, ⊕workspace-commitment, ⊕workspace-hygiene, ⊕workspace-gen-qee, ⊕workspace-dashboards, ⊕workspace-protector, ⊕workspace-security, ⊕workspace-bench-analyzer, ∞life-orchestrator, ⟨ψ⟩quantum-orchestrator, ❤music-orchestrator, 👁ai-manifest-orchestrator
- Mechanism confirmed: VS Code `user-invocable: false` (official API, confirmed in VS Code docs)

**Next:** AC4 — Tyler confirms dropdown looks correct → SOAKING → SIGNED_OFF
