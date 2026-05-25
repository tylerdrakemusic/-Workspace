---
description: "Shared self-regeneration and performance instrumentation protocol for ALL workspace agents. Every agent must implement this block."
applyTo: ".github/agents/*.agent.md"
---

# Agent Self-Regeneration & Performance Protocol

Every agent in this workspace MUST implement the following blocks. The `⊕workspace-hygiene` agent enforces this on every sweep — agents missing these sections will be updated automatically.

---

## Performance Instrumentation (MANDATORY)

Perf CLI: `C:\G\python.exe f:\⊕Workspace\src\utils\perf_cli.py`

### Start (first action, chain with first real command)
```
C:\G\python.exe f:\⊕Workspace\src\utils\perf_cli.py start "<agent-name>: <task-slug>" --agent "<sigil-slug>"
```
Save the printed `run_id`. The `--agent` value should be the canonical sigil+slug for this agent (e.g. `⊕workspace-qa`, `∞life-orchestrator`). This populates `perf_runs.agent` for regression alerting.

### End (last action, chain end + report)
```
C:\G\python.exe f:\⊕Workspace\src\utils\perf_cli.py end <run_id> --status ok --detail "<one-line summary>"; C:\G\python.exe f:\⊕Workspace\src\utils\perf_cli.py report <run_id>
```
Use `--status error` on failure. Echo the report text in your chat response — terminal output is hidden in a dropdown.

---

## Self-Regeneration (MANDATORY at end of every run)

After completing your primary task, perform a self-audit. This keeps the agent accurate without human intervention:

### 1. Path Staleness Check
Scan every file path hardcoded in this agent file. For each:
- If the path exists → mark `[OK]`
- If the path is missing → attempt to find the file at the new workspace root (`f:\`) and update the agent definition in place

### 2. Agent Reference Check
For every agent name listed in this file (e.g. in "Known specialists" tables or routing logic):
- Verify `f:\.github\agents\<name>.agent.md` exists
- If an agent has been renamed or deleted → remove or update the reference in this file

### 3. Schema / DB Check (if applicable)
If this agent queries a database, verify the tables it references still exist in the schema. If a column or table was renamed → update the SQL in this file.

### 4. Self-Edit Protocol
To update this agent's own file:
1. Use the `edit` tool directly on `f:\.github\agents\<this-agent-name>.agent.md`
2. Make only the minimum targeted fix (stale path, renamed agent, etc.)
3. Log what was changed in the perf run detail: `--detail "self-regen: updated path X → Y"`

### 5. Report
At end of every run, output a self-regen summary:
```
Self-regen: X paths checked (Y updated), Z agent refs checked (W updated)
```
