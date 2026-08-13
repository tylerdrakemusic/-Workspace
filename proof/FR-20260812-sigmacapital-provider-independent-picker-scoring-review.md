# Automated Review - FR-20260812-sigmacapital-provider-independent-picker-scoring

**Decision:** CHANGES_REQUESTED

| Gate | Result | Notes |
|------|--------|-------|
| Scope conformance | PASS with blocker | Five changed SigmaCapital source/test files match the scoring and qualification scope. No implementation of future providers or earnings-research reimplementation found. |
| Security | PASS | No hard-coded secrets, tokens, account identifiers, non-Schwab broker API, or live-order call was introduced. |
| Alignment | PASS with blocker | Provider-neutral result, deterministic fallback, DB threshold, and all three buy candidate paths are wired. The evidence flag is incorrectly trusted from a caller-shaped non-empty mapping. |
| SigmaCapital SIMULATED/REAL scan | PASS | No `live=True`, `confirm=True`, or real-mode change in the diff. Existing manual Trade Gate and Schwab protections are outside the diff and preserved. |
| Architecture diagrams | PASS_WITH_UPDATES | Final ledger event records `ARCHITECTURE_REVIEW:PASS_WITH_UPDATES`; topology and source checks were reported PASS. |
| Worktree path audit | PASS | No `.worktrees/` path is present in the changed-file diff. |
| tmp cleanliness | PASS | No ephemeral PR artifacts found under the worktree `tmp/` directory. |
| Tests | BLOCKED | Focused slice passes 41 tests, but the missing builder-level evidence case is not covered. A direct probe returns a candidate with empty summary and no financial evidence when given a qualifying deterministic result. |
| Functional QA | PASS_WITH_RESIDUAL_GAP | Ledger records `QA PASS`, but its AC4 proof claim is contradicted by the direct builder probe. |
| Proof-in-the-pudding | BLOCKED | Proof run exists, but the associated successful run reports Coverage 0%; its AC4 claim is not sufficient to clear the reproduced defect. |
| Demo | N/A | No visible surface changed. |
| UI Validation | N/A | No HTML or output surface changed. |

## Acceptance Criteria Check

1. Active scoring path removes Ollama runtime dependency and retains deterministic fallback - satisfied by static diff and focused tests.
2. Provider-neutral typed scoring contract and provenance fields - satisfied by `ScoreResult` and focused scoring tests.
3. Perplexity context and strict validation with deterministic failure fallback - satisfied by focused tests and static inspection.
4. Provider-independent, DB-tunable, fail-closed qualification before candidate creation - **not satisfied**. `_build_candidate_row` passes `{"summary": "", "financial_summary": ""}` to scoring. The mapping is truthy, so fallback `signal_available` can remain true; with a score at or above the configured threshold, the row is returned. Direct probe reproduced this with symbol `EMPTY`, threshold `7.0`, score `7.5`, and no evidence.
5. Existing risk, performance, freshness, margin, sizing, provenance, and manual approval gates - preserved in the changed surface; surrounding safety regression evidence passes.
6. Focused tests cover qualification boundaries and candidate paths - incomplete because no test exercises empty builder evidence with a qualifying result.

## Required Changes

- [ ] Make signal availability derive from actual non-empty evidence at the qualification boundary, or pass an evidence-aware technical context from `_build_candidate_row`; do not treat the presence of an empty-field mapping as evidence.
- [ ] Add a regression test through `_build_candidate_row` or each candidate-generation path proving empty summary and absent financial evidence never creates a row, even when the fallback score is at or above the configured threshold.
- [ ] Re-run the focused and safety suites, refresh the AC4 proof artifact, and re-request review.

## Evidence

- Focused tests: `tests/test_research.py tests/test_scoring.py` -> 41 passed, 1 deselected.
- Direct read-only builder probe: returned a populated buy row for empty evidence with a qualifying deterministic score.
- Final architecture ledger event: `ARCHITECTURE_REVIEW:PASS_WITH_UPDATES`.
- GitHub search: no pull request exists for the requested branch, so no GitHub-native review comment was possible.
