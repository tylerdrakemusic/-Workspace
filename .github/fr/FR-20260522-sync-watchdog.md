# FR-20260522-sync-watchdog

**Title:** Nightly Sync Failure Watchdog
**Type:** feature
**Status:** REVIEW_REQUESTED
**Affected Project:** ∞Life (`tylerdrakemusic/Life`)
**Branch:** `feature/infinitelife/sync-watchdog`

Work tracked in this branch: `feature/infinitelife/sync-watchdog`

---

## Motivation

The `InfiniteLife-NightlySync` Task Scheduler job runs 4 sync sources nightly
(garmin, mfp, withings, trainerize). When one silently fails or goes stale for
days, there is no detection — health data ages without awareness.

## Outcome

After each sync run, per-source health rows are written to the DB and
stale/errored sources generate a deduplicated alert row, making sync health
queryable and visible.

---

## Scope

### In

- New `∞Life/tools/sync_watchdog.py` — called from `master_sync.py` after all
  sources complete; receives per-source result dicts
- New `sync_health` table in `infinitelife.db`:
  `(id, source, run_ts, status, records_written, error_msg)`
- New `sync_alerts` table in `infinitelife.db`:
  `(id, source, triggered_at, reason, resolved_at)`
- Alert logic: fire on `status='error'` OR last `status='ok'` > 24h ago;
  `status='skip'` does **not** reset the last-success clock
- Alert dedup: insert new alert only if no open (unresolved) alert already
  exists for that source (`resolved_at IS NULL`)
- `[ALERT]`-prefixed log line written to existing `master_sync_YYYY-MM-DD.log`
  on every new alert insert
- `∞Life/tests/test_sync_watchdog.py` — unit tests with in-memory SQLite
  (schema, insert, staleness query, alert dedup logic)

### Out

- Email / push notification (future FR)
- Dashboard UI for alerts (future FR)
- Changes to `nightly_master_sync.ps1` or individual sync source modules
- Any changes outside the ∞Life project

---

## Acceptance Criteria

1. `sync_health` table exists in `infinitelife.db` after first watchdog run;
   one row per source per sync
2. `status='ok'` rows advance the last-success clock; `status='skip'` does not
3. `sync_alerts` row is inserted on error or when last-ok > 24h; no duplicate
   open alert for the same source while one remains unresolved
4. `[ALERT]` line appears in `master_sync_YYYY-MM-DD.log` each time a new
   alert is inserted
5. `pytest ∞Life/tests/test_sync_watchdog.py` passes with in-memory DB, no
   live API calls

---

## Design Decisions (from grill-me interview 2026-05-22)

| Question | Decision |
|---|---|
| Watchdog home | New standalone `tools/sync_watchdog.py` called from `master_sync.py` |
| Granularity | One row per source per run (independent staleness tracking) |
| Alert mechanism | DB row + `[ALERT]` log line; no email/push yet |
| Skip handling | `skip` does not reset last-success clock |
| Alert dedup | New row only if no open (unresolved) alert for that source |
| Test coverage | `tests/test_sync_watchdog.py` with in-memory SQLite |

---

## Risk

**Medium** — new DB schema (`CREATE TABLE IF NOT EXISTS`, idempotent), new
write path added to `master_sync.py`. No changes to sync logic, OAuth, or
auth flows. Private repo — health-data gitignore audit required before push.
