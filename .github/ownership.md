# GitHub Markdown Ownership

This map is the authoritative boundary for agent customization Markdown.

| Repository | Local ownership | Central ownership retained |
|---|---|---|
| `⊕Workspace` | Workspace agents and workspace-only validators | Shared agents, shared instructions, general skills, shared prompts, root instructions, security policy, legacy FR records |
| `∞Life` | `∞life-*.agent.md`, `∞life-*.instructions.md` | None of its project-specific Markdown |
| `❤Music` | `❤music-*.agent.md`, `❤music-base.instructions.md` | None of its project-specific Markdown |
| `⟨ψ⟩Quantum` | `⟨ψ⟩quantum-*.agent.md`, `⟨ψ⟩quantum-base.instructions.md` | None of its project-specific Markdown |
| `👁AI-Manifest` | `👁ai-manifest-*.agent.md` | None of its project-specific Markdown |
| `ΣCapital` | `Σcapital-*.agent.md`, `sigmacapital-*.instructions.md`, and active SigmaCapital prompts | No inert SigmaCapital picker smoke-test agent is recreated |

Repository startup directives discover project-specific files from local
`.github/` paths. Workspace discovery and frontmatter integrity scan both the
central shared surface and all six repository-local surfaces.

The public repositories must not receive ∞Life health data or ΣCapital
financial data. The private repositories retain their domain guidance without
changing data storage or access policy.