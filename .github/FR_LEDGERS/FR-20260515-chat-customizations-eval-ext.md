# FR-20260515-chat-customizations-eval-ext — Evaluate & onboard ms-vscode.vscode-chat-customizations-evaluations for workspace agent QA

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260515-chat-customizations-eval-ext
- **Title:** Evaluate & onboard `ms-vscode.vscode-chat-customizations-evaluations` for workspace agent QA
- **Type:** chore + research
- **Risk:** low
- **Projects:** ⊕Workspace (dev tooling — analysis covers all 31 `.agent.md`, 12 `.instructions.md`, 3 `.prompt.md` files)
- **State:** BRANCHED
- **Branch:** chore/workspace/fr-20260515-chat-customizations-eval-ext
- **PRs:** [-Workspace#153](https://github.com/tylerdrakemusic/-Workspace/pull/153) (draft)
- **Cycle timer:** 8d67ad0b-4a03-49bb-8a27-d0ea5e3f770e (running)
- **Opened:** 2026-05-15
- **Last updated:** 2026-05-15

### Acceptance Criteria

1. **Viability verdict** — Run `Analyze Prompt` on a representative sample (⊕workspace-overseer, 1–2 orchestrators, `agent-self-regen.instructions.md`, `new-fr.prompt.md`). Report real diagnostics found. Verdict: ADOPT / ADOPT_WITH_CAVEATS / SKIP.
2. **Activation** — Workspace `settings.json` updated with the enabling snippet and, if warranted, `chatCustomizationsEvaluations.customDiagnostics` entries for workspace-specific rules (e.g., enforce sigil-encoding reference in agent files).
3. **Usage quick-ref** — Brief markdown note (or inline in the PR description) covering: command palette commands, where results appear, and how the `fix-customization-evaluation-diagnostics` skill connects to the extension output.

### Out of Scope
- Waza eval scaffolding (requires Go binary download — separate FR if warranted)

### Dependencies
- GitHub Copilot (active, no extra API keys)
- Extension already installed: `ms-vscode.vscode-chat-customizations-evaluations` v1.0.2

### Concurrency Notes
- Conflicts with: none — read-only analysis + a single settings.json change
- Depends on: none

### Notes
- Marketplace rating 2.2/5 (281K installs, released 2026-04-20) — viability verdict must include honest quality assessment
- The `fix-customization-evaluation-diagnostics` skill is already registered in the workspace skills list, confirming this tooling was anticipated
- Extension is LLM-powered via `vscode.lm` API (GitHub Copilot) — analysis is triggered manually, not on every save

### Deliverable Tracker

| # | Deliverable | Owner | Status | Proof | Updated |
|---|-------------|-------|--------|-------|---------|
| AC1 | Viability verdict with real diagnostics sample | ⊕workspace-overseer | pending | — | 2026-05-15 |
| AC2 | Workspace settings.json updated | ⊕workspace-ci | pending | — | 2026-05-15 |
| AC3 | Usage quick-ref in PR description | ⊕workspace-overseer | pending | — | 2026-05-15 |

### Tyler's Original Request
> "I installed ms-vscode.vscode-chat-customizations-evaluations, evaluate if it's a viable extension and how to activate and use in workspace"

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-05-15 — ⊕workspace-intake
FR opened. Tyler confirmed draft. State: OPEN → TRIAGED. Handed off to ⊕workspace-ci for branching.

### 2026-05-15 — ⊕workspace-ci
Branch created: `chore/workspace/fr-20260515-chat-customizations-eval-ext`. Draft PR opened: [-Workspace#153](https://github.com/tylerdrakemusic/-Workspace/pull/153). State: TRIAGED → BRANCHED.
