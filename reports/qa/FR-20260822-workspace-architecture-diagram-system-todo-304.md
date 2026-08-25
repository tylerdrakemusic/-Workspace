# QA Report - FR-20260822-workspace-architecture-diagram-system TODO 304
**Decision:** FAIL

| # | Acceptance criterion | Test type | Result | Evidence |
|---|---|---|---|---|
| 1 | TODO 324 guidance explicitly enforces `DIAGRAM_BUDGETS.md` budgets, split rules, parent/derived traceability, relationship preservation, and renderer evidence. | Focused pytest plus source inspection | PASS | `pytest tests/test_diagram_budgets.py tests/test_diagram_inventory.py tests/test_todo_graph_guidance.py tests/test_architecture_agent_contract.py -q`: 16 passed. `DIAGRAM_BUDGETS.md`, `⊕workspace-architecture-reviewer.agent.md`, and `⊕workspace-architecture-beautifier.agent.md` contain the required rules. |
| 2 | TODOs 325-328 refactor the four oversized Mermaid source families into focused views while preserving semantics. | Diff and normalized parent/derived edge audit | FAIL | `git diff origin/main...HEAD` contains the four parent rewrites and 10 derived views. The normalized edge audit found missing parent relationships in `capital-architecture.mmd`, `capital-db-schema.mmd`, `manifest-architecture.mmd`, and `workspace-integrations.mmd`; examples include `RISK_THRESHOLDS -> TRADE_CANDIDATES`, `EXITS -> EXITS`, `AudioOut -> Portal`, `BackupContract -> BackupInventory`, `Life -> OpenAI`, `Music -> FlyIO`, and `Quantum -> IBMQ`. The current parent-plus-derived unions do not preserve the origin/main relationship sets. |
| 3 | Every resulting source meets applicable character/byte/node/edge budgets and has valid Mermaid syntax. | Canonical budget measurement plus renderer | FAIL | All 13 TODO 304 changed/added sources individually pass the applicable budget and traceability checks. However, `validate_inventory()` reports 29 existing inventory mismatches, including stale metrics for `capital-tech-stack.mmd`, `life-architecture.mmd`, `quantum-architecture.mmd`, `workspace-architecture-detail.mmd`, and others; therefore the resulting source set is not inventory/budget-clean as a whole. `tools/diagram_beautifier.py --validate` reports 32/32 with `mmdc not found` skips, not true local syntax validation. |
| 4 | Inventory and focused tests reflect the derived views. | Inventory validator and pytest | FAIL | Focused pytest passes, and inventory lists 32 sources including all derived views. The executable inventory reconciliation reports 29 metric mismatches, including swapped `workspace-integrations.mmd` bytes/characters and stale counts for unchanged sources. |
| 5 | TODO 305 renderer implementation and TODO 306 gallery-wide validation are untouched. | Diff scope check | PASS | `git diff --name-only origin/main...HEAD` contains no renderer, gallery, `diagrams_dashboard.py`, `gen_diagram_gallery.py`, or `diagrams_zoom_check.py` changes. |

## Test execution

- Focused: `C:\G\python.exe -m pytest tests/test_diagram_budgets.py tests/test_diagram_inventory.py tests/test_todo_graph_guidance.py tests/test_architecture_agent_contract.py -q` -> 16 passed.
- Full: `C:\G\python.exe -m pytest -q` -> 902 passed, 13 skipped, 11 deselected.
- Inventory/measurements: `C:\G\python.exe -c "from utils.diagram_budgets import measure_source, validate_inventory; ..."` -> 29 findings.
- Built-in syntax command: `C:\G\python.exe tools/diagram_beautifier.py --validate` -> 32/32 reported, but all used `mmdc not found` skip behavior.
- Backend rendering: `C:\G\python.exe tools/diagrams_dashboard.py --no-open` -> 32/32 rendered through `mermaid.ink`; all TODO 304 changed/derived sources generated non-fallback SVGs. Three unrelated/pre-existing sources used fallback: `music-architecture`, `music-icecast-primary-architecture`, and `workspace-architecture-detail`.
- Diff scope: `git diff --name-status origin/main...HEAD` -> 19 expected files; no TODO 305/306 renderer/gallery files.

## Residual risks

- The Mermaid HTTP backend evidence demonstrates generated SVGs, but local `mmdc` syntax validation remains unavailable.
- Parent/derived semantic preservation needs implementation repair before architecture review; the missing-edge list above is representative, not exhaustive.
- Inventory metrics are not reconciled with the current 32-source checkout, so downstream budget reports cannot be trusted as a clean whole-repository gate.
- QA timer direct-script startup failed because `perf_cli.py` imports relatively outside package context; the run succeeded through `PYTHONPATH=src` and `python -m utils.perf_cli`.

## Verdict

FAIL. Do not advance to `ARCHITECTURE_REVIEW` until the missing relationships are restored or explicitly represented with documented cross-view linkage, and the inventory is regenerated/reconciled so `validate_inventory()` returns no findings.