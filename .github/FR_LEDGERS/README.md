# FR Ledgers

One markdown file per feature request, created by `⊕workspace-intake` when
an FR is opened and appended to by every agent that touches the FR throughout
its lifecycle. The ledger is the **complete narrative history and shared
context** for a single FR.

**Filename:** `<FR-ID>.md` (e.g. `FR-20260422-multi-agent-flow.md`)

## Why a per-FR ledger

- Every agent that picks up the FR has instant full context without chasing
  chat history, PR comments, or worktree contents
- Tyler can read the full story of any FR in one file
- Survives branch/worktree deletion (ledger is committed on main / workspace
  repo, not on the feature branch)
- Acts as the FR's permanent forensic record — who did what, when, why

## Structure

Every ledger has three top-level sections (see [`_TEMPLATE.md`](_TEMPLATE.md)):

1. **Header** — FR metadata (ID, title, type, projects, acceptance criteria,
   current state). Updated in place by intake / CI only.
2. **Event Log** — append-only chronological entries. Every agent appends one
   entry per significant action (state transition, delegation, decision,
   finding, failure).
3. **Artifacts** — links to perf run IDs, proof artifact IDs, PR URLs, test
   reports, commits, screenshots. Append-only.

## Write Protocol

- **Intake** creates the ledger on FR open (copy `_TEMPLATE.md`, fill header)
- **Every agent** that acts on the FR appends one event entry before finishing
  its turn
- **CI** updates the header's `State` field on state transitions and appends
  an event entry with the transition
- **Reviewer** appends its full review summary as an event entry and links the
  GitHub PR review URL in Artifacts
- **NO agent** ever deletes or rewrites past event entries — append only

## Read Protocol

Every agent that receives an FR handoff MUST read the FR's ledger as part of
its context bootstrap, before taking action. This is how agents get shared
state without a central DB.

## Event Entry Format

```markdown
### <ISO-8601 timestamp> — <agent-name>

**Event:** <state-transition | delegation | decision | finding | failure | artifact | note>

**Summary:** <one-line summary>

**Details:**
<optional multi-line body — what was done, why, links to artifacts>

**Next:** <next agent/action, or "awaiting Tyler: <gateway>">
```

## Lifecycle

- Created on FR open (`OPEN` state)
- Grows throughout FR lifecycle
- On `CLOSED`, the ledger is NOT deleted — it moves to a final archive
  section at the top of the header (`Closed: <date>`, `Final state: MERGED |
  REJECTED`) and stays in the repo permanently as historical record
- Archived FRs can be searched by grep across this directory
