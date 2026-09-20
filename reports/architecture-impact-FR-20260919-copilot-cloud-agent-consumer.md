# ⊕ Architecture Impact Report - FR-20260919-copilot-cloud-agent-consumer

**Commit reviewed:** `6e20b758c46b714aa679203dcf9a97d371b5c67d`
**Decision:** PASS

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

`diagrams/workspace-architecture-detail.mmd` represents the new bounded
`⊕ Supported Copilot cloud-agent consumer surface` inside the existing
Workspace boundary. It shows metadata-only route inputs through
`CachedInventory`, `select_model`, and `shadow_replay`, live capability
preflight, the official or extension-owned `CloudAgentConsumer` boundary,
`consume_cloud_agent`, opaque `ConsumerResult` and `TelemetryRecord` output,
observed accepted cost followed by the authoritative published-pricing
fallback, `persist_consumer_result`, and the bounded FR artifact boundary.
Unavailable preflight and bounded delegation failure are labeled as
`not-activated` or `unavailable`, fail closed.

No update is required for `workspace-agent-topology.mmd`,
`workspace-db-schema.mmd`, `workspace-tech-stack.mmd`,
`workspace-integrations.mmd`, or the scheduler views: the branch adds no
agent, dependency, database schema, cross-project integration, or scheduler.

No host-level delegation, undocumented endpoint, VS Code command, prompt,
task payload, source code, output, or provider implementation is represented.

## Validation

- Current branch diagram set rendered through `mermaid.ink HTTP`: `47/47`,
  valid SVG output.
- Focused deterministic architecture and scheduler suite: `38 passed`.
- Architecture-detail budget and lineage validation: compliant; the target
  remains within the detail budget and preserves its parent/derived-view
  contract.
- Complete-agent-topology check: `23/23` agent files represented.
- `git diff --check`: passed.

## Boundary Validation

- No new dependency, database schema, cross-project integration, security, or
  repository-visibility issue was found. The public Workspace surface remains
  metadata-only and excludes credentials, prompts, task payloads, source code,
  outputs, and sensitive domain data.
- The implementation documentation's
  `proof/copilot-consumer-demonstration.json` is present as a committed,
  metadata-only demonstration of the supported consumer boundary. It records
  the explicit `live_available: false` fail-closed result and contains no
  prompts, task payloads, source code, outputs, or sensitive domain data.
