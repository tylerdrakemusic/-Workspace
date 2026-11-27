# Agentic QA Feasibility

## Decision

The current host cannot safely run the workout planner as a mocked QA target.
Do not invoke it through `runSubagent` until the host can replace every declared
and nested tool with an isolated synthetic adapter and provide an auditable
action trace. No planner run or production database access was performed for
this assessment.

## Verified Host Surface

- The documented VS Code extension APIs found for chat create an extension-owned
  chat participant, send a language-model request, or open editor chat. They do
  not invoke an existing local `.agent.md` by name.
- The available `runSubagent` call accepts an agent name, description, and
  prompt. It can dispatch named workspace agents, but has no per-call tool
  override, fixture-root, credential, timeout, cancellation, or trace-sink
  parameters. Its caller receives a final response, not a host-verifiable tool
  event stream.
- The workout planner declares SQLCipher list, describe, and read tools plus a
  nested `∞life-risk` agent. The current tool mapping points at live workspace
  capabilities. A prompt asking the planner not to use them is not isolation.
- The operator-run fallback is not verified as a way to inject synthetic tool
  adapters or capture a complete host-authenticated trace.

## Mock Terminology

**Mocked agent evaluation** means the exact target agent and skill definitions
are executed, identified by hashes from the FR branch, while every external
tool and writable state is replaced at the host boundary with synthetic
adapters and disposable fixtures. Label its result `MOCKED_AGENT_EVAL`. It
tests the target instructions against those synthetic dependencies; it does
not establish behavior against production data or services.

A **mock or stand-in agent** does not execute the target agent definition. It
may test an evidence formatter or harness contract only. Its output is never
evidence that the target agent or skill behaved correctly.

## Required Guardrails

1. Authorize only the designated Workspace QA roles and the human operator.
   Resolve targets only from the six governed workspace repositories.
2. Resolve and hash the exact target `.agent.md`, referenced `SKILL.md` files,
   and branch revision before execution. Refuse if the executed definitions do
   not match those identities.
3. Inventory every declared tool recursively, including nested-agent tools.
   Bind each tool to an isolated synthetic adapter before invocation. Reject
   the run if any tool is missing an adapter or can fall through to a live
   service.
4. Provide only synthetic scenario-owned data and disposable writable state.
   Remove production credentials from the execution environment and deny
   production databases, files, services, and network destinations.
5. Keep nested agents inside the same tool and fixture boundary. A mocked
   `∞life-risk` result is a synthetic safety-gate test, not a real health
   assessment or clearance.
6. Enforce a configurable hard time ceiling, cancellation, and cleanup. A
   cancelled, timed-out, or cleanup-failed run is incomplete and cannot pass.
7. Capture actual host-observed tool/action events. Sanitize inputs and outputs
   before persistence; retain no raw transcript, secret, personal data, or
   sensitive payload. Agent-authored summaries alone are not verified traces.
8. Store structured evidence with the run label, agent and skill hashes,
   branch SHA, criterion mapping, sanitized synthetic input, observed action
   sequence, sanitized outputs, verdict, and limitations. Keep mocked evidence
   distinct from live-run evidence and CI results.
9. Keep deterministic file-contract tests in ordinary pytest collection.
   These can validate frontmatter, metadata shape, and referenced-file
   existence, but cannot prove agent or skill behavior by matching source text.

## Pilot Gate

The workout-planning skill is a candidate because it exercises an agent, a
skill, and a nested safety review. Its declared SQLCipher tools must be
replaced with schema-compatible synthetic adapters before it is invoked. The
pilot must not read or write the real Life database or use real health data.
If the host cannot enforce those replacements and provide observed action
events, stop before invoking the planner and record the affected behavior
criteria as `NOT_VERIFIED_HOST_LIMITATION`. QA may still advance with
`PASS_WITH_LIMITATIONS` when its deterministic checks pass and there are no
other functional or security failures.

The Workspace QA and BDD contracts now allow the FR flow to continue with
`PASS_WITH_LIMITATIONS` when all deterministic checks pass and only
agent/skill behavior remains unverified because the host cannot safely invoke
the target. Each such criterion stays `NOT_VERIFIED`, is not counted as a pass
or CI result, and remains visible through review and Tyler's final approval.
If a later host-supported route passes this gate, add its tested procedure and
evidence template to the new-FR and Workspace QA guidance. No general-purpose
runner or mocked planner result is claimed as implemented.

## Prerequisites for a Safe Pilot

- A supported invocation boundary that can run the exact named agent while
  binding all declared and nested tools to fixture adapters.
- Host-observed invocation and tool events, with redaction before persistence.
- Enforced fixture-only paths, no production credentials, and no production
  network or database access.
- Bounded execution, cancellation, and verified cleanup of disposable state.
- Executable tests for the deterministic controls, collected by the normal
  Workspace pytest suite.