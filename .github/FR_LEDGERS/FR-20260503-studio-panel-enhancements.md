# FR-20260503-studio-panel-enhancements — Studio Panel Enhancements — new gear, favicon, tab order, equipment categories

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260503-studio-panel-enhancements
- **Title:** Studio Panel Enhancements — new gear, favicon, tab order, equipment categories
- **Type:** feature
- **Risk:** low
- **Projects:** ❤Music
- **State:** TRIAGED
- **Branch:** pending
- **PRs:** pending
- **Cycle timer:** a94bfaab-9628-47f0-bc29-08c0e6c91a87
- **Opened:** 2026-05-03
- **Last updated:** 2026-05-03
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria

1. **New gear — Aviator Cub amp:** `studio_equipment` row added with `model_key="AviatorCubU"`, `name` containing "Aviator Cub 50W 1x12"`, `studio="Personal Studio"`, `category="amplifiers"`, `purchased_from="Sweetwater"`, `condition="Used"`.
2. **New gear — Shure SM57:** `studio_equipment` row added with name "Shure SM57", `studio="Personal Studio"`, `category="microphones"`, owned by Tyler.
3. **Favicon — no 404:** Flask app at port 5065 serves `/favicon.ico` returning HTTP 200 (no more 404).
4. **Favicon — branding:** `/favicon.ico` serves the HyperThreat logo (`f:\❤Music\Brand\hyperthreat\hyperthreat-logo.png`) as a fallback; OR context-aware serving (Personal Studio tab uses Tyler personal brand asset from `f:\❤Music\Brand\`, HyperThreat tab uses hyperthreat logo).
5. **Tab order:** Studio panel renders tabs in order: Personal Studio → HyperThreat Studio → Mic Config (Mic Config is last).
6. **HyperThreat categories:** All HyperThreat Studio items currently categorized as "other" are re-categorized to proper pro-studio labels (e.g. "rack gear", "monitors", "preamps", "processors", "converters", "interfaces") based on `f:\❤Music\studio_master\studio_equipment.json` source data.
7. **Tests pass:** `f:\❤Music\tests\test_studio_panel.py` updated and green — covers favicon 200 response, tab order assertion, and DB presence of new gear rows.

### Concurrency Notes

- Conflicts with: none
- Depends on: FR-20260503-studio-equipment-panel (must be merged before branches can be created — this FR builds directly on the studio panel it delivered)

### Deliverable Tracker

| #   | Deliverable                         | Owner              | Status      | Proof | Updated    |
| --- | ----------------------------------- | ------------------ | ----------- | ----- | ---------- |
| AC1 | Aviator Cub amp DB row              | ❤music-orchestrator | not-started | —     | 2026-05-03 |
| AC2 | Shure SM57 DB row                   | ❤music-orchestrator | not-started | —     | 2026-05-03 |
| AC3 | Favicon 200 endpoint                | ❤music-orchestrator | not-started | —     | 2026-05-03 |
| AC4 | Favicon branding assets served      | ❤music-orchestrator | not-started | —     | 2026-05-03 |
| AC5 | Tab order: Personal → HyperThreat → Mic Config | ❤music-orchestrator | not-started | — | 2026-05-03 |
| AC6 | HyperThreat categories recategorized | ❤music-orchestrator | not-started | —    | 2026-05-03 |
| AC7 | Tests updated and passing           | ❤music-orchestrator | not-started | —     | 2026-05-03 |

### Tyler's Original Request

> File a new Feature Request for ❤Music studio panel enhancements. Tyler has approved and merged the studio equipment panel (FR-20260503-studio-equipment-panel) and now has the following follow-up requests:
>
> **FR Title:** Studio Panel Enhancements — new gear, favicon, tab order, equipment categories
>
> **Project scope:** ❤Music (`f:\❤Music\`) — `src/studio/studio_panel.py` and `heartmusic.db` `studio_equipment` table
>
> **Enhancement list (all in one FR):**
>
> 1. Add new personal studio equipment to DB: Aviator Cub 50W 1x12" Combo amplifier (model key `AviatorCubU`, Used from Sweetwater, Personal Studio, amplifiers) and Shure SM57 microphone (Personal Studio, microphones)
> 2. Favicon icons: fix 404 for `/favicon.ico`; serve HyperThreat logo as fallback; optionally context-aware per tab
> 3. Tab order: Personal Studio | HyperThreat Studio | Mic Config (Mic Config last)
> 4. HyperThreat equipment categories: re-categorize items currently in "other" using the JSON source (`studio_equipment.json`) for proper labels (rack gear, monitors, preamps, processors, converters, interfaces, etc.)
>
> Context: Flask on port 5065, heartmusic.db (SQLCipher, HEARTMUSIC_DB_KEY), Brand assets at `f:\❤Music\Brand\hyperthreat\hyperthreat-logo.png`, tests at `f:\❤Music\tests\test_studio_panel.py`

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-05-03T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, triage complete → TRIAGED

**Details:**
- Scope: ❤Music only (`src/studio/studio_panel.py`, `heartmusic.db` `studio_equipment` table, `Brand/` assets)
- Interview phase skipped — request was fully specified by Tyler with complete context
- 7 acceptance criteria drafted covering: 2 new DB gear rows, favicon endpoint, branding, tab order, recategorization, tests
- Concurrency check: clean — no file-level overlap with any active FR; soft dependency on FR-20260503-studio-equipment-panel (must merge first)
- Risk: low — no auth, no secrets, no new DB schema, no health data

**Next:** awaiting Tyler: approve scope

---

## Artifacts

<!-- APPEND-ONLY. Links to concrete evidence. -->

- **Perf runs:** a94bfaab-9628-47f0-bc29-08c0e6c91a87 — FR cycle timer started at intake (2026-05-03)
