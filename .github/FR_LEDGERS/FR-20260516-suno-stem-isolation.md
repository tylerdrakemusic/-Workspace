# FR-20260516-suno-stem-isolation — Suno Stem Isolation via Demucs

## Header

- **FR ID:** FR-20260516-suno-stem-isolation
- **Title:** Suno stem isolation CLI via Demucs htdemucs_6s
- **Type:** feature
- **Risk:** low
- **Projects:** ❤Music
- **State:** MERGED
- **Branch:** feature/music/fr-20260516-suno-stem-isolation
- **PRs:** [Music#52](https://github.com/tylerdrakemusic/Music/pull/52)
- **Cycle timer:** perf_cli run "FR-20260516-suno-stem-isolation-impl"
- **Opened:** 2026-05-16
- **Last updated:** 2026-05-16
- **Merged at:** 2026-05-16
- **Signed off at:** 2026-05-16
- **Closed:** 2026-05-16
- **Final state:** MERGED

### Acceptance Criteria
1. `tools/stem_isolate.py` exists and implements the Demucs-based stem isolation CLI
2. Filename→instrument detection covers all 7 Marigolds stems correctly
3. Unit tests pass (`pytest tests/test_stem_isolate.py`)
4. `demucs` added to `requirements.txt`
5. `--device auto` tries CUDA then falls back to CPU
6. `.demucs_tmp/` cleaned up after each file

### Concurrency Notes
- Conflicts with: none
- Depends on: none

### Deliverable Tracker

| #   | Deliverable                                    | Owner               | Status | Proof                               | Updated    |
| --- | ---------------------------------------------- | ------------------- | ------ | ----------------------------------- | ---------- |
| AC1 | `tools/stem_isolate.py` CLI implemented        | ❤music-orchestrator | done   | `f:\❤Music\tools\stem_isolate.py`  | 2026-05-16 |
| AC2 | Filename→instrument detection for all 7 stems  | ❤music-orchestrator | done   | 13/13 pytest passed                 | 2026-05-16 |
| AC3 | `tests/test_stem_isolate.py` passing           | ❤music-orchestrator | done   | 13 passed in 0.13s                  | 2026-05-16 |
| AC4 | `demucs` added to `requirements.txt`           | ❤music-orchestrator | done   | `f:\❤Music\requirements.txt`       | 2026-05-16 |
| AC5 | CUDA→CPU auto-fallback in `_run_demucs()`      | ❤music-orchestrator | done   | see `tools/stem_isolate.py` L68-80  | 2026-05-16 |
| AC6 | `.demucs_tmp/` cleaned up after each file      | ❤music-orchestrator | done   | see `_cleanup()` called per-file    | 2026-05-16 |

### Tyler's Original Request
> Implement FR-20260516-suno-stem-isolation on branch `feature/music/fr-20260516-suno-stem-isolation`.
> Build `tools/stem_isolate.py` — a CLI that takes a folder of Suno-exported stem WAV files,
> runs Demucs htdemucs_6s on each, and extracts the target instrument stem to `<input_folder>/isolated/`.

---

## Event Log

### 2026-05-16T00:00:00Z — ❤music-orchestrator

**Event:** implementation-complete

**Summary:** All 6 acceptance criteria satisfied. 13/13 unit tests pass.

**Details:**
- Created `f:\❤Music\tools\stem_isolate.py` — full CLI with argparse, `detect_instrument()`, CUDA→CPU fallback, per-file cleanup
- Created `f:\❤Music\tests\test_stem_isolate.py` — 13 parametrized + targeted tests, all passing
- Appended `demucs` to `f:\❤Music\requirements.txt`
- Updated `FEATURE_REQUESTS.md`: BRANCHED → IN_PROGRESS → REVIEW_REQUESTED
- Committed to `feature/music/fr-20260516-suno-stem-isolation`

**Proof artifacts:**
- pytest: `13 passed in 0.13s`
- Files: `tools/stem_isolate.py`, `tests/test_stem_isolate.py`, `requirements.txt`
