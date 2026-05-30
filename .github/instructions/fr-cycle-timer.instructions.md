<!-- applyTo: .github/agents/*.agent.md -->

# FR Cycle Timer — Full Lifecycle Timing Protocol

Every FR has one `perf_cli` run that measures the full cycle: from intake open
to merge. This is separate from each agent's own short-lived perf runs — it
spans the entire FR lifecycle, including all human approval gates.

## Protocol

1. **Intake starts the cycle timer** on FR open:
   ```
   C:\G\python.exe f:\⊕Workspace\src\utils\perf_cli.py start "fr-cycle-<FR-ID>"
   ```
   Stash the returned run_id; record it via:
   ```powershell
   $env:PYTHONUTF8="1"
   C:\G\python.exe f:\⊕Workspace\src\utils\fr_cli.py record-artifact <FR-ID> metric "Cycle timer run_id" --path "<run_id>"
   ```

2. **Every state transition** appends an Event Log entry with an ISO timestamp.
   Phase durations (open→scope-approved, branched→review, review→merge) are
   derivable by parsing these timestamps — no extra perf calls needed.

3. **CI closes the cycle timer when it merges the PR** (primary path):
   ```
   C:\G\python.exe f:\⊕Workspace\src\utils\perf_cli.py end <cycle_run_id> \
       --status ok --detail "FR-<ID> merged: <merge SHAs>"
   ```

4. **Safety net — reconciliation** (for when Tyler merges on GitHub.com without
   CI agent action): `⊕workspace-ci` exposes a `reconcile-fr-timers` capability
   that:
   - Queries `fr_cli.py list --active` for FRs in `TYLER_APPROVED` or `AUTO_REVIEWED`
     state with an open (unclosed) Cycle timer
   - Queries GitHub via `mcp_github` tools for each PR's `merged_at` timestamp
   - For any merged PR, closes the cycle timer with `--at <merged_at>` to
     backfill the true merge time
   - Updates FR state via `fr_cli.py update-state` and records a reconciliation event
   - Can be invoked on-demand (`@⊕workspace-ci reconcile`) or scheduled

## Why This Design
- **Zero infrastructure** — no webhook server, no always-on daemon
- **Accurate timing** — GitHub's `merged_at` is authoritative even if Tyler
  merges manually
- **Tyler stays sovereign** — he can merge via GitHub UI, CLI, or the CI agent;
  reconciliation closes the loop either way
- **Optional acceleration** — a GitHub Actions workflow per repo can trigger
  reconciliation automatically on merge (template at
  `.github/workflow-templates/fr-merge-reconcile.yml`), but is not required

## Reporting
After close, `perf_cli report <cycle_run_id>` shows total FR wall-clock time.
For phase breakdowns, parse the ledger's Event Log timestamps.
