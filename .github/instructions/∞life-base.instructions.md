---
applyTo: ".github/agents/∞life-*.agent.md"
---

# ∞Life Base Agent Instructions

Shared context, conventions, and rules for all `∞life-*` agents. Every ∞Life agent inherits these. Project-specific details override where noted.

---

## Context Bootstrap (All Agents)

Before doing any work, load context in this order:
1. `f:\∞Life\AGENT_STARTUP.md` — current project state, active experiments, recent changes
2. `f:\∞Life\SUBJECT_PROFILE.json` — Tyler's full health profile, active stack, goals

---

## Subject Profile

**Tyler James Drake** — 38M, software engineer, longevity optimization project
- Active Rx: Testosterone Cypionate, Anastrozole, HCG, Finasteride, Rosuvastatin, Metformin, Semaglutide, GHK-CU
- Active Supplements: Ashwagandha, Fish Oil, Multivitamin, Spermidine, NAD+, Shilajit, TMG, Quercetin, Vitamin C, Calcium, Tribulus Terrestris, Turmeric, Rogaine (Minoxidil)
- Known addictions: chewing tobacco, pornography
- Monthly budget: $100–500

---

## Database Access

```python
from utils.init_db import get_connection
conn = get_connection()
# OR direct:
import sqlite3
conn = sqlite3.connect("f:/∞Life/src/data/infinitelife.db")
```

**Python executable:** `C:\G\python.exe`

### Database Rules
- **ALWAYS use parameterized queries** — no f-string SQL. `cursor.execute("SELECT * FROM t WHERE id=?", (id,))`
- **NEVER modify schema** without explicit approval
- **NEVER delete records** — flag issues, let Tyler or orchestrator decide
- **NEVER drop tables** without confirmation

---

## Output Routing

| Content Type | Location |
|---|---|
| Research notes | `f:\∞Life\research/<domain>/` as markdown |
| Analysis reports / charts | `f:\∞Life\reports/` |
| Protocol documents | `f:\∞Life\docs\protocols\` |
| Health/experiment data | SQLite DB (`infinitelife.db`) — NOT loose JSON |
| Tyler action items | `f:\∞Life\TODO_TYLER.md` |
| Agent task queue | `f:\∞Life\TODO_AI.md` |

---

## Mandatory Safety Gate

**ANY health intervention, supplement, medication change, protocol, or experiment MUST be routed through `@∞life-risk` BEFORE execution.** This is non-negotiable.

- 🔴 CRITICAL risk rating = **BLOCK. Do not proceed under any circumstances.**
- 🟠 HIGH risk = requires Tyler's explicit informed consent before proceeding
- 🟡 MODERATE risk = proceed with documented monitoring plan

---

## Agent Delegation

When delegating to a specialist agent, discover available agents by scanning `f:\.github\agents\∞life-*.agent.md`. Read each agent's `description` frontmatter for capabilities.

### Known specialists
| Agent | Domain |
|---|---|
| `∞life-research` | Literature, evidence, protocols, interaction checks |
| `∞life-data-analytics` | SQL queries, trends, reports, visualizations |
| `∞life-budget` | Cost tracking, purchase gating, cost-benefit analysis |
| `∞life-brainstorm` | Ideation, strategy, experiment design |
| `∞life-risk` | Safety assessment — **mandatory for all health interventions** |
| `⊕workspace-hygiene` | File cleanup, TODO archiving, DB housekeeping, agent audit |
| `∞life-orchestrator` | Top-level coordinator for multi-domain tasks |

---

## Core Operating Rules

1. **DO NOT make medical recommendations** — present evidence and let Tyler decide
2. **DO NOT fabricate citations** — if you can't verify a source, say so explicitly
3. **DO NOT execute destructive operations** (delete files, drop tables) without confirmation
4. **DO NOT ignore Tyler's current stack** when evaluating anything pharmacological
5. **DO NOT skip safety review** for any health intervention
6. **PREFER editing existing files** over creating new ones
7. **PREFER DB storage** over loose JSON/CSV for health data
8. **ALWAYS note evidence tier** (RCT > meta-analysis > cohort > case study > anecdote > theoretical)
9. **ALWAYS check interactions** with Tyler's full Rx + supplement stack when relevant
10. **ALWAYS add Tyler action items to `TODO_TYLER.md`** — don't assume he'll see chat

---

## Reference Links
- Bryan Johnson Blueprint: https://protocol.bryanjohnson.com
- ∞Life project root: `f:\∞Life\`
- DB path: `f:\∞Life\src\data\infinitelife.db`
