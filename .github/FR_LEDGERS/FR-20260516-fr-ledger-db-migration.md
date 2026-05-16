# FR-20260516-fr-ledger-db-migration — Migrate FR Ledgers + Registry to Dedicated Encrypted DB

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260516-fr-ledger-db-migration
- **Title:** Migrate FR ledgers + registry from repo files to dedicated encrypted SQLite DB
- **Type:** chore
- **Risk:** high
- **Projects:** ⊕Workspace (primary); all 5 projects' agent `.md` files need protocol repointing
- **State:** BRANCHED
- **Branch:** chore/workspace/fr-20260516-fr-ledger-db-migration
- **PRs:** pending
- **Cycle timer:** pending
- **Opened:** 2026-05-16
- **Last updated:** 2026-05-16
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria

1. `fr_ledgers.db` exists at `f:\⊕Workspace\src\data\fr_ledgers.db`, encrypted via SQLCipher, key stored in `FR_LEDGERS_DB_KEY` Windows System Environment Variable
2. DB schema has three tables: `feature_requests`, `fr_events`, `fr_artifacts` (see schema below)
3. `fr_cli.py` at `f:\⊕Workspace\src\utils\fr_cli.py` supports: `open`, `record-event`, `update-state`, `close`, `list` — mirrors `perf_cli.py` / `proof_cli.py` conventions
4. All 95 historical ledger `.md` files imported into DB — verifiable row count ≥ 95 in `feature_requests` table
5. `fr_server.py` reads exclusively from DB for registry + event data; `/api/ledger/<FR-ID>` endpoint returns JSON event list
6. FR panel "ledger →" link replaced with in-panel AJAX drawer rendering events from `/api/ledger/<FR-ID>`
7. `FEATURE_REQUESTS.md` and `.github/FR_LEDGERS/` deleted from ⊕Workspace repo (historical `.md` files preserved as local archive only — not re-committed)
8. Ledger-only PR logic removed from `⊕workspace-ci` agent
9. **All 9 agent files + `feature-request-flow.instructions.md` updated** to replace file-based ledger protocol with `fr_cli.py` calls for state transitions and event recording:
   - `⊕workspace-intake.agent.md`
   - `⊕workspace-ci.agent.md`
   - `⊕workspace-reviewer.agent.md`
   - `⊕workspace-architecture-reviewer.agent.md`
   - `⊕workspace-architecture-beautifier.agent.md`
   - `⊕workspace-commitment.agent.md`
   - `⊕workspace-discovery.agent.md`
   - `⊕workspace-overseer.agent.md`
   - `⊕workspace-hygiene.agent.md`
   - `feature-request-flow.instructions.md`
10. Zero regression on active FR panel display — all existing FR states visible correctly after migration

### Proposed DB Schema

```sql
CREATE TABLE feature_requests (
    id          TEXT PRIMARY KEY,      -- FR-YYYYMMDD-slug
    title       TEXT NOT NULL,
    type        TEXT NOT NULL,         -- feature | fix | chore | bugfix | etc.
    risk        TEXT,                  -- low | medium | high
    projects    TEXT,
    state       TEXT NOT NULL,
    branch      TEXT,
    prs         TEXT,
    owner       TEXT,
    opened_at   TEXT NOT NULL,         -- ISO-8601
    updated_at  TEXT NOT NULL,         -- ISO-8601
    merged_at   TEXT,
    signed_off_at TEXT,
    closed_at   TEXT,
    final_state TEXT,
    cycle_timer_run_id TEXT,
    acceptance_criteria TEXT,          -- JSON array of strings
    concurrency_notes TEXT
);

CREATE TABLE fr_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fr_id       TEXT NOT NULL REFERENCES feature_requests(id),
    ts          TEXT NOT NULL,         -- ISO-8601
    agent       TEXT NOT NULL,
    event_type  TEXT NOT NULL,         -- state-transition | delegation | decision | finding | failure | artifact | note
    summary     TEXT NOT NULL,
    details     TEXT,
    next_action TEXT
);

CREATE TABLE fr_artifacts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    fr_id         TEXT NOT NULL REFERENCES feature_requests(id),
    ts            TEXT NOT NULL,
    artifact_type TEXT NOT NULL,       -- perf_run | proof | pr | commit | report | dashboard
    label         TEXT NOT NULL,
    path_or_url   TEXT
);
```

### fr_cli.py Verb Reference (proposed)

```
fr_cli.py open    <FR-ID> <title> --type <type> --risk <risk> --projects "<p1,p2>"
fr_cli.py record-event <FR-ID> <agent> <event-type> "<summary>" [--details "..."] [--next "..."]
fr_cli.py update-state <FR-ID> <new-state> [--branch "..."] [--prs "..."]
fr_cli.py record-artifact <FR-ID> <artifact-type> "<label>" [--path "..."]
fr_cli.py close <FR-ID> --final-state <state>
fr_cli.py list [--active] [--state <state>]
fr_cli.py get <FR-ID>
```

### Concurrency Notes

- Conflicts with: none known
- Depends on: none (self-contained infrastructure change)
- **High-risk coordination:** All agent `.md` file updates must be deployed atomically with the DB migration and `fr_cli.py` — no partial state where some agents write to files and others write to DB

### Deliverable Tracker

| #    | Deliverable                                          | Owner                      | Status      | Proof | Updated    |
|------|------------------------------------------------------|----------------------------|-------------|-------|------------|
| AC1  | `fr_ledgers.db` + SQLCipher setup + `FR_LEDGERS_DB_KEY` | ⊕workspace-ci              | not-started | —     | —          |
| AC2  | DB schema (3 tables)                                  | ⊕workspace-ci              | not-started | —     | —          |
| AC3  | `fr_cli.py` with all verbs                           | ⊕workspace-overseer         | not-started | —     | —          |
| AC4  | Historical migration script (95 ledgers → DB)        | ⊕workspace-overseer         | not-started | —     | —          |
| AC5  | `fr_server.py` DB reader + `/api/ledger/<FR-ID>`     | ⊕workspace-overseer         | not-started | —     | —          |
| AC6  | FR panel in-panel AJAX drawer                        | ⊕workspace-overseer         | not-started | —     | —          |
| AC7  | Delete `FR_LEDGERS/` + `FEATURE_REQUESTS.md` from repo | ⊕workspace-ci             | not-started | —     | —          |
| AC8  | Remove ledger-only PR logic from ci agent            | ⊕workspace-overseer         | not-started | —     | —          |
| AC9  | Update 9 agent files + instructions file             | ⊕workspace-overseer         | not-started | —     | —          |
| AC10 | Zero regression validation on FR panel               | ⊕workspace-reviewer         | not-started | —     | —          |

### Tyler's Original Request

> "I am considering moving the FR-Ledgers to a dedicated encrypted database. The problem with FR-ledgers being in repository is that it causes sync issues and couples the ledger entries with the actual implementation. That should be decoupled. The impacted dashboard panel is Feature Requests, we would need to try not to impact that panel in the migration. What do you think of the move? Grill-me for clarifications.
>
> yes, a couple things to look at for. The FR functionality will have to integrate with the DB for state transitions. The agent files may need to be rewritten to repoint FR instructions as far as state transitions"

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-05-16T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened via grill-me interview, scope confirmed → TRIAGED

**Details:**
- Tyler initiated via `new-fr.prompt.md` with intent to decouple FR ledgers from repo
- Phase A grill-me completed: 7 clarifying questions answered, all design decisions locked
- Key decisions: new `fr_ledgers.db` with own key; both registry + event logs to DB; migrate 95 historical ledgers; in-panel AJAX drawer for ledger link; `fr_cli.py` for agent write protocol; clean repo (no FR artifacts); ledger-only PRs eliminated
- Risk assessed HIGH: 9 agent files + 1 instruction file require protocol repointing; must deploy atomically
- Concurrency check: no conflicts with open FRs
- Scope: ⊕Workspace primary; all projects' agent files need updates

### 2026-05-16T00:00:01Z — ⊕workspace-ci

**Event:** state-transition

**Summary:** Branch created, worktree staged, draft PR opened → BRANCHED

**Details:**
- Branch `chore/workspace/fr-20260516-fr-ledger-db-migration` created from `origin/main` (c137b84) and pushed to `tylerdrakemusic/-Workspace`
- Draft PR opened: pending (PR URL will be updated on next commit)
- Ledger + registry updated to BRANCHED state on the feature branch
- No implementation commits yet — branch is the handoff/tracking surface for implementation agents

**Next action:** ⊕workspace-overseer to begin implementation sprint: AC1 (fr_ledgers.db), AC2 (schema), AC3 (fr_cli.py)

**Next:** awaiting Tyler: approve scope → ⊕workspace-ci to branch

---

## Artifacts

<!-- APPEND-ONLY. Links to concrete evidence. -->

- **Perf runs:** pending — FR-20260516-fr-ledger-db-migration intake session
- **Proof artifacts:** —
- **PRs:** pending
- **Commits:** —
- **Reports / dashboards:** —
