# FR-20260426-huggingface-image-integration — HuggingFace Image Generation Client — 👁AI-Manifest Integration

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260426-huggingface-image-integration
- **Title:** HuggingFace Image Generation Client — 👁AI-Manifest Integration
- **Type:** feature
- **Risk:** low
- **Projects:** 👁AI-Manifest
- **State:** TRIAGED
- **Branch:** pending
- **PRs:** pending
- **Cycle timer:** 27d9d807-6348-4687-9832-83e5974d2b19
- **Opened:** 2026-04-26
- **Last updated:** 2026-04-26
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. `src/integrations/huggingface_images/client.py` with `generate_image(prompt, size) -> Path` function
2. Uses `HF_TOKEN` from environment — never hardcoded
3. Saves image to `output/images/<sha256_hash>.png` with content-addressed filename
4. Returns `Path`; raises typed exception (`HuggingFaceImageError`) on API or model failure
5. Tests in `tests/test_huggingface_image_client.py` using mocked HTTP (no live API calls)

### Concurrency Notes
- Conflicts with: FR-20260426-dalle3-image-integration (both create `output/images/` dir — first writer creates it; idempotent `mkdir` makes this safe)
- Depends on: none

### Architecture Review

**Reviewer:** ⊕workspace-architecture-reviewer (inline, 2026-04-26)

**Impact assessment:**

| Dimension | Finding |
|-----------|---------|
| Pattern fit | Mirrors `elevenlabs/client.py` and the DALL-E FR pattern. Consistent integration layer. |
| New directory | `src/integrations/huggingface_images/` — needs `__init__.py`. Peers: `elevenlabs/`, `openai_images/`. |
| HF Inference API | Endpoint: `POST https://api-inference.huggingface.co/models/<model_id>`. Returns raw image bytes when `Content-Type: image/jpeg` or `image/png`. Binary response — no JSON unwrapping needed. |
| Model selection | `stabilityai/stable-diffusion-xl-base-1.0` is a solid default; cold-start latency on free tier can be 20–60s. Recommend `timeout=120` in httpx call. Model should be constructor-injectable (`model_id` param) for future swapping. |
| Size parameter | HF Inference API does not natively accept a `size` param in the same way DALL-E does — it's passed as JSON body `{ "inputs": prompt, "parameters": { "width": ..., "height": ... } }`. Implementor must parse `"1024x1024"` → width/height. |
| Credentials | `HF_TOKEN` is already documented in AI-Manifest env config. No new secret provisioning. |
| Output path | Same `output/images/` as DALL-E FR. `mkdir(parents=True, exist_ok=True)` in both clients makes this safe. |
| Error handling | HF API returns error JSON `{ "error": "..." }` with non-2xx status on model load failure or rate limit. Wrap in `HuggingFaceImageError`. |
| Risk | **Low.** Additive. No existing file modified except `.gitignore` (shared with DALL-E FR). |

**Blockers:** none.

**Recommendations:**
- Make `model_id` a constructor parameter defaulting to `"stabilityai/stable-diffusion-xl-base-1.0"` so tests and Lily Portrait can override.
- Parse `size` string `"WxH"` → `(width, height)` tuple for the `parameters` payload.
- Set `httpx` timeout to 120s minimum — SDXL cold-starts are slow.
- `.gitignore` addition for `output/images/` will be handled by FR-20260426-lily-portrait-executive-brief (AC7) — confirm no double-add.

### Deliverable Tracker

| #   | Deliverable | Owner | Status | Proof | Updated |
| --- | ----------- | ----- | ------ | ----- | ------- |
| AC1 | `src/integrations/huggingface_images/client.py` with `generate_image()` | orchestrator | not-started | — | — |
| AC2 | `HF_TOKEN` env-only credential use | orchestrator | not-started | — | — |
| AC3 | Content-addressed save to `output/images/<hash>.png` | orchestrator | not-started | — | — |
| AC4 | Typed `HuggingFaceImageError` on API/model failure | orchestrator | not-started | — | — |
| AC5 | `tests/test_huggingface_image_client.py` (mocked HTTP) | orchestrator | not-started | — | — |

### Tyler's Original Request
> Add a HuggingFace inference API image generation client at `src/integrations/huggingface_images/client.py`. Uses existing `HF_TOKEN` env var. Targets a photorealistic model (e.g. `stabilityai/stable-diffusion-xl-base-1.0` or best available). Same interface as DALL-E client: `generate_image(prompt, size) -> Path`.

---

## Event Log

### 2026-04-26T00:00:00 — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened with pre-confirmed scope → TRIAGED

**Details:**
- Scope: 👁AI-Manifest only
- Tyler confirmed scope directly (batch intake)
- Concurrency check: minor overlap with FR-20260426-dalle3-image-integration on `output/images/` dir — safe (idempotent mkdir); no file-level conflict
- Architecture review: completed inline (see Architecture Review section)
- Perf cycle started: 27d9d807-6348-4687-9832-83e5974d2b19

**Next:** pending — route to ⊕workspace-ci for branch creation once Tyler approves all 3 FRs

---

## Artifacts

- **Perf runs:** 27d9d807-6348-4687-9832-83e5974d2b19 — fr-cycle-FR-20260426-huggingface-image-integration
