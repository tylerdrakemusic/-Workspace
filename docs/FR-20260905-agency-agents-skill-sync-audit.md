# Agency Agents Skill Sync Audit

FR: `FR-20260905-agency-agents-skill-sync-audit`
Parent TODO: `#516`
Child TODOs: `#534-#538`

## Audit Inputs

- Audit date: 2026-09-05
- Scope: `⊕Workspace/.github/skills`
- Canonical catalog: `.github/skills/skill-catalog.json`
- Catalog SHA-256: `039383d9518840c14b6aa1a612c73a33a5ccea1f4ae1e26c9267121bc7da27aa`
- Sync configuration: `tools/skill-sync-config.json`
- Sync configuration SHA-256: `dadf66ace621941a40ce394af2b9022040330395f3d91429953193dc56fcbc42`
- Current local skill directories: 35
- Configured source entries: 7

Configured sources are `mp-skills-engineering`, `mp-skills-productivity`,
`addyosmani-agent-skills`, `andrej-karpathy-skills`, `davidondrej-skills`,
`humanizer`, and `superpowers`. The configuration contains one existing
external synchronization mapping, Humanizer, pinned to
`e2e92e7b4b8229253ed5c8e81dc65463fdeddda5` with its recorded SHA-256. No
Agency Agents source or mapping was added because this audit found no unique
approved workflow skill.

## Upstream Provenance

- Repository: <https://github.com/msitarzewski/agency-agents>
- Pinned commit: `af128a92888fd7d7c389b6cb37f1820be1b3cd9d`
- Commit subject: `fix(install): honor CLAUDE_CONFIG_DIR as config root, not agents dir (#834)`
- Commit author: `emindagg`
- Commit timestamp: `2026-09-04T21:06:36+03:00`
- License: MIT
- License SHA-256: `9a45258434d5cedf0af73c9ad4771373701225038d246c49219026c33677f66f`
- Provenance rule: hashes below are SHA-256 of the exact files at the pinned
  commit. No upstream Markdown was rewritten or copied.

The pinned tree contains 319 Markdown files. The majority are persona files,
with additional examples, integration documentation, marketing content,
strategy playbooks, and runbooks. The screening set below contains every file
whose name or location presented a plausible workflow interpretation. Files
that are examples, marketing, personas, or domain playbooks are not eligible
workflow skills under this FR.

## Candidate Dispositions

Disposition counts: 0 unique, 1 overlap, 18 out-of-scope, 0 deferred. The
eligible set therefore contains no importable candidate.

| Upstream path | SHA-256 | Disposition | Evidence |
|---|---|---|---|
| `engineering/engineering-git-workflow-master.md` | `b2ab151fa5dc31035ba5f40f9b104f61cc8ef45dab8a8249ad15675141550d77` | overlap | Persona content overlaps the existing `git-workflow-and-versioning`; the local skill owns repository lifecycle mechanics. |
| `project-management/project-management-jira-workflow-steward.md` | `e45c68423c1df0c20452916a5caafe7f41a97b56ca5af8872af966212ccbf389` | out-of-scope | Jira-specific project-management persona, not a reusable workflow skill. |
| `specialized/specialized-workflow-architect.md` | `74d46f03dcdd769163ce73ea8ac025bae48ae2356792a7aff3619c92f802a8ef` | out-of-scope | Specialized persona and workflow architecture role, not a host-neutral skill. |
| `testing/testing-workflow-optimizer.md` | `021ba71e2455071983ce1a6044783bec224b025b864757ce76b2bd4d40c00211` | out-of-scope | Testing-operations persona, not a generic testing workflow contract. |
| `examples/workflow-book-chapter.md` | `a0382f06c7536579be480c737d56257c3247b55fbacfc6fdc219f870053a8f3f` | out-of-scope | Explicit example content. |
| `examples/workflow-landing-page.md` | `05942259ec3fa56d32dc882e27646c75d69bdd8cb8333212ac9589eaba729bac` | out-of-scope | Explicit example and marketing-shaped content. |
| `examples/workflow-startup-mvp.md` | `e540cc1c11e16ea5726dbfe2122e8832e020b865f957fdeb44a2216ab5873308` | out-of-scope | Explicit example for a startup domain. |
| `examples/workflow-with-memory.md` | `12d75f810271871ea4aec14feb3705ea51fb0bb2519ef1e651c68777475c2453` | out-of-scope | Explicit example content. |
| `strategy/playbooks/phase-0-discovery.md` | `0ae7d5cfc479e0d2818bf5a8559d59f90ee446b03d754b355594a1c0c62b294e` | out-of-scope | NEXUS studio strategy playbook. |
| `strategy/playbooks/phase-1-strategy.md` | `8509ef04a669ec01752ebf8da5048ec538fd0c3c1e85029f83a2ea90d8888bdd` | out-of-scope | NEXUS studio strategy playbook. |
| `strategy/playbooks/phase-2-foundation.md` | `16c02d3c0debc95732ac4b9a7187d02e832ba55683d9bd605395a958be0f5e94` | out-of-scope | NEXUS studio foundation playbook. |
| `strategy/playbooks/phase-3-build.md` | `b9b2383e0c6e135d3bcd59a8ab995f234c420c6c04900fabff19e083a92468d2` | out-of-scope | NEXUS studio build playbook. |
| `strategy/playbooks/phase-4-hardening.md` | `0db1b7dc62dccc30579f06e8f2b480f7b04fcd153fca7df43aa2470f46907386` | out-of-scope | NEXUS studio hardening playbook. |
| `strategy/playbooks/phase-5-launch.md` | `afae11996e699041f9c094e9a07452c866ce12d959bb93a89526307617e7205b` | out-of-scope | NEXUS studio launch and growth playbook. |
| `strategy/playbooks/phase-6-operate.md` | `5681569052513c334bcb2219374776ea3f7c78eedfbde587b1a051372d0c476b` | out-of-scope | NEXUS studio operations playbook. |
| `strategy/runbooks/scenario-enterprise-feature.md` | `40e20eac5c6eb54f4a5017b1f8d9f56bba44ae9afc82bfb2c678f971c7d5fb2b` | out-of-scope | Enterprise feature scenario runbook tied to NEXUS orchestration. |
| `strategy/runbooks/scenario-incident-response.md` | `b08fe23eddcc6f5038a4a8e33930f7d40d67b6916144076667eb6d50ce604fff` | out-of-scope | Incident-response scenario runbook, not a generic skill. |
| `strategy/runbooks/scenario-marketing-campaign.md` | `979c985e5cbb6a42aae2bfbd02494712fac75f8fceac5d7f9ca704b071ef7f57` | out-of-scope | Marketing-campaign domain runbook. |
| `strategy/runbooks/scenario-startup-mvp.md` | `90eb81f4338453ce3064d33434967cf028f6a3a668fccb436c64424d1e00ff26` | out-of-scope | Startup-MVP domain runbook. |

No candidate was deferred: the reviewed files had enough provenance and
content evidence for a disposition at this pin. No candidate was classified
as unique, so no `.github/skills/*/SKILL.md`, catalog entry, or sync mapping
was added.

## Approved Result

This FR produces a documented no-op. The upstream source is not registered in
`tools/skill-sync-config.json`, because registering a source without an
approved unique mapping would create a misleading synchronization contract.
The canonical catalog remains unchanged, and upstream files remain verbatim
in their source repository only.

## Review Boundary

- Repository: `tylerdrakemusic/-Workspace`
- Branch: `feature/FR-20260905-agency-agents-skill-sync-audit`
- Worktree: `F:\⊕Workspace\.worktrees\feature-FR-20260905-agency-agents-skill-sync-audit`
- Change scope: this audit document only; no catalog, sync configuration, skill,
  manifest, or upstream source file is changed.
- Protected-file result: no existing local skill or synchronized file was
  overwritten during the audit or dry run.

## Validation Evidence

Commands run from the isolated worktree:

```text
C:\G\python.exe -m pytest tests/test_skill_catalog.py tests/test_skill_integrity.py -q
& .\tools\sync-skills.ps1 -ConfigPath $env:TEMP\skill-sync-dryrun-agency-agents.json
```

Results:

- Catalog and integrity tests: `30 passed in 2.26s`.
- Sync dry run: completed with `=== skill-sync complete ===`; all configured
  skills were reported as existing protected files and skipped.
- The nested `powershell.exe -File` form reported an unexpected closing brace
  before execution, while the active PowerShell host parsed and completed the
  same script. This is a host invocation quirk, not a catalog or sync result.
- No files were copied, no protected skill was overwritten, and no upstream
  source repository was pulled during the dry run.
