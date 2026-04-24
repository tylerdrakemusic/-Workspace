# FR-20260423-living-security-dashboard — Living Security Dashboard + Close Remediated SQL Injection Findings (IDs 7–11)

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260423-living-security-dashboard
- **Title:** Living Security Dashboard + Close Remediated SQL Injection Findings (IDs 7–11)
- **Type:** feature
- **Risk:** medium
- **Projects:** ⊕Workspace, ❤Music
- **State:** MERGED → CLOSED
- **Branch:** merged (feature/workspace/living-security-dashboard)
- **PRs:** https://github.com/tylerdrakemusic/-Workspace/pull/8 (merged)
- **Cycle timer:** 045e1d9f-5b50-4d43-b87d-43eeb174b822
- **Opened:** 2026-04-23
- **Last updated:** 2026-04-23
- **Closed:** 2026-04-23
- **Final state:** DONE

### Acceptance Criteria
1. Findings 7, 8, 9, 10, 11 are marked RESOLVED/CLOSED in the security tracking registry and/or security dashboard.
2. A scan script exists at `f:\⊕Workspace\src\utils\security_scan.py` that generates `security_dashboard.html`. The dashboard **auto-runs the scan on page load** (via an embedded `<script>` that calls a local endpoint or, more practically, the HTML is regenerated fresh each time it is opened via a launcher — e.g., a `.bat` / PowerShell wrapper that runs `security_scan.py` then opens the resulting HTML). No manual "run the script first" step required.
3. `security_dashboard.html` visually distinguishes OPEN (red) vs RESOLVED (green/strikethrough) findings.
4. Dashboard includes a "last scanned" timestamp reflecting the most recent scan run.
5. Verification step: opening the dashboard triggers a fresh scan and confirms findings 7–11 remain RESOLVED (no `execute(f"` in music_dashboard.py, migrate files archived with validated identifiers).
6. All changes committed and pushed; no regressions in existing security dashboard behavior.

### Concurrency Notes
- Conflicts with: none (no active FR touches security_dashboard.html or ❤Music source)
- Depends on: none

### Deliverable Tracker

| #   | Deliverable | Owner | Status | Proof | Updated |
| --- | ----------- | ----- | ------ | ----- | ------- |
| D1  | Close/mark RESOLVED findings 7–11 in security registry / dashboard | ❤Music orchestrator | not-started | — | — |
| D2  | Create `security_scan.py` scan script that regenerates dashboard HTML | ⊕workspace orchestrator | not-started | — | — |
| D3  | Create launcher (`open_security_dashboard.bat` or `.ps1`) that runs scan then opens HTML — scan fires on every open, no manual step | ⊕workspace orchestrator | not-started | — | — |
| D4  | Update `security_dashboard.html` to show OPEN vs RESOLVED with color/strikethrough + "last scanned" timestamp | ⊕workspace orchestrator | not-started | — | — |

### Tyler's Original Request
> Tyler has 5 HIGH SQL injection findings from a prior security scan that appear to already be remediated:
> - Finding 7: ❤Music/src/analysis/music_dashboard.py:1300
> - Finding 8: ❤Music/src/analysis/music_dashboard.py:1592
> - Finding 10: ❤Music/src/analysis/music_dashboard.py:930
> - Finding 9: ❤Music/tools/migrate_add_release_ops_columns.py:48
> - Finding 11: ❤Music/tools/migrate_add_full_hash_suite.py:54
>
> Verification confirms: no `execute(f"` patterns in music_dashboard.py; both migrate files are in `archive/` and use validated identifiers. These should be marked CLOSED/RESOLVED in the security tracking.
>
> Additionally, Tyler wants the security vulnerability dashboard at `f:\⊕Workspace\reports\security_dashboard.html` to become "living" — meaning it should reflect the current actual state of vulnerabilities rather than a static snapshot. Proposed approach: a re-runnable scan script that re-generates the dashboard HTML on demand, or an auto-refresh mechanism that re-scans on open. The dashboard should clearly show OPEN vs RESOLVED status per finding.

---

## Event Log

### 2026-04-23T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, triage complete → TRIAGED

**Details:**
- Scope: ⊕Workspace (security dashboard + scan script), ❤Music (close findings 7–11)
- Risk: medium — touches security dashboard, no auth/secrets/DB schema changes
- Acceptance criteria drafted (see Header)
- Concurrency check: clean — no active FRs overlap security_dashboard.html or ❤Music analysis files
- Cycle timer started: 045e1d9f-5b50-4d43-b87d-43eeb174b822

**Next:** awaiting Tyler: approve scope

---

### 2026-04-23T00:00:00Z — ⊕workspace-ci

**Event:** merged

**Summary:** PR #8 merged to main — FR cycle complete → MERGED → CLOSED

**Details:**
- PR: https://github.com/tylerdrakemusic/-Workspace/pull/8
- Merge method: merge commit
- Merge SHA: b41de811b7b3b2e114c2535b00bed0fe740b95be
- Branch `feature/workspace/living-security-dashboard` confirmed deleted (remote 404)
- Final state: DONE

---

## Artifacts

- **Perf runs:** 045e1d9f-5b50-4d43-b87d-43eeb174b822 — FR cycle timer started at intake
- **Merge SHA:** b41de811b7b3b2e114c2535b00bed0fe740b95be
