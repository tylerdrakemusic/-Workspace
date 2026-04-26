# FR-20260426-biomarker-external-portal — External Portal Integration for Biomarker Health Panel

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260426-biomarker-external-portal
- **Title:** External Portal Integration for Biomarker Health Panel
- **Type:** feature
- **Risk:** high (touches ∞Life health DB — real medical/genomic data; private repo)
- **Projects:** ∞Life
- **State:** BRANCHED
- **Branch:** feature/life/biomarker-external-portal
- **PRs:** https://github.com/tylerdrakemusic/Life/pull/4
- **Cycle timer:** 6e53c098-c290-4e30-a6b0-144ad0774c8e
- **Opened:** 2026-04-26
- **Last updated:** 2026-04-26T00:00:00Z (branched)
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria

1. **Portal link accessible** — The athenahealth patient portal URL (`https://9821-12.portal.athenahealth.com/`) is surfaced as a clickable link in the ∞Life biomarker health panel UI/dashboard (no credentials or session tokens stored anywhere).
2. **Medications table populated** — All 9 current medications are inserted into `infinitelife.db` with correct dosage, form, route, and active status. A migration script or seed is committed so the data is reproducible.
3. **Lab results ingested** — The 12/18/2025 lab results (HbA1c + full CMP) are stored in `infinitelife.db` under the existing or a new `lab_results`/`biomarkers` schema. No static HTML files used as the source of truth.
4. **Abnormal flag preserved** — Creatinine (1.28 mg/dL, HIGH) is tagged with an out-of-range flag so the panel and any query can surface it immediately.
5. **Provider note stored** — The provider note from John Waters, NP at Burrows Internal Medicine (dated 12/18/2025) is stored in the DB alongside the lab results batch.
6. **Panel UI updated** — The biomarker health panel renders the portal link, current medications list, and most-recent lab results from the DB (not from hardcoded values).
7. **No health data in public repos** — Confirmed via gitignore audit that no lab values, medication data, or portal URLs land in any public-facing repo or commit.

### Concurrency Notes

- Conflicts with: none
- Depends on: none (∞Life DB is already restored per FR-20260424-infinitelife-db-restore — CLOSED)

### Deliverable Tracker

| #   | Deliverable                                    | Owner                 | Status      | Proof | Updated    |
| --- | ---------------------------------------------- | --------------------- | ----------- | ----- | ---------- |
| AC1 | Portal link in biomarker panel UI              | ∞life-orchestrator    | not-started | —     | 2026-04-26 |
| AC2 | 9 medications inserted into infinitelife.db    | ∞life-orchestrator    | not-started | —     | 2026-04-26 |
| AC3 | 12/18/2025 lab results ingested to DB          | ∞life-orchestrator    | not-started | —     | 2026-04-26 |
| AC4 | Creatinine HIGH flag preserved in DB           | ∞life-orchestrator    | not-started | —     | 2026-04-26 |
| AC5 | Provider note stored alongside lab batch       | ∞life-orchestrator    | not-started | —     | 2026-04-26 |
| AC6 | Biomarker panel reads from DB, not static HTML | ∞life-orchestrator    | not-started | —     | 2026-04-26 |
| AC7 | Gitignore audit — no health data in public     | ⊕workspace-security   | not-started | —     | 2026-04-26 |

### Tyler's Original Request

> Tyler wants to add an external patient portal (athenahealth) to his biomarker health panel in ∞Life. Specifically:
> 1. External portal link — https://9821-12.portal.athenahealth.com/ — should be accessible/handy from the ∞Life biomarker health panel UI/dashboard
> 2. Medication tracking — Current medications to be added/synced into the ∞Life database: metformin 500 mg tablet, anastrozole 1 mg tablet, hydroxyzine HCl 50 mg tablet, finasteride 1 mg tablet, rosuvastatin 10 mg tablet, HCG, nicotinamide-adenine dinucleotide red disod (bulk) 100% powder, Zepbound 5 mg/0.5 mL subcutaneous pen injector, testosterone cypionate 200 mg/mL intramuscular syringe
> 3. Lab results DB ingestion — Instead of static HTML, lab test results should be stored in infinitelife.db. Lab results from 12/18/2025 (ordered by John Waters, NP at Burrows Internal Medicine):
>    - HbA1c: 5.3% (Normal, <5.7%)
>    - Creatinine: 1.28 mg/dL (HIGH, >1.26 upper limit)
>    - Full CMP: glucose 88, BUN 22, eGFR 73, BUN/Cr 17, Na 136, K 4.3, Cl 102, CO2 25, Ca 9.5, protein 6.9, albumin 4.7, globulin 2.2, A/G 2.1, bili 0.7, ALP 39, AST 30, ALT 42 — all Normal except creatinine
>    - Provider note: "Screening for Lynch Syndrome was okay. Kidney function looks better; limit intake of over the counter NSAIDs and alcohol. Aim for at least 64 oz of water daily. Liver function and blood sugar look good."

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-04-26T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, triage complete → TRIAGED

**Details:**
- Scope: ∞Life (private repo — health data only)
- Risk: high (real medical data, medications, lab values — all must stay in infinitelife.db)
- Acceptance criteria drafted: AC1–AC7 (see Header)
- Concurrency check: clean — no active ∞Life FRs, no file-path conflicts
- Depends on: none (infinitelife.db already restored per FR-20260424-infinitelife-db-restore)
- Portal URL confirmed external-link-only — no credentials stored
- Gitignore audit (AC7) assigned to ⊕workspace-security as a parallel pre-push gate

**Next:** awaiting Tyler: approve scope → branch creation via ⊕workspace-ci

---

## Artifacts

- **Perf runs:** 6e53c098-c290-4e30-a6b0-144ad0774c8e — fr-cycle-FR-20260426-biomarker-external-portal (started 2026-04-26)
- **Proof artifacts:** —
- **PRs:** https://github.com/tylerdrakemusic/Life/pull/4 (draft)
- **Commits:** e162ab9 — ∞ life: begin FR-20260426-biomarker-external-portal
- **Reports / dashboards:** —

---

### 2026-04-26T00:00:00Z — ⊕workspace-ci

**Event:** state-transition

**Summary:** Branch created and draft PR opened → BRANCHED

**Details:**
- Branch: `feature/life/biomarker-external-portal` created from `main` (SHA ce448ea)
- Seed commit: e162ab9 — empty initial commit to open PR
- Draft PR: https://github.com/tylerdrakemusic/Life/pull/4
- No code committed yet — implementation pending by ∞life-orchestrator
- Pre-push gitignore audit (AC7) required before any merge

**Next:** ∞life-orchestrator implements AC1–AC6; ⊕workspace-security runs AC7 gitignore audit before merge
