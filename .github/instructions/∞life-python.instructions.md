---
description: "Use when writing Python scripts that interact with the ∞Life SQLite database, creating sync tools, data migrations, or any database operations. Covers connection patterns, schema conventions, and data safety."
applyTo: "∞Life/**/*.py"
---

# ∞Life Python & Database Conventions

## Database Connection
```python
# Preferred: use project utility
import sys
sys.path.insert(0, "f:/∞Life/src")
from utils.init_db import get_connection

# Direct (for standalone tools):
import sqlite3
conn = sqlite3.connect("f:/∞Life/src/data/infinitelife.db")
```

## Safety Rules
- Always use parameterized queries: `cursor.execute("SELECT * FROM t WHERE id=?", (id,))`
- Never use f-strings or .format() in SQL
- Upsert pattern: INSERT OR REPLACE with unique constraints
- Log all sync operations to `sync_log` table
- Close connections in finally blocks or use context managers

## Sync Tool Pattern
All sync tools follow this contract:
- CLI with argparse: `--days N`, `--full`, `--summary`
- Log to `logs/<source>_sync.log`
- Record sync metadata in `sync_log` table
- Handle auth refresh gracefully
- Exit 0 on success, 1 on failure with error message
