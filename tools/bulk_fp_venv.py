"""One-shot: bulk-mark .venv and .worktrees vulnerability entries as false_positive."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from utils.init_db import get_connection

conn = get_connection()
cur = conn.execute(
    """UPDATE vulnerabilities
       SET status = 'false_positive',
           override_note = 'Auto-bulk: .venv third-party package or .worktrees duplicate checkout — not workspace code',
           remediated_at = datetime('now')
       WHERE status = 'open'
         AND (file_path LIKE '%.venv%' OR file_path LIKE '%.worktrees%')"""
)
conn.commit()
print(f"Bulk-marked {cur.rowcount} entries as false_positive")
remaining = conn.execute("SELECT COUNT(*) FROM vulnerabilities WHERE status='open'").fetchone()[0]
print(f"Remaining open: {remaining}")
conn.close()
