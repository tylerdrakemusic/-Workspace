---
applyTo: ".github/agents/❤music-*.agent.md"
---

# ❤Music Base Agent Instructions

Shared context, conventions, and rules for all `❤music-*` agents. Every ❤Music agent inherits these. Agent-specific details override where noted.

---

## Context Bootstrap (All Agents)

Before doing any work, load context in this order:
1. `f:\❤Music\AGENT_STARTUP.md` — current project state, recent migrations, active tasks
2. `f:\❤Music\ARTIST_PROFILE.json` — Tyler's artist profile, all source locations, album definitions, track lists

---

## Artist Profile

**Tyler James Drake** — solo artist + lead of CopperCreek
- Bloom album: in progress at Hyperthreat Studios
- EP: released (Marigold, Get Out, What I Do)
- Python executable: `C:\G\python.exe`

---

## Database Access

```python
from utils.init_db import get_connection
conn = get_connection()
# OR direct:
import sqlite3
conn = sqlite3.connect("f:/❤Music/src/data/heartmusic.db")
```

**Python executable:** `C:\G\python.exe`  
**Run from project root:** `f:\❤Music\`

### Database Rules
- **ALWAYS use parameterized queries** — no f-string SQL
- **NEVER modify schema** without explicit approval
- **NEVER delete records** — flag issues, let Tyler decide
- **NEVER drop tables** without confirmation

---

## Catalog Source Locations (Read-Only External Sources)

| Name | Path |
|---|---|
| Masters (F:) | `f:\Masters\` |
| Rockstar backup (G:) | `G:\TylerJamesDrake\rockstar\` |
| Roughs (E:) | `E:\Roughs\` |
| Recordings | `f:\recordings\` |
| Lyrics source | `f:\lyrics\` |
| Guitar source | `f:\Guitar\` |
| Bands | `f:\bands\` |

**Do NOT move, delete, or rename source files from external locations. Reference or copy into catalog only.**

---

## Catalog (Local Source of Truth)

| Content | Path |
|---|---|
| Bloom masters | `catalog/masters/Bloom/` |
| EP masters | `catalog/ep/` |
| Roughs | `catalog/roughs/<album>/<song>/` |
| Sheet music — originals | `catalog/sheet_music/originals/` |
| Sheet music — covers | `catalog/sheet_music/covers/` |
| Sheet music — templates (JSON) | `catalog/sheet_music/templates/` |
| Sheet music — generated (DOCX) | `catalog/sheet_music/generated/` |
| Lyrics data | `catalog/lyrics/` |
| Music training configs | `catalog/music_training/` |
| Video projects | `catalog/video_projects/` |

---

## Output Routing

| Content Type | Location |
|---|---|
| Research notes | `research/<domain>/` as markdown |
| Production notes | `docs/protocols/` |
| Session journal | `docs/journal/YYYY-MM-DD.md` |
| Artist/album/track data | SQLite DB (`heartmusic.db`) — NOT loose JSON |
| Tyler action items | `TODO_TYLER.md` |
| Agent task queue | `TODO_AI.md` |
| Studio metadata | `src/data/studio_master/` |

---

## Tools Prefix Convention

| Prefix | Category |
|---|---|
| `@` | Creative / performance tools (`@music_training.py`, `@group_rhymes.py`, `@make_chord_sheet.py`) |
| `~` | Migration / maintenance tools (`~catalog_index.py`, `~migrate_*.py`) |

---

## Agent Delegation

Discover available agents by scanning `f:\.github\agents\❤music-*.agent.md`. Read `description` frontmatter for capabilities.

### Known specialists
| Agent | Domain |
|---|---|
| `❤music-catalog` | File indexing, dedup, track linking, DB imports |
| `❤music-production` | Bloom album tracking, track status, studio sessions |
| `❤music-performance` | Gigs, practice log, CopperCreek, setlists |
| `⊕workspace-hygiene` | File cleanup, TODO archiving, DB housekeeping, agent audit |
| `❤music-orchestrator` | Top-level coordinator for multi-domain tasks |

---

## Core Operating Rules

1. **DO NOT move or delete external source files** (Masters, Rockstar, Roughs on E:/F:/G: drives)
2. **DO NOT fabricate metadata** — if a track's BPM/key is unknown, mark as null in DB
3. **DO NOT execute destructive operations** without confirmation
4. **PREFER editing existing files** over creating new ones
5. **PREFER DB storage** over loose JSON/CSV for structured music data
6. **ALWAYS use UTF-8 encoding** — `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")` in all tools
7. **ALWAYS add Tyler action items to `TODO_TYLER.md`** — don't assume he'll see chat
8. **ALWAYS run from project root** `f:\❤Music\` so relative paths resolve correctly

---

## Reference
- ❤Music project root: `f:\❤Music\`
- DB path: `f:\❤Music\src\data\heartmusic.db`
- ARTIST_PROFILE: `f:\❤Music\ARTIST_PROFILE.json`
