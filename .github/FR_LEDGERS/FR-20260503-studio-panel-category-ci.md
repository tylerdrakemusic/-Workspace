# FR-20260503-studio-panel-category-ci

| Field | Value |
|-------|-------|
| **ID** | FR-20260503-studio-panel-category-ci |
| **Title** | Studio panel category normalization + CI server auto-restart on merge |
| **Type** | fix + chore |
| **Projects** | ❤Music, ⊕Workspace |
| **State** | TRIAGED |
| **Owner** | ⊕workspace-intake |
| **Opened** | 2026-05-03 |
| **Branches** | TBD |
| **PRs** | TBD |

## Motivation

Personal Studio shows duplicate category sections (`Amplifier`/`amplifiers`, `Microphone`/`microphones`) because the original migration JSON used Title Case singular while the new gear inserted via AC1/AC2 used `lowercase_underscore` plural. All Personal Studio categories need normalization to match the HyperThreat convention.

Additionally, after merging feature branches that touch registered Flask app files, the running server keeps serving the old code until manually killed — requiring Tyler to notice and restart it himself.

## Acceptance Criteria

### AC1 — Normalize Personal Studio DB categories
UPDATE all Personal Studio rows to `lowercase_underscore` plural:

| Old | New |
|-----|-----|
| `Amplifier` | `amplifiers` |
| `Microphone` | `microphones` |
| `Acoustic Guitar` | `acoustic_guitars` |
| `Bass Guitar` | `bass_guitars` |
| `Drums` | `drums` |
| `Guitar` | `guitars` |
| `Headphones` | `headphones` |
| `Interface` | `audio_interfaces` |
| `Keyboard` | `keyboards` |
| `MIDI Controller` | `midi_controllers` |
| `Monitor` | `monitors` |

### AC2 — Fix migration script
Update `f:\❤Music\src\studio\migrate_equipment_json.py` to insert Personal Studio categories using the normalized names so future re-runs don't reintroduce the old Title Case singular form.

### AC3 — CI agent auto-restart on merge
In `⊕workspace-ci` agent: after a branch is merged to main, inspect `portal_servers.json` to find registered servers whose source paths overlap with files changed in the merge. For each match:
1. Find the running process on the registered port.
2. Kill it gracefully.
3. Restart using the registered `cli` command.
4. Health-check (HTTP 200 on `/`) before reporting success.

Trigger: merge to main that touches any file under a path registered in `portal_servers.json` → `source_dir` (or infer from `cli`).

## Out of Scope
- Category validation on write routes (POST/PUT)
- UI category pickers / dropdowns
- Auto-restart for non-registered / ad-hoc servers
- Other portal servers not affected by the merge

## Risk
Low — data UPDATEs + agent behavior change, no schema changes.

## Dependencies
- `portal_servers.json` (already has port + cli per server)
- `migrate_equipment_json.py`

## State History
| Date | State | Note |
|------|-------|------|
| 2026-05-03 | OPEN | Filed by Tyler via overseer |
| 2026-05-03 | TRIAGED | Scope confirmed by Tyler |
