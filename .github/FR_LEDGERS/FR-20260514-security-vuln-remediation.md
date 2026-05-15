# FR-20260514-security-vuln-remediation

**Title:** Security Vulnerability Dashboard — Scanner Exclusion Fix + Full Remediation Sprint (1505 → 0 open)
**Type:** `security-fix + chore`
**State:** `BRANCHED`
**Opened:** 2026-05-14
**Updated:** 2026-05-14
**Owner:** ⊕workspace-overseer → route to ⊕workspace-ci

---

## Motivation

The security vulnerability dashboard currently shows 1505 open findings. Audit reveals:

| Category | Count | Disposition |
|----------|-------|-------------|
| `.venv` third-party packages | 1,397 | False positives — scanner hits installed pip packages |
| `.worktrees` duplicate checkout | 35 | False positives — mirrors of main checkout |
| **Real workspace code** | **73** | Require fix, accepted-with-note, or confirmed FP |

93% of the dashboard is noise from missing scanner exclusions. This FR remediates both the scanner configuration and all real findings.

---

## Affected Projects

All 5: ⊕Workspace, ∞Life, ❤Music, ⟨ψ⟩Quantum, 👁AI-Manifest

---

## Real Findings Breakdown (73 total)

| Severity | Count | Key Locations |
|----------|-------|---------------|
| Critical | 3 | `∞Life/tools/mfp_probe.py` (hardcoded MFP credential); 2 test files with fake API key strings |
| High | 38 | SQL f-strings in `init_db.py` across all 5 projects; `shell=True` in `dashboard_portal.py` + `fr_signoff_handler.py`; `eval`/`exec` in scan pattern constants (likely FPs); `exec` in `👁AI-Manifest/tools/manifest/` |
| Low | 32 | HTTP URLs in test files (Ollama localhost), source HTML generators, portrait utilities |

---

## Remediation Plan

### Phase 1 — Scanner Fix (⊕Workspace)
- Exclude `.venv/` and `.worktrees/` from `SCAN_ROOTS` in `tools/security_dashboard.py`
- Add FP patterns for: `eval`/`exec` inside regex string literals (scan pattern definitions), `http://localhost:*` URL variants

### Phase 2 — DB Bulk Cleanup (⊕Workspace)
- Bulk-mark 1,432 existing `.venv` + `.worktrees` entries as `false_positive` in `workspace.db`
- Re-run scanner; dashboard should show ≤73 open

### Phase 3 — Real Finding Triage (all 5 projects)
- **Critical → fix or FP:**
  - `∞Life/tools/mfp_probe.py` line 5: replace hardcoded credential with `os.environ` lookup
  - `⊕Workspace/tests/test_dalle3_client.py` line 50 + `test_huggingface_image_client.py` line 46: review — if fake test keys, mark `false_positive` and add FP pattern
- **High SQL f-strings → fix or accepted:**
  - `init_db.py` in ⊕Workspace, ∞Life, ❤Music, ⟨ψ⟩Quantum, 👁AI-Manifest: use parameterised queries or table-name allowlist
  - `∞Life/tmp/`, `❤Music/tools/archive/`, migration scripts: mark `accepted` (one-time scripts, internal-only, no user input)
- **High shell=True → fix or accepted:**
  - `⊕Workspace/tools/dashboard_portal.py` line 322: use list args instead of string + `shell=True`
  - `⊕Workspace/tools/fr_signoff_handler.py` line 19: same
- **High eval/exec in `security_dashboard.py`:** inspect — scan pattern string literals → `false_positive`
- **High exec in `👁AI-Manifest/tools/manifest/`:** review; script bootstrap pattern → `accepted` with note or fix
- **Low HTTP URLs:** `localhost:*` → `false_positive`; CDN/static links in HTML generators → `accepted`; upgradeable links → fix to `https://`

---

## Acceptance Criteria

1. Scanner excludes `.venv/` and `.worktrees/` on all future runs — verified by re-running `--scan` and confirming 0 new `.venv` findings
2. 1,432 DB entries bulk-marked `false_positive`; dashboard re-renders correctly
3. All 3 critical findings resolved (fixed or confirmed FP with note)
4. All 38 high findings resolved (fixed, accepted with notes, or FP)
5. All 32 low findings triaged (accepted or fixed)
6. Dashboard shows **0 open** after full sprint; all findings have a status + override note
7. CI green across all 5 affected repos

---

## Risk

**Medium**
- Modifying `init_db.py` in ∞Life touches health data DB layer — requires test pass before merge
- `mfp_probe.py` credential removal could break MFP sync if env var not pre-set — verify env var exists before removing
- Bulk DB write is a reversible UPDATE (status field only)

---

## Out of Scope

- Third-party package vulnerabilities inside `.venv` (dependency upgrade sprint = separate FR)
- Security findings in non-Python files (HTML, JSON, markdown)

---

## Branch Plan

| Repo | Branch |
|------|--------|
| ⊕Workspace | `fix/workspace/fr-20260514-security-vuln-remediation` |
| ∞Life | `fix/life/fr-20260514-security-vuln-remediation` |
| ❤Music | `fix/music/fr-20260514-security-vuln-remediation` |
| ⟨ψ⟩Quantum | `fix/quantum/fr-20260514-security-vuln-remediation` |
| 👁AI-Manifest | `fix/ai-manifest/fr-20260514-security-vuln-remediation` |

---

## Perf Run

`f35e9f50-625b-4129-89cf-7b098d32155c`

---

## Changelog

| Date | State | Note |
|------|-------|------|
| 2026-05-14 | OPEN | Tyler filed via ⊕workspace-intake |
| 2026-05-14 | TRIAGED | Scope confirmed by Tyler; 1505 findings analyzed; 73 real, 1432 FP |
| 2026-05-14 | BRANCHED | All 5 fix branches created and pushed; draft PRs opened by ⊕workspace-ci |
