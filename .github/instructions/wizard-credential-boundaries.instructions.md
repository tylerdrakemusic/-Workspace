---
description: "Use when creating or running the Workspace wizard. Covers terminal-only credential entry, external environment files, and confirmed remote secret writes."
applyTo: [".github/skills/wizard/**", "tools/skill-sync-adaptations/wizard/**"]
---

# Wizard Credential Boundaries

- Collect secrets only through hidden terminal prompts such as `ask_secret`. Never ask the user to paste a credential into chat or put its value in model context, repository files, or logs.
- Set `ENV_FILE` explicitly to an absolute, non-symlink path outside the Git repository before persisting a credential. The file must be on a filesystem that enforces POSIX permissions; Windows shells and DrvFS-backed paths are refused. Existing files must be private and single-link. The wizard refuses repository `.env` paths and does not choose a fallback location.
- Persist a credential only when the user has approved that destination. If no external environment file is approved, keep the value in the interactive process and do not write it.
- A GitHub secret write requires the exact `OWNER/REPO`, a CI need for that secret, and a separate confirmation for that write. Do not infer the destination or batch confirmations.
- Do not run the interactive wizard end-to-end as an agent. Validate scripts with `bash -n` and isolated tests; leave live credential entry and remote writes to the user at the confirmation prompt.
- Report only safe status, secret name, and destination metadata. Never print credential values or matching log lines.