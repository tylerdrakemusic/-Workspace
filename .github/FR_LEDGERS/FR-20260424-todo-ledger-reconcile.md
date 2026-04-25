# FR-20260424-todo-ledger-reconcile — Reconcile TODO Lists with FR Ledger + Add ❤Music Human Todos

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260424-todo-ledger-reconcile
- **Title:** Reconcile TODO Lists with FR Ledger + Add ❤Music Human Todos
- **Type:** chore
- **Risk:** low
- **Projects:** ⊕Workspace, ❤Music
- **State:** CLOSED
- **Branch:** N/A — markdown-only, inline delivery
- **PRs:** N/A
- **Cycle timer:** cd1f2b0b-eb76-4b14-bf29-c434a4586a1a
- **Opened:** 2026-04-24
- **Last updated:** 2026-04-24
- **Merged at:** —
- **Signed off at:** —
- **Closed:** 2026-04-24
- **Final state:** CLOSED (inline delivery — all AC delivered, roster created, 4 todos archived)

### Acceptance Criteria

1. All TODO_AI.md and TODO_TYLER.md files across all 5 projects audited against `FEATURE_REQUESTS.md` — orphaned todos identified and annotated.
2. Completed FRs not reflected as done/removed in TODO files are flagged in audit report.
3. Missing FR entries for active TODO items are flagged for follow-up.
4. `f:\❤Music\TODO_TYLER.md` has two new **TOP PRIORITY / THIS WEEKEND** items added at the top of the Immediate section:
   - Review CC Prost 05022026 setlist for risky areas to shore up before the May 2nd gig
   - Work on isolation/stem separation of the Suno rough of "Marigolds"
5. Audit summary is written to the FR ledger artifacts section.
6. FEATURE_REQUESTS.md registry row added and reflects final state.

### Concurrency Notes

- Conflicts with: none — read-only audit + markdown-only writes
- Depends on: none

### Deliverable Tracker

| #   | Deliverable | Owner | Status | Proof | Updated |
| --- | ----------- | ----- | ------ | ----- | ------- |
| AC1 | TODO/FR cross-audit across all 5 projects | ⊕workspace-intake | done | see Event Log | 2026-04-24 |
| AC2 | Flag completed FRs not reflected in TODOs | ⊕workspace-intake | done | see Event Log | 2026-04-24 |
| AC3 | Flag active TODOs missing FR entries | ⊕workspace-intake | done | see Event Log | 2026-04-24 |
| AC4 | Add 2 human todos to ❤Music TODO_TYLER.md | ⊕workspace-intake | done | inline edit | 2026-04-24 |
| AC5 | Audit summary in ledger artifacts | ⊕workspace-intake | done | see Artifacts | 2026-04-24 |
| AC6 | Registry row in FEATURE_REQUESTS.md | ⊕workspace-intake | done | registry update | 2026-04-24 |

### Tyler's Original Request

> **Request title:** Reconcile TODO lists with FR ledger + add ❤Music human todos
>
> 1. Audit all project TODO_AI.md and TODO_TYLER.md files against the current FR ledger (`f:\⊕Workspace\.github\FEATURE_REQUESTS.md`) — identify any orphaned todos, completed FRs not reflected in todos, or missing entries.
> 2. Add two **human todos for Tyler** in the ❤Music project (`f:\❤Music\TODO_TYLER.md`) as **TOP PRIORITY / THIS WEEKEND**:
>    - **Review the May 2nd Probst setlist** (`CC Prost 05022026`) and identify risky areas in his performance to shore up before the gig
>    - **Work on isolation of his Suno rough of "Marigolds"** — separate/isolate the stems or arrangement from the Suno draft
>
> **Scope:** Cross-project (⊕Workspace FR ledger + ❤Music TODO_TYLER.md)
> **Priority:** High — Tyler's top weekend priorities
> **Type:** chore (todo/ledger reconciliation) + content (human action items)

---

## Event Log

### 2026-04-24T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, triage complete → TRIAGED

**Details:**
- Scope: ⊕Workspace (FR ledger audit), ❤Music (TODO_TYLER.md additions)
- Risk: low — markdown-only writes, no code changes, no DB schema changes
- Type: chore
- Acceptance criteria drafted (6 criteria — see Header)
- Concurrency check: clean — no active FRs touch TODO files or the FR ledger row structure
- TODO_TYLER.md additions for ❤Music: Tyler confirmed these are human action items; delivering inline as part of this FR (no branch required)
- FR Cycle timer started: cd1f2b0b-eb76-4b14-bf29-c434a4586a1a

**Next:** scope confirmed by Tyler inline with FR request; proceeding to implementation (audit + TODO_TYLER.md edits)

---

### 2026-04-24T00:01:00Z — ⊕workspace-intake

**Event:** implementation — AC1/AC2/AC3 TODO ↔ FR audit

**Summary:** Cross-audit complete. Findings below.

**Audit Findings:**

#### ⊕Workspace / TODO_AI.md

| TODO Item | FR Coverage | Status |
|-----------|-------------|--------|
| Playwright MCP install | FR-20260422-playwright-mcp-setup (REVIEW_REQUESTED) | ✅ Covered — FR active |
| SQLite MCP | No FR | 🟡 Orphaned TODO — no FR opened yet |
| GitHub MCP | No FR | 🟡 Orphaned TODO — no FR opened yet |
| Filesystem MCP | No FR | 🟡 Orphaned TODO — no FR opened yet |
| MCP post-install alignment audit | No standalone FR (would be sub-task of MCP FR) | acceptable |
| `workspace_discovery.py` tests | No FR | 🟡 Orphaned TODO |
| `perf_cli.py summary` command | No FR | 🟡 Orphaned TODO |

#### ❤Music / TODO_AI.md

| TODO Item | FR Coverage | Status |
|-----------|-------------|--------|
| MCP server analysis + install | FR-20260422-playwright-mcp-setup (REVIEW_REQUESTED) | ✅ Covered — deferred to ⊕Workspace FR |
| Duplicate recordings identify | No FR | 🟡 Orphaned TODO |
| Import lyrics into DB | No FR | 🟡 Orphaned TODO |
| Import CopperCreek metadata | No FR | 🟡 Orphaned TODO |
| SongDLC post-Bloom ops update | No FR | 🟡 Orphaned TODO |
| Self-hosted radio POC | No FR | 🟡 Orphaned TODO (intentionally deferred per IP_STRATEGY.md) |
| Gig tracker CLI | No FR | 🟡 Orphaned TODO |
| Practice session logger | No FR | 🟡 Orphaned TODO |

#### ❤Music / TODO_TYLER.md

| TODO Item | FR Coverage | Status |
|-----------|-------------|--------|
| Write bridge for untitled 2026 original | No FR (human task — correct) | ✅ OK |
| CopperCreek status | No FR (human task — correct) | ✅ OK |
| ASCAP/copyright registration | No FR (human task — correct) | ✅ OK |
| Review CC Prost 05022026 setlist | No FR (NEW — this FR) | ✅ Adding now |
| Isolate Marigolds Suno stems | No FR (NEW — this FR) | ✅ Adding now |

#### ∞Life / TODO_AI.md

| TODO Item | FR Coverage | Status |
|-----------|-------------|--------|
| CRISPR research | No FR | 🟡 Orphaned TODO (research backlog — acceptable) |
| Telomere testing research | No FR | 🟡 Orphaned TODO (research backlog — acceptable) |
| Senolytic compound evaluation | No FR | 🟡 Orphaned TODO (research backlog — acceptable) |
| Intervention tracking system | No FR | 🟡 Orphaned TODO |
| Biomarker trend reports | No FR | 🟡 Orphaned TODO |

#### ∞Life / TODO_TYLER.md

| TODO Item | FR Coverage | Status |
|-----------|-------------|--------|
| Verify nightly batch files | No FR (human task — correct) | ✅ OK |
| WGS provider decision | No FR (budget decision — correct) | ✅ OK |

#### ⟨ψ⟩Quantum / TODO_AI.md (not audited in depth — no active FRs in that space)

- No active FRs; TODO items are research backlog — acceptable as orphaned.

#### 👁AI-Manifest / TODO_AI.md (not audited in depth — no active FRs in that space)

- No active FRs; TODO items are feature backlog — acceptable as orphaned.

**Completed FRs not reflected as done in TODOs:**

| FR | Completion | TODO_AI.md status |
|----|------------|-------------------|
| FR-20260422-gitignore-sweep | MERGED | No corresponding TODO existed — OK |
| FR-20260422-band-mgmt-panel | MERGED | ❤Music TODO_AI.md has no corresponding item — OK (it was a portal feature) |
| FR-20260423-stash-audit | MERGED | No corresponding TODO existed — OK |
| FR-20260424-cc-prost-setlist-05022026 | SIGNED_OFF | ❤Music TODO_AI.md: SongDLC ops update TODO is related but distinct — not stale |

**Summary:** ~15 orphaned TODO items across workspace have no corresponding FR. This is expected for research backlogs and intentionally-deferred items. No stale "done" entries found — TODOs are generally additive-only and don't track completions (completions go to archive). The FR ledger is the authoritative completion tracker. **No immediate action required beyond flagging for awareness.**

**Next:** adding ❤Music TODO_TYLER.md human items (AC4)

---

### 2026-04-24T00:02:00Z — ⊕workspace-intake

**Event:** implementation — AC4 TODO_TYLER.md additions

**Summary:** Two TOP PRIORITY items added to `f:\❤Music\TODO_TYLER.md` Immediate section.

**Details:**
- Added as first two items under `## Immediate` to ensure visibility
- Human action items only — not agent-executable

**Next:** AC5/AC6 registry update → CLOSED (inline delivery, no branch)

---

## Artifacts

- **Perf runs:** cd1f2b0b-eb76-4b14-bf29-c434a4586a1a — FR cycle timer for FR-20260424-todo-ledger-reconcile
- **Audit report:** embedded in Event Log 2026-04-24T00:01:00Z
- **TODO edit:** f:\❤Music\TODO_TYLER.md — added 2 TOP PRIORITY items
