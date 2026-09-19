# ⊕ Architecture Impact Report - FR-20260919-copilot-cloud-agent-consumer

**Commit reviewed:** `cdbd235cad32b927ae53e9b3d0638e3db8eee239`
**Decision:** STALE

## Diff Review

| File in diff | Impact type | Affected diagram |
| --- | --- | --- |
| `src/utils/copilot_model_selection.py` | New Workspace model-selection and supported-consumer contract, including preflight, bounded delegation, opaque outcome recording, cost fallback, and JSONL metadata persistence | `diagrams/workspace-architecture-detail.mmd` |
| `docs/copilot-model-selection.md` | Documents the new consumer boundary and operational flow | `diagrams/workspace-architecture-detail.mmd` |
| `tests/test_copilot_model_selection_contract.py` | Focused contract coverage; no architectural surface by itself | None |

## Boundary Checks

| Check | Result | Evidence |
| --- | --- | --- |
| Official route only | PASS for this slice | The code exposes only `DelegationConsumer`/`CloudAgentConsumer` protocols and a test double. It contains no undocumented VS Code command, private endpoint, reverse-engineered API, host activation, or agent-YAML mutation. A real consumer must be supplied by an official or extension-owned adapter. |
| Advisory/shadow model selection | PASS | Selection is metadata-only and `shadow_replay` does not activate a consumer. The selected model/provider remain route intent, not an exact execution claim. |
| Opaque provider outcome | PASS | `consume_cloud_agent` records missing actual model/provider values as explicit `unknown` values. |
| Fail closed | PASS | Invalid role/tier, unavailable preflight, missing consumer preflight, unavailable inventory, and failed bounded delegation return `not-activated` or an unavailable result without activation. |
| Cost provenance | PASS | Observed accepted-outcome cost takes precedence; the existing authoritative published pricing snapshot is the fallback; unavailable remains unavailable. |
| Dependencies | PASS | No `requirements.txt`, `pyproject`, or other dependency manifest change. |
| Database schema | PASS | No `CREATE TABLE`, `ALTER TABLE`, migration, or database access was added. Persistence is append-only JSONL metadata. |
| Cross-project imports/integrations | PASS | No cross-project import, `sys.path` shim, `src/integrations/` file, network call, or provider implementation was added. |
| Agent definitions | PASS | No `.github/agents/*.agent.md` change. Topology completeness check found no missing Workspace agent node. |
| Security/visibility | PASS | The Workspace repository is public, but the slice stores only bounded metadata and explicitly rejects prompts, task payloads, source code, outputs, and sensitive domain data. No credentials or tokens are introduced. |

## Diagram Review

`diagrams/workspace-architecture-detail.mmd` does not contain the new
`copilot_model_selection.py`, `consume_cloud_agent`, `CloudAgentConsumer`, or
`persist_consumer_result` surface. The commit contains no Mermaid update, so
the new controlling module is not represented in the architecture view.

No update is required for `workspace-agent-topology.mmd`,
`workspace-db-schema.mmd`, `workspace-tech-stack.mmd`,
`workspace-integrations.mmd`, or the scheduler views: the commit adds no
agent, dependency, schema, external integration, or scheduler.

Required remediation: add a bounded Workspace consumer subgraph to
`diagrams/workspace-architecture-detail.mmd` showing the metadata-only
selection/inventory inputs, advisory or shadow selection, live preflight gate,
official/extension-owned consumer boundary, opaque outcome recording, observed
cost then published-pricing fallback, and fail-closed path. Preserve the
existing diagram budgets, style, lineage, and all current relationships.

Delegate to `⊕workspace-architecture-beautifier`.

## Remediation Applied

Updated `diagrams/workspace-architecture-detail.mmd` with a compact
`⊕ Supported Copilot cloud-agent consumer surface` inside the existing
Workspace boundary. The subgraph shows metadata-only route inputs through
`CachedInventory`, `select_model`, and `shadow_replay`, live capability
preflight, the official or extension-owned `CloudAgentConsumer` boundary,
`consume_cloud_agent`, opaque `ConsumerResult` and `TelemetryRecord` output,
observed accepted cost followed by the authoritative published-pricing
fallback, `persist_consumer_result`, and the bounded FR artifact boundary.
Unavailable preflight and bounded delegation failure are labeled as
`not-activated` or `unavailable`, fail closed.

No host-level delegation, undocumented endpoint, VS Code command, prompt,
task payload, source code, output, or provider implementation is represented.

## Remediation Validation

- Corrected worktree diagram rendered through `mermaid.ink HTTP`: `200`, valid
  SVG, `74,255` bytes.
- Architecture-detail budget and lineage validation: compliant; `4,233`
  UTF-8 characters, `41` nodes, `24` edges, no findings.
- `git diff --check`: passed.

## Validation Evidence

- Focused consumer, diagram-inventory, and scheduler suite: `34 passed`.
- Deterministic scheduler validator: no findings; all six canonical projects and
  audited job records are covered.
- Mermaid renderer: `mermaid.ink HTTP`; `47/47` diagrams rendered.
- `git diff --check`: passed.
- Documentation references `proof/copilot-consumer-demonstration.json`, but that
  file is absent at the reviewed commit. This is recorded as a documentation
  consistency gap, separate from the diagram staleness decision.

## Required Handoff

The hard-blocking `STALE` result requires the beautifier update above, followed
by a re-run of this architecture review before the FR can advance.