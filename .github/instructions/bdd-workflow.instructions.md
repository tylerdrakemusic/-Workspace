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
- Some approved scenarios describe agent-only orchestration or MCP behavior for which the repository has no deterministic runtime boundary. Do not invent a fake classifier, simulator, or instruction-text test. When a supported host can invoke the exact agent with isolated tools, QA records structured evidence from that actual workflow invocation: criterion ID, approved context/input, actual tools/actions, sanitized observable outputs/state, FR event/artifact references, outcome, and limitations.
- When no supported isolated invocation path exists, QA records a structured `NOT_VERIFIED_HOST_LIMITATION` artifact for each affected criterion. It must identify the target agent/skill and branch, explain why invocation was unavailable or unsafe, and state what remains unverified. It is not a PASS proof or CI result. QA may report `PASS_WITH_LIMITATIONS` and advance to `ARCHITECTURE_REVIEW` only when every deterministic criterion passes, the only unverified criteria are agent/skill behavior blocked by the host limitation, and no other functional or security failure exists. The QA report and artifact must keep those criteria explicitly `NOT_VERIFIED`.
- A `PASS_WITH_LIMITATIONS` `functional-qa-evidence` artifact must be criteria-bound and stored as JSON under the FR worktree's `proof/` directory. Include schema version, artifact type, FR ID, branch, criteria version/hash, decision, gate summary (`deterministic_checks_passed`, `security_checks_passed`, empty `other_failures`), one ordered result per acceptance criterion, and matching unverified-criterion reasons. Classify each criterion as `deterministic`, `agent_skill_behavior`, or `conditional`; only `agent_skill_behavior` may use `NOT_VERIFIED_HOST_LIMITATION`. The ledger validates this structure and refuses label-only or out-of-worktree evidence.
- Keep deterministic tests and agent-only evidence distinct. A structured QA artifact cannot substitute for an executable test where production behavior has a real deterministic boundary, and it cannot be described as a CI result.
- Run the ordinary project pytest command. Every required executable feature scenario must be discovered and pass in that run before `FUNCTIONAL_QA`. Each agent-only scenario must have either structured real-invocation evidence or, when the supported invocation path is unavailable, the limitation evidence and outcome defined above.
- Extend project test configuration only when a focused executable scenario demonstrates a discovery gap. Keep BDD scenarios in the normal pytest/CI collection path.

## CI Contract

CI validates deterministic BDD scenarios through the project's normal pytest suite. A separate command that runs feature files outside normal collection does not satisfy this gate. Agent-only structured QA evidence and `PASS_WITH_LIMITATIONS` artifacts are not represented as automated CI coverage.