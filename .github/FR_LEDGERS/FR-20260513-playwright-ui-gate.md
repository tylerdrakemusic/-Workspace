# FR-20260513-playwright-ui-gate — Add Playwright UI Validation Gate to Feature Flow

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260513-playwright-ui-gate
- **Title:** Add Playwright UI validation gate to the feature flow before review/merge
- **Type:** feature
- **Risk:** medium
- **Projects:** ⊕Workspace, ❤Music, 👁AI-Manifest, ⟨ψ⟩Quantum, ∞Life
- **State:** SOAKING
- **Branch:** `feature/playwright-ui-gate`
- **PRs:** [-Workspace#146](https://github.com/tylerdrakemusic/-Workspace/pull/146) (ffe6320) · [Life#26](https://github.com/tylerdrakemusic/Life/pull/26) (8f8f1de) · [Music#44](https://github.com/tylerdrakemusic/Music/pull/44) (89c00b9) · [Quantum#19](https://github.com/tylerdrakemusic/Quantum/pull/19) (ce15848) · [AI-Manifest#29](https://github.com/tylerdrakemusic/AI-Manifest/pull/29) (e4a71fc)
- **Cycle timer:** 8a4a4d81-45c0-4cc8-9b26-263b7d78dccf
- **Opened:** 2026-05-13
- **Last updated:** 2026-05-14
- **Merged at:** 2026-05-14
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria

1. `⊕workspace-reviewer.agent.md` has a new Gate (UI Validation) that: checks whether the PR diff touches any generated HTML/dashboard file, and if so, requires proof that Playwright ran against the artifact and passed.
2. `feature-request-flow.instructions.md` documents the Playwright validation requirement — orchestrators must run Playwright against any changed HTML output before marking a PR as `REVIEW_REQUESTED`.
3. Each of the 5 projects gains a Playwright test stub/skeleton for its primary HTML output file(s), runnable locally via `pytest -m playwright` with a documented invocation pattern.
4. The existing Playwright test in `👁AI-Manifest/tests/test_executive_brief_portal.py` is un-skipped locally (the `pytestmark = pytest.mark.skip` guard is gated behind a `CI` env var or removed, so it runs in local dev and `pytest -m playwright`).
5. CI browser setup (Chromium install step) is added to `.github/workflows/test.yml` in all 5 repos, controlled by a `PLAYWRIGHT_ENABLED` flag (default off; on = local/manual trigger), so CI does not regress due to 200MB Chromium binary on every run.
6. `⊕workspace-reviewer` review comment template includes a `UI Validation` row in the Gate Summary table.
7. A `playwright` pytest mark is registered in each project's `pytest.ini` so `pytest -m playwright` works without warnings.

### Concurrency Notes
- Conflicts with: none (no active FRs on reviewer agent or feature-flow instructions)
- Depends on: FR-20260422-playwright-mcp-setup (MERGED — Playwright MCP already installed; @playwright/mcp@0.0.70, Chromium at `C:\Users\tyler\AppData\Local\ms-playwright\chromium-1217`)

### Deliverable Tracker

| #   | Deliverable | Owner | Status | Proof | Updated |
| --- | ----------- | ----- | ------ | ----- | ------- |
| AC1 | Reviewer agent new UI Validation gate | ⊕workspace-overseer | not-started | — | — |
| AC2 | Feature-flow instructions updated | ⊕workspace-overseer | not-started | — | — |
| AC3 | Playwright test stubs in all 5 projects | ⊕workspace-overseer | not-started | — | — |
| AC4 | 👁AI-Manifest existing test un-skipped | 👁ai-manifest-orchestrator | not-started | — | — |
| AC5 | CI workflow updated with PLAYWRIGHT_ENABLED flag | ⊕workspace-ci | not-started | — | — |
| AC6 | Reviewer template includes UI Validation row | ⊕workspace-overseer | not-started | — | — |
| AC7 | `playwright` mark registered in all 5 pytest.ini files | ⊕workspace-overseer | not-started | — | — |

### Tyler's Original Request
> "I've noticed that in the feature flow, UI changes are rarely verified through playwright before handing off for review. They should be validated through playwright before proceeding towards review and merge."

---

## Event Log

### 2026-05-13T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened and triaged from user note → TRIAGED

**Details:**
- Codebase inspection confirmed: Playwright installed (FR-20260422-playwright-mcp-setup MERGED); @playwright/mcp@0.0.70 + Chromium available locally.
- 👁AI-Manifest already has `test_executive_brief_portal.py` with Playwright tests, but skipped via `pytestmark = pytest.mark.skip` (CI browser setup deferred note from FR-20260425 follow-up).
- 5 projects all have generated HTML dashboards/panels that lack Playwright validation: ⊕Workspace (portal.html + 8 other dashboards), ❤Music (band_management_panel.html, radio player), 👁AI-Manifest (executive_brief_portal.html), ⟨ψ⟩Quantum (benchmark_dashboard.html), ∞Life (biomarker/dashboard panels).
- No active FRs conflict with reviewer agent or feature-flow instructions files.
- Risk: medium — touches agent framework (reviewer + feature-flow) and requires CI browser setup, but no auth/secrets/health data involved.
- Cycle timer started: 8a4a4d81-45c0-4cc8-9b26-263b7d78dccf

**Next:** awaiting Tyler: approve scope

---

## Artifacts

- **Perf runs:** 8a4a4d81-45c0-4cc8-9b26-263b7d78dccf — FR-20260513-playwright-ui-gate cycle timer

---

### 2026-05-14T00:00:00Z — ⊕workspace-ci

**Event:** state-transition — MERGED → SOAKING

**Summary:** Tyler approved all 5 draft PRs. CI green on all. PRs undrafted and squash-merged. FR transitions to SOAKING.

**Details:**
- All 5 `test` CI checks completed with `success` before merge.
- PRs were in draft state — undrafted via API before merge.
- Squash merges completed:
  - `-Workspace#146` → `ffe6320d9a26fb6f1e4e8a6370c3730f7e645aca`
  - `Life#26` → `8f8f1dee47ecefbc51f293b6a1c08797dad1cf83`
  - `Music#44` → `89c00b9952c036cfa76f956672e5ea3dcec136c0`
  - `Quantum#19` → `ce15848ba5e51e89ba6f9a29c75e58295303a720`
  - `AI-Manifest#29` → `e4a71fcef2e9b1cfc084cce7bc93589eaa27223f`
- State machine: TRIAGED → MERGED → SOAKING (skipping intermediate states per Tyler's direct approval instruction)
- Cycle timer 8a4a4d81-45c0-4cc8-9b26-263b7d78dccf still open — to be closed at Tyler's post-soak signoff.

**Next:** Tyler signs off after soak period → ARCHIVED
