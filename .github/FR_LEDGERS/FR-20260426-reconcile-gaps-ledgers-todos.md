# FR-20260426-reconcile-gaps-ledgers-todos — Reconcile Gaps: Agent Ops Monitor, FR Ledgers, and All-Project TODOs

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260426-reconcile-gaps-ledgers-todos
- **Title:** Reconcile Gaps: Agent Ops Monitor, FR Ledgers, and All-Project TODOs
- **Type:** chore
- **Risk:** low
- **Projects:** ⊕Workspace, ❤Music, ∞Life, ⟨ψ⟩Quantum, 👁AI-Manifest
- **State:** TRIAGED
- **Branch:** none (markdown-only + CLI — no branch required)
- **PRs:** none
- **Cycle timer:** 2933ae01-59fe-40ae-923b-fcae010cd304
- **Opened:** 2026-04-26
- **Last updated:** 2026-04-26
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria

1. **FR Registry cleanup:** Active table row for `FR-20260425-mermaid-diagrams-integration` is removed (duplicate — already in Archive as MERGED → CLOSED).
2. **FR Registry cleanup:** `FR-20260425-guitar-trainer-data-to-db` is moved from Active to Archive as `CLOSED (superseded by FR-20260425-guitar-trainer-db-migration)`.
3. **Agent Ops Monitor:** `agent_ops_monitor.py --fix` is run and orphan runs (ended, 0 proofs) are auto-closed; health metric returns >95%.
4. **TODO reconciliation — 👁AI-Manifest:** `TODO_TYLER.md` "Install Node.js" item is verified (Playwright MCP confirmed installed) and marked done.
5. **TODO reconciliation — all 4 projects:** Each `TODO_AI.md` and `TODO_TYLER.md` is reviewed; completed items are checked off, items that duplicate active FRs are annotated with the FR ID or removed.
6. **TODO cross-validation — ⊕Workspace:** `TODO_AI.md` MCP server research items are checked against active FRs; redundant items removed or annotated.
7. **Hygiene agent update:** `⊕workspace-hygiene.agent.md` gains three new sweep phases: (a) FR Registry Ledger reconciliation (duplicate rows, superseded FRs in wrong state), (b) TODO cross-validation (orphaned todos → FRs, FRs without TODO backing), (c) `agent_ops_monitor.py --fix` as a routine hygiene step.

### Concurrency Notes
- Conflicts with: none
- Depends on: none (all prerequisite context gathered by overseer)

### Deliverable Tracker

| #   | Deliverable | Owner | Status | Proof | Updated |
| --- | ----------- | ----- | ------ | ----- | ------- |
| AC1 | Remove duplicate Active row: FR-20260425-mermaid-diagrams-integration | ⊕workspace-overseer | not-started | — | — |
| AC2 | Archive FR-20260425-guitar-trainer-data-to-db as CLOSED (superseded) | ⊕workspace-overseer | not-started | — | — |
| AC3 | Run agent_ops_monitor.py --fix; verify health >95% | ⊕workspace-overseer | not-started | — | — |
| AC4 | Verify + mark done: 👁AI-Manifest TODO_TYLER.md "Install Node.js" | ⊕workspace-overseer | not-started | — | — |
| AC5 | Reconcile all 8 TODO files (4× AI + 4× human) | ⊕workspace-overseer | not-started | — | — |
| AC6 | ⊕Workspace TODO_AI.md MCP items vs active FRs cross-check | ⊕workspace-overseer | not-started | — | — |
| AC7 | Update ⊕workspace-hygiene.agent.md with 3 new sweep phases | ⊕workspace-overseer | not-started | — | — |

### Tyler's Original Request
> "Reconciliation of gaps in agent ops monitor, ledgers in feature requests, and TODOs in all 4 projects (AI todo and human todo). Get hygiene agent to help if needed and update hygiene agent according to the new source."

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-04-26T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened by overseer with pre-gathered context → TRIAGED (scope already confirmed by overseer; Tyler's approval implicit in routing)

**Details:**
- Scope: ⊕Workspace, ❤Music, ∞Life, ⟨ψ⟩Quantum, 👁AI-Manifest
- Type: chore / risk: low
- No branch required — all work is markdown edits + existing CLI tools
- Cycle timer started: 2933ae01-59fe-40ae-923b-fcae010cd304
- Acceptance criteria: 7 items covering registry cleanup (AC1–2), ops monitor fix (AC3), TODO reconciliation (AC4–6), hygiene agent update (AC7)
- Routed directly to ⊕workspace-overseer for implementation
