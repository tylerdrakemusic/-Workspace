"""
fr_cli.py — Feature Request ledger CLI for ⊕Workspace.

Wraps feature_requests / fr_events / fr_artifacts tables in fr_ledgers.db (SQLCipher).
Mirrors the perf_cli / proof_cli conventions that agents already know.

Usage:
    python fr_cli.py open   <FR-ID> <title> --type <type> --risk <risk> --projects "<p>"
    python fr_cli.py record-event <FR-ID> <agent> <event-type> "<summary>" [--details "..."] [--next "..."]
    python fr_cli.py update-state <FR-ID> <new-state> [--branch "..."] [--prs "..."]
    python fr_cli.py record-artifact <FR-ID> <artifact-type> "<label>" [--path "..."]
    python fr_cli.py close  <FR-ID> --final-state <state>
    python fr_cli.py list   [--active] [--state <state>]
    python fr_cli.py get    <FR-ID>
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from init_fr_db import get_connection, init_db
from fr_cost_lifecycle import capture_baseline, finalize_cost, reconcile_cost
from copilot_cost import DEFAULT_SNAPSHOT_PATH, refresh_pricing

ACTIVE_STATES = {
    "OPEN", "TRIAGED", "BRANCHED", "IN_PROGRESS",
    "REVIEW_REQUESTED", "AUTO_REVIEWED", "TYLER_APPROVED",
    "CHANGES_REQUESTED", "SOAKING",
}

# Matches an event summary tagging a passing architecture review, e.g.
# "ARCHITECTURE_REVIEW:PASS — ..." or "ARCHITECTURE_REVIEW: PASS_WITH_UPDATES ..."
_ARCH_REVIEW_PASS_RE = re.compile(
    r"ARCHITECTURE_REVIEW\s*[:\-]?\s*(PASS_WITH_UPDATES|PASS)\b", re.IGNORECASE
)


def _conn():
    init_db()
    return get_connection()


def _has_architecture_review_pass(conn, fr_id: str) -> bool:
    """Return True if the FR's event log contains an ARCHITECTURE_REVIEW:PASS
    (or PASS_WITH_UPDATES) event, per the feature-request-flow state machine.
    """
    rows = conn.execute(
        "SELECT summary FROM fr_events WHERE fr_id=?", (fr_id,)
    ).fetchall()
    for row in rows:
        summary = row["summary"] if hasattr(row, "keys") else row[0]
        if summary and _ARCH_REVIEW_PASS_RE.search(summary):
            return True
    return False


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─────────────────────────────────────────────────────────────────────────────

def cmd_open(args: argparse.Namespace) -> None:
    fr_id: str = args.fr_id
    title: str = args.title
    now = _now()
    opened = getattr(args, "opened", None) or now[:10]
    conn = _conn()
    existing = conn.execute("SELECT id FROM feature_requests WHERE id=?", (fr_id,)).fetchone()
    if existing:
        print(f"[fr_cli] FR already exists: {fr_id}", file=sys.stderr)
        conn.close()
        sys.exit(1)
    conn.execute(
        """INSERT INTO feature_requests
           (id, title, type, risk, projects, state, branch, prs, owner,
            opened_at, updated_at, cycle_timer_run_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            fr_id, title,
            getattr(args, "type", "feature") or "feature",
            getattr(args, "risk", None),
            getattr(args, "projects", None),
            "OPEN",
            getattr(args, "branch", None),
            None,
            getattr(args, "owner", None),
            opened, now,
            getattr(args, "cycle_timer", None),
        ),
    )
    conn.commit()
    conn.close()
    print(fr_id)


def cmd_record_event(args: argparse.Namespace) -> None:
    conn = _conn()
    fr = conn.execute("SELECT id FROM feature_requests WHERE id=?", (args.fr_id,)).fetchone()
    if not fr:
        print(f"[fr_cli] FR not found: {args.fr_id}", file=sys.stderr)
        conn.close()
        sys.exit(1)
    now = _now()
    conn.execute(
        "INSERT INTO fr_events (fr_id, ts, agent, event_type, summary, details, next_action) VALUES (?,?,?,?,?,?,?)",
        (args.fr_id, now, args.agent, args.event_type, args.summary,
         getattr(args, "details", None), getattr(args, "next", None)),
    )
    conn.execute("UPDATE feature_requests SET updated_at=? WHERE id=?", (now, args.fr_id))
    conn.commit()
    conn.close()
    print(f"[fr_cli] event recorded → {args.fr_id}")


def cmd_update_state(args: argparse.Namespace) -> None:
    conn = _conn()
    fr = conn.execute("SELECT id FROM feature_requests WHERE id=?", (args.fr_id,)).fetchone()
    if not fr:
        print(f"[fr_cli] FR not found: {args.fr_id}", file=sys.stderr)
        conn.close()
        sys.exit(1)
    if args.new_state.upper() == "MERGED" and not _has_architecture_review_pass(conn, args.fr_id):
        print(
            f"[fr_cli] BLOCKED: cannot transition {args.fr_id} to MERGED — "
            "no ARCHITECTURE_REVIEW:PASS (or PASS_WITH_UPDATES) event found in event log. "
            "Run the architecture review and record the passing event before merging.",
            file=sys.stderr,
        )
        conn.close()
        sys.exit(1)
    now = _now()
    if args.new_state.upper() == "MERGED" and getattr(args, "cost_model", None) and getattr(args, "cost_usage_json", None):
        usage = _parse_usage(args.cost_usage_json)
        if getattr(args, "cost_async", False):
            github_json = getattr(args, "cost_github_usage_json", None)
            github_usage = (lambda: _parse_usage(github_json)) if github_json else (lambda: {})
            source, reconciled_usage = asyncio.run(
                reconcile_cost(
                    github_usage,
                    operator_confirmation=getattr(args, "cost_operator_confirmed", False),
                )
            )
            if source == "github":
                usage = reconciled_usage
            elif source == "operator":
                source = "operator"
            else:
                print(f"[FR cost] {args.fr_id}: reconciliation unavailable; cost not finalized.")
                usage = None
            if usage is not None:
                finalize_cost(conn, args.fr_id, args.cost_model, usage, source=source, reporter=print)
        else:
            finalize_cost(
                conn, args.fr_id, args.cost_model, usage,
                source=getattr(args, "cost_source", None) or "telemetry", reporter=print,
            )
    updates: list[tuple] = [("state", args.new_state), ("updated_at", now)]
    if getattr(args, "branch", None):
        updates.append(("branch", args.branch))
    if getattr(args, "prs", None):
        updates.append(("prs", args.prs))
    if getattr(args, "merged_at", None):
        updates.append(("merged_at", args.merged_at))
    if getattr(args, "signed_off_at", None):
        updates.append(("signed_off_at", args.signed_off_at))
    if getattr(args, "owner", None):
        updates.append(("owner", args.owner))
    if getattr(args, "cycle_timer", None):
        updates.append(("cycle_timer_run_id", args.cycle_timer))

    set_clause = ", ".join(f"{col}=?" for col, _ in updates)
    values = [v for _, v in updates] + [args.fr_id]
    conn.execute(f"UPDATE feature_requests SET {set_clause} WHERE id=?", values)  # nosec B608 — col names are internal, not user input
    conn.commit()
    conn.close()
    print(f"[fr_cli] state updated → {args.fr_id} = {args.new_state}")


def cmd_record_artifact(args: argparse.Namespace) -> None:
    conn = _conn()
    fr = conn.execute("SELECT id FROM feature_requests WHERE id=?", (args.fr_id,)).fetchone()
    if not fr:
        print(f"[fr_cli] FR not found: {args.fr_id}", file=sys.stderr)
        conn.close()
        sys.exit(1)
    now = _now()
    conn.execute(
        "INSERT INTO fr_artifacts (fr_id, ts, artifact_type, label, path_or_url) VALUES (?,?,?,?,?)",
        (args.fr_id, now, args.artifact_type, args.label, getattr(args, "path", None)),
    )
    conn.execute("UPDATE feature_requests SET updated_at=? WHERE id=?", (now, args.fr_id))
    conn.commit()
    conn.close()
    print(f"[fr_cli] artifact recorded → {args.fr_id}")


def _parse_usage(value: str) -> dict:
    usage = json.loads(value)
    if not isinstance(usage, dict):
        raise ValueError("usage JSON must be an object")
    return usage


def cmd_cost_baseline(args: argparse.Namespace) -> None:
    conn = _conn()
    capture_baseline(conn, args.fr_id, args.model, _parse_usage(args.usage_json))
    conn.close()
    print(f"[fr_cli] cost baseline recorded → {args.fr_id}")


def cmd_cost_finalize(args: argparse.Namespace) -> None:
    conn = _conn()
    result = finalize_cost(
        conn, args.fr_id, args.model, _parse_usage(args.usage_json),
        source=args.source, reporter=print,
    )
    conn.close()
    print(f"[fr_cli] cost persisted → {args.fr_id} ({result.status})")


def cmd_cost_refresh(args: argparse.Namespace) -> None:
    """Refresh the persisted GitHub Copilot pricing snapshot explicitly."""
    path = Path(getattr(args, "snapshot_path", None) or DEFAULT_SNAPSHOT_PATH)
    snapshot = refresh_pricing(path=path)
    print(
        f"[fr_cli] Copilot pricing refreshed → {path} "
        f"({len(snapshot['models'])} models, {snapshot['retrieved_at']})"
    )


def cmd_close(args: argparse.Namespace) -> None:
    conn = _conn()
    fr = conn.execute("SELECT id FROM feature_requests WHERE id=?", (args.fr_id,)).fetchone()
    if not fr:
        print(f"[fr_cli] FR not found: {args.fr_id}", file=sys.stderr)
        conn.close()
        sys.exit(1)
    now = _now()
    conn.execute(
        "UPDATE feature_requests SET state=?, final_state=?, closed_at=?, updated_at=? WHERE id=?",
        (args.final_state, args.final_state, now, now, args.fr_id),
    )
    conn.commit()
    conn.close()
    print(f"[fr_cli] FR closed → {args.fr_id} = {args.final_state}")


def cmd_list(args: argparse.Namespace) -> None:
    conn = _conn()
    where_parts: list[str] = []
    params: list[str] = []
    if getattr(args, "active", False):
        placeholders = ",".join("?" * len(ACTIVE_STATES))
        where_parts.append(f"state IN ({placeholders})")
        params.extend(ACTIVE_STATES)
    if getattr(args, "state", None):
        where_parts.append("UPPER(state)=UPPER(?)")
        params.append(args.state)
    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    rows = conn.execute(
        f"SELECT id, title, state, opened_at FROM feature_requests {where} ORDER BY opened_at DESC LIMIT 50",  # nosec B608
        params,
    ).fetchall()
    conn.close()
    if not rows:
        print("(no FRs found)")
        return
    for r in rows:
        print(f"{r['id']:50s}  {r['state']:20s}  {r['opened_at'][:10]}  {r['title'][:60]}")


def cmd_get(args: argparse.Namespace) -> None:
    conn = _conn()
    fr = conn.execute("SELECT * FROM feature_requests WHERE id=?", (args.fr_id,)).fetchone()
    if not fr:
        print(f"[fr_cli] FR not found: {args.fr_id}", file=sys.stderr)
        conn.close()
        sys.exit(1)
    print(f"ID:          {fr['id']}")
    print(f"Title:       {fr['title']}")
    print(f"Type:        {fr['type']}")
    print(f"Risk:        {fr['risk']}")
    print(f"Projects:    {fr['projects']}")
    print(f"State:       {fr['state']}")
    print(f"Branch:      {fr['branch']}")
    print(f"PRs:         {fr['prs']}")
    print(f"Owner:       {fr['owner']}")
    print(f"Opened:      {fr['opened_at']}")
    print(f"Updated:     {fr['updated_at']}")
    print(f"Merged:      {fr['merged_at']}")
    print(f"Signed off:  {fr['signed_off_at']}")
    print(f"Closed:      {fr['closed_at']}")
    print(f"Cycle timer: {fr['cycle_timer_run_id']}")
    print(f"AI credits: {fr['ai_credits_estimated']}")
    print(f"USD cost:   {fr['usd_cost_estimated']}")
    print(f"Cost status: {fr['cost_status']}")
    print(f"Cost source: {fr['cost_source']}")
    events = conn.execute(
        "SELECT ts, agent, event_type, summary FROM fr_events WHERE fr_id=? ORDER BY ts",
        (args.fr_id,),
    ).fetchall()
    conn.close()
    if events:
        print(f"\nEvents ({len(events)}):")
        for e in events:
            print(f"  {e['ts']}  [{e['agent']}]  {e['event_type']:20s}  {e['summary'][:80]}")


# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="FR ledger CLI — open, record, update, list FRs in fr_ledgers.db"
    )
    sub = parser.add_subparsers(dest="cmd")

    # open
    p_open = sub.add_parser("open", help="Create a new FR record")
    p_open.add_argument("fr_id")
    p_open.add_argument("title")
    p_open.add_argument("--type", default="feature")
    p_open.add_argument("--risk", default=None)
    p_open.add_argument("--projects", default=None)
    p_open.add_argument("--owner", default=None)
    p_open.add_argument("--branch", default=None)
    p_open.add_argument("--opened", default=None, help="Override opened_at (ISO date)")
    p_open.add_argument("--cycle-timer", dest="cycle_timer", default=None)

    # record-event
    p_ev = sub.add_parser("record-event", help="Append an event to an FR's log")
    p_ev.add_argument("fr_id")
    p_ev.add_argument("agent")
    p_ev.add_argument("event_type")
    p_ev.add_argument("summary")
    p_ev.add_argument("--details", default=None)
    p_ev.add_argument("--next", default=None)

    # update-state
    p_st = sub.add_parser("update-state", help="Transition an FR to a new state")
    p_st.add_argument("fr_id")
    p_st.add_argument("new_state")
    p_st.add_argument("--branch", default=None)
    p_st.add_argument("--prs", default=None)
    p_st.add_argument("--merged-at", dest="merged_at", default=None)
    p_st.add_argument("--signed-off-at", dest="signed_off_at", default=None)
    p_st.add_argument("--owner", default=None)
    p_st.add_argument("--cycle-timer", dest="cycle_timer", default=None)
    p_st.add_argument("--cost-model", dest="cost_model", default=None)
    p_st.add_argument("--cost-usage-json", dest="cost_usage_json", default=None)
    p_st.add_argument("--cost-source", dest="cost_source", default=None)
    p_st.add_argument("--cost-async", dest="cost_async", action="store_true")
    p_st.add_argument("--cost-github-usage-json", dest="cost_github_usage_json", default=None)
    p_st.add_argument("--cost-operator-confirmed", dest="cost_operator_confirmed", action="store_true")

    # record-artifact
    p_art = sub.add_parser("record-artifact", help="Record a proof/artifact link for an FR")
    p_art.add_argument("fr_id")
    p_art.add_argument("artifact_type")
    p_art.add_argument("label")
    p_art.add_argument("--path", default=None)

    # cost lifecycle
    p_base = sub.add_parser("cost-baseline", help="Capture the current-session AI usage baseline")
    p_base.add_argument("fr_id")
    p_base.add_argument("--model", required=True)
    p_base.add_argument("--usage-json", required=True)

    p_final = sub.add_parser("cost-finalize", help="Persist final current-session AI cost")
    p_final.add_argument("fr_id")
    p_final.add_argument("--model", required=True)
    p_final.add_argument("--usage-json", required=True)
    p_final.add_argument("--source", default="telemetry")

    p_refresh = sub.add_parser("cost-refresh", help="Refresh the persisted Copilot pricing snapshot")
    p_refresh.add_argument("--path", dest="snapshot_path", default=None)

    # close
    p_cl = sub.add_parser("close", help="Close/archive an FR")
    p_cl.add_argument("fr_id")
    p_cl.add_argument("--final-state", dest="final_state", default="ARCHIVED")

    # list
    p_ls = sub.add_parser("list", help="List FRs")
    p_ls.add_argument("--active", action="store_true", help="Only active FRs")
    p_ls.add_argument("--state", default=None, help="Filter by state")

    # get
    p_get = sub.add_parser("get", help="Show full FR detail including events")
    p_get.add_argument("fr_id")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "open": cmd_open,
        "record-event": cmd_record_event,
        "update-state": cmd_update_state,
        "record-artifact": cmd_record_artifact,
        "cost-baseline": cmd_cost_baseline,
        "cost-finalize": cmd_cost_finalize,
        "cost-refresh": cmd_cost_refresh,
        "close": cmd_close,
        "list": cmd_list,
        "get": cmd_get,
    }
    dispatch[args.cmd](args)


if __name__ == "__main__":
    main()
