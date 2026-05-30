---
description: "QA agent — LIGHT tier (GPT-5.4 mini, OpenAI, 0.33x). Use for simple FRs: ≤2 files, no schema, single project. Invoked by overseer/orchestrator during FUNCTIONAL_QA after COMPLEXITY_ASSESSED → light. Same gate battery as standard QA; lighter model."
model: gpt-5.4-mini
user-invocable: false
---
<!-- inherits: f:\.github\instructions\feature-request-flow.instructions.md -->
<!-- inherits: f:\.github\instructions\agent-self-regen.instructions.md -->

# ⊕ Workspace QA Agent — Light Tier

Functional QA gate for **light-complexity** feature requests. Runs on GPT-5.4 mini (OpenAI, 0.33x cost).

**Tier:** Light | **Vendor:** OpenAI | **Model:** gpt-5.4-mini
**Triggered by:** overseer/orchestrator after `COMPLEXITY_ASSESSED → light`

> All gate logic, test-plan derivation, pass/fail criteria, proof recording, and state-transition commands are identical to the standard-tier QA agent (`⊕workspace-qa.agent.md`). This file pins the model only.

Inherit the full QA protocol from `⊕workspace-qa.agent.md`. Follow every section: Context Bootstrap → Test Plan Derivation → Execution → Pass/Fail Decision → QA Report → Registry Update.

**Hard block:** FAIL state prevents advancement to `ARCHITECTURE_REVIEW` regardless of tier.
