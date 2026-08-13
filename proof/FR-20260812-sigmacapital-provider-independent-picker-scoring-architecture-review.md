## ⊕ Architecture Impact Report — FR-20260812-sigmacapital-provider-independent-picker-scoring
**Decision:** STALE
**Next state:** ARCHITECTURE_REVIEW (blocked pending diagram remediation and re-review)

### Review scope
- ΣCapital worktree: `F:\ΣCapital\.worktrees\feature-FR-20260812-sigmacapital-provider-independent-picker-scoring`
- Compared the complete uncommitted worktree diff against `HEAD`/`main` because the feature branch has no commits beyond `main`.
- Focused validation: `41 passed, 1 deselected` for `tests/test_scoring.py` and `tests/test_research.py`, excluding integration and Playwright coverage.

### Findings
- The consumer boundary is a typed `ScoreResult` plus `qualifies_candidate()`, and candidate generation remains responsible for sizing, persistence, pending approval, and no-order execution. The boundary is usable, but its implementation is still Perplexity-specific: the adapter, parser, `method`, `provenance`, and direct news fetch are hardcoded in `src/utils/scoring.py`. This is acceptable as the active provider adapter only if the architecture diagram makes the provider-neutral boundary explicit.
- Perplexity reuse is isolated through the existing Workspace integration package. No new dependency or duplicate earnings-research implementation was introduced; existing earnings/fundamentals data remains supplied by `financials.py` and is passed as scoring context.
- The qualification policy migration is additive and idempotent: it adds no table or destructive operation and seeds `risk_thresholds.qualification_score` only when absent, preserving existing rows and defaults. Existing candidates remain backward compatible because the policy is applied at generation time and does not rewrite historical rows.
- Future earnings/fundamental, news-sentiment, and social-sentiment providers have no concrete implementations in this diff. The current public contract is an aggregate `ScoreResult`; channel-specific future interfaces are intentionally not implemented and should remain a later extension rather than being inferred here.
- Risk, margin, performance, freshness, sizing, provenance, manual approval, Schwab, compliance, and real-money boundaries remain in their existing modules and routes. Candidate generation still persists pending recommendations and does not place orders.
- No private health, financial credential, token, database, or real-account data was added to the public Workspace scope. The changed code stays in the private ΣCapital worktree and consumes the already-governed Workspace Perplexity integration.

### Diagram impact
| File in diff / architectural surface | Impact type | Affected diagram | Status |
|---|---|---|---|
| `src/utils/scoring.py` | New explicit provider-neutral scoring boundary with Perplexity adapter and deterministic fallback | `F:\⊕Workspace\diagrams\capital-architecture.mmd` | STALE |
| `src/utils/init_db.py` | New DB-backed qualification policy dimension and seed behavior | `F:\⊕Workspace\diagrams\capital-db-schema.mmd` | STALE |
| Existing ΣCapital-to-Workspace Perplexity wiring | Cross-project import remains present and is reused, not newly represented | `F:\⊕Workspace\diagrams\workspace-integrations.mmd` | PASS |
| Existing dependency set | No requirements or dependency change | `F:\⊕Workspace\diagrams\capital-tech-stack.mmd` | PASS |
| All `.github/agents/*.agent.md` files | Mandatory topology completeness check finds agent files without topology nodes, including architecture, QA, reviewer, TDD, CI, intake, security, hygiene, dashboard, discovery, doer, protector, and benchmark agents | `F:\⊕Workspace\diagrams\workspace-agent-topology.mmd` | STALE |

### Required remediation
1. Update `F:\⊕Workspace\diagrams\capital-architecture.mmd` to show `src/utils/scoring.py` as the provider-neutral scoring boundary, its Perplexity adapter, deterministic fallback, qualification gate, and the unchanged pending/manual/Schwab real-money boundary. Keep future earnings/fundamental, news-sentiment, and social-sentiment providers as contract-only or future-labelled nodes with no implementation claim.
2. Update `F:\⊕Workspace\diagrams\capital-db-schema.mmd` to document `risk_thresholds.dimension='qualification_score'` and its seeded default, plus the existing candidate scoring/provenance fields used by the boundary.
3. Reconcile every agent file missing from `F:\⊕Workspace\diagrams\workspace-agent-topology.mmd`, including the current architecture reviewer and beautifier agents, and re-run the mandatory completeness check.
4. Delegate diagram updates to `⊕workspace-architecture-beautifier`, then re-run ARCHITECTURE_REVIEW. No code or diagram was modified by this review.
