# <FR-ID> — <Title>

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** <FR-YYYYMMDD-slug>
- **Title:** <short descriptive title>
- **Type:** feature | fix | chore
- **Risk:** low | medium | high
- **Projects:** <comma-separated list>
- **State:** OPEN
- **Branch:** <feature/FR-ID | pending>
- **PRs:** <per-repo URLs | pending>
- **Cycle timer:** <perf_cli run_id started at intake | pending>
- **Opened:** <ISO date>
- **Last updated:** <ISO date>
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. <criterion>
2. <criterion>
3. <criterion>

### Concurrency Notes
- Conflicts with: <other FR IDs or "none">
- Depends on: <other FR IDs or "none">

### Deliverable Tracker

<!-- Mutable table. Agents flip their own row's Status + Proof + Updated in place.
     Status vocab: not-started → in-progress → blocked → done → verified.
     Proof column: proof_artifact id (from proof_cli) or PR comment URL. -->

| #   | Deliverable   | Owner   | Status      | Proof | Updated |
| --- | ------------- | ------- | ----------- | ----- | ------- |
| AC1 | <deliverable> | <agent> | not-started | —     | —       |

### Tyler's Original Request
> <verbatim quote of Tyler's plain-language request>

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### <ISO-8601 timestamp> — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, triage complete → TRIAGED

**Details:**
- Scope: <projects>
- Acceptance criteria drafted (see Header)
- Concurrency check: <result>

**Next:** awaiting Tyler: approve scope

---

## Artifacts

<!-- APPEND-ONLY. Links to concrete evidence. -->

- **Perf runs:** <run_id> — <short description>
- **Proof artifacts:** <proof_id> — <short description>
- **PRs:** <URL>
- **Commits:** <SHA> — <message>
- **Reports / dashboards:** <path or URL>
