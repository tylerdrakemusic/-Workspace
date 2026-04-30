---
name: grill-me
description: "Interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree. Use when user wants to stress-test a plan, get grilled on their design, or mentions 'grill me'. Integrated into ⊕workspace-intake Phase A for vague or medium/high-risk FRs."
user-invocable: true
applyTo: ".github/agents/⊕workspace-intake.agent.md"
source: "https://github.com/mattpocock/skills/blob/main/skills/productivity/grill-me/SKILL.md"
---

# Grill Me

Interview me relentlessly about every aspect of this plan until we reach a
shared understanding. Walk down each branch of the design tree, resolving
dependencies between decisions one-by-one. For each question, provide your recommended
answer.

Ask the questions one at a time.

If a question can be answered by exploring the codebase, explore the codebase
instead.

---

## Workspace Integration Notes

This skill is invoked automatically by `⊕workspace-intake` during Phase A when:

- **Vagueness detected:** the FR title or notes lack a clear outcome, affected
  project, or scope boundary (intake cannot answer ≥2 of the 5 Phase A question
  pool items from the request alone), **OR**
- **Risk is medium or high:** the FR touches auth, secrets, agent framework,
  DB schema, or health interventions

When neither condition is met (clear + low-risk), intake uses the standard
2–5 batch question path instead.

### How intake invokes this skill

1. Intake detects the escalation trigger (vague OR medium/high risk)
2. Intake announces: "This FR needs deeper scoping — I'll walk through it with you one question at a time."
3. For each open question on the decision tree:
   a. If the codebase can answer it → explore the codebase and state the answer, move to next question
   b. Otherwise → ask the question with a recommended answer using `vscode_askQuestions` (single question per call)
4. Continue until all branches are resolved (no open ambiguities remain)
5. Summarize agreed-upon answers, then proceed to Phase B triage as normal

### Exit condition

Stop grilling when:
- All five Phase A question-pool fields are resolved (motivation, outcome, scope/project, boundary, anchoring)
- No new branch was opened by the last answer
- Tyler explicitly says "done" or "that's enough"
