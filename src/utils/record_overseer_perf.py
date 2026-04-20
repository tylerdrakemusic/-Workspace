"""Record the wall-clock time of a live overseer agent invocation."""
import time, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(r"f:\executedcode\∞Life\src")))
from utils.agent_perf import PerfTracker

start = json.loads(open(r"f:\tmp\overseer_start.json").read())["start"]
end = time.time()
elapsed_s = end - start
elapsed_ms = elapsed_s * 1000

tracker = PerfTracker()
run_id = tracker.start_run("overseer-live-invocation")

sid = tracker.start_step(run_id, "⊕workspace-overseer", "full cross-project status check (LIVE)")
tracker._conn.execute(
    "UPDATE perf_steps SET ended_at=started_at+?, elapsed_ms=?, status=?, detail=? WHERE step_id=?",
    (elapsed_s, elapsed_ms, "ok",
     "58/58 tests passed across 3 projects, TODO scan, alignment report", sid),
)
tracker._conn.commit()
tracker.end_run(run_id, status="ok", detail=f"wall-clock {elapsed_ms:.0f}ms")

summary = tracker.summary(run_id)
print()
print("=" * 72)
print("  LIVE OVERSEER INVOCATION PERF REPORT")
print("=" * 72)
for step in summary["steps"]:
    icon = "+" if step["status"] == "ok" else "X"
    ms = step["elapsed_ms"] or 0
    print(f"  {icon} [{ms:10.0f}ms] {step['agent']:30s} {step['description']}")
    if step["detail"]:
        print(f"    {'':30s}   -> {step['detail'][:90]}")
print("-" * 72)
print(f"  WALL-CLOCK: {elapsed_ms:,.0f}ms ({elapsed_s:.1f}s)")
print(f"  STATUS: {summary['status']}")
print("=" * 72)

print()
print("All PerfTracker runs on record:")
for r in tracker.all_runs():
    ms = r["total_ms"] or 0
    print(f"  {r['name']:40s} steps={r['step_count']}  total={ms:,.0f}ms  status={r['status']}")

tracker.close()
