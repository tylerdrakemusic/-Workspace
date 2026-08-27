# TODO Decision Metadata Standard

The workspace contract is implemented by `src/utils/todo_decision_metadata.py`.
AI-Manifest consumers should use the same field names and validation rules,
without maintaining a second contract.

## Contract

Each assessment contains these required fields:

- `expected_value`, `user_or_system_benefit`, `strategic_alignment`,
  `confidence`, and `cost_of_delay`: integer scores from 1 through 10.
- `primary_benefit_category`: one of `user`, `system`, `strategic`, `revenue`,
  `risk_reduction`, `learning`, `maintenance`, or `compliance`.
- `secondary_benefit_category`: optional, using the same category set.
- `benefit_summary` and `justification`: non-empty strings.
- `evidence`: a list of non-empty textual sources. It may be empty for
  assessments below the high-impact threshold.

Score anchors are explicit: `1` is minimal, `3` low, `5` moderate, `7` strong,
`8` high, `9` very high, and `10` exceptional. The validator returns these
anchors with the normalized metadata. Scores outside the inclusive 1-10 scale,
unsupported categories, unknown fields, and malformed evidence are rejected.

Completeness increases with impact. Any score of 8 or more requires at least
one evidence item. Any score of 9 or 10 requires at least two evidence items.
The contract does not infer or rename legacy fields such as `benefit_score`,
`confidence_score`, `impact_level`, or `rationale`.

## Compatibility And History

Migration is additive and idempotent. Existing TODO rows retain a null
`decision_metadata` value until an assessment is explicitly written. No
historical value is inferred or fabricated. Each successful write replaces the
current JSON value and appends the validated assessment to
`todo_decision_metadata_history` with an assessment timestamp.

The contract is progressively enforced: legacy rows remain readable while new
assessments must use the canonical fields, with additional evidence required
for high-impact decisions.

## Priority Guidance

`priority_guidance()` reports the current priority and a recommended 1-10
priority as advisory information. It never changes a TODO priority and does not
write `priority_history`. Explicit human-approved priority changes remain the
responsibility of the TODO persistence owner and must continue to use its
existing priority-history operation.