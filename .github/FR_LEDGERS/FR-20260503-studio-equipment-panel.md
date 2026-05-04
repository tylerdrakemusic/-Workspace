# FR-20260503-studio-equipment-panel — Studio Equipment Panel with CRUD and Mic Config Print

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260503-studio-equipment-panel
- **Title:** Studio Equipment Panel — equipment CRUD + mic config print button
- **Type:** feature
- **Risk:** medium
- **Projects:** ❤Music (primary: Flask app + DB migration), ⊕Workspace (portal pane-5 upgrade)
- **State:** REVIEW_REQUESTED
- **Branch:** feature/heart-music/studio-equipment-panel (❤Music), feature/workspace/studio-equipment-panel (⊕Workspace)
- **PRs:** https://github.com/tylerdrakemusic/Music/pull/28 (❤Music), https://github.com/tylerdrakemusic/-Workspace/pull/89 (⊕Workspace)
- **Cycle timer:** 1f5b4474-59e9-45d2-adf3-6ba2b34b6c35
- **Opened:** 2026-05-03
- **Last updated:** 2026-05-03
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. New Flask app `src/studio/studio_panel.py` on port 5060 serving the Studio Equipment Panel
2. `heartmusic.db` — new `studio_equipment` table, migrated from `studio_equipment.json` (columns: id, studio_name, category, label, spec_json, status, created_at, updated_at)
3. Panel has selectable studio tabs: **Personal Studio** and **HyperThreat Studio**
4. Equipment displayed grouped by category (Microphones, Interfaces, Guitars, Pedals, Amps, etc.)
5. CRUD: Add item (modal form), Edit item via modal, Delete with confirmation — all persist to `heartmusic.db`
6. **Mic Config tab/button** in the panel nav → renders `studio/mic_config_template.html` content with a **Print** button (`window.print()`)
7. `❤Music/dashboard.json` updated with new `studio-panel` entry (type: flask_app, port 5060)
8. `⊕Workspace/reports/portal.html` pane-5 upgraded from static iframe → live Flask app URL (`http://localhost:5060`)
9. DB migration script at `❤Music/src/studio/migrate_equipment_json.py` (reads `studio_master/studio_equipment.json`, populates `studio_equipment` table)

### Out of Scope
- Equipment photos or images
- Price tracking or depreciation
- Warranty date tracking
- Mic configuration rows 17–32 (already out-of-scope from FR-20260503-mic-config-template)
- Export back to JSON

### Concurrency Notes
- Conflicts with: none currently active
- Depends on: FR-20260503-mic-config-template (MERGED — pane-5 established, `studio/mic_config_template.html` exists)

### Deliverable Tracker

| #   | Deliverable | Owner | Status | Proof | Updated |
| --- | ----------- | ----- | ------ | ----- | ------- |
| AC1 | `src/studio/studio_panel.py` Flask app on port 5060 | ❤music-orchestrator | done | commit 18ac898 | 2026-05-03 |
| AC2 | `heartmusic.db` `studio_equipment` table schema + test coverage | ❤music-orchestrator | done | commit 18ac898 | 2026-05-03 |
| AC3 | Panel studio-selector tabs (Personal Studio / HyperThreat Studio) | ❤music-orchestrator | done | commit 18ac898 | 2026-05-03 |
| AC4 | Category-grouped equipment display | ❤music-orchestrator | done | commit 18ac898 | 2026-05-03 |
| AC5 | CRUD modals (Add / Edit / Delete) writing to DB | ❤music-orchestrator | done | commit 18ac898 | 2026-05-03 |
| AC6 | Mic Config tab + Print button (`window.print()`) | ❤music-orchestrator | done | commit 18ac898 | 2026-05-03 |
| AC7 | `❤Music/dashboard.json` studio-panel entry | ❤music-orchestrator | done | commit 18ac898 | 2026-05-03 |
| AC8 | `portal.html` pane-5 → Flask URL | ⊕workspace-doer | done | commit e57eb77 | 2026-05-03 |
| AC9 | `migrate_equipment_json.py` migration script | ❤music-orchestrator | done | commit 18ac898 | 2026-05-03 |

### Tyler's Original Request
> I'd like to enhance the studio panel, the mic configuration should just be a simple tab or button that takes you to print the .html file. The studio equipment json file is the current data I have for my own studio and Hyperthreat's equipment as well. I think it's important for the project to have awareness of this equipment, equipment may be sold or replaced in the future and new equipment may be added so I would probably need functionality in manipulating the data through the panel.

---

## Event Log

### 2026-05-03T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened via grill-me intake, triage complete → TRIAGED

**Details:**
- Grill-me interview completed (5 questions answered)
- Scope confirmed: ❤Music (primary) + ⊕Workspace (portal pane)
- Risk: medium — new Flask app, new DB table, portal pane upgrade
- Builds on FR-20260503-mic-config-template (MERGED): pane-5 and mic_config_template.html already exist
- CRUD persistence: heartmusic.db (Tyler's choice)
- Panel type: Flask app
- Studio scope: both Personal Studio and HyperThreat Studio as selectable tabs
- Mic config: Print button via window.print() inside the pane
- Concurrency: no conflicts

### 2026-05-03T01:00:00Z — ⊕workspace-ci

**Event:** state-transition

**Summary:** Branches created, draft PRs opened → BRANCHED

**Details:**
- ❤Music branch: `feature/heart-music/studio-equipment-panel`
- ⊕Workspace branch: `feature/workspace/studio-equipment-panel`
- Draft PR ❤Music: https://github.com/tylerdrakemusic/Music/pull/28
- Draft PR ⊕Workspace: https://github.com/tylerdrakemusic/-Workspace/pull/89

### 2026-05-03T02:00:00Z — ❤music-orchestrator + ⊕workspace-doer

**Event:** state-transition

**Summary:** Implementation complete → REVIEW_REQUESTED

**Details:**
- AC1–AC7, AC9: `src/studio/studio_panel.py`, `src/studio/migrate_equipment_json.py`, `dashboard.json` updated — commit `18ac898` on `feature/heart-music/studio-equipment-panel`
- 33 equipment rows migrated to `heartmusic.db` `studio_equipment` table
- Tests: 6 passed
- AC8: `portal.html` pane-5 upgraded to Flask URL — commit `e57eb77` on `feature/workspace/studio-equipment-panel`

**Next:** Tyler approves PRs Music#28 + -Workspace#89

---

## Artifacts

- **Perf runs:** b6b2f8b6-3a0e-4c3a-a595-e4049b073f4e — intake session
- **Perf runs:** 1f5b4474-59e9-45d2-adf3-6ba2b34b6c35 — FR cycle timer (open)
- **Perf runs:** 22741470-f8dd-4943-8bca-ba242d321f10 — implementation run
- **Source data:** `f:\❤Music\studio_master\studio_equipment.json`
- **Existing asset:** `f:\❤Music\studio\mic_config_template.html`
- **Flask app:** `f:\❤Music\src\studio\studio_panel.py`
- **Migration:** `f:\❤Music\src\studio\migrate_equipment_json.py`
- **Tests:** `f:\❤Music\tests\test_studio_panel.py` — 6 passed
- **Commits:** `18ac898` — feat: Studio Equipment Panel (❤Music), `e57eb77` — feat: portal pane-5 upgrade (⊕Workspace)
- **PRs:** https://github.com/tylerdrakemusic/Music/pull/28, https://github.com/tylerdrakemusic/-Workspace/pull/89
