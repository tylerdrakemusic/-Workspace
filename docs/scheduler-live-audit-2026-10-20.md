# Scheduler Live Audit — 2026-10-20

Observed at `2026-10-20T21:47:46Z`: read-only Task Scheduler metadata.
The query selected the Quantum cache-fill, Shor, VQE, and backend-monitor task
names and returned task name, task path, Python script basename, MultipleInstances,
and state. Raw command arguments were not retained.

| Task Name | Task Path | Action Script | MultipleInstances | State |
| --- | --- | --- | --- | --- |
| QuantumCacheFill_Monthly | `\` | `fill_cache.py` | IgnoreNew | Ready |
| ShorsMonthlyBench | `\` | `run_shors_bench.py` | IgnoreNew | Ready |
| VQEMonthlyBench | `\` | `run_vqe_bench.py` | IgnoreNew | Ready |
| QuantumBackendAvailabilityMonitor_Daily | not observed | not observed | not observed | not observed |

## Source Policy

Source policy reference: Quantum PR #105 at head `af919dafbbfcbd1e271af6ec7f956af4c54df0dc`,
file `src/config/execution_policy.json`. It specifies:

| Task Name | Policy schedule | Action | multiple_instances |
| --- | --- | --- | --- |
| QuantumCacheFill_Monthly | Day 1 07:00 UTC | `tools/fill_cache.py` | IgnoreNew |
| ShorsMonthlyBench | Day 1 08:00 UTC | `tools/run_shors_bench.py --scheduled` | IgnoreNew |
| VQEMonthlyBench | Day 15 03:00 UTC | `tools/run_vqe_bench.py --molecule all` | IgnoreNew |
| QuantumBackendAvailabilityMonitor_Daily | schedule=daily 07:45 UTC | `tools/backend_availability_monitor.py` | multiple_instances=IgnoreNew |

The monitor's 07:45 schedule, action, and IgnoreNew setting are source-policy
evidence only; it was not observed as a live task. Source-policy arguments are
not asserted as observed live action arguments. Its policy task name is
unqualified, and `tools/sync_scheduled_tasks.py` passes that name to
`schtasks.exe /TN` without a folder component. Therefore TaskPath `\` is the
configured target, not a live observation. No Task Scheduler task was created,
modified, or removed during this audit.