# Heavy Automated Review: FR-20260815-qec-security-maintenance

**Decision:** REQUEST_CHANGES
**Review tier:** Heavy
**Review state:** REVIEW_REQUESTED
**Reviewed worktree:** `f:\worktrees\FR-20260815-qec-security-maintenance\workspace`
**Reviewed base:** `70d8832cdd0e082301c7129f0ff621a84494ee4a`

## Findings

### Critical: Integrity manifest is bound to the temporary worktree path

`.github/!!☾⛧security/agent-manifest.json` contains 88 absolute keys under
`F:\worktrees\FR-20260815-qec-security-maintenance\workspace`, while the
canonical checkout is `F:\⊕Workspace`. The unchanged
`update_manifest.py` uses `str(path)` as each manifest key, so regenerating or
verifying from the canonical checkout will produce canonical-path keys and
report all worktree entries as missing plus all canonical entries as new.
This makes the integrity baseline fail immediately after merge and defeats
the security agent's first gate. Generate stable repository-relative keys (or
normalize the repository root) and add a checkout-path regression test.

### High: Temporary QA and dependency-audit artifacts remain in `tmp/`

The worktree currently contains `tmp/pip-audit-qa.json`,
`tmp/test_qec_security_maintenance_regressions.py`,
`tmp/test_scanner_output_path.py`, and `tmp/security_scan_results.json`.
They are ignored by git, but the reviewer hard gate explicitly requires
ephemeral PR artifacts to be removed from `tmp/` before merge. The regression
tests and scan output should be promoted to tracked test/proof locations when
they are intended to be durable, otherwise remove them before re-review.

### Required follow-up: pip-audit evidence is separated, but not durably
### tracked and its counts disagree

The FR event history explicitly says the shared `C:\G` pip-audit findings are
excluded from this FR and remain a separate remediation item, so they were not
silently treated as fixed. However, the only local evidence is the ignored
`tmp/pip-audit-qa.json`, whose first line reports 380 vulnerabilities in 66
packages, while the QA event records 386 findings across 66 packages. No
follow-up FR, issue, artifact, or backlog identifier is recorded. Preserve the
scope separation, but create a durable follow-up reference and reconcile the
count/source before closing this review item.

## Gate Results

| Gate | Result | Evidence |
|---|---|---|
| Scope conformance | PASS | Exactly five tracked authorized files are modified; no dependency remediation is included. |
| Security | REQUEST_CHANGES | Integrity manifest is checkout-path dependent; no secret was found in the reviewed diff. |
| Alignment | PASS | Workspace-root paths, QEC constant reference, scanner roots, and agent references match the intended workspace. |
| Architecture diagrams | PASS | Ledger architecture review PASS and recorded architecture impact artifact; no new topology node or integration boundary. |
| Worktree path audit | PASS | No committed `.worktrees/` path was found in the five-file diff. |
| tmp cleanliness | FAIL | Four ephemeral/QA artifacts remain in the worktree `tmp/` directory. |
| Tests | PASS with evidence gap | Ledger records 20 focused tests passed and 3 skipped; QEC self-test independently passed 14/14. No tracked regression test is present in the five-file diff. |
| Functional QA | PASS | Ledger contains `FUNCTIONAL_QA PASS` after remediation. |
| Proof | PASS with follow-up gap | Architecture proof is recorded; pip-audit evidence is only in ignored tmp and has a count mismatch. |
| Demo | PASS | CLI QEC self-test output and scanner execution are recorded in QA events. |
| UI validation | N/A | No HTML or UI file changed. |

## Validation Performed

- Read the complete five-file diff and the full FR event/artifact records.
- Ran QEC self-test with a nonexistent cache override: 14 passed, 0 failed.
- Confirmed scanner output path resolution points to the workspace root `tmp/`.
- Confirmed the proposed manifest has 88 worktree-prefixed keys and the
  generator derives keys from absolute paths.
- Confirmed `git diff --check` passes.
- Confirmed no PR is recorded for this FR, so no GitHub review was posted.

## Required Changes Before Re-review

1. Make integrity-manifest keys stable across worktrees/checkouts and test
   verification from the canonical workspace path.
2. Remove or promote the four temporary QA/audit artifacts.
3. Record a durable follow-up reference for the shared `C:\G` pip-audit
   backlog and reconcile the 380-versus-386 count discrepancy.

No FR state transition was performed by this review.

## Final Heavy Review Rerun — 2026-08-15

**Decision:** APPROVE

The prior findings are resolved and the reviewed worktree is clean:

- Portable manifest verification passed: all 88 entries match, with repository-relative keys.
- QEC self-test passed: 14 tests passed, 0 failed.
- Manifest, QEC cache, security-agent, scanner roots, and scanner output paths are checkout/workspace-correct; no stale operative `f:\.github` or `f:\executedcode` references remain in the implementation surface.
- The focused manifest portability suite passed: 2 tests passed.
- `tmp/` contains no files, including no residual `__pycache__` artifacts.
- Shared `C:\G` pip-audit remediation is durably tracked by `FR-20260815-shared-python-dependency-remediation` and remains out of scope.
- Functional QA rerun is recorded as PASS, proof is recorded as 8/8, and the architecture rerun is PASS.
- The complete scope remains the six intended tracked implementation files plus the tracked portability test and the two review proof artifacts; no dependency/configuration changes, `.worktrees/` paths, or unrelated source changes are present.

**Gate decision:** all heavy review gates pass. No FR state transition, commit, push, merge, or GitHub review was performed.