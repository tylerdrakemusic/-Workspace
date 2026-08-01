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
- Verify `f:\⊕Workspace\.github\agents\<name>.agent.md` exists
- If an agent has been renamed or deleted → remove or update the reference in this file

### 3. Schema / DB Check (if applicable)
If this agent queries a database, verify the tables it references still exist in the schema. If a column or table was renamed → update the SQL in this file.

### 4. Self-Edit Protocol
To update this agent's own file:
1. Use the `edit` tool directly on `f:\⊕Workspace\.github\agents\<this-agent-name>.agent.md`
2. Make only the minimum targeted fix (stale path, renamed agent, etc.)
3. Log what was changed in the perf run detail: `--detail "self-regen: updated path X → Y"`

### 5. Report
At end of every run, output a self-regen summary:
```
Self-regen: X paths checked (Y updated), Z agent refs checked (W updated)
```

---

## Feedback Capture (MANDATORY at end of every run)

Any agent or prompt may hit friction mid-run: a stale instruction, missing
detail, unclear branching logic, a broken cross-reference not already caught
by the Self-Regeneration checks above. Capture it so it can be fixed once
instead of re-discovered every run.

### 1. Opt-in capture during the run
If friction is actually encountered, append a line to a session-scoped tmp
file — do NOT create this file preemptively if no friction occurs:
```
<workspace-root>/tmp/feedback.md
```
Each line/entry should capture: artifact type (`agent|instructions|prompt|skill|reference`),
target file path, and a short finding description.

### 2. End-of-run processing
Alongside the self-audit above, check whether `tmp/feedback.md` exists for
this session. If it does, for each finding insert a row via:
```
C:\G\python.exe f:\⊕Workspace\src\utils\feedback_cli.py log "<agent-name>" <artifact_type> "<target_file>" "<finding_text>" <severity> [--fr-id <FR-ID>]
```
- `severity=trivial` — same class of issue already handled by the Self-Regeneration
  auto-repair above (typo, stale path, broken cross-ref).
- `severity=substantive` — anything requiring judgment or design changes.

### 3. Trivial findings — auto-apply
Trivial findings are auto-applied via the tiered approval gate:
```
C:\G\python.exe f:\⊕Workspace\src\utils\feedback_cli.py auto-apply-trivial
```
This marks matching rows `auto_applied`. It does not itself edit files —
if the underlying fix requires a file edit, perform it inline as part of the
existing Self-Regeneration step (Section 4 above) before or after logging.

### 4. Substantive findings — Tyler approval required
Substantive findings must NOT be applied automatically. Leave them
`status=pending` and surface them in the final chat summary for Tyler's
explicit approval. Once Tyler approves:
1. The calling agent edits the target file directly.
2. Record the decision: `feedback_cli.py apply <id> --applied-by "<agent-or-tyler>"`.

### 5. Fold-in behavior
- If an FR is currently active/in-flight for the calling session, pass
  `--fr-id <FR-ID>` when logging so the eventual fix commit lands on that
  FR's existing branch.
- If no FR is active, an approved substantive fix should go through the
  standard intake → CI flow (`⊕workspace-intake` → `⊕workspace-ci`) to create
  a dedicated fix branch/PR rather than being applied ad hoc.

### 6. Report
Surface findings inline in the final chat summary, e.g.:
```
Feedback: 2 trivial (auto-applied), 1 substantive (pending Tyler approval — id=17)
```

