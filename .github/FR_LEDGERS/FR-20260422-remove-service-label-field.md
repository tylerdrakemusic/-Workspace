# FR-20260422-remove-service-label-field — Remove "Service/Label" Field from Password Generator Panel

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260422-remove-service-label-field
- **Title:** Remove "Service/Label" Field from Password Generator Panel
- **Type:** chore
- **Risk:** low
- **Projects:** ⊕Workspace
- **State:** TRIAGED
- **Branch:** pending
- **PRs:** pending
- **Cycle timer:** c6d6b6e9-2eae-4b4e-be8c-c394816442ea
- **Opened:** 2026-04-22
- **Last updated:** 2026-04-22
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. The "Service / Label" `<label>` element and its associated `<input>` are removed from the password generator panel HTML in `dashboard_portal.py`.
2. The generated `portal.html` no longer contains the "Service / Label" field when regenerated.
3. The password generator panel still renders and functions correctly (length, charset, generate button all intact).
4. No JavaScript references to the removed input field remain active (if any existed).

### Concurrency Notes
- Conflicts with: none
- Depends on: none

### Tyler's Original Request
> Remove the "Service/Label" field from the password generator panel in the portal (dashboard). The password generator panel in the workspace portal has a "Service/Label" field. Tyler says this field is not needed and wants it removed from the UI.

---

## Event Log

### 2026-04-22T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, triage complete → TRIAGED

**Details:**
- Scope: ⊕Workspace
- Source files identified: `f:\⊕Workspace\tools\dashboard_portal.py` (line 123) and `f:\⊕Workspace\reports\portal.html` (line 403)
- Acceptance criteria drafted (see Header)
- Concurrency check: clean

**Next:** awaiting Tyler: approve scope

---

## Artifacts

- **Perf runs:** c6d6b6e9-2eae-4b4e-be8c-c394816442ea — FR-20260422-remove-service-label-field cycle timer
