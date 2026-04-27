# FR-20260426-lily-portrait-executive-brief — Lily Portrait — AI-generated persona image in Executive Audio Brief portal

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260426-lily-portrait-executive-brief
- **Title:** Lily Portrait — AI-generated persona image in Executive Audio Brief portal
- **Type:** feature
- **Risk:** low
- **Projects:** 👁AI-Manifest
- **State:** TRIAGED
- **Branch:** pending
- **PRs:** pending
- **Cycle timer:** ceb53233-01f6-4e51-ae3e-eceb3ad70dc7
- **Opened:** 2026-04-26
- **Last updated:** 2026-04-26
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. `src/utils/lily_portrait.py` — `get_daily_portrait() -> Path` with 24h cache check
2. Generation cascade: DALL-E 3 → HuggingFace → SVG silhouette placeholder (never fails hard)
3. Portrait displayed in `output/executive_brief_portal.html` as square image alongside audio player
4. Cache file at `output/images/lily_portrait_<YYYY-MM-DD>.png`; prior days cleaned up (keep last 3)
5. Daily outfit rotation: list of 7 descriptors cycling by day-of-week
6. Tests in `tests/test_lily_portrait.py`
7. `output/images/` added to `.gitignore` (generated assets, not tracked)

### Concurrency Notes
- Conflicts with: none (portal HTML is safe to modify — not currently under active FR)
- Depends on: FR-20260426-dalle3-image-integration, FR-20260426-huggingface-image-integration

### Architecture Review

**Reviewer:** ⊕workspace-architecture-reviewer (inline, 2026-04-26)

**Impact assessment:**

| Dimension | Finding |
|-----------|---------|
| Dependency sequencing | This FR **must land after** both image client FRs. Orchestrator must not start until branches for DALL-E and HuggingFace FRs are merged (or at minimum exist as worktrees the orchestrator can import from). |
| `src/utils/lily_portrait.py` placement | Correct scope — `src/utils/` is the right location for cross-integration orchestration utilities. Peers: `tokens.py`. |
| Cascade logic | `get_daily_portrait()` should try `DalleImageClient.generate_image(prompt)` → on `ImageGenerationError`, try `HuggingFaceImageClient.generate_image(prompt)` → on `HuggingFaceImageError`, write inline SVG silhouette and return that path. No exception should propagate to the caller. |
| Cache strategy | Date-keyed filename `lily_portrait_YYYY-MM-DD.png` is correct. Check: `Path(output_images / f"lily_portrait_{today}.png").exists()` before generating. Cleanup: glob `lily_portrait_*.png`, sort by name (ISO date = lexicographic sort), keep last 3, delete older. |
| Outfit rotation | `OUTFITS = [...]` list of 7 strings; index via `datetime.date.today().weekday()`. Lock this list in the module (not DB) — it's presentation config, not data. |
| Portal integration | `executive_brief_portal.html` currently has a `.audio-player` div. The portrait should be displayed in a new `.lily-portrait` element alongside (flex row) the audio player. The `<img src>` path must be relative and correct from `output/` — since portal is served from `output/`, `src="images/lily_portrait_YYYY-MM-DD.png"` works. The portal HTML is statically rendered by the Python tool — update `tools/executive_audio_brief.py` to inject the portrait path. |
| SVG fallback | Inline SVG silhouette embedded as `data:image/svg+xml;base64,...` avoids any missing-file 404. Define a small silhouette constant in `lily_portrait.py`. |
| `.gitignore` | Add `output/images/` to `👁AI-Manifest/.gitignore`. This AC covers the shared need from both image client FRs. |
| Test scope | `test_lily_portrait.py`: (1) cache hit returns existing file without calling clients; (2) DALL-E success path; (3) DALL-E fail → HF success; (4) both fail → SVG fallback; (5) cleanup keeps only 3 files. |
| Risk | **Low-medium.** Modifies `executive_brief_portal.html` and `tools/executive_audio_brief.py` (existing files). No DB changes. No new credentials. |

**Blockers:**
- **Hard blocker:** FR-20260426-dalle3-image-integration and FR-20260426-huggingface-image-integration must be merged before implementation can start on the cascade logic. Orchestrator may stub the clients behind an interface in parallel if desired.

**Recommendations:**
- Define a `PortraitClient` protocol/ABC in `lily_portrait.py` with a `generate_image(prompt: str) -> Path` method — lets both real clients and the test double satisfy the same interface without importing from the integration modules at module load time.
- The prompt base is locked per Tyler's spec — encode it as a constant `LILY_PROMPT_BASE` in the module.
- Portal injection: use a template comment `<!-- LILY_PORTRAIT -->` in the HTML and do string replacement in the brief generator rather than regex surgery on the HTML.

### Deliverable Tracker

| #   | Deliverable | Owner | Status | Proof | Updated |
| --- | ----------- | ----- | ------ | ----- | ------- |
| AC1 | `src/utils/lily_portrait.py` with `get_daily_portrait()` + 24h cache | orchestrator | not-started | — | — |
| AC2 | Generation cascade: DALL-E → HF → SVG (never fails hard) | orchestrator | not-started | — | — |
| AC3 | Portrait in `executive_brief_portal.html` as square image | orchestrator | not-started | — | — |
| AC4 | Cache file `lily_portrait_<date>.png`; keep last 3 | orchestrator | not-started | — | — |
| AC5 | 7-descriptor daily outfit rotation by weekday | orchestrator | not-started | — | — |
| AC6 | `tests/test_lily_portrait.py` (all cascade branches) | orchestrator | not-started | — | — |
| AC7 | `output/images/` added to `.gitignore` | orchestrator | not-started | — | — |

### Tyler's Original Request
> Integrate a daily-cached AI-generated portrait of "Lily" (photorealistic, casual-professional blend, velvety actress/secretary aesthetic) into the executive audio brief portal. Generation cascade: try DALL-E 3 first → fallback to HuggingFace → fallback to SVG silhouette placeholder. Cache: once per 24h, stored at `output/images/lily_portrait_<date>.png`. Portrait displayed as a square image in the brief portal alongside the audio player.
>
> **Prompt base (locked):** "A photorealistic portrait of an elegant, professional woman in her 30s, casual-professional attire, warm studio lighting, velvety soft-focus background, square crop, headshot style. Daily variation: [outfit/attire descriptor rotated daily]"

---

## Event Log

### 2026-04-26T00:00:00 — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened with pre-confirmed scope → TRIAGED

**Details:**
- Scope: 👁AI-Manifest only
- Tyler confirmed scope directly (batch intake)
- Concurrency check: clean — `executive_brief_portal.html` and `executive_audio_brief.py` not under any active FR
- Hard dependency noted: FR-20260426-dalle3-image-integration + FR-20260426-huggingface-image-integration must merge first
- Architecture review: completed inline (see Architecture Review section)
- Perf cycle started: ceb53233-01f6-4e51-ae3e-eceb3ad70dc7

**Next:** pending — route to ⊕workspace-ci for branch creation; implementation blocked until dependency FRs merge

---

## Artifacts

- **Perf runs:** ceb53233-01f6-4e51-ae3e-eceb3ad70dc7 — fr-cycle-FR-20260426-lily-portrait-executive-brief
