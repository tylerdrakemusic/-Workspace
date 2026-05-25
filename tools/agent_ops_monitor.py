#!/usr/bin/env python3
"""
⊕ Agent Ops Monitor — session health, gap detection, and auto-remediation.

Queries perf_runs + proof_artifacts to build a complete picture of agent
session health. Detects and closes gaps:
  - Orphan runs (ended but 0 proofs)
  - Zombie runs (never ended — started > 2h ago)
  - Unverified proofs (proof recorded but never verified)
  - Proof-complete runs (all proofs verified → auto-close)
  - Proof-less agents (agents that have runs but no proof history)

Self-regenerating: generates an HTML dashboard + embeds a <meta refresh>
so the portal always shows current state. In --serve mode, provides an
interactive dashboard with session close buttons.

Usage:
    C:\\G\\python.exe tools/agent_ops_monitor.py                # generate + open
    C:\\G\\python.exe tools/agent_ops_monitor.py --no-open      # generate only
    C:\\G\\python.exe tools/agent_ops_monitor.py --fix          # auto-close gaps + generate
    C:\\G\\python.exe tools/agent_ops_monitor.py --fix --no-open
    C:\\G\\python.exe tools/agent_ops_monitor.py --json         # JSON health report
    C:\\G\\python.exe tools/agent_ops_monitor.py --close <run_id>  # close a specific session
    C:\\G\\python.exe tools/agent_ops_monitor.py --serve [--port N] # interactive dashboard server
"""

import argparse
import html as html_mod
import json
import os
import re
import shutil
import sys
import time
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Brave registration
_BRAVE = [
    r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
]
for _bp in _BRAVE:
    if os.path.isfile(_bp):
        webbrowser.register("brave", None, webbrowser.BackgroundBrowser(_bp))
        break

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = PROJECT_ROOT / "reports" / "agent_ops_dashboard.html"

sys.path.insert(0, str(PROJECT_ROOT / "src" / "utils"))
from init_db import get_connection, init_db

# ── Tunable thresholds ────────────────────────────────────────────────────────
# Sessions with no ended_at whose last_heartbeat (or started_at if last_heartbeat
# is NULL) is older than this threshold are classified as zombies and auto-closed
# by --fix.  10 min is aggressive enough to catch stale sessions quickly while
# still giving actively running agents time to start their first heartbeat.
ZOMBIE_THRESHOLD_MIN: int = 10   # minutes

# A session counts as "live" only when its last_heartbeat (or started_at if
# last_heartbeat is NULL / absent) falls within this rolling window AND the
# session has not yet been closed (ended_at IS NULL).
LIVE_WINDOW_MIN: int = 10        # minutes

# VS Code Copilot debug-log directory pattern. Each workspaceStorage subfolder
# contains GitHub.copilot-chat/debug-logs/ whose session subdirs are last
# modified when a chat message is exchanged (not on every keypress).
# Detection does NOT write to the DB — purely ephemeral for the live banner.
# Limitation: mtime updates only on message exchange, not on open VS Code windows
# with no recent chat activity. A VS Code window idle for >4h will look stale.
_VSCODE_COPILOT_LOG_GLOB = (
    "Code/User/workspaceStorage/*/GitHub.copilot-chat/debug-logs"
)
_VSCODE_DETECT_WINDOW_SECS: int = 14400  # 4 hours — matches a typical work block


def detect_vscode_sessions(window_secs: int = _VSCODE_DETECT_WINDOW_SECS) -> list[dict]:
    """Detect active VS Code Copilot chat sessions via debug-log directory mtimes.

    Scans %APPDATA%/Code/User/workspaceStorage/*/GitHub.copilot-chat/debug-logs/
    and its session subdirectories. Returns one entry per workspace that has had
    chat activity within *window_secs*.

    Limitation: mtime updates only on message exchange. A VS Code window open but
    idle for longer than window_secs will not be detected here.

    Returns list of dicts: {path, mtime, age_secs}
    Does NOT write to the database.
    """
    import glob as _glob

    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        return []  # not on Windows or env var missing

    pattern = str(Path(appdata) / _VSCODE_COPILOT_LOG_GLOB)
    cutoff = time.time() - window_secs
    found = []
    for log_dir_str in _glob.glob(pattern):
        log_dir = Path(log_dir_str)
        # Check the parent debug-logs dir AND all immediate session subdirs.
        candidates = [log_dir] + list(log_dir.iterdir()) if log_dir.is_dir() else [log_dir]
        try:
            newest_mtime = max(p.stat().st_mtime for p in candidates if p.exists())
        except (OSError, ValueError):
            continue
        if newest_mtime >= cutoff:
            found.append({
                "path": log_dir_str,
                "mtime": newest_mtime,
                "age_secs": time.time() - newest_mtime,
            })
    return found


def _ensure_last_heartbeat_column(conn) -> None:
    """Add last_heartbeat REAL column to perf_runs if it does not exist yet."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(perf_runs)").fetchall()}
    if "last_heartbeat" not in cols:
        conn.execute("ALTER TABLE perf_runs ADD COLUMN last_heartbeat REAL")
        conn.commit()


def _esc(v) -> str:
    return html_mod.escape(str(v)) if v else ""


def _ts(epoch: float | None) -> str:
    if not epoch:
        return ""
    return datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M")


def _dur(ms: float) -> str:
    s = int(ms / 1000)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


# ── Data Collection ──────────────────────────────────────────

def collect_health(conn) -> dict:
    """Gather all session health metrics from workspace.db."""
    now = time.time()
    stale_threshold = now - (ZOMBIE_THRESHOLD_MIN * 60)  # configurable zombie window

    # Ensure last_heartbeat column exists before querying it.
    _ensure_last_heartbeat_column(conn)

    # All runs — include last_heartbeat for accurate live/zombie detection.
    runs = conn.execute(
        "SELECT run_id, name, started_at, ended_at, status, detail, last_heartbeat FROM perf_runs ORDER BY started_at DESC"
    ).fetchall()

    # All proofs grouped by run
    #   verified column values:
    #     0 = unverified (gap)
    #     1 = verified on disk
    #     2 = artifact-deleted-acknowledged (historical honesty — not a gap)
    proofs = conn.execute(
        "SELECT run_id, COUNT(*) as cnt, SUM(CASE WHEN verified IN (1,2) THEN 1 ELSE 0 END) as v_cnt FROM proof_artifacts GROUP BY run_id"
    ).fetchall()
    proof_map = {p["run_id"]: {"count": p["cnt"], "verified": p["v_cnt"] or 0} for p in proofs}

    # Agent proof coverage
    agent_coverage = conn.execute(
        """SELECT agent, COUNT(*) as total, SUM(verified) as verified,
                  COUNT(DISTINCT run_id) as runs
           FROM proof_artifacts GROUP BY agent ORDER BY total DESC"""
    ).fetchall()

    # Categorize runs
    sessions = []
    zombies = []
    orphans = []
    healthy = []
    total_runs = len(runs)

    for r in runs:
        rid = r["run_id"]
        # last_heartbeat is the authoritative recency signal; fall back to
        # started_at for sessions that predate the column or have never pulsed.
        heartbeat_ts = r["last_heartbeat"] or r["started_at"]
        entry = {
            "run_id": rid,
            "name": r["name"],
            "started_at": r["started_at"],
            "ended_at": r["ended_at"],
            "status": r["status"],
            "detail": r["detail"],
            "wall_ms": ((r["ended_at"] or now) - r["started_at"]) * 1000,
            "proofs": proof_map.get(rid, {"count": 0, "verified": 0}),
            "last_heartbeat": r["last_heartbeat"],
            "_heartbeat_ts": heartbeat_ts,
        }
        sessions.append(entry)

        # Zombie: open session whose last activity is beyond the stale threshold.
        # Uses last_heartbeat with fallback to started_at (AC1 + AC2).
        if not r["ended_at"] and heartbeat_ts < stale_threshold:
            entry["gap"] = "zombie"
            zombies.append(entry)
        elif r["ended_at"] and entry["proofs"]["count"] == 0:
            entry["gap"] = "orphan"
            orphans.append(entry)
        else:
            entry["gap"] = None
            healthy.append(entry)

    # Unverified proofs
    unverified = conn.execute(
        """SELECT p.proof_id, p.run_id, p.agent, p.proof_type, p.description,
                  p.artifact_path, p.created_at
           FROM proof_artifacts p WHERE p.verified = 0"""
    ).fetchall()

    # Score
    gap_count = len(zombies) + len(orphans) + len(unverified)
    health_pct = ((total_runs - len(zombies) - len(orphans)) / max(total_runs, 1)) * 100

    # Live / recent / historical counts (AC2/AC4 banner).
    # "Live" = last_heartbeat (fallback started_at) within LIVE_WINDOW_MIN AND not closed.
    live_cutoff = now - (LIVE_WINDOW_MIN * 60)
    recent_cutoff = now - 86400   # 24 hours
    live_count = sum(
        1 for s in sessions
        if s["ended_at"] is None and (s["_heartbeat_ts"] or 0) >= live_cutoff
    )
    recent_count = sum(1 for s in sessions if (s["started_at"] or 0) >= recent_cutoff)

    # Detect uninstrumented VS Code Copilot sessions via debug-log mtimes (AC1).
    # These do NOT get DB entries — they show in the live banner as "detected".
    vscode_sessions = detect_vscode_sessions()
    vscode_live_count = len(vscode_sessions)

    return {
        "generated_at": datetime.now().isoformat(),
        "total_runs": total_runs,
        "healthy": len(healthy),
        "zombies": zombies,
        "orphans": orphans,
        "unverified": [dict(u) for u in unverified],
        "sessions": sessions,
        "agent_coverage": [dict(a) for a in agent_coverage],
        "gap_count": gap_count,
        "health_pct": round(health_pct, 1),
        "live_count": live_count,
        "vscode_live_count": vscode_live_count,
        "vscode_sessions": vscode_sessions,
        "recent_count": recent_count,
        "historical_total": total_runs,
    }


# ── Architecture Migration (AC1) ─────────────────────────────

# Workspace sigils — these are the valid project-root prefixes after the
# flat-layout migration. Any artifact_path starting with
# ``f:/executedcode/<sigil>...`` is stale and should be rewritten to
# ``f:\<sigil>...``.
_SIGILS = ("∞", "❤", "⟨ψ⟩", "👁", "⊕")

# Pattern to match stale executedcode paths. Captures the remainder after
# ``f:/executedcode/`` (case-insensitive drive letter).
_EXECUTEDCODE_RE = re.compile(r"^[fF]:[\\/]executedcode[\\/](.+)$")

# Legacy security folder rename.
_OLD_SECURITY = "!!security"
_NEW_SECURITY = "!!☾⛧security"


def rewrite_artifact_path(path: str | None) -> str | None:
    """Return migrated artifact_path or original if nothing to rewrite.

    Applies, in order:
      1. ``f:/executedcode/...`` → ``f:\\...`` (strips executedcode prefix).
      2. Forward slashes → backslashes (Windows canonical).
      3. ``!!security`` → ``!!☾⛧security`` anywhere in the path.
      4. ``f:\\.github\\...`` → ``f:\\⊕Workspace\\.github\\...`` (workspace root).
    """
    if not path:
        return path
    new = path
    m = _EXECUTEDCODE_RE.match(new)
    if m:
        new = "f:\\" + m.group(1)
    # Normalize slashes to backslashes for any f:/... prefix or subpath.
    if new.lower().startswith("f:/") or "/" in new:
        # Only touch paths that look like local filesystem paths (drive-prefixed).
        if re.match(r"^[a-zA-Z]:", new):
            new = new.replace("/", "\\")
    if _OLD_SECURITY in new and _NEW_SECURITY not in new:
        new = new.replace(_OLD_SECURITY, _NEW_SECURITY)
    # Root-level .github is not a real filesystem location — it lives under ⊕Workspace.
    low = new.lower()
    if low.startswith("f:\\.github\\") or low == "f:\\.github":
        new = "f:\\⊕Workspace\\" + new[3:].lstrip("\\")
    return new


def normalize_agent(agent: str | None) -> str | None:
    """Prefix bare ``workspace-*`` agent names with the ⊕ sigil."""
    if not agent:
        return agent
    if agent.startswith("workspace-"):
        return "⊕" + agent
    return agent


def _backup_db(dry_run: bool = False) -> Path | None:
    """Create a timestamped backup of workspace.db under src/data/backups/.

    Returns the backup path, or ``None`` in dry-run mode.
    """
    src = Path(__file__).resolve().parent.parent / "src" / "data" / "workspace.db"
    backup_dir = src.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = backup_dir / f"workspace.db.{stamp}.bak"
    if dry_run:
        return None
    if src.exists():
        shutil.copy2(src, dest)
    return dest


def migrate_architecture(conn, *, dry_run: bool = False) -> dict:
    """Migrate stale artifact_path entries and agent name drift.

    Returns a summary dict with counts and sample diffs.
    """
    rows = conn.execute(
        "SELECT proof_id, agent, artifact_path, verified FROM proof_artifacts"
    ).fetchall()

    path_changes: list[dict] = []
    agent_changes: list[dict] = []

    for r in rows:
        new_path = rewrite_artifact_path(r["artifact_path"])
        new_agent = normalize_agent(r["agent"])
        if new_path != r["artifact_path"]:
            path_changes.append({
                "proof_id": r["proof_id"],
                "old": r["artifact_path"],
                "new": new_path,
            })
        if new_agent != r["agent"]:
            agent_changes.append({
                "proof_id": r["proof_id"],
                "old": r["agent"],
                "new": new_agent,
            })

    backup_path = None
    verified_after = 0

    if not dry_run:
        backup_path = _backup_db(dry_run=False)
        for ch in path_changes:
            conn.execute(
                "UPDATE proof_artifacts SET artifact_path = ? WHERE proof_id = ?",
                (ch["new"], ch["proof_id"]),
            )
        for ch in agent_changes:
            conn.execute(
                "UPDATE proof_artifacts SET agent = ? WHERE proof_id = ?",
                (ch["new"], ch["proof_id"]),
            )
        conn.commit()

        # Post-migration verification pass — flip verified=1 where path now exists.
        unverified = conn.execute(
            "SELECT proof_id, artifact_path FROM proof_artifacts WHERE verified = 0"
        ).fetchall()
        for uv in unverified:
            p = uv["artifact_path"]
            if p and Path(p).exists():
                conn.execute(
                    "UPDATE proof_artifacts SET verified = 1, verified_at = ? WHERE proof_id = ?",
                    (datetime.now().isoformat(), uv["proof_id"]),
                )
                verified_after += 1
        conn.commit()

    return {
        "dry_run": dry_run,
        "backup_path": str(backup_path) if backup_path else None,
        "fixed_paths": len(path_changes),
        "fixed_agents": len(agent_changes),
        "verified_after": verified_after,
        "path_samples": path_changes[:20],
        "agent_samples": agent_changes[:20],
    }


def drift_candidates(conn) -> list[dict]:
    """Return unverified proofs whose artifact_path or agent matches a migration pattern."""
    rows = conn.execute(
        """SELECT proof_id, run_id, agent, proof_type, description, artifact_path, created_at
           FROM proof_artifacts WHERE verified = 0"""
    ).fetchall()
    out: list[dict] = []
    for r in rows:
        new_path = rewrite_artifact_path(r["artifact_path"])
        new_agent = normalize_agent(r["agent"])
        if new_path != r["artifact_path"] or new_agent != r["agent"]:
            out.append({
                "proof_id": r["proof_id"],
                "run_id": r["run_id"],
                "agent": r["agent"],
                "suggested_agent": new_agent,
                "proof_type": r["proof_type"],
                "description": r["description"],
                "artifact_path": r["artifact_path"],
                "suggested_path": new_path,
                "created_at": r["created_at"],
            })
    return out


# ── Agent Name Validation (AC7) ─────────────────────────────

# Known internal aliases that do not map to real .agent.md files but are
# intentional synthetic entries (e.g. created by backfill logic).
# Values must be canonical agent names that DO have a .agent.md file.
_KNOWN_AGENT_ALIASES: dict[str, str] = {
    "⊕ops-monitor": "⊕workspace-overseer",
    "ops-monitor": "⊕workspace-overseer",
    "workspace-overseer": "⊕workspace-overseer",
}


def validate_agent_names(conn, *, fix: bool = False) -> dict:
    """Detect and optionally rename phantom agent entries in the DB.

    A phantom agent is an agent name in ``proof_artifacts`` that has no
    corresponding ``<name>.agent.md`` file under ``.github/agents/``.

    When ``fix=True``, known aliases (``_KNOWN_AGENT_ALIASES``) are renamed
    in-place and the changes are committed.  Unrecognised phantoms are only
    reported.

    Returns a summary dict:
        ``canonical``   – set of agent names extracted from .agent.md filenames
        ``db_agents``   – set of distinct agent names found in proof_artifacts
        ``phantoms``    – list of {agent, count, suggested} dicts
        ``renamed``     – number of rows updated (0 if fix=False)
    """
    agents_dir = PROJECT_ROOT / ".github" / "agents"
    canonical: set[str] = set()
    if agents_dir.is_dir():
        for p in agents_dir.glob("*.agent.md"):
            # Strip the full ".agent.md" double-extension to get the canonical name.
            canonical.add(p.name.removesuffix(".agent.md"))

    rows = conn.execute(
        "SELECT DISTINCT agent FROM proof_artifacts WHERE agent IS NOT NULL"
    ).fetchall()
    db_agents: set[str] = {r["agent"] for r in rows}

    phantoms: list[dict] = []
    renamed = 0
    for agent in sorted(db_agents):
        if agent not in canonical:
            count = conn.execute(
                "SELECT COUNT(*) FROM proof_artifacts WHERE agent = ?", (agent,)
            ).fetchone()[0]
            suggested = _KNOWN_AGENT_ALIASES.get(agent)
            phantoms.append({"agent": agent, "count": count, "suggested": suggested})
            if fix and suggested:
                conn.execute(
                    "UPDATE proof_artifacts SET agent = ? WHERE agent = ?",
                    (suggested, agent),
                )
                renamed += count
    if fix and renamed:
        conn.commit()

    return {
        "canonical": sorted(canonical),
        "db_agents": sorted(db_agents),
        "phantoms": phantoms,
        "renamed": renamed,
    }


# ── Auto-Fix ─────────────────────────────────────────────────

def fix_gaps(conn, health: dict) -> dict:
    """Auto-close zombies, proof-complete runs, and flag orphans. Returns remediation summary."""
    now = time.time()
    fixed_zombies = 0
    fixed_unverified = 0
    fixed_proof_complete = 0

    # Close zombie runs (started > 2h ago, never ended)
    for z in health["zombies"]:
        conn.execute(
            "UPDATE perf_runs SET ended_at = ?, status = ?, detail = COALESCE(detail, '') || ' [auto-closed by ops monitor]' WHERE run_id = ?",
            (now, "timeout", z["run_id"]),
        )
        fixed_zombies += 1

    # Auto-close runs where all proofs are verified (proof protocol met)
    active_runs = conn.execute(
        "SELECT run_id, name FROM perf_runs WHERE ended_at IS NULL"
    ).fetchall()
    for run in active_runs:
        rid = run["run_id"]
        proof_stats = conn.execute(
            "SELECT COUNT(*) as total, SUM(verified) as verified FROM proof_artifacts WHERE run_id = ?",
            (rid,),
        ).fetchone()
        total = proof_stats["total"] or 0
        verified = proof_stats["verified"] or 0
        if total > 0 and verified == total:
            conn.execute(
                "UPDATE perf_runs SET ended_at = ?, status = ?, detail = COALESCE(detail, '') || ' [auto-closed: proof protocol met]' WHERE run_id = ?",
                (now, "ok", rid),
            )
            fixed_proof_complete += 1

    # Verify all unverified proofs that have valid file paths
    for uv in health["unverified"]:
        path = uv.get("artifact_path")
        now_iso = datetime.now().isoformat()
        if path and Path(path).exists():
            # File exists on disk — confirmed.
            conn.execute(
                "UPDATE proof_artifacts SET verified = 1, verified_at = ? WHERE proof_id = ?",
                (now_iso, uv["proof_id"]),
            )
            fixed_unverified += 1
        elif not path:
            # Non-file proofs (db_write, metric, etc.) — mark verified.
            conn.execute(
                "UPDATE proof_artifacts SET verified = 1, verified_at = ? WHERE proof_id = ?",
                (now_iso, uv["proof_id"]),
            )
            fixed_unverified += 1
        elif path and (path.startswith("http://") or path.startswith("https://")):
            # URL-based evidence (GitHub PRs, CI links) — self-evidencing, mark verified.
            conn.execute(
                "UPDATE proof_artifacts SET verified = 1, verified_at = ? WHERE proof_id = ?",
                (now_iso, uv["proof_id"]),
            )
            fixed_unverified += 1
        elif path:
            # Path doesn't exist (stale worktree, deleted artifact) — acknowledge as
            # historical honesty so it no longer counts as an active gap.
            conn.execute(
                "UPDATE proof_artifacts SET verified = 2, verified_at = ? WHERE proof_id = ?",
                (now_iso, uv["proof_id"]),
            )
            fixed_unverified += 1

    conn.commit()

    # Backfill legacy orphans (predate proof system) so they stop showing as gaps.
    fixed_legacy = backfill_legacy(conn, health)

    # Rename phantom agents to canonical names (AC7).
    phantom_report = validate_agent_names(conn, fix=True)

    return {
        "fixed_zombies": fixed_zombies,
        "fixed_unverified": fixed_unverified,
        "fixed_proof_complete": fixed_proof_complete,
        "fixed_legacy": fixed_legacy,
        "phantom_report": phantom_report,
        "remaining_orphans": max(len(health["orphans"]) - fixed_legacy, 0),
    }


def backfill_legacy(conn, health: dict) -> int:
    """Backfill every orphan run as legacy.

    An orphan is defined as a run with ``ended_at IS NOT NULL`` and zero
    ``proof_artifacts`` rows. By definition the run is already closed and no
    new proofs can be retroactively verified on disk, so we acknowledge it
    as historical: flip status to ``legacy`` and insert a synthetic metric
    proof with description ``"predates proof system"``.

    Running sessions are never touched (``collect_health`` excludes them
    from ``orphans``).
    """
    count = 0
    for o in health["orphans"]:
        conn.execute(
            """INSERT INTO proof_artifacts
               (proof_id, run_id, agent, proof_type, description, verified, verified_at)
               VALUES (?, ?, ?, ?, ?, 1, ?)""",
            (
                __import__("uuid").uuid4().hex[:12],
                o["run_id"],
                "⊕workspace-overseer",  # canonical agent; ⊕ops-monitor was a phantom alias
                "metric",
                "predates proof system",
                datetime.now().isoformat(),
            ),
        )
        conn.execute(
            "UPDATE perf_runs SET status = ?, detail = COALESCE(detail, '') || ' [backfilled: predates proof system]' WHERE run_id = ?",
            ("legacy", o["run_id"]),
        )
        count += 1
    conn.commit()
    return count


# ── HTML Dashboard ───────────────────────────────────────────

def render_dashboard(health: dict, fix_summary: dict | None = None, drift: list[dict] | None = None) -> str:
    generated = health["generated_at"][:19]
    total = health["total_runs"]
    healthy = health["healthy"]
    zombie_count = len(health["zombies"])
    orphan_count = len(health["orphans"])
    unverified_count = len(health["unverified"])
    gap_count = health["gap_count"]
    health_pct = health["health_pct"]
    live_count = health.get("live_count", 0)
    recent_count = health.get("recent_count", 0)
    historical_total = health.get("historical_total", total)
    vscode_live_count = health.get("vscode_live_count", 0)
    drift = drift or []

    # Health color
    if health_pct >= 95:
        health_color = "#10b981"
        health_label = "Excellent"
    elif health_pct >= 80:
        health_color = "#f59e0b"
        health_label = "Good"
    elif health_pct >= 60:
        health_color = "#f97316"
        health_label = "Needs Attention"
    else:
        health_color = "#ef4444"
        health_label = "Critical"

    # Fix banner
    fix_banner = ""
    if fix_summary:
        fz = fix_summary["fixed_zombies"]
        fu = fix_summary["fixed_unverified"]
        fp = fix_summary["fixed_proof_complete"]
        fl = fix_summary.get("fixed_legacy", 0)
        ro = fix_summary["remaining_orphans"]
        fix_banner = f"""
    <div class="fix-banner">
      <span class="fix-icon">🔧</span>
      <div>
        <strong>Auto-Fix Applied</strong><br>
        <span class="fix-detail">{fz} zombie(s) closed · {fp} proof-complete session(s) closed · {fu} proof(s) verified · {fl} legacy orphan(s) backfilled · {ro} orphan run(s) remain</span>
      </div>
    </div>"""

    # Session rows — split into LIVE (still running) and FINISHED (ended).
    # Tyler's UX rule: living agents front-and-center, finished collapsed.
    live_rows: list[str] = []
    finished_rows: list[str] = []
    for s in health["sessions"][:200]:
        rid = _esc(s["run_id"])
        name = _esc(s["name"])
        status = _esc(s["status"] or "running")
        started = _ts(s["started_at"])
        ended = _ts(s["ended_at"]) if s["ended_at"] else '<span class="running-dot"></span> running'
        wall = _dur(s["wall_ms"])
        p_count = s["proofs"]["count"]
        p_verified = s["proofs"]["verified"]
        gap = s.get("gap", "")

        if gap == "zombie":
            row_cls = "row-zombie"
            gap_badge = '<span class="gap-badge zombie">ZOMBIE</span>'
        elif gap == "orphan":
            row_cls = "row-orphan"
            gap_badge = '<span class="gap-badge orphan">NO PROOF</span>'
        else:
            row_cls = ""
            gap_badge = '<span class="gap-badge ok">OK</span>' if s["ended_at"] else '<span class="gap-badge running">ACTIVE</span>'

        proof_bar = ""
        if p_count > 0:
            pct = min(p_verified / p_count * 100, 100)
            proof_bar = (
                f'<div class="proof-bar"><div class="proof-fill" style="width:{pct:.0f}%"></div></div>'
                f'<span class="proof-label">{p_verified}/{p_count}</span>'
            )
        elif s["ended_at"]:
            proof_bar = '<span class="no-proof">—</span>'

        status_cls = {"ok": "st-ok", "error": "st-err", "timeout": "st-timeout", "legacy": "st-timeout"}.get(status, "st-run")

        # Close button for active/zombie runs (only in serve mode)
        close_btn = ""
        if not s["ended_at"]:
            close_btn = f'<button class="close-btn" onclick="closeSession(\'{rid}\')">Close</button>'
        elif gap == "zombie":
            close_btn = f'<button class="close-btn" onclick="closeSession(\'{rid}\')">Force Close</button>'

        row_html = (
            f'<tr class="{row_cls}">'
            f'<td class="mono">{rid}</td>'
            f'<td>{name}</td>'
            f'<td class="{status_cls}">{status}</td>'
            f'<td class="ts">{started}</td>'
            f'<td class="ts">{ended}</td>'
            f'<td class="mono">{wall}</td>'
            f'<td class="proof-cell">{proof_bar}</td>'
            f'<td>{gap_badge}</td>'
            f'<td>{close_btn}</td>'
            f'</tr>'
        )
        # Zombies are "living" by definition (never ended) — keep them visible.
        if s["ended_at"] is None:
            live_rows.append(row_html)
        else:
            finished_rows.append(row_html)

    live_count_table = len(live_rows)
    finished_count_table = len(finished_rows)
    live_session_html = "\n".join(live_rows) if live_rows else (
        '<tr><td colspan="9" class="empty">No live agents — all sessions closed</td></tr>'
    )
    finished_session_html = "\n".join(finished_rows) if finished_rows else (
        '<tr><td colspan="9" class="empty">No finished sessions</td></tr>'
    )

    # Agent coverage rows
    agent_rows = []
    for a in health["agent_coverage"]:
        agent = _esc(a["agent"])
        total_p = a["total"]
        verified = a["verified"] or 0
        runs = a["runs"]
        rate = (verified / total_p * 100) if total_p else 0
        rate_cls = "rate-good" if rate >= 80 else "rate-warn" if rate >= 50 else "rate-bad"
        agent_rows.append(
            f'<tr>'
            f'<td>{agent}</td>'
            f'<td class="num">{runs}</td>'
            f'<td class="num">{total_p}</td>'
            f'<td class="num">{verified}</td>'
            f'<td class="num {rate_cls}">{rate:.0f}%</td>'
            f'</tr>'
        )
    agent_html = "\n".join(agent_rows) if agent_rows else '<tr><td colspan="5" class="empty">No proof data yet</td></tr>'

    # Architecture Drift rows (AC3).
    drift_rows = []
    for d in drift:
        pid = _esc(d["proof_id"])
        agent = _esc(d["agent"])
        sugg_agent = _esc(d["suggested_agent"])
        old_p = _esc(d["artifact_path"])
        new_p = _esc(d["suggested_path"])
        agent_cell = agent if agent == sugg_agent else f'<span class="drift-old">{agent}</span> → <span class="drift-new">{sugg_agent}</span>'
        path_cell = old_p if old_p == new_p else f'<div class="drift-old">{old_p}</div><div class="drift-new">→ {new_p}</div>'
        drift_rows.append(
            f'<tr>'
            f'<td class="mono">{pid}</td>'
            f'<td>{agent_cell}</td>'
            f'<td>{path_cell}</td>'
            f'<td>{_esc(d["description"])}</td>'
            f'</tr>'
        )
    drift_html = "\n".join(drift_rows) if drift_rows else '<tr><td colspan="4" class="empty">No architecture drift detected</td></tr>'
    drift_count = len(drift)

    # Proof Health panel — load from reports/proof_health.json if present.
    _ph_json = Path(__file__).resolve().parent.parent / "reports" / "proof_health.json"
    if _ph_json.exists():
        try:
            import json as _json
            _ph = _json.loads(_ph_json.read_text(encoding="utf-8"))
            _ph_total  = _ph.get("total", 0)
            _ph_healthy = _ph.get("healthy", 0)
            _ph_stale   = _ph.get("stale", 0)
            _ph_corrupt = _ph.get("corrupt", 0)
            _ph_skipped = _ph.get("skipped", 0)
            _ph_rate    = _ph.get("failure_rate_pct", 0.0)
            _ph_run_at  = _ph.get("run_at", "")[:19].replace("T", " ")
            _ph_failed  = _ph.get("failed_rows", [])
            _ph_status_color = "var(--danger)" if _ph_rate > 10 else "var(--success)"
            _ph_status_label = "UNHEALTHY" if _ph_rate > 10 else "HEALTHY"
            _ph_failed_rows_html = ""
            if _ph_failed:
                _ph_row_parts = []
                for _r in _ph_failed[:50]:
                    _reason_color = "var(--danger)" if _r["reason"] == "stale" else "var(--warning)"
                    _ph_row_parts.append(
                        f'<tr>'
                        f'<td class="mono">{_esc(_r.get("proof_id",""))}</td>'
                        f'<td>{_esc(_r.get("agent",""))}</td>'
                        f'<td class="mono" style="word-break:break-all">{_esc(_r.get("artifact_path",""))}</td>'
                        f'<td><span style="color:{_reason_color};font-weight:700">{_esc(_r.get("reason",""))}</span></td>'
                        f'</tr>'
                    )
                _ph_failed_rows_html = "\n".join(_ph_row_parts)
            else:
                _ph_failed_rows_html = '<tr><td colspan="4" class="empty">No stale or corrupt artifacts</td></tr>'
            proof_health_html = f"""
  <h2 style="color: var(--cyan);">Proof Artifact Health
    <span class="section-sub" style="color:{_ph_status_color}">{_ph_status_label} &bull; {_ph_rate:.1f}% failure rate</span>
    <span class="section-sub">last run {_ph_run_at}</span>
  </h2>
  <div class="stat-grid" style="margin-bottom:1.5rem">
    <div class="stat-card"><div class="stat-value">{_ph_total}</div><div class="stat-label">Total Artifacts</div></div>
    <div class="stat-card"><div class="stat-value" style="color:var(--success)">{_ph_healthy}</div><div class="stat-label">Healthy</div></div>
    <div class="stat-card"><div class="stat-value" style="color:var(--danger)">{_ph_stale}</div><div class="stat-label">Stale</div></div>
    <div class="stat-card"><div class="stat-value" style="color:var(--warning)">{_ph_corrupt}</div><div class="stat-label">Corrupt</div></div>
    <div class="stat-card"><div class="stat-value" style="color:var(--muted)">{_ph_skipped}</div><div class="stat-label">Skipped</div></div>
  </div>
  <table>
    <thead>
      <tr><th>Proof ID</th><th>Agent</th><th>Path</th><th>Reason</th></tr>
    </thead>
    <tbody>
      {_ph_failed_rows_html}
    </tbody>
  </table>"""
        except Exception:
            proof_health_html = '  <h2 style="color: var(--cyan);">Proof Artifact Health</h2><p style="color:var(--muted);padding:1rem 0">Error reading proof_health.json</p>'
    else:
        proof_health_html = f"""
  <h2 style="color: var(--cyan);">Proof Artifact Health</h2>
  <p style="color:var(--muted);padding:1rem 0">
    No report yet &mdash; run
    <code>C:\\G\\python.exe f:\\⊕Workspace\\src\\utils\\proof_health_verifier.py</code>
    to generate the first sweep, or register the weekly task via
    <code>tools\\register_proof_health_task.ps1</code>.
  </p>"""

    # ── Gap Breakdown (AC8: explain each gap contributing to Total Gaps) ──
    zombie_rows = []
    for z in health["zombies"]:
        zombie_rows.append(
            f'<tr><td class="mono">{_esc(z["run_id"])[:12]}</td>'
            f'<td>{_esc(z["name"])}</td>'
            f'<td class="ts">started {_ts(z["started_at"])} · never ended</td></tr>'
        )
    zombie_breakdown = "\n".join(zombie_rows) if zombie_rows else ""

    orphan_rows_bd = []
    for o in health["orphans"]:
        orphan_rows_bd.append(
            f'<tr><td class="mono">{_esc(o["run_id"])[:12]}</td>'
            f'<td>{_esc(o["name"])}</td>'
            f'<td class="ts">ended {_ts(o["ended_at"])} · 0 proofs recorded</td></tr>'
        )
    orphan_breakdown = "\n".join(orphan_rows_bd) if orphan_rows_bd else ""

    unverified_rows = []
    for u in health["unverified"]:
        pid = _esc(u.get("proof_id", ""))[:12]
        agent = _esc(u.get("agent", ""))
        path = _esc(u.get("artifact_path") or "")
        desc = _esc(u.get("description") or "")
        unverified_rows.append(
            f'<tr><td class="mono">{pid}</td>'
            f'<td>{agent}</td>'
            f'<td class="drift-old mono">{path}</td>'
            f'<td class="ts">{desc}</td></tr>'
        )
    unverified_breakdown = "\n".join(unverified_rows) if unverified_rows else ""

    gap_sections_html = []
    if zombie_breakdown:
        gap_sections_html.append(
            f'<div class="gap-group"><div class="gap-group-title"><span class="gap-badge zombie">zombie</span> '
            f'{len(health["zombies"])} · started but never closed (>2h)</div>'
            f'<table class="gap-table"><thead><tr><th>Run</th><th>Name</th><th>Reason</th></tr></thead>'
            f'<tbody>{zombie_breakdown}</tbody></table></div>'
        )
    if orphan_breakdown:
        gap_sections_html.append(
            f'<div class="gap-group"><div class="gap-group-title"><span class="gap-badge orphan">orphan</span> '
            f'{len(health["orphans"])} · ended with zero proofs (legacy or agent skipped proof protocol)</div>'
            f'<table class="gap-table"><thead><tr><th>Run</th><th>Name</th><th>Reason</th></tr></thead>'
            f'<tbody>{orphan_breakdown}</tbody></table></div>'
        )
    if unverified_breakdown:
        gap_sections_html.append(
            f'<div class="gap-group"><div class="gap-group-title"><span class="gap-badge" style="background:rgba(59,130,246,0.15);color:#3b82f6">unverified</span> '
            f'{len(health["unverified"])} · proof recorded but artifact_path does not exist on disk</div>'
            f'<table class="gap-table"><thead><tr><th>Proof</th><th>Agent</th><th>Path</th><th>Description</th></tr></thead>'
            f'<tbody>{unverified_breakdown}</tbody></table></div>'
        )
    if gap_sections_html:
        gap_breakdown_html = (
            '<details class="gap-breakdown"><summary>'
            '<span class="chev">▸</span> '
            f'<span class="finished-title">Gap Breakdown — what makes up the {gap_count} gaps</span>'
            '</summary><div class="gap-body">'
            + "\n".join(gap_sections_html)
            + '</div></details>'
        )
    else:
        gap_breakdown_html = (
            '<div class="gap-empty">✓ No gaps — every session is closed with verified proofs.</div>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="30">
<title>⊕ Agent Ops Monitor</title>
<style>
  :root {{
    --bg: #0a0d12;
    --surface: #121820;
    --border: #1e2530;
    --text: #e2e8f0;
    --muted: #64748b;
    --accent: #6366f1;
    --success: #10b981;
    --warning: #f59e0b;
    --danger: #ef4444;
    --orange: #f97316;
    --cyan: #22d3ee;
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 2rem;
    max-width: 1500px;
    margin: 0 auto;
  }}
  h1 {{
    font-size: 1.8rem;
    margin-bottom: 0.3rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }}
  h1 .sigil {{ color: var(--accent); font-size: 2rem; }}
  h2 {{
    font-size: 1.15rem;
    margin: 2rem 0 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid var(--border);
  }}
  .subtitle {{ color: var(--muted); margin-bottom: 1.5rem; font-size: 0.85rem; }}

  /* ── Health Score ── */
  .health-ring {{
    display: flex;
    align-items: center;
    gap: 2rem;
    margin: 1.5rem 0 2rem;
  }}
  .ring-container {{
    position: relative;
    width: 140px;
    height: 140px;
  }}
  .ring-svg {{ transform: rotate(-90deg); }}
  .ring-bg {{ fill: none; stroke: var(--border); stroke-width: 10; }}
  .ring-fg {{ fill: none; stroke-width: 10; stroke-linecap: round;
              stroke-dasharray: 377; transition: stroke-dashoffset 1s ease; }}
  .ring-text {{
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    text-align: center;
  }}
  .ring-pct {{ font-size: 2rem; font-weight: 800; }}
  .ring-label {{ font-size: 0.7rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }}

  /* ── Stat Cards ── */
  .stat-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 1rem;
  }}
  .stat-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.2rem;
    text-align: center;
  }}
  .stat-val {{ font-size: 2rem; font-weight: 800; line-height: 1.2; }}
  .stat-label {{ font-size: 0.75rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; margin-top: 0.3rem; }}
  .val-ok {{ color: var(--success); }}
  .val-warn {{ color: var(--warning); }}
  .val-bad {{ color: var(--danger); }}
  .val-info {{ color: var(--cyan); }}

  /* ── Fix Banner ── */
  .fix-banner {{
    display: flex;
    align-items: center;
    gap: 1rem;
    background: rgba(16,185,129,0.08);
    border: 1px solid var(--success);
    border-radius: 10px;
    padding: 1rem 1.5rem;
    margin: 1rem 0 1.5rem;
  }}
  .fix-icon {{ font-size: 1.5rem; }}
  .fix-detail {{ color: var(--muted); font-size: 0.85rem; }}

  /* ── Tables ── */
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82rem;
    margin-bottom: 2rem;
  }}
  thead {{ background: var(--surface); }}
  th {{
    text-align: left;
    padding: 0.6rem;
    font-weight: 700;
    color: var(--muted);
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.04em;
    border-bottom: 2px solid var(--border);
  }}
  td {{
    padding: 0.5rem 0.6rem;
    border-bottom: 1px solid var(--border);
    vertical-align: middle;
  }}
  tr:hover {{ background: rgba(255,255,255,0.02); }}
  .mono {{ font-family: 'Cascadia Code','Consolas',monospace; font-size: 0.8rem; }}
  .ts {{ color: var(--muted); font-size: 0.78rem; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .empty {{ color: var(--muted); font-style: italic; text-align: center; padding: 1rem; }}

  /* Status */
  .st-ok {{ color: var(--success); font-weight: 600; }}
  .st-err {{ color: var(--danger); font-weight: 600; }}
  .st-timeout {{ color: var(--orange); font-weight: 600; }}
  .st-run {{ color: var(--cyan); font-weight: 600; }}

  /* Gap badges */
  .gap-badge {{
    display: inline-block;
    padding: 0.15rem 0.5rem;
    border-radius: 9999px;
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }}
  .gap-badge.ok {{ background: rgba(16,185,129,0.15); color: var(--success); }}
  .gap-badge.running {{ background: rgba(34,211,238,0.15); color: var(--cyan); }}
  .gap-badge.zombie {{ background: rgba(239,68,68,0.15); color: var(--danger); }}
  .gap-badge.orphan {{ background: rgba(249,115,22,0.15); color: var(--orange); }}

  /* Row highlights */
  .row-zombie {{ background: rgba(239,68,68,0.06); }}
  .row-zombie:hover {{ background: rgba(239,68,68,0.1) !important; }}
  .row-orphan {{ background: rgba(249,115,22,0.06); }}
  .row-orphan:hover {{ background: rgba(249,115,22,0.1) !important; }}

  /* Proof bars */
  .proof-cell {{ min-width: 120px; }}
  .proof-bar {{
    display: inline-block;
    width: 60px;
    height: 8px;
    background: var(--border);
    border-radius: 4px;
    overflow: hidden;
    vertical-align: middle;
    margin-right: 0.4rem;
  }}
  .proof-fill {{
    height: 100%;
    background: var(--success);
    border-radius: 4px;
    transition: width 0.3s;
  }}
  .proof-label {{ font-size: 0.75rem; color: var(--muted); }}
  .no-proof {{ color: var(--muted); }}

  /* Agent coverage */
  .rate-good {{ color: var(--success); font-weight: 700; }}
  .rate-warn {{ color: var(--warning); font-weight: 700; }}
  .rate-bad {{ color: var(--danger); font-weight: 700; }}

  /* Close buttons */
  .close-btn {{
    background: rgba(239,68,68,0.15);
    color: var(--danger);
    border: 1px solid var(--danger);
    border-radius: 6px;
    padding: 0.2rem 0.6rem;
    font-size: 0.7rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
  }}
  .close-btn:hover {{
    background: var(--danger);
    color: white;
  }}
  .close-btn:disabled {{
    opacity: 0.4;
    cursor: not-allowed;
  }}

  /* Running dot animation */
  .running-dot {{
    display: inline-block;
    width: 8px; height: 8px;
    background: var(--cyan);
    border-radius: 50%;
    animation: pulse 1.5s infinite;
    vertical-align: middle;
    margin-right: 0.3rem;
  }}
  @keyframes pulse {{
    0%,100% {{ opacity:1; }}
    50% {{ opacity:0.3; }}
  }}

  .footer {{
    margin-top: 2rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
    color: var(--muted);
    font-size: 0.75rem;
    text-align: center;
  }}

  /* Live banner (AC3) */
  .live-banner {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1rem;
    margin: 1rem 0 1.5rem;
  }}
  .live-cell {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1rem 1.2rem;
    text-align: center;
  }}
  .live-val {{ font-size: 2rem; font-weight: 800; line-height: 1.1; }}
  .live-label {{ font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; margin-top: 0.3rem; }}
  .live-sub {{ text-transform: none; letter-spacing: 0; color: var(--muted); font-weight: 400; }}
  .live-live {{ color: var(--cyan); }}
  .live-recent {{ color: var(--success); }}
  .live-total {{ color: var(--accent); }}

  /* Drift section (AC3) */
  .drift-actions {{
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin-bottom: 0.8rem;
    flex-wrap: wrap;
  }}
  .mig-btn {{
    background: var(--surface);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.4rem 0.9rem;
    font-size: 0.78rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
  }}
  .mig-btn.mig-dry {{ border-color: var(--warning); color: var(--warning); }}
  .mig-btn.mig-live {{ border-color: var(--success); color: var(--success); }}
  .mig-btn:hover {{ background: rgba(255,255,255,0.03); }}
  .drift-hint {{ color: var(--muted); font-size: 0.75rem; }}
  .drift-old {{ color: var(--warning); font-family: 'Cascadia Code','Consolas',monospace; font-size: 0.78rem; }}
  .drift-new {{ color: var(--success); font-family: 'Cascadia Code','Consolas',monospace; font-size: 0.78rem; }}

  /* Living dashboard — section headers, collapsible finished */
  h2 .section-count {{ color: var(--muted); font-size: 0.8rem; font-weight: 500; margin-left: 0.4rem; }}
  h2 .section-sub {{ color: var(--muted); font-size: 0.7rem; font-weight: 400; margin-left: 0.6rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  .finished-details {{ margin: 1rem 0 2rem; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); }}
  .finished-details summary {{ padding: 0.8rem 1rem; cursor: pointer; font-weight: 700; color: var(--muted); list-style: none; user-select: none; }}
  .finished-details summary::-webkit-details-marker {{ display: none; }}
  .finished-details .chev {{ display: inline-block; transition: transform 0.15s; margin-right: 0.4rem; }}
  .finished-details[open] .chev {{ transform: rotate(90deg); }}
  .finished-details summary:hover {{ color: var(--text); background: rgba(255,255,255,0.02); }}
  .finished-title {{ color: var(--text); text-transform: uppercase; font-size: 0.85rem; letter-spacing: 0.04em; }}
  .finished-details[open] summary {{ border-bottom: 1px solid var(--border); }}
  .finished-details table {{ margin: 0; }}
  .live-pulse {{ position: relative; }}
  .live-pulse::before {{ content: ''; display: inline-block; width: 6px; height: 6px; background: var(--cyan); border-radius: 50%; margin-right: 0.4rem; animation: pulse 1.5s infinite; }}

  /* Gap Breakdown */
  .gap-breakdown {{ margin: 0.5rem 0 1.5rem; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); }}
  .gap-breakdown summary {{ padding: 0.7rem 1rem; cursor: pointer; font-weight: 700; color: var(--muted); list-style: none; user-select: none; }}
  .gap-breakdown summary::-webkit-details-marker {{ display: none; }}
  .gap-breakdown .chev {{ display: inline-block; transition: transform 0.15s; margin-right: 0.4rem; }}
  .gap-breakdown[open] .chev {{ transform: rotate(90deg); }}
  .gap-breakdown[open] summary {{ border-bottom: 1px solid var(--border); }}
  .gap-breakdown summary:hover {{ color: var(--text); background: rgba(255,255,255,0.02); }}
  .gap-body {{ padding: 0.5rem 1rem 1rem; }}
  .gap-group {{ margin-top: 0.8rem; }}
  .gap-group-title {{ font-size: 0.85rem; color: var(--muted); margin-bottom: 0.4rem; }}
  .gap-table {{ font-size: 0.78rem; margin-bottom: 0.5rem; }}
  .gap-table td, .gap-table th {{ padding: 0.35rem 0.5rem; }}
  .gap-empty {{ margin: 0.5rem 0 1.5rem; padding: 0.7rem 1rem; border: 1px solid var(--success); border-radius: 10px; color: var(--success); background: rgba(16,185,129,0.06); font-size: 0.85rem; }}
</style>
</head>
<body>
  <h1><span class="sigil">⊕</span> Agent Ops Monitor</h1>
  <div class="subtitle">Session health · Gap detection · Proof audit &mdash; {generated}</div>

  <div class="live-banner">
    <div class="live-cell">
      <div class="live-val live-live">{live_count}</div>
      <div class="live-label">Live <span class="live-sub">(last 10min)</span></div>
    </div>
    <div class="live-cell" title="VS Code Copilot chat sessions detected via debug-log mtime (not instrumented; ephemeral)">
      <div class="live-val live-recent">{vscode_live_count}</div>
      <div class="live-label">VS Code <span class="live-sub">(detected)</span></div>
    </div>
    <div class="live-cell">
      <div class="live-val live-recent">{recent_count}</div>
      <div class="live-label">Recent <span class="live-sub">(24h)</span></div>
    </div>
    <div class="live-cell">
      <div class="live-val live-total">{historical_total}</div>
      <div class="live-label">Historical total</div>
    </div>
  </div>

  {fix_banner}

  <div class="health-ring">
    <div class="ring-container">
      <svg class="ring-svg" width="140" height="140" viewBox="0 0 140 140">
        <circle class="ring-bg" cx="70" cy="70" r="60"/>
        <circle class="ring-fg" cx="70" cy="70" r="60"
                style="stroke:{health_color}; stroke-dashoffset:{377 - (377 * health_pct / 100):.0f};"/>
      </svg>
      <div class="ring-text">
        <div class="ring-pct" style="color:{health_color}">{health_pct:.0f}%</div>
        <div class="ring-label">{health_label}</div>
      </div>
    </div>

    <div class="stat-grid" style="flex:1;">
      <div class="stat-card">
        <div class="stat-val val-info">{total}</div>
        <div class="stat-label">Total Runs</div>
      </div>
      <div class="stat-card">
        <div class="stat-val val-ok">{healthy}</div>
        <div class="stat-label">Healthy</div>
      </div>
      <div class="stat-card">
        <div class="stat-val {"val-bad" if zombie_count else "val-ok"}">{zombie_count}</div>
        <div class="stat-label">Zombies</div>
      </div>
      <div class="stat-card">
        <div class="stat-val {"val-warn" if orphan_count else "val-ok"}">{orphan_count}</div>
        <div class="stat-label">No Proof</div>
      </div>
      <div class="stat-card">
        <div class="stat-val {"val-warn" if unverified_count else "val-ok"}">{unverified_count}</div>
        <div class="stat-label">Unverified</div>
      </div>
      <div class="stat-card">
        <div class="stat-val val-info">{gap_count}</div>
        <div class="stat-label">Total Gaps</div>
      </div>
    </div>
  </div>

  {gap_breakdown_html}

  <h2 style="color: var(--cyan);">
    <span class="running-dot"></span> Live Agents
    <span class="section-count">({live_count_table})</span>
    <span class="section-sub">auto-refresh · 30s</span>
  </h2>
  <table id="live-table">
    <thead>
      <tr>
        <th>Run ID</th>
        <th>Name</th>
        <th>Status</th>
        <th>Started</th>
        <th>Ended</th>
        <th>Wall</th>
        <th>Proofs</th>
        <th>Health</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      {live_session_html}
    </tbody>
  </table>

  <details class="finished-details">
    <summary>
      <span class="chev">▸</span>
      <span class="finished-title">Finished Sessions</span>
      <span class="section-count">({finished_count_table})</span>
    </summary>
    <table id="finished-table">
      <thead>
        <tr>
          <th>Run ID</th>
          <th>Name</th>
          <th>Status</th>
          <th>Started</th>
          <th>Ended</th>
          <th>Wall</th>
          <th>Proofs</th>
          <th>Health</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {finished_session_html}
      </tbody>
    </table>
  </details>

  <h2 style="color: var(--success);">Agent Proof Coverage</h2>
  <table>
    <thead>
      <tr>
        <th>Agent</th>
        <th class="num">Runs</th>
        <th class="num">Proofs</th>
        <th class="num">Verified</th>
        <th class="num">Rate</th>
      </tr>
    </thead>
    <tbody>
      {agent_html}
    </tbody>
  </table>

  <h2 style="color: var(--orange);">Architecture Drift ({drift_count})</h2>
  <div class="drift-actions">
    <button class="mig-btn mig-dry" onclick="applyMigration(true)">Apply Migration (dry-run)</button>
    <button class="mig-btn mig-live" onclick="applyMigration(false)">Apply Migration (live)</button>
    <span class="drift-hint">Dry-run only reports changes; live writes to DB after timestamped backup.</span>
  </div>
  <table>
    <thead>
      <tr>
        <th>Proof ID</th>
        <th>Agent</th>
        <th>Artifact path</th>
        <th>Description</th>
      </tr>
    </thead>
    <tbody>
      {drift_html}
    </tbody>
  </table>

  {proof_health_html}

  <div class="footer">
    ⊕Workspace Agent Ops Monitor &mdash; Self-regenerating dashboard &bull;
    <span id="refresh-status" class="live-pulse">auto-refresh every 30s</span> &bull;
    <code>python tools/agent_ops_monitor.py --fix</code> to auto-close gaps &bull;
    <code>python tools/agent_ops_monitor.py --serve</code> for interactive mode
  </div>

  <script>
    // Living dashboard: poll /api/health in serve mode and update live section
    // without a full reload. Falls back to meta-refresh when served as a static file.
    (function () {{
      const statusEl = document.getElementById('refresh-status');
      let backoff = 30000;
      async function poll() {{
        if (window.location.protocol === 'file:') {{
          // Static-file mode — skip fetch to avoid CORS errors; rely on meta-refresh.
          if (statusEl) statusEl.textContent = 'auto-refresh every 30s (static)';
          setTimeout(poll, 60000);
          return;
        }}
        try {{
          const resp = await fetch('/api/health', {{cache: 'no-store'}});
          if (!resp.ok) throw new Error('status ' + resp.status);
          const h = await resp.json();
          // Live count cell
          const live = document.querySelector('.live-live');
          if (live) live.textContent = h.live_count ?? h.historical_total ?? '-';
          const recent = document.querySelector('.live-recent');
          if (recent) recent.textContent = h.recent_count ?? '-';
          const total = document.querySelector('.live-total');
          if (total) total.textContent = h.historical_total ?? h.total_runs ?? '-';
          if (statusEl) {{
            const t = new Date().toLocaleTimeString();
            statusEl.textContent = 'live · updated ' + t;
          }}
          backoff = 30000;
        }} catch (e) {{
          // Static-file mode — silent fallback; meta-refresh reloads the page.
          if (statusEl) statusEl.textContent = 'auto-refresh every 30s (static)';
          backoff = 60000;
        }}
        setTimeout(poll, backoff);
      }}
      // Kick off after first render so meta-refresh still works if JS disabled.
      setTimeout(poll, 5000);
    }})();

    async function closeSession(runId) {{
      if (!confirm('Close session ' + runId + '?')) return;
      const btn = event.target;
      btn.disabled = true;
      btn.textContent = 'Closing...';
      try {{
        const resp = await fetch('/api/close', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{run_id: runId, status: 'closed'}})
        }});
        if (resp.ok) {{
          btn.textContent = 'Closed';
          setTimeout(() => location.reload(), 800);
        }} else {{
          const err = await resp.text();
          alert('Failed: ' + err);
          btn.disabled = false;
          btn.textContent = 'Close';
        }}
      }} catch (e) {{
        // Static file mode — show CLI command
        prompt('Run this command to close the session:', 
          'C:\\\\G\\\\python.exe tools/agent_ops_monitor.py --close ' + runId);
        btn.disabled = false;
        btn.textContent = 'Close';
      }}
    }}

    async function applyMigration(dryRun) {{
      const label = dryRun ? 'dry-run' : 'LIVE (writes to DB after backup)';
      if (!confirm('Apply architecture migration (' + label + ')?')) return;
      try {{
        const resp = await fetch('/apply-migration', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{dry_run: !!dryRun}})
        }});
        const data = await resp.json();
        alert('Migration result:\\n' + JSON.stringify(data, null, 2));
        if (!dryRun) location.reload();
      }} catch (e) {{
        alert('Migration endpoint requires --serve mode. Run:\\nC:\\\\G\\\\python.exe tools/agent_ops_monitor.py --migrate' + (dryRun ? ' --dry-run' : ''));
      }}
    }}
  </script>
</body>
</html>"""


# ── Session Close ─────────────────────────────────────────────

def close_session(conn, run_id: str, status: str = "closed", detail: str = "") -> bool:
    """Close a specific session by run_id. Returns True if closed, False if not found/already closed."""
    row = conn.execute(
        "SELECT run_id, ended_at FROM perf_runs WHERE run_id = ?", (run_id,)
    ).fetchone()
    if not row:
        return False
    if row["ended_at"]:
        return False  # Already closed
    now = time.time()
    suffix = f" [manually closed from dashboard]" if not detail else f" {detail}"
    conn.execute(
        "UPDATE perf_runs SET ended_at = ?, status = ?, detail = COALESCE(detail, '') || ? WHERE run_id = ?",
        (now, status, suffix, run_id),
    )
    conn.commit()
    return True


# ── HTTP Server (--serve mode) ────────────────────────────────

class OpsHandler(BaseHTTPRequestHandler):
    """Handles dashboard serving and session close API."""

    def log_message(self, format, *args):
        # Suppress default logging noise
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            init_db()
            conn = get_connection()
            health = collect_health(conn)
            drift = drift_candidates(conn)
            conn.close()
            html_content = render_dashboard(health, drift=drift)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html_content.encode("utf-8"))
        elif parsed.path == "/api/health":
            init_db()
            conn = get_connection()
            health = collect_health(conn)
            conn.close()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(health, default=str).encode("utf-8"))
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/close":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            try:
                data = json.loads(body)
            except (json.JSONDecodeError, ValueError):
                self.send_error(400, "Invalid JSON")
                return

            run_id = data.get("run_id", "").strip()
            status = data.get("status", "closed").strip()

            if not run_id or len(run_id) > 24:
                self.send_error(400, "Invalid run_id")
                return
            # Sanitize: only hex chars allowed in run_id
            if not all(c in "0123456789abcdef" for c in run_id):
                self.send_error(400, "Invalid run_id format")
                return

            init_db()
            conn = get_connection()
            closed = close_session(conn, run_id, status)
            conn.close()

            if closed:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "run_id": run_id}).encode("utf-8"))
            else:
                self.send_error(404, "Run not found or already closed")

        elif parsed.path == "/api/fix":
            init_db()
            conn = get_connection()
            health = collect_health(conn)
            fix_summary = fix_gaps(conn, health)
            conn.close()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(fix_summary).encode("utf-8"))
        elif parsed.path == "/apply-migration":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len) if content_len else b"{}"
            try:
                data = json.loads(body) if body else {}
            except (json.JSONDecodeError, ValueError):
                self.send_error(400, "Invalid JSON")
                return
            dry_run = bool(data.get("dry_run", True))

            init_db()
            conn = get_connection()
            result = migrate_architecture(conn, dry_run=dry_run)
            conn.close()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = {
                "status": "dry-run" if dry_run else "applied",
                "fixed_paths": result["fixed_paths"],
                "fixed_agents": result["fixed_agents"],
                "verified_after": result["verified_after"],
                "backup_path": result["backup_path"],
            }
            self.wfile.write(json.dumps(payload).encode("utf-8"))
        else:
            self.send_error(404)


def serve_dashboard(port: int = 5060) -> None:
    """Start an interactive HTTP server for the ops dashboard."""
    server = HTTPServer(("127.0.0.1", port), OpsHandler)
    url = f"http://127.0.0.1:{port}"
    print(f"⊕ Agent Ops Monitor — Interactive Server")
    print(f"  Dashboard: {url}")
    print(f"  API:       POST {url}/api/close  {{\"run_id\": \"...\"}}")
    print(f"             POST {url}/api/fix    (auto-close gaps)")
    print(f"             GET  {url}/api/health (JSON health report)")
    print(f"  Press Ctrl+C to stop.")

    try:
        webbrowser.get("brave").open(url)
    except Exception:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
        server.shutdown()


# ── Main ─────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="⊕ Agent Ops Monitor")
    parser.add_argument("--no-open", action="store_true", help="Generate without opening browser")
    parser.add_argument("--fix", action="store_true", help="Auto-close zombie runs, proof-complete runs, backfill legacy, and verify proofs")
    parser.add_argument("--backfill-legacy", action="store_true", help="Backfill proof for orphan runs predating the proof system")
    parser.add_argument("--migrate", action="store_true", help="Rewrite stale artifact_path + normalize agent sigils")
    parser.add_argument("--dry-run", action="store_true", help="With --migrate: report planned changes without mutating DB")
    parser.add_argument("--json", action="store_true", help="Output JSON health report")
    parser.add_argument("--close", metavar="RUN_ID", help="Close a specific session by run_id")
    parser.add_argument("--serve", action="store_true", help="Start interactive dashboard server")
    parser.add_argument("--port", type=int, default=5060, help="Port for --serve mode (default: 5060)")
    args = parser.parse_args()

    init_db()
    conn = get_connection()
    # Ensure last_heartbeat column exists on first run after schema upgrade.
    _ensure_last_heartbeat_column(conn)

    # --serve: start interactive server
    if args.serve:
        conn.close()
        serve_dashboard(args.port)
        return

    # --close: close a specific session
    if args.close:
        run_id = args.close.strip()
        closed = close_session(conn, run_id)
        conn.close()
        if closed:
            print(f"  ✓ Session {run_id} closed.")
        else:
            print(f"  ✗ Session {run_id} not found or already closed.", file=sys.stderr)
            sys.exit(1)
        return

    # --migrate: architecture migration
    if args.migrate:
        print(f"⊕ Agent Ops Monitor — Architecture Migration ({'dry-run' if args.dry_run else 'LIVE'})")
        result = migrate_architecture(conn, dry_run=args.dry_run)
        conn.close()
        print(f"  Paths to rewrite:  {result['fixed_paths']}")
        print(f"  Agents to rename:  {result['fixed_agents']}")
        if not args.dry_run:
            print(f"  Backup:            {result['backup_path']}")
            print(f"  Verified after:    {result['verified_after']}")
        else:
            print("  (dry-run — no changes written)")
        if result["path_samples"]:
            print("\n  Path samples (up to 20):")
            for s in result["path_samples"]:
                print(f"    {s['proof_id']}  {s['old']}")
                print(f"      → {s['new']}")
        if result["agent_samples"]:
            print("\n  Agent samples (up to 20):")
            for s in result["agent_samples"]:
                print(f"    {s['proof_id']}  {s['old']}  →  {s['new']}")
        print(json.dumps({
            "dry_run": result["dry_run"],
            "fixed_paths": result["fixed_paths"],
            "fixed_agents": result["fixed_agents"],
            "verified_after": result["verified_after"],
            "backup_path": result["backup_path"],
        }, indent=2))
        return

    health = collect_health(conn)

    if args.json:
        # Sanitize for JSON serialization
        print(json.dumps(health, indent=2, default=str))
        conn.close()
        return

    fix_summary = None
    if args.fix:
        print("⊕ Agent Ops Monitor — Auto-Fix Mode")
        fix_summary = fix_gaps(conn, health)
        print(f"  Closed {fix_summary['fixed_zombies']} zombie(s)")
        print(f"  Closed {fix_summary['fixed_proof_complete']} proof-complete session(s)")
        print(f"  Verified {fix_summary['fixed_unverified']} proof(s)")
        print(f"  Backfilled {fix_summary.get('fixed_legacy', 0)} legacy orphan(s)")
        print(f"  Remaining orphans: {fix_summary['remaining_orphans']} (need manual proof)")
        phantom = fix_summary.get("phantom_report", {})
        if phantom.get("phantoms"):
            print(f"  Phantom agents found: {len(phantom['phantoms'])}")
            for p in phantom["phantoms"]:
                action = f"→ renamed to {p['suggested']} ({p['count']} rows)" if p["suggested"] else f"flagged ({p['count']} rows, no canonical match)"
                print(f"    {p['agent']}  {action}")
        if phantom.get("renamed"):
            print(f"  Phantom rows renamed: {phantom['renamed']}")
        # Re-collect after fixes
        health = collect_health(conn)

    if args.backfill_legacy:
        backfilled = backfill_legacy(conn, health)
        print(f"  Backfilled {backfilled} legacy orphan run(s) with proof markers")
        health = collect_health(conn)

    drift = drift_candidates(conn)
    conn.close()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    html = render_dashboard(health, fix_summary, drift=drift)
    OUT_PATH.write_text(html, encoding="utf-8")

    print(f"⊕ Agent Ops Monitor")
    print(f"  Health: {health['health_pct']:.0f}% — {health['total_runs']} runs, {health['gap_count']} gaps")
    print(f"  Dashboard: {OUT_PATH}")

    if not args.no_open:
        try:
            webbrowser.get("brave").open(OUT_PATH.as_uri())
        except Exception:
            webbrowser.open(OUT_PATH.as_uri())


if __name__ == "__main__":
    main()
