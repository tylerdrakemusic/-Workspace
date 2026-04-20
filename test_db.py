import os, sys, sqlcipher3
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(r"f:\executedcode\.env"))
key = os.environ.get("WORKSPACE_DB_KEY")
db_path = r"f:\executedcode\?Workspace\src\data\workspace.db"
print("DB Path:", db_path)
print("File exists:", os.path.exists(db_path))
try:
    conn = sqlcipher3.connect(db_path)
    conn.execute("PRAGMA key=\"%s\"" % key)
    print("Connection OK")
    result = conn.execute("SELECT count(*) FROM vulnerabilities").fetchone()
    print("Vulns:", result[0])
    conn.close()
    print("PASS")
except Exception as e:
    print("Error:", e)
    import traceback
    traceback.print_exc()
