# FR-20260423-repo-privacy-audit — Repo Privacy Audit — Privatize Sensitive Repos + Agent Awareness for Public/Private Status

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260423-repo-privacy-audit
- **Title:** Repo Privacy Audit — Privatize Sensitive Repos + Agent Awareness for Public/Private Status
- **Type:** feature
- **Risk:** high
- **Projects:** ∞Life, ❤Music, ⟨ψ⟩Quantum, 👁AI-Manifest, ⊕Workspace
- **State:** TRIAGED
- **Branch:** feature/all/repo-privacy-audit (pending CI)
- **PRs:** pending
- **Cycle timer:** 3a38e6fa-77aa-48c6-aea5-db95978fee29
- **Opened:** 2026-04-23
- **Last updated:** 2026-04-23
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. Privacy recommendation documented per repo with rationale (which repos to privatize vs leave public, and why)
2. `REPO_VISIBILITY.md` created at workspace level listing public/private status + sensitivity level per repo
3. Agent instructions updated in `.github/` so all agents know each repo's visibility and adapt behavior (e.g., warn before pushing to public repos with sensitive data, skip public-unsafe operations)
4. Security audit of ∞Life repo: scan for any health data, biomarker files, genomics, or bloodwork that may have been committed publicly and flag for remediation

### Concurrency Notes
- Conflicts with: FR-20260423-living-security-dashboard (minor — both touch `.github/` files in ⊕Workspace; different deliverables, no file-level clash expected — monitor)
- Depends on: none

### Deliverable Tracker

| #   | Deliverable | Owner | Status | Proof | Updated |
| --- | ----------- | ----- | ------ | ----- | ------- |
| AC1 | Privacy recommendation doc per repo | ⊕workspace-overseer | not-started | — | — |
| AC2 | REPO_VISIBILITY.md config artifact | ⊕workspace-overseer | not-started | — | — |
| AC3 | Agent instructions updated for visibility-aware behavior | ⊕workspace-overseer | not-started | — | — |
| AC4 | ∞Life security audit for already-public sensitive data | ⊕workspace-security | not-started | — | — |

### Tyler's Original Request
> Tyler is currently hosting all workspace repos publicly but is questioning that decision. `∞Life` contains private health/biomarker/genomic data. He wants:
> 1. A recommendation on which repos to privatize vs leave public (with rationale)
> 2. Agent awareness baked in: agents should know which repos are public vs private and adjust behavior accordingly (e.g., no pushing secrets to public repos, different PR strategies, different visibility warnings)
>
> Cross-project — affects all 5 repos (∞Life, ❤Music, ⟨ψ⟩Quantum, 👁AI-Manifest, ⊕Workspace). Also touches `.github/` agent files (agent awareness). Security-critical: ∞Life has health data, genomics, bloodwork.
>
> Budget: No direct cost — this is a policy + config change. Priority: High — ∞Life has private health data and is currently public.

---

## Event Log

### 2026-04-23T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, triage complete → TRIAGED

**Details:**
- Scope: All 5 projects (∞Life, ❤Music, ⟨ψ⟩Quantum, 👁AI-Manifest, ⊕Workspace) + `.github/` agent files
- Risk: HIGH — ∞Life repo contains health data (biomarkers, bloodwork, genomics); currently public
- Type: feature (policy + config + agent awareness)
- Acceptance criteria drafted (see Header)
- Concurrency check: minor overlap with FR-20260423-living-security-dashboard on `.github/`; no blocking conflict
- Cycle timer started: 3a38e6fa-77aa-48c6-aea5-db95978fee29

**Next:** awaiting Tyler: approve scope → then route to ⊕workspace-ci for branch creation

---

## Artifacts

- **Perf runs:** 3a38e6fa-77aa-48c6-aea5-db95978fee29 — FR cycle timer (started at intake)
