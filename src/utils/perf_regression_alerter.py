"""
perf_regression_alerter.py — Weekly agent performance regression detector.

Queries perf_runs for agents with >= MIN_BASELINE_RUNS ok-status runs in a
rolling 30-day window. Computes:
  - 30-day rolling median wall-clock (ok runs only) as baseline
  - most-recent-RECENT_RUNS-run average as current performance

Flags agents where recent avg >= REGRESSION_THRESHOLD * 30d_median.
Writes alert rows to proof_artifacts:
  - proof_type='perf_regression_alert'  for confirmed regressions
  - proof_type='perf_low_data'          for agents below the data floor

Silent on no regressions; prints a summary block on detection.
Wraps itself in a perf_run (start/end) for auditability.

Usage:
    python perf_regression_alerter.py
    python perf_regression_alerter.py --dry-run
"""
import argparse
import statistics
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from init_db import get_connection, init_db

MIN_BASELINE_RUNS: int = 5       # min ok runs in 30d window to qualify for regression check
REGRESSION_THRESHOLD: float = 2.0  # flag if recent_avg >= this * 30d_median
WINDOW_DAYS: int = 30
RECENT_RUNS: int = 3             # number of most-recent runs used for "current" average

ALERTER_AGENT = "⊕workspace-perf-alerter"


def _conn():
    init_db()
    return get_connection()


def run_alerter(dry_run: bool = False) -> int:
    """Run the regression scan. Returns the count of regression alerts detected."""
    conn = _conn()
    window_start = time.time() - WINDOW_DAYS * 86400

    alerter_run_id = str(uuid.uuid4())
    scan_started_at = time.time()

    if not dry_run:
        conn.execute(
            "INSERT INTO perf_runs (run_id, name, agent, started_at) VALUES (?, ?, ?, ?)",
            (alerter_run_id, f"{ALERTER_AGENT}: weekly regression scan", ALERTER_AGENT, scan_started_at),
        )
        conn.commit()

    # ── 1. Discover all distinct agents with at least 1 ok run in the 30d window ──
    agent_rows = conn.execute(
        """
        SELECT agent, COUNT(*) AS run_count_30d
        FROM perf_runs
        WHERE status = 'ok'
          AND ended_at IS NOT NULL
          AND started_at >= ?
          AND agent IS NOT NULL
        GROUP BY agent
        """,
        (window_start,),
    ).fetchall()

    alerts: list[tuple] = []     # (agent, recent_avg_ms, median_ms, ratio, run_count_30d)
    low_data: list[tuple] = []   # (agent, actual_count)

    for row in agent_rows:
        agent: str = row[0]
        run_count_30d: int = row[1]

        # ── 2a. Collect all 30d ok run durations for baseline median ──────────
        baseline_rows = conn.execute(
            """
            SELECT (ended_at - started_at) * 1000 AS elapsed_ms
            FROM perf_runs
            WHERE status = 'ok'
              AND ended_at IS NOT NULL
              AND started_at >= ?
              AND agent = ?
            ORDER BY started_at
            """,
            (window_start, agent),
        ).fetchall()

        elapsed_30d = [r[0] for r in baseline_rows]

        if len(elapsed_30d) < MIN_BASELINE_RUNS:
            low_data.append((agent, len(elapsed_30d)))
            continue

        median_ms = statistics.median(elapsed_30d)

        # ── 2b. Collect most-recent RECENT_RUNS ok runs (all-time) ────────────
        recent_rows = conn.execute(
            """
            SELECT (ended_at - started_at) * 1000 AS elapsed_ms
            FROM perf_runs
            WHERE status = 'ok'
              AND ended_at IS NOT NULL
              AND agent = ?
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (agent, RECENT_RUNS),
        ).fetchall()

        if len(recent_rows) < RECENT_RUNS:
            # Not enough total history for a meaningful recent average
            low_data.append((agent, len(recent_rows)))
            continue

        recent_avg_ms = sum(r[0] for r in recent_rows) / len(recent_rows)
        ratio = recent_avg_ms / median_ms if median_ms > 0 else 0.0

        if ratio >= REGRESSION_THRESHOLD:
            alerts.append((agent, recent_avg_ms, median_ms, ratio, run_count_30d))

    # ── 3. Write proof_artifacts rows ─────────────────────────────────────────
    if not dry_run:
        now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        for agent, recent_avg, median_ms, ratio, n in alerts:
            proof_id = uuid.uuid4().hex[:12]
            desc = (
                f"Agent {agent}: {RECENT_RUNS}-run avg {recent_avg / 1000:.1f}s vs "
                f"30d median {median_ms / 1000:.1f}s ({ratio:.2f}x regression)"
            )
            conn.execute(
                """
                INSERT INTO proof_artifacts
                    (proof_id, run_id, agent, proof_type, description, created_at)
                VALUES (?, ?, ?, 'perf_regression_alert', ?, ?)
                """,
                (proof_id, alerter_run_id, agent, desc, now),
            )

        for agent, n in low_data:
            proof_id = uuid.uuid4().hex[:12]
            desc = (
                f"Agent {agent}: only {n} ok run(s) in {WINDOW_DAYS}-day window "
                f"(min {MIN_BASELINE_RUNS} required for regression check)"
            )
            conn.execute(
                """
                INSERT INTO proof_artifacts
                    (proof_id, run_id, agent, proof_type, description, created_at)
                VALUES (?, ?, ?, 'perf_low_data', ?, ?)
                """,
                (proof_id, alerter_run_id, agent, desc, now),
            )

        # Close the alerter's own perf run
        detail = (
            f"{len(alerts)} regression(s), {len(low_data)} below data floor"
        )
        conn.execute(
            "UPDATE perf_runs SET ended_at=?, status=?, detail=? WHERE run_id=?",
            (time.time(), "ok", detail, alerter_run_id),
        )
        conn.commit()

    conn.close()

    # ── 4. Print summary only when regressions are detected ───────────────────
    if alerts:
        bar = "=" * 64
        print(f"\n{bar}")
        print(f"  PERF REGRESSION ALERT — {time.strftime('%Y-%m-%d')}")
        print(bar)
        for agent, recent_avg, median_ms, ratio, n in alerts:
            print(
                f"  !! {agent}\n"
                f"     {RECENT_RUNS}-run avg:  {recent_avg / 1000:>8.1f}s\n"
                f"     30d median:  {median_ms / 1000:>8.1f}s\n"
                f"     ratio:       {ratio:>8.2f}x  (threshold: {REGRESSION_THRESHOLD}x)\n"
                f"     baseline N:  {n} run(s) in window\n"
            )
        print(bar)
        if dry_run:
            print("  [DRY RUN — no rows written to DB]")
        print()

    return len(alerts)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="⊕Workspace weekly agent performance regression alerter"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute and print alerts without writing anything to the DB",
    )
    args = parser.parse_args()
    run_alerter(dry_run=args.dry_run)
    sys.exit(0)


if __name__ == "__main__":
    main()
