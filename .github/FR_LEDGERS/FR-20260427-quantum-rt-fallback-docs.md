# FR-20260427-quantum-rt-fallback-docs — quantum_rt: document secrets fallback paths explicitly

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260427-quantum-rt-fallback-docs
- **Title:** quantum_rt: document secrets fallback paths explicitly
- **Type:** chore
- **Risk:** low
- **Projects:** ⟨ψ⟩Quantum
- **State:** REVIEW_REQUESTED
- **Branch:** chore/quantum/quantum-rt-fallback-docs
- **PRs:** Quantum#5
- **Opened:** 2026-04-27
- **Last updated:** 2026-04-27
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria

1. Module-level docstring in `quantum_rt.py` explicitly documents both fallback paths:
   - (a) empty/missing cache → `secrets` from the very first bit request
   - (b) mid-stream exhaustion → `secrets` for all remaining reads
2. Inline comment on `_load_bitstream()`'s `return ""` branch clarifies the downstream effect (i.e., `_BitStream` will use `secrets` for every read).
3. The `_BitStream._next_bits()` `secrets` block has a comment marking it as intentional CSPRNG fallback, not a silent bug.

### Concurrency Notes

- Conflicts with: none
- Depends on: Quantum#3 (merged — canonical quantum_rt.py)

### Deliverable Tracker

| #   | Deliverable                                         | Owner                     | Status      | Proof | Updated    |
| --- | --------------------------------------------------- | ------------------------- | ----------- | ----- | ---------- |
| AC1 | Module docstring documents both fallback paths      | ⟨ψ⟩quantum-orchestrator   | completed   | commit 2c938bc | 2026-04-27 |
| AC2 | `_load_bitstream` return "" branch comment          | ⟨ψ⟩quantum-orchestrator   | completed   | commit 2c938bc | 2026-04-27 |
| AC3 | `_next_bits` secrets block comment                  | ⟨ψ⟩quantum-orchestrator   | completed   | commit 2c938bc | 2026-04-27 |

### Tyler's Original Request

> "quantum_rt was implemented, but perhaps it should have a fallback to legacy classical random if ty_string_cache is empty"

During intake interview, Tyler confirmed the existing `secrets` fallback already satisfies the intent. The deliverable is documentation only — no code behaviour change.

---

## Event Log

### 2026-04-27T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened via interview, scope confirmed → BRANCHED

**Details:**
- Tyler initially thought a code change was needed
- Intake showed the existing `secrets` fallback in `_load_bitstream` (returns "") and `_BitStream._next_bits`
- Tyler confirmed: docs-only chore, no API or behaviour change
- Branch `chore/quantum/quantum-rt-fallback-docs` created from Quantum main

**Next:** implement documentation changes → PR → review → merge

---

## Artifacts

- **PRs:** [Quantum#5](https://github.com/tylerdrakemusic/Quantum/pull/5)
- **Commits:** [2c938bc](https://github.com/tylerdrakemusic/Quantum/commit/2c938bc)
- **Reports / dashboards:** —
