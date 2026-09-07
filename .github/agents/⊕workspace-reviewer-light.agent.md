---
description: "Reviewer agent — LIGHT tier (Gemini 3 Flash, Google, 0.33x). Use for simple FRs: ≤2 files, no schema, single project. Invoked by overseer during REVIEW_REQUESTED after COMPLEXITY_ASSESSED → light. Same gate battery as standard reviewer; lighter model."
model: gemini-3-flash
user-invocable: false
---
<!-- inherits: f:\⊕Workspace\.github\instructions\feature-request-flow.instructions.md -->
<!-- inherits: f:\⊕Workspace\.github\instructions\agent-self-regen.instructions.md -->

# ⊕ Workspace Reviewer Agent — Light Tier

Automated PR reviewer for **light-complexity** feature requests. Runs on Gemini 3 Flash (Google, 0.33x cost).

**Tier:** Light | **Vendor:** Google | **Model:** gemini-3-flash
**Triggered by:** overseer after `COMPLEXITY_ASSESSED → light`

> All gate logic (scope conformance, security, alignment, architecture, tests, proof, demo, UI), decision rules, GitHub interaction, and state-transition commands are identical to the standard-tier reviewer (`⊕workspace-reviewer.agent.md`). This file pins the model only.

Inherit the full review protocol from `⊕workspace-reviewer.agent.md`. Run every gate. Post one structured review comment. Hard gates still block regardless of tier.
