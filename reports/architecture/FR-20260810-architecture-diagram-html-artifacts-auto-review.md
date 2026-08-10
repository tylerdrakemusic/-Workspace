# Automated Review - FR-20260810-architecture-diagram-html-artifacts
**Decision:** REQUEST_CHANGES

## Findings

1. **Required: AC6 is not satisfied literally.** The approved intake event requires the one-time migration to process all 25 existing Mermaid files. The worktree contains 23 canonical files under `diagrams/` and two additional `.mmd` files under `proof/FR-20260602-cap-picker-pipeline/`; the implementation publishes only the 23 canonical files. The earlier QA and architecture evidence explicitly exclude those two proof snapshots, so the 25-file acceptance criterion is still unproven. Either publish traceable artifacts for all 25 files, or obtain and record a scope clarification that formally excludes proof snapshots and updates AC6.

2. **Residual risk: HTML artifacts depend on a third-party CDN.** All 23 generated HTML files import Mermaid from `cdn.jsdelivr.net`, so offline or network-restricted use renders the source/provenance block but not the diagram. This is not a security blocker because the source is escaped and Mermaid uses `securityLevel: "strict"`, but it should be documented or addressed before calling the artifacts fully stable.

## Gate Evidence

| Gate | Result | Evidence |
|------|--------|----------|
| Scope conformance | FAIL | AC1-AC5 verified; AC6 is 23/25 as currently worded. |
| Security | PASS | Malicious `</div><script>` source was HTML-escaped; canonical path restriction is enforced. |
| Alignment | PASS | ⊕Workspace-only changes; dashboard and agent contracts follow local patterns. |
| Architecture diagrams | PASS_WITH_UPDATES | Prior architecture-review event; topology artifact has reviewer/beautifier provenance. |
| Worktree path audit | PASS | No `.worktrees/` path in the feature diff. |
| Tests | PASS | Focused: 25 passed. Full suite: 634 passed, 13 skipped, 11 deselected. `py_compile` and `git diff --check` passed. |
| Functional QA | PASS | Prior ledger event records `QA PASS: AC1-AC6 verified`; this review identifies the AC6 evidence mismatch. |
| Proof-in-the-pudding | FAIL | Proof demonstrates 23 canonical artifacts, not the literal 25-file AC6 requirement. |
| Demo | PASS | `reports/diagrams_dashboard.html` contains 23 canonical HTML iframes and links. |
| UI validation | N/A | No browser run required by the recorded QA plan; static artifact checks were used. |

## Acceptance Criteria

1. Deterministic HTML for every `diagrams/*.mmd` source - satisfied for 23/23 canonical sources.
2. Dashboard consumes published HTML as canonical output - satisfied.
3. Mermaid semantics and source provenance preserved - satisfied for generated artifacts.
4. Agent and FR-flow contracts require publication, provenance, proof, and migration behavior - satisfied.
5. Focused tests cover discovery, rendering, provenance, failure handling, and contracts - satisfied; 25 passed.
6. One-time pass processes all 25 existing diagrams - **not satisfied/proven**; 23 canonical files were processed and two proof snapshots were excluded.

## Required Change

- Clarify AC6 in the canonical FR ledger to exclude proof snapshots, or publish and prove artifacts for the two files under `proof/FR-20260602-cap-picker-pipeline/`.

## Residual Risk

The generated artifacts require network access to load Mermaid from jsdelivr. The source and provenance remain visible if the CDN is unavailable, but the rendered diagram does not.