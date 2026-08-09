---
name: perfect-td
description: Turn a todo ID, todo text, or approved feature request into a substantially more implementation-ready todo.
disable-model-invocation: true
argument-hint: "A todo ID, todo text, or approved feature request"
---

# Perfect Todo

Turn the supplied work item into a clear, implementation-ready todo without
implementing it or changing any external state.

## Input

Accept one of:

- An existing todo ID, when its text is available in the conversation or the
  user provides the text alongside it.
- Todo text.
- An approved feature request, including its ID and any available scope,
  acceptance criteria, or decisions.

If an ID is supplied without its content, ask the user to provide
the text or paste the relevant request details.

## Process

1. Preserve the original intent and identify the user-visible outcome.
2. Separate the problem from the proposed solution when the input mixes them.
3. Make the scope concrete: state what is included and what is out of scope.
4. Identify assumptions, dependencies, blockers, risks, and unresolved
   decisions. Do not invent project-specific facts.
5. Write observable acceptance criteria that a later implementer can verify.
6. Add a focused validation approach appropriate to the work item.
7. Return the result as one polished todo, followed by a short list of
   questions only where missing information could change the implementation.

## Output

Use this structure:

```markdown
# <clear todo title>

## Outcome
<What will be true for the user when this is complete.>

## Problem
<The concrete problem or opportunity.>

## Scope
<What this todo includes.>

## Out of scope
- <Boundary 1>

## Acceptance criteria
- [ ] <Observable criterion>
- [ ] <Observable criterion>

## Dependencies and blockers
- <Dependency, blocker, or "None identified">

## Assumptions and risks
- <Assumption or risk, or "None identified">

## Validation
<The smallest useful test, check, or demonstration.>

## Open questions
- <Only questions that materially affect implementation, or "None">
```

Keep the result project- and workflow-agnostic. Prefer precise, testable
language over implementation guesses. Do not add tracker-specific fields,
file paths, branch names, or technical design details unless they were already
present in the input or are necessary to make a criterion verifiable.