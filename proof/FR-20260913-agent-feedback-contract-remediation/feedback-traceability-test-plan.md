# FR-20260913 Agent Feedback Contract Remediation

## Initial feedback inventory

The governed `agent_feedback` read returned 12 pending substantive records. No
feedback row is changed or closed by this pass.

| Feedback ID | Owning surface | Disposition | Evidence / follow-up |
| --- | --- | --- | --- |
| 1 | ❤Music worktree-aware database instructions | Project-owned, routed to child 693 | Preserve as a separate project contract; no shared CLI edit here. |
| 2 | `src/utils/proof_cli.py` | Shared contract, child 692 | Directory paths must be recordable without a hashing crash. |
| 4 | `⊕workspace-reviewer-heavy.agent.md` | Agent-owned, child 693 | Agent-contract remediation was completed in the final branch; the heavy reviewer file itself was not modified. |
| 11 | `⊕workspace-architecture-reviewer.agent.md` | Agent-owned, child 693 | Agent-contract remediation was completed in the final branch. |
| 14 | `⊕workspace-architecture-reviewer.agent.md` | Agent-owned, child 693 | Duplicate execution-path concern grouped with agent contract work. |
| 18 | Reviewer/QA proof contract | Shared process contract, child 695 | Requires independent validation and proof policy decision; no closure here. |
| 20 | `∞Life/SUBJECT_PROFILE.json` bootstrap wording | Project-owned, child 694 | Preserve health-project scope; no health data or instructions touched here. |
| 29 | `src/utils/perf_cli.py` | Shared contract, child 692 | Direct script/module invocation must honor the package import boundary. |
| 39 | `⊕workspace-discovery.agent.md` / Capital routing | Agent/project routing, child 693/694 | Agent-contract remediation was completed in the final branch; project-owned routing remains unchanged. |
| 40 | `src/utils/fr_cli.py` | Shared contract, child 692 | `get` must expose acceptance criteria, full event summaries, and artifacts. |
| 41 | `src/utils/fr_approval_notification.py` | Shared contract, child 692 | Documented direct invocation must bootstrap repository imports. |
| 42 | `src/utils/fr_cli.py` | Duplicate shared contract, child 692 | Consolidated with 40; retain both source IDs for traceability. |

## Deduplicated groups

| Group | Source IDs | Expected behavior |
| --- | --- | --- |
| Proof directory safety | 2 | Recording a directory path does not raise while computing an optional file hash. |
| Canonical FR read completeness | 40, 42 | `fr_cli get` prints criteria, untruncated event summaries, and artifact rows. |
| Direct invocation bootstrap | 29, 41 | `perf_cli.py` and `fr_approval_notification.py` support documented direct execution from the repository root. |

## Focused TDD plan for child 692

1. RED: add isolated tests for the three groups above, using temporary or
   in-memory SQLite fixtures and subprocesses with production database access
   disabled.
2. GREEN: make the smallest compatibility-preserving changes in
   `proof_cli.py`, `fr_cli.py`, `fr_approval_notification.py`, and `perf_cli.py`.
3. REFACTOR: remove only duplication exposed by the focused tests, then run the
   focused suite and the existing neighboring CLI tests.

## Final branch scope

Commit `43146b4` modified these shared workspace contract surfaces:

- `.github/agents/⊕workspace-architecture-reviewer.agent.md`
- `.github/agents/⊕workspace-discovery.agent.md`
- `.github/agents/⊕workspace-qa-light.agent.md`
- `.github/agents/⊕workspace-reviewer-light.agent.md`
- `.github/agents/⊕workspace-reviewer.agent.md`
- `.github/agents/⊕workspace-tdd-light.agent.md`
- `.github/instructions/feature-request-flow.instructions.md`
- `.github/instructions/hygiene-base.instructions.md`

The same commit also refreshed the generated
`.github/!!☾⛧security/agent-manifest.json` and added
`tests/test_feedback_contracts.py`. No project-owned changes were present in
the final branch: no files under `∞Life`, `❤Music`, `⟨ψ⟩Quantum`,
`👁AI-Manifest`, or `ΣCapital` were modified.

The focused proof check is
`tests/test_feedback_contracts.py::test_traceability_plan_matches_final_branch_ownership_scope`.
It verifies that this plan names every modified agent/instruction file and
records the no-project-owned-changes result. The pre-correction run was RED
(7 passed, 1 failed because the plan was stale); after this correction the
focused suite is expected to be GREEN.
