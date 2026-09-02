# ⊕ Architecture Impact Report - FR-20260822-workspace-architecture-diagram-system / TODO 305

**Decision:** PASS
**Review:** Architecture rerun after fallback-provenance repair
**Reviewed worktree:** `F:\⊕Workspace\.worktrees\feature-FR-20260822-workspace-architecture-diagram-system-todo-305`
**Scope:** TODO 305 only: dashboard rendering and fallback diagnostics. TODO 306 gallery validation remains explicitly out of scope.

## Evidence

| Check | Result | Evidence |
|---|---|---|
| FR ledger and handoff | PASS | Latest ledger events record the prior heavy-review `REQUEST_CHANGES`, the fallback-provenance repair, and the latest QA-heavy `FUNCTIONAL_QA:PASS` at `2026-08-25T16:43:41Z`. Parent FR remains `SOAKING`; no lifecycle transition was made. |
| Prior finding addressed | PASS | The prior review identified false success when `--no-render` reused a persisted fallback SVG. New fallback SVGs carry `diagrams-dashboard:fallback`; `_fallback_provenance()` also recognizes legacy `Fallback Preview:` SVGs and recovers their escaped error text. |
| Diff scope | PASS | The final diff changes only `tools/diagrams_dashboard.py`, `tests/test_diagrams_dashboard.py`, and `tests/test_mermaid_client.py`; this report is the only additional review artifact. No TODO 306 path or change is present. |
| Render semantics | PASS | Genuine Mermaid output remains `ok=True`, `status="rendered"`. Backend failure remains `ok=False`, `status="fallback"`, writes a bounded source snapshot, and preserves `fallback_error`. Missing persisted output remains `status="error"` with `Not rendered yet`. |
| Persisted current and legacy fallbacks | PASS | `--no-render` classifies newly marked fallback SVGs and legacy SVGs containing `Fallback Preview:` as `status="fallback"`, so neither can inflate the rendered count. Unmarked existing SVGs remain genuine `status="rendered"`. Focused tests cover persisted fallback reconstruction; implementation inspection confirms both marker generations. |
| Bounded previews | PASS | Fallback source snapshots still include only `source.splitlines()[:18]`; no source-preview or diagram-discovery expansion was introduced. `_svg_dims()` remains bounded to the first 1024 SVG characters. |
| HTTP/error behavior | PASS | The focused client test confirms HTTP 414 is surfaced as `MermaidRenderError("HTTP 414: Request-URI Too Long")`; the repair does not swallow or relabel genuine renderer errors during active rendering. |
| Tests and QA | PASS | Focused dashboard/Mermaid suite: `18 passed`. Full Workspace suite: `907 passed, 13 skipped, 11 deselected`. Compileall and `git diff --check` pass. Live `--no-render --no-open` exits `0` and rebuilds the index. |

## Architecture and Diagram Impact

The repair changes runtime result classification and persisted fallback diagnostics inside the existing dashboard boundary. It adds no agent, dependency, database table, integration, top-level module, cross-project import, or FR-flow behavior. The mandatory topology completeness check found no workspace agent file missing from `diagrams/workspace-agent-topology.mmd`.

**Required updates:** None. `diagrams/*.mmd`, `DIAGRAM_DISCOVERY.md`, diagram budgets/style documentation, Mermaid integration documentation, and architecture documentation do not require updates for TODO 305. Existing diagram budget, traceability, and derived-view work belongs to TODO 304 and is not reopened. TODO 306 is not reviewed.

## Renderer Evidence

- Backend availability: local `mmdc` is unavailable; the configured fallback backend is `mermaid.ink HTTP`.
- Latest QA PASS includes live renderer, HTTP failure, and no-render evidence. The rerun itself intentionally used `--no-render --no-open`, so no new renderer request was made and its renderer result is `NOT RUN (intentional no-render validation)`.
- The live renderer evidence remains `29/32` genuine renders and `3` explicit fallbacks, including the known HTTP 414 cases and the pre-existing unrelated HTTP 400 case documented by QA.

## Conclusion

The fallback-provenance repair prevents false success for persisted current and legacy fallback SVGs, preserves genuine render and error semantics, keeps previews bounded, and is strictly scoped to TODO 305.

**Handoff:** PASS permits governed handoff to `⊕workspace-reviewer-heavy`.