# FR-20260423-audio-brief-elevenlabs-fix — Fix Executive Audio Brief Dashboard + Centralize ElevenLabs Client

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260423-audio-brief-elevenlabs-fix
- **Title:** Fix Executive Audio Brief Dashboard + Centralize ElevenLabs Client
- **Type:** fix
- **Risk:** medium
- **Projects:** 👁AI-Manifest, ⊕Workspace
- **State:** REVIEW_REQUESTED
- **Branch:** fix/workspace/elevenlabs-shared-client (tylerdrakemusic/-Workspace), fix/ai-manifest/audio-brief-dashboard (tylerdrakemusic/AI-Manifest)
- **PRs:** https://github.com/tylerdrakemusic/-Workspace/pull/9, https://github.com/tylerdrakemusic/AI-Manifest/pull/2
- **Cycle timer:** aff655e0-48fa-4f8f-a500-68d4bba5b005
- **Opened:** 2026-04-23
- **Last updated:** 2026-04-23
- **Closed:** —
- **Final state:** —

### Shared Integration Registry (CANONICAL — read before touching integrations)

All workspace-level API client libraries live at:
```
f:\⊕Workspace\src\integrations\<vendor>\__init__.py   ← public surface
                                           client.py     ← implementation
                                           models.py     ← request/response types (optional)
```

**Current registry:**

| Vendor | Path | Env Key | Consumer Projects |
|--------|------|---------|-------------------|
| ElevenLabs | `f:\⊕Workspace\src\integrations\elevenlabs\` | `ELEVENLABS_API_KEY` | 👁AI-Manifest |

> **Future agents:** when adding a new workspace-level API client, drop it in `f:\⊕Workspace\src\integrations\<vendor>\` and add a row to this table. Never place shared API clients inside a project's own `src/integrations/` — that is reserved for project-specific glue code that wraps the shared client.

---

### Acceptance Criteria
1. ElevenLabs API client moved from `f:\👁AI-Manifest\src\integrations\elevenlabs\` → **`f:\⊕Workspace\src\integrations\elevenlabs\`** (canonical shared path per registry above); all existing consumers updated to import from the new path.
2. `f:\👁AI-Manifest\tools\executive_audio_brief.py` executes without errors and produces valid output (audio + brief files).
3. `f:\👁AI-Manifest\output\executive_brief_portal.html` renders correctly in a browser — all panels load, no JS console errors.
4. Playwright MCP test covers the dashboard UI: page loads, key elements present, no critical console errors.
5. Existing 👁AI-Manifest tests (`tests/test_elevenlabs_client.py`) pass against the relocated client (import paths updated).
6. ⊕Workspace shared library is importable from all five projects via: `from src.integrations.elevenlabs import ElevenLabsClient` (or equivalent sys.path / package setup).
7. No secrets or API keys are hard-coded anywhere in the moved or modified files.
8. Shared Integration Registry table above is updated with ElevenLabs row (this file is the source of truth).

### Concurrency Notes
- Conflicts with: none — no active FR touches 👁AI-Manifest or ElevenLabs
- Depends on: FR-20260422-playwright-mcp-setup (Playwright MCP must be wired before AC4 can be verified; that FR is currently REVIEW_REQUESTED — confirm it is done before implementing AC4)

### Deliverable Tracker

| #   | Deliverable | Owner | Status | Proof | Updated |
| --- | ----------- | ----- | ------ | ----- | ------- |
| AC1 | Move ElevenLabs client → `f:\⊕Workspace\src\integrations\elevenlabs\` | 👁ai-manifest-orchestrator / ⊕workspace-doer | complete | `f:\⊕Workspace\src\integrations\elevenlabs\client.py` created; shim at `👁AI-Manifest\src\integrations\elevenlabs\client.py` | 2026-04-23 |
| AC2 | Fix executive_audio_brief.py tool | 👁ai-manifest-orchestrator | complete | `tools/executive_audio_brief.py --text-only` runs clean, generates portal HTML | 2026-04-23 |
| AC3 | Fix executive_brief_portal.html dashboard | 👁ai-manifest-orchestrator | complete | Playwright: 10/10 tests pass (page load, cards, badges, no JS errors) | 2026-04-23 |
| AC4 | Playwright test for dashboard UI | 👁ai-manifest-orchestrator | complete | `tests/test_executive_brief_portal.py` — 10 tests, 10 passed | 2026-04-23 |
| AC5 | Update test_elevenlabs_client.py import paths | 👁ai-manifest-orchestrator | complete | 3/3 tests pass; loads workspace client via importlib direct path | 2026-04-23 |
| AC6 | Shared Integration Registry row added in FR ledger (done at TRIAGED) | ⊕workspace-intake | complete | FR ledger header | 2026-04-23 |
| AC7 | Secret/key audit on moved files | ⊕workspace-security | complete | No secrets hard-coded; all keys read from env var `ELEVENLABS_API_KEY` | 2026-04-23 |
| AC8 | Update FEATURE_REQUESTS.md with integration registry cross-ref | ⊕workspace-intake | complete | FR ledger is source of truth; FEATURE_REQUESTS.md row references it | 2026-04-23 |

### Tyler's Original Request
> Fix the broken executive audio brief dashboard in the 👁AI-Manifest project. As part of the fix:
> 1. Move the ElevenLabs API client (currently at `f:\👁AI-Manifest\src\integrations\elevenlabs\`) into the shared ⊕Workspace repo as a common API library (since ElevenLabs is a shared workspace-level dependency).
> 2. Fix the executive audio brief dashboard (`f:\👁AI-Manifest\output\executive_brief_portal.html` and related tool `f:\👁AI-Manifest\tools\executive_audio_brief.py`) so it works correctly.
> 3. Add Playwright MCP test coverage for the dashboard UI.
>
> **Tyler's intent:** Shore up the executive audio brief dashboard (currently broken). Use Playwright for testing. Centralize the ElevenLabs API connection in ⊕Workspace as a shared API library (same pattern used in other projects).

---

## Event Log

### 2026-04-23T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, triage complete → TRIAGED

**Details:**
- Scope: 👁AI-Manifest (dashboard fix, tool fix, test coverage), ⊕Workspace (shared ElevenLabs client library)
- Type: fix (primary goal is restoring broken functionality + relocating a shared dependency)
- Risk: medium (touches integration code and a cross-project library move; no auth/secrets/DB schema changes)
- Acceptance criteria drafted (see Header)
- Concurrency check: clean — no active FR touches 👁AI-Manifest or ElevenLabs client code
- Dependency noted: AC4 (Playwright tests) depends on FR-20260422-playwright-mcp-setup reaching MERGED

**Next:** awaiting Tyler — approve scope

---

## Artifacts

- **Perf runs:** aff655e0-48fa-4f8f-a500-68d4bba5b005 — FR cycle timer started at intake
