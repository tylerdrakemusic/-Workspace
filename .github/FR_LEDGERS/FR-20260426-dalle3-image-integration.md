# FR-20260426-dalle3-image-integration — DALL-E 3 Image Generation Client — 👁AI-Manifest Integration

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260426-dalle3-image-integration
- **Title:** DALL-E 3 Image Generation Client — 👁AI-Manifest Integration
- **Type:** feature
- **Risk:** low
- **Projects:** 👁AI-Manifest
- **State:** TRIAGED
- **Branch:** pending
- **PRs:** pending
- **Cycle timer:** b9a7a9a9-b18c-4e72-b922-b5c6220e509e
- **Opened:** 2026-04-26
- **Last updated:** 2026-04-26
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. `src/integrations/openai_images/client.py` with `generate_image(prompt, size, quality) -> Path` function
2. Uses `OPENAPI_TOKEN` from environment — never hardcoded
3. Saves image to `output/images/<sha256_hash>.png` with content-addressed filename
4. Returns `Path` to saved file; raises typed exception (`ImageGenerationError`) on API failure
5. Tests in `tests/test_dalle3_client.py` using mocked HTTP (no live API calls)

### Concurrency Notes
- Conflicts with: none
- Depends on: none

### Architecture Review

**Reviewer:** ⊕workspace-architecture-reviewer (inline, 2026-04-26)

**Impact assessment:**

| Dimension | Finding |
|-----------|---------|
| Pattern fit | Mirrors existing `src/integrations/elevenlabs/client.py` pattern exactly — thin wrapper over httpx, env-key resolution in `__init__`, typed exception class. No deviation needed. |
| New directory | `src/integrations/openai_images/` — consistent with `elevenlabs/` peer. Needs `__init__.py`. |
| Credentials | `OPENAPI_TOKEN` already in env for AI-Manifest (same key used by ElevenLabs portal generation flow). No new secret provisioning. |
| Output path | `output/images/` does not exist yet. Utility must `mkdir(parents=True, exist_ok=True)` on first write. Add `output/images/` to `.gitignore`. |
| Content-addressed filename | SHA-256 of raw PNG bytes is the right approach — deterministic, collision-resistant, idempotent re-saves. |
| Error handling | Typed `ImageGenerationError(Exception)` defined in the module; wrap all `httpx` errors + non-2xx responses. |
| Test isolation | Mock `httpx.post` — no network required. Fixture returns synthetic PNG bytes. |
| Risk | **Low.** Additive. No existing file modified except `.gitignore`. |

**Blockers:** none.

**Recommendations:**
- Define `ImageGenerationError` in `src/integrations/openai_images/client.py` (not a shared exceptions module) to keep the integration self-contained.
- Accept `size: str = "1024x1024"` and `quality: str = "standard"` as kwargs matching OpenAI's API vocabulary.
- The OpenAI images endpoint is `POST https://api.openai.com/v1/images/generations` — confirm `OPENAPI_TOKEN` is an OpenAI key (not a generic API token name collision).

### Deliverable Tracker

| #   | Deliverable | Owner | Status | Proof | Updated |
| --- | ----------- | ----- | ------ | ----- | ------- |
| AC1 | `src/integrations/openai_images/client.py` with `generate_image()` | orchestrator | not-started | — | — |
| AC2 | `OPENAPI_TOKEN` env-only credential use | orchestrator | not-started | — | — |
| AC3 | Content-addressed save to `output/images/<hash>.png` | orchestrator | not-started | — | — |
| AC4 | Typed `ImageGenerationError` on API failure | orchestrator | not-started | — | — |
| AC5 | `tests/test_dalle3_client.py` (mocked HTTP) | orchestrator | not-started | — | — |

### Tyler's Original Request
> Add a DALL-E 3 image generation client wrapper at `src/integrations/openai_images/client.py`. Uses existing `OPENAPI_TOKEN` env var. Exposes `generate_image(prompt, size, quality) -> Path` — downloads and saves to `output/images/`. No new credentials needed.

---

## Event Log

### 2026-04-26T00:00:00 — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened with pre-confirmed scope → TRIAGED

**Details:**
- Scope: 👁AI-Manifest only
- Tyler confirmed scope directly (batch intake)
- Concurrency check: clean — no active FRs touching `src/integrations/` in AI-Manifest
- Architecture review: completed inline (see Architecture Review section)
- Perf cycle started: b9a7a9a9-b18c-4e72-b922-b5c6220e509e

**Next:** pending — route to ⊕workspace-ci for branch creation once Tyler approves all 3 FRs

---

## Artifacts

- **Perf runs:** b9a7a9a9-b18c-4e72-b922-b5c6220e509e — fr-cycle-FR-20260426-dalle3-image-integration
