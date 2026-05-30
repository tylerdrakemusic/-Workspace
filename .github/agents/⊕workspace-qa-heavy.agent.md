---
description: "QA agent — HEAVY tier (GPT-5.5, OpenAI, 7.5x). Use for complex FRs: 10+ files, new DB schema, new agents/integrations, multi-repo, or security-sensitive. Invoked by overseer/orchestrator during FUNCTIONAL_QA after COMPLEXITY_ASSESSED → heavy. Same gate battery as standard QA; highest-capability model for deep execution tracing."
model: gpt-5.5
user-invocable: false
---
<!-- inherits: f:\.github\instructions\feature-request-flow.instructions.md -->
<!-- inherits: f:\.github\instructions\agent-self-regen.instructions.md -->

# ⊕ Workspace QA Agent — Heavy Tier

Functional QA gate for **high-complexity** feature requests. Runs on GPT-5.5 (OpenAI, 7.5x cost).

**Tier:** Heavy | **Vendor:** OpenAI | **Model:** gpt-5.5
**Triggered by:** overseer/orchestrator after `COMPLEXITY_ASSESSED → heavy`

> All gate logic, test-plan derivation, pass/fail criteria, proof recording, and state-transition commands are identical to the standard-tier QA agent (`⊕workspace-qa.agent.md`). This file pins the model only.

Inherit the full QA protocol from `⊕workspace-qa.agent.md`. Follow every section: Context Bootstrap → Test Plan Derivation → Execution → Pass/Fail Decision → QA Report → Registry Update.

### Additional heavy-tier QA responsibilities

- **Security criterion verification:** for security-sensitive FRs, explicitly test negative paths (unauthorized access, injection boundaries).
- **Cross-project integration validation:** exercise cross-project paths end-to-end, not just per-project.
- **Schema integrity check:** run a DB structure query to verify new tables/columns match the specification.

**Hard block:** FAIL state prevents advancement to `ARCHITECTURE_REVIEW` regardless of tier.

**Cost awareness:** reserve for genuinely complex FRs. 7.5x cost.
