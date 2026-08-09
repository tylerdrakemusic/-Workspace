---
name: tradeoffs
description: Help choose between materially different options by weighing goals, constraints, cost, risk, effort, reversibility, and long-term value. Can also be invoked with /tradeoffs.
---

# Tradeoffs

Help the user make a consequential choice before design or implementation,
during active work, or after options have been listed.

## Recognize the Decision

Accept any of these inputs:

- A vague dilemma or an explicit list of options.
- A goal plus constraints, even when no options are named.
- A decision that emerges from work already in progress.

Treat a choice as meaningful when at least two plausible options differ
materially in cost, risk, effort, reversibility, or long-term value. Skip
trivial preferences and choices where one option is clearly better under the
stated goals and constraints.

If the situation is underspecified, infer only what is explicit. Ask no more
than one clarifying question, and only when its answer would change the
recommendation. Ask for the highest-value missing fact.

## Weigh the Options

Identify the user's goal, constraints, and the plausible alternatives. Compare
the options on the dimensions that matter to this decision; do not force every
dimension into the analysis.

Pay special attention to the tension between simplicity or reversibility and
long-term value. Do not silently choose which side wins. If that priority is
unclear, ask the user to set it. If the options remain genuinely close, ask
which priority should decide, using the single-question limit.

Prefer the option that best fits the stated priorities, not the option with the
most features. State important assumptions briefly. Do not invent specialized
health, legal, financial, or safety guardrails; remain domain-neutral.

## Respond

Unless a clarifying question is essential, keep the response concise:

**Recommendation:** [option]

- [reason]
- [reason]
- [optional third reason]

**Main tradeoff:** [what this choice gives up]

Mention a practical next step only when it helps the user act. If a question is
essential, ask only that question and explain in a few words why it determines
the choice. Do not make the decision on the user's behalf when the deciding
priority belongs to them.
