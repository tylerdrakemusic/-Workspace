# Behavior-Driven Acceptance Rules

## Intake Contract

Apply this workflow to feature requests processed by `.github/skills/new-fr/SKILL.md`.

- Classify the request by its observable effect before presenting the scope draft.
- For a behavior-changing feature request, write one or more explicit Given/When/Then scenarios before Tyler approves scope. Each scenario states the starting context, the user or system action, and an observable outcome. Ask about missing conditions or outcomes instead of guessing.
- Preserve pure documentation, housekeeping, and behavior-neutral refactors as exemptions from the G/W/T requirement. For mixed requests, write scenarios for the behavior-changing parts only.
- Include the scenarios in the scope draft and confirmation block. After scope approval and FR registration, record an intake `decision` event as `SCOPE_APPROVED: behavior-changing | <rationale>`, then preserve the approved scenarios unchanged in the canonical FR acceptance-criteria record before implementation is dispatched. Exempt requests use `SCOPE_APPROVED: exempt | <rationale>` and skip G/W/T persistence. The marker records the approval received in the intake turn; it is audit evidence, not identity authentication. The CLI permits `BRANCHED` only from `TRIAGED` with a valid approval classification, and requires stored scenarios for behavior-changing FRs.

## Implementation Contract

- Treat every approved Given/When/Then scenario as an implementation contract. Do not weaken, omit, or silently reinterpret an approved outcome.
- For deterministic production behavior, implement the approved scenario as an executable `.feature` under `tests/features/` with pytest-bdd bindings under `tests/bdd/`. Bind steps to the real user- or system-visible boundary, isolate databases and external effects, and include the scenario in the ordinary pytest/CI collection path.
- Some approved scenarios describe agent-only orchestration or MCP behavior for which the repository has no deterministic runtime boundary. For those scenarios only, do not invent a fake classifier, simulator, or instruction-text test. QA may instead record structured evidence from an actual workflow invocation: criterion ID, approved context/input, actual tools/actions, sanitized observable outputs/state, FR event/artifact references, outcome, and limitations.
- Keep deterministic tests and agent-only evidence distinct. A structured QA artifact cannot substitute for an executable test where production behavior has a real deterministic boundary, and it cannot be described as a CI result.
- Run the ordinary project pytest command. Every required executable feature scenario must be discovered and pass in that run before `FUNCTIONAL_QA`; each agent-only scenario must have its structured real-invocation evidence recorded during QA.
- Extend project test configuration only when a focused executable scenario demonstrates a discovery gap. Keep BDD scenarios in the normal pytest/CI collection path.

## CI Contract

CI validates deterministic BDD scenarios through the project's normal pytest suite. A separate command that runs feature files outside normal collection does not satisfy this gate. Agent-only structured QA evidence is recorded as QA proof and is not represented as automated CI coverage.