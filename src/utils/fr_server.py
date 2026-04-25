"""
FR Server — Live Feature Request Ledger Panel
==============================================
Lightweight HTTP server (stdlib only) that:
  - Serves fr_dashboard.html at /
  - Exposes GET /api/frs  → JSON list of parsed FRs
  - Exposes POST /signoff → approves a GitHub PR via GITHUB_TOKEN
  - Watches FEATURE_REQUESTS.md + FR_LEDGERS/ and regenerates the dashboard HTML on change

Usage:
    C:\\G\\python.exe f:\\⊕Workspace\\src\\utils\\fr_server.py [--port 7474]

Port 7474 is the default. The server checks if the port is already in use and
exits gracefully if another instance is running.
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import re
import socket
import sys
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path
from typing import Any

# ── Paths ─────────────────────────────────────────────────────────────────────

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent  # f:\⊕Workspace
GITHUB_ROOT = WORKSPACE_ROOT / ".github"
REGISTRY_FILE = GITHUB_ROOT / "FEATURE_REQUESTS.md"
LEDGERS_DIR = GITHUB_ROOT / "FR_LEDGERS"
DASHBOARD_HTML = WORKSPACE_ROOT / "reports" / "fr_dashboard.html"
TEMPLATES_DIR = Path(__file__).resolve().parent  # same dir for template snippets

# ── GitHub defaults ────────────────────────────────────────────────────────────

GH_OWNER = "tylerdrakemusic"
GH_REPO = "-Workspace"

# ── State machine for active-vs-archived ─────────────────────────────────────

ACTIVE_STATES = {
    "OPEN", "TRIAGED", "BRANCHED", "IN_PROGRESS",
    "REVIEW_REQUESTED", "AUTO_REVIEWED", "TYLER_APPROVED", "CHANGES_REQUESTED",
    "SOAKING",
}
SIGNOFF_ELIGIBLE_STATES = {"REVIEW_REQUESTED", "AUTO_REVIEWED", "TYLER_APPROVED"}


# ─────────────────────────────────────────────────────────────────────────────
# FR Parsing
# ─────────────────────────────────────────────────────────────────────────────

def _extract_pr_number(pr_field: str) -> int | None:
    """Return the first PR number found in a markdown PR field, or None."""
    # Matches [#23] or #23 patterns
    m = re.search(r"#(\d+)", pr_field)
    if m:
        return int(m.group(1))
    return None


def _state_class(state: str) -> str:
    """Map FR state to CSS class name."""
    mapping = {
        "MERGED": "state-done",
        "CLOSED": "state-muted",
        "SIGNED_OFF": "state-done",
        "DONE": "state-done",
        "SOAKING": "state-soak",
        "REVIEW_REQUESTED": "state-info",
        "AUTO_REVIEWED": "state-info",
        "TYLER_APPROVED": "state-ok",
        "IN_PROGRESS": "state-warn",
        "BRANCHED": "state-warn",
        "TRIAGED": "state-warn",
        "OPEN": "state-warn",
        "CHANGES_REQUESTED": "state-danger",
    }
    return mapping.get(state.upper(), "state-muted")


def parse_feature_requests(registry_path: Path) -> list[dict[str, Any]]:
    """
    Parse FEATURE_REQUESTS.md and return a list of FR dicts.

    Each dict has keys: id, title, type, projects, state, branch, prs, pr_number,
    owner, opened, updated, is_active, signoff_eligible, state_class.
    """
    if not registry_path.exists():
        return []

    text = registry_path.read_text(encoding="utf-8")
    frs: list[dict[str, Any]] = []

    # Find all markdown table rows (skip header / separator lines)
    row_re = re.compile(
        r"^\|\s*(?P<id>FR-[\w-]+)\s*\|"
        r"\s*(?P<title>[^|]*?)\s*\|"
        r"\s*(?P<type>[^|]*?)\s*\|"
        r"\s*(?P<projects>[^|]*?)\s*\|"
        r"\s*(?P<state>[^|]*?)\s*\|"
        r"\s*(?P<branch>[^|]*?)\s*\|"
        r"\s*(?P<prs>[^|]*?)\s*\|"
        r"\s*(?P<owner>[^|]*?)\s*\|"
        r"\s*(?P<opened>[^|]*?)\s*\|"
        r"\s*(?P<updated>[^|]*?)\s*\|",
        re.MULTILINE,
    )

    for m in row_re.finditer(text):
        state = m.group("state").strip()
        prs_raw = m.group("prs").strip()
        pr_num = _extract_pr_number(prs_raw)
        is_active = state.upper() in ACTIVE_STATES
        signoff_eligible = (
            state.upper() in SIGNOFF_ELIGIBLE_STATES and pr_num is not None
        )
        frs.append(
            {
                "id": m.group("id").strip(),
                "title": m.group("title").strip(),
                "type": m.group("type").strip(),
                "projects": m.group("projects").strip(),
                "state": state,
                "branch": m.group("branch").strip(),
                "prs": prs_raw,
                "pr_number": pr_num,
                "owner": m.group("owner").strip(),
                "opened": m.group("opened").strip(),
                "updated": m.group("updated").strip(),
                "is_active": is_active,
                "signoff_eligible": signoff_eligible,
                "state_class": _state_class(state),
            }
        )

    return frs


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard HTML Generation
# ─────────────────────────────────────────────────────────────────────────────

_CSS = """
:root {
  --bg: #0a0d12; --surface: #151a22; --surface-2: #1b2230;
  --border: #1e2530; --accent: #6366f1; --text: #e2e8f0; --muted: #64748b;
  --ok: #10b981; --warn: #f59e0b; --danger: #ef4444; --info: #60a5fa;
  --soak: #a78bfa; --done: #34d399;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  background: var(--bg); color: var(--text);
  padding: 1.5rem; min-height: 100vh;
}
h1 { font-size: 1.35rem; font-weight: 700; margin-bottom: 0.25rem; }
h1 .sigil { color: var(--accent); margin-right: 0.3rem; }
.subtitle { color: var(--muted); font-size: 0.78rem; margin-bottom: 0.5rem; }
.status-bar {
  display: flex; align-items: center; gap: 0.75rem;
  font-size: 0.72rem; margin-bottom: 1rem;
}
.dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.dot-ok { background: var(--ok); box-shadow: 0 0 6px var(--ok); }
.dot-warn { background: var(--warn); }
.dot-danger { background: var(--danger); box-shadow: 0 0 6px var(--danger); }
.refreshed { color: var(--muted); margin-left: auto; }
.banner {
  padding: 0.6rem 0.9rem; border-radius: 6px; margin-bottom: 1rem;
  font-size: 0.8rem; font-weight: 600;
}
.banner-warn {
  background: rgba(245,158,11,0.12); border: 1px solid rgba(245,158,11,0.4);
  color: var(--warn);
}
.banner-danger {
  background: rgba(239,68,68,0.12); border: 1px solid rgba(239,68,68,0.4);
  color: var(--danger);
}
.banner-ok {
  background: rgba(52,211,153,0.12); border: 1px solid rgba(52,211,153,0.4);
  color: var(--done);
}
.section-title {
  font-size: 0.78rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.08em; color: var(--muted);
  margin: 1.5rem 0 0.6rem; display: flex; align-items: center; gap: 0.5rem;
}
.section-title .count {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; padding: 0.05rem 0.5rem; font-size: 0.7rem; color: var(--text);
}
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 0.9rem; }
.fr-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; padding: 0.85rem 0.95rem;
  display: flex; flex-direction: column; gap: 0.55rem;
  transition: border-color .15s;
}
.fr-card:hover { border-color: var(--accent); }
.fr-top { display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; }
.fr-id {
  font-family: 'Cascadia Code', 'Consolas', monospace;
  font-size: 0.72rem; color: var(--muted); letter-spacing: 0.02em;
}
.fr-badges { display: flex; gap: 0.35rem; align-items: center; flex-wrap: wrap; }
.state-badge {
  font-size: 0.62rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.05em; padding: 0.18rem 0.45rem; border-radius: 4px; white-space: nowrap;
}
.state-ok    { background: rgba(16,185,129,0.16); color: var(--ok); }
.state-warn  { background: rgba(245,158,11,0.16); color: var(--warn); }
.state-danger{ background: rgba(239,68,68,0.16);  color: var(--danger); }
.state-info  { background: rgba(96,165,250,0.16); color: var(--info); }
.state-soak  { background: rgba(167,139,250,0.18); color: var(--soak); }
.state-done  { background: rgba(52,211,153,0.18); color: var(--done); }
.state-muted { background: var(--surface-2); color: var(--muted); }
.fr-title { font-size: 0.98rem; font-weight: 700; line-height: 1.25; }
.fr-meta {
  display: flex; flex-direction: column; gap: 0.2rem;
  border-top: 1px solid var(--border); padding-top: 0.5rem; font-size: 0.72rem;
}
.meta-row { display: flex; justify-content: space-between; gap: 0.5rem; }
.meta-key { color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; font-size: 0.66rem; }
.meta-val { color: var(--text); text-align: right; overflow: hidden; text-overflow: ellipsis; max-width: 65%; }
.meta-val code {
  background: var(--surface-2); padding: 0.05rem 0.35rem;
  border-radius: 3px; font-size: 0.7rem; color: #a5f3fc; word-break: break-all;
}
.meta-val a { color: var(--accent); text-decoration: none; }
.meta-val a:hover { text-decoration: underline; }
.approve-btn {
  background: var(--soak); color: #0a0d12;
  border: none; border-radius: 4px;
  padding: 0.35rem 0.75rem; font-size: 0.72rem; font-weight: 700;
  cursor: pointer; white-space: nowrap; transition: filter .1s;
  width: 100%; margin-top: 0.3rem;
}
.approve-btn:hover { filter: brightness(1.15); }
.approve-btn:active { filter: brightness(0.9); }
.approve-btn:disabled { opacity: 0.45; cursor: not-allowed; filter: none; }
.fr-foot {
  font-size: 0.72rem; border-top: 1px solid var(--border);
  padding-top: 0.4rem; text-align: right;
}
.fr-foot a { color: var(--accent); text-decoration: none; }
.fr-foot a:hover { text-decoration: underline; }
details.archive { margin-top: 1rem; }
details.archive > summary {
  cursor: pointer; padding: 0.5rem 0; color: var(--muted);
  font-size: 0.8rem; font-weight: 600; list-style: none;
}
details.archive > summary::before { content: '▸ '; display: inline-block; transition: transform .15s; }
details.archive[open] > summary::before { transform: rotate(90deg); }
.empty {
  padding: 1.5rem; text-align: center; color: var(--muted);
  background: var(--surface); border: 1px dashed var(--border); border-radius: 8px;
}
.footer {
  margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--border);
  color: var(--muted); font-size: 0.68rem;
}
.footer code {
  background: var(--surface); padding: 0.1rem 0.35rem;
  border-radius: 3px; color: #a5f3fc;
}
"""

_JS = r"""
(function () {
  const API = 'http://localhost:7474';
  let serverOnline = false;

  function escHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function stateClass(state) {
    const map = {
      MERGED:'state-done', CLOSED:'state-muted', SIGNED_OFF:'state-done',
      DONE:'state-done', SOAKING:'state-soak', REVIEW_REQUESTED:'state-info',
      AUTO_REVIEWED:'state-info', TYLER_APPROVED:'state-ok',
      IN_PROGRESS:'state-warn', BRANCHED:'state-warn', TRIAGED:'state-warn',
      OPEN:'state-warn', CHANGES_REQUESTED:'state-danger',
    };
    return map[state] || 'state-muted';
  }

  function prsHtml(prs) {
    if (!prs || prs === '—' || prs === '-') return '<span class="meta-val">—</span>';
    // linkify #N
    const linked = prs.replace(/#(\d+)/g, '<a href="https://github.com/tylerdrakemusic/-Workspace/pull/$1" target="_blank" rel="noopener">#$1</a>');
    return '<span class="meta-val">' + linked + '</span>';
  }

  function renderFR(fr) {
    const approveBtn = fr.signoff_eligible
      ? `<button class="approve-btn" onclick="approvePR('${escHtml(fr.id)}', ${fr.pr_number}, this)">
           ✓ Approve PR #${fr.pr_number}
         </button>`
      : '';

    return `
      <div class="fr-card">
        <div class="fr-top">
          <div class="fr-id">${escHtml(fr.id)}</div>
          <div class="fr-badges">
            <span class="state-badge ${stateClass(fr.state)}">${escHtml(fr.state)}</span>
          </div>
        </div>
        <div class="fr-title">${escHtml(fr.title)}</div>
        <div class="fr-meta">
          <div class="meta-row"><span class="meta-key">Projects</span><span class="meta-val">${escHtml(fr.projects)}</span></div>
          <div class="meta-row"><span class="meta-key">Branch</span><span class="meta-val"><code>${escHtml(fr.branch)}</code></span></div>
          <div class="meta-row"><span class="meta-key">PRs</span>${prsHtml(fr.prs)}</div>
          <div class="meta-row"><span class="meta-key">Opened</span><span class="meta-val">${escHtml(fr.opened)}</span></div>
          <div class="meta-row"><span class="meta-key">Updated</span><span class="meta-val">${escHtml(fr.updated)}</span></div>
        </div>
        ${approveBtn}
        <div class="fr-foot"><a href="../.github/FR_LEDGERS/${escHtml(fr.id)}.md" target="_blank" rel="noopener">ledger →</a></div>
      </div>`;
  }

  function renderBoard(frs) {
    const active = frs.filter(f => f.is_active);
    const archived = frs.filter(f => !f.is_active);

    const activeHtml = active.length
      ? active.map(renderFR).join('')
      : '<div class="empty">No active FRs.</div>';

    const archivedHtml = archived.length
      ? archived.map(renderFR).join('')
      : '<div class="empty">No archived FRs.</div>';

    document.getElementById('active-count').textContent = active.length;
    document.getElementById('active-grid').innerHTML = activeHtml;
    document.getElementById('archived-count').textContent = archived.length;
    document.getElementById('archived-grid').innerHTML = archivedHtml;
  }

  function setStatus(online, refreshed) {
    const dot = document.getElementById('status-dot');
    const label = document.getElementById('status-label');
    const offlineBanner = document.getElementById('offline-banner');
    const staleBanner = document.getElementById('stale-banner');
    if (online) {
      dot.className = 'dot dot-ok';
      label.textContent = 'Server online';
      if (offlineBanner) offlineBanner.style.display = 'none';
    } else {
      dot.className = 'dot dot-danger';
      label.textContent = 'Server offline';
      if (offlineBanner) offlineBanner.style.display = '';
    }
    if (refreshed) {
      document.getElementById('refreshed').textContent = 'Refreshed ' + refreshed;
    }
    serverOnline = online;
  }

  async function fetchFRs() {
    try {
      const r = await fetch(API + '/api/frs', {cache: 'no-store'});
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const data = await r.json();
      if (data.stale) {
        const sb = document.getElementById('stale-banner');
        if (sb) sb.style.display = '';
      } else {
        const sb = document.getElementById('stale-banner');
        if (sb) sb.style.display = 'none';
      }
      renderBoard(data.frs || []);
      const now = new Date().toLocaleTimeString();
      setStatus(true, now);
    } catch (e) {
      setStatus(false, null);
    }
  }

  window.approvePR = async function(frId, prNumber, btn) {
    if (!serverOnline) {
      alert('FR server is offline. Cannot approve PR.');
      return;
    }
    if (!confirm('Approve PR #' + prNumber + ' for ' + frId + '?')) return;
    btn.disabled = true;
    btn.textContent = 'Approving…';
    try {
      const r = await fetch(API + '/signoff', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({fr_id: frId, pr_number: prNumber}),
      });
      const data = await r.json();
      if (r.ok && data.ok) {
        btn.textContent = '✓ Approved';
        btn.style.background = 'var(--ok)';
        const flash = document.getElementById('flash-slot');
        if (flash) {
          flash.className = 'banner banner-ok';
          flash.textContent = '✓ PR #' + prNumber + ' approved for ' + frId;
          flash.style.display = '';
          setTimeout(() => { flash.style.display = 'none'; }, 8000);
        }
      } else {
        btn.textContent = '✗ Failed: ' + (data.error || 'unknown');
        btn.disabled = false;
        btn.style.background = 'var(--danger)';
        btn.style.color = '#fff';
      }
    } catch (e) {
      btn.textContent = '✗ Network error';
      btn.disabled = false;
    }
  };

  // Initial load + polling
  fetchFRs();
  setInterval(fetchFRs, 3000);
})();
"""


def _html_escape(text: str) -> str:
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _pr_links_html(prs_raw: str) -> str:
    if not prs_raw or prs_raw in ("—", "-", "N/A"):
        return "—"
    return re.sub(
        r"\[#(\d+)\]\([^)]+\)",
        lambda m: f'<a href="https://github.com/{GH_OWNER}/{GH_REPO}/pull/{m.group(1)}" '
                  f'target="_blank" rel="noopener">#{m.group(1)}</a>',
        prs_raw,
    )


def regenerate_dashboard(frs: list[dict[str, Any]], stale: bool = False) -> None:
    """Write a fresh fr_dashboard.html from the parsed FR list."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    active = [f for f in frs if f["is_active"]]
    archived = [f for f in frs if not f["is_active"]]

    def card(fr: dict[str, Any]) -> str:
        approve_btn = ""
        if fr["signoff_eligible"]:
            approve_btn = (
                f'<button class="approve-btn" '
                f'onclick="approvePR(\'{_html_escape(fr["id"])}\', {fr["pr_number"]}, this)">'
                f'✓ Approve PR #{fr["pr_number"]}</button>'
            )
        return f"""
    <div class="fr-card">
      <div class="fr-top">
        <div class="fr-id">{_html_escape(fr["id"])}</div>
        <div class="fr-badges">
          <span class="state-badge {fr["state_class"]}">{_html_escape(fr["state"])}</span>
        </div>
      </div>
      <div class="fr-title">{_html_escape(fr["title"])}</div>
      <div class="fr-meta">
        <div class="meta-row"><span class="meta-key">Projects</span><span class="meta-val">{_html_escape(fr["projects"])}</span></div>
        <div class="meta-row"><span class="meta-key">Branch</span><span class="meta-val"><code>{_html_escape(fr["branch"])}</code></span></div>
        <div class="meta-row"><span class="meta-key">PRs</span><span class="meta-val">{_pr_links_html(fr["prs"])}</span></div>
        <div class="meta-row"><span class="meta-key">Opened</span><span class="meta-val">{_html_escape(fr["opened"])}</span></div>
        <div class="meta-row"><span class="meta-key">Updated</span><span class="meta-val">{_html_escape(fr["updated"])}</span></div>
      </div>
      {approve_btn}
      <div class="fr-foot"><a href="../.github/FR_LEDGERS/{_html_escape(fr["id"])}.md" target="_blank" rel="noopener">ledger →</a></div>
    </div>"""

    active_html = "\n".join(card(f) for f in active) if active else '<div class="empty">No active FRs.</div>'
    archived_html = "\n".join(card(f) for f in archived) if archived else '<div class="empty">No archived FRs.</div>'

    stale_banner = (
        '<div class="banner banner-warn" id="stale-banner">⚠ Registry file unavailable — showing last known data.</div>'
        if stale else
        '<div class="banner banner-warn" id="stale-banner" style="display:none">⚠ Registry file unavailable — showing last known data.</div>'
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>⊕ Feature Request Board</title>
<style>
{_CSS}
</style>
</head>
<body>
  <h1><span class="sigil">⊕</span> Feature Request Board</h1>
  <div class="subtitle">
    Live panel · auto-refreshes every 3 s ·
    Registry: <code>.github/FEATURE_REQUESTS.md</code>
  </div>

  <div class="status-bar">
    <div class="dot dot-warn" id="status-dot"></div>
    <span id="status-label">Connecting…</span>
    <span class="refreshed" id="refreshed">Last refresh: —</span>
  </div>

  <div class="banner banner-danger" id="offline-banner" style="display:none">
    &#9888; FR server offline &mdash; start it with:
    <code>{_html_escape(str(Path(__file__).resolve()))}</code>
  </div>
  {stale_banner}

  <div id="flash-slot" class="banner banner-ok" style="display:none"></div>

  <div class="section-title">
    Active <span class="count" id="active-count">{len(active)}</span>
  </div>
  <div class="grid" id="active-grid">
    {active_html}
  </div>

  <details class="archive">
    <summary>Archived / Signed off <span class="count" id="archived-count">{len(archived)}</span></summary>
    <div class="grid" id="archived-grid" style="margin-top:0.6rem">
      {archived_html}
    </div>
  </details>

  <div class="footer">
    Soak protocol: after merge, FRs enter <code>SOAKING</code> so Tyler can verify
    the feature is live on <code>main</code> before signing off.<br>
    Server: <code>C:\\G\\python.exe f:\\⊕Workspace\\src\\utils\\fr_server.py</code> ·
    Generated: {now_str}
  </div>

  <script>
{_JS}
  </script>
</body>
</html>"""

    DASHBOARD_HTML.write_text(html, encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# File Watcher
# ─────────────────────────────────────────────────────────────────────────────

class _WatcherThread(threading.Thread):
    """Background thread that polls FEATURE_REQUESTS.md + FR_LEDGERS/ for changes."""

    def __init__(self, interval: float = 3.0) -> None:
        super().__init__(daemon=True, name="fr-watcher")
        self._interval = interval
        self._stop_event = threading.Event()
        self._last_mtimes: dict[Path, float] = {}
        self._lock = threading.Lock()
        self._frs: list[dict[str, Any]] = []
        self._stale = False

    @property
    def frs(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._frs)

    @property
    def stale(self) -> bool:
        with self._lock:
            return self._stale

    def _current_mtimes(self) -> dict[Path, float]:
        mtimes: dict[Path, float] = {}
        if REGISTRY_FILE.exists():
            mtimes[REGISTRY_FILE] = REGISTRY_FILE.stat().st_mtime
        if LEDGERS_DIR.exists():
            for p in LEDGERS_DIR.iterdir():
                if p.suffix == ".md":
                    mtimes[p] = p.stat().st_mtime
        return mtimes

    def _reload(self) -> None:
        stale = not REGISTRY_FILE.exists()
        frs = parse_feature_requests(REGISTRY_FILE)
        with self._lock:
            self._frs = frs
            self._stale = stale
        try:
            regenerate_dashboard(frs, stale=stale)
        except Exception as exc:
            print(f"[fr-watcher] Dashboard regen failed: {exc}", file=sys.stderr)

    def run(self) -> None:
        self._reload()
        while not self._stop_event.wait(self._interval):
            current = self._current_mtimes()
            if current != self._last_mtimes:
                self._last_mtimes = current
                self._reload()

    def stop(self) -> None:
        self._stop_event.set()


# Try watchdog for more efficient inotify-style watching (optional dependency)
try:
    from watchdog.observers import Observer  # type: ignore
    from watchdog.events import FileSystemEventHandler  # type: ignore

    class _WatchdogHandler(FileSystemEventHandler):  # type: ignore
        def __init__(self, watcher: "_WatcherThread") -> None:
            self._watcher = watcher

        def on_any_event(self, event: Any) -> None:  # type: ignore
            self._watcher._reload()

    _WATCHDOG_AVAILABLE = True
except ImportError:
    _WATCHDOG_AVAILABLE = False


def _start_watcher() -> "_WatcherThread":
    watcher = _WatcherThread()
    watcher.start()

    if _WATCHDOG_AVAILABLE:
        observer = Observer()
        handler = _WatchdogHandler(watcher)
        if GITHUB_ROOT.exists():
            observer.schedule(handler, str(GITHUB_ROOT), recursive=True)
        observer.start()

    return watcher


# ─────────────────────────────────────────────────────────────────────────────
# GitHub PR Approval
# ─────────────────────────────────────────────────────────────────────────────

def approve_pr(pr_number: int, fr_id: str) -> dict[str, Any]:
    """
    Approve a GitHub PR using GITHUB_TOKEN from the environment.
    Returns {"ok": True} on success or {"ok": False, "error": "..."} on failure.
    """
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN", "")
    if not token:
        return {
            "ok": False,
            "error": "GITHUB_TOKEN env var not set. Set it with: "
                     "[System.Environment]::SetEnvironmentVariable('GITHUB_TOKEN', 'ghp_...', 'Machine')",
        }

    url = f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}/pulls/{pr_number}/reviews"
    body = json.dumps({"event": "APPROVE", "body": f"✓ Approved via FR Ledger Panel for {fr_id}"})
    req = urllib.request.Request(
        url,
        data=body.encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "fr-server/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status in (200, 201):
                return {"ok": True}
            return {"ok": False, "error": f"GitHub API returned HTTP {resp.status}"}
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail = str(exc)
        return {"ok": False, "error": f"GitHub API error {exc.code}: {detail}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
# HTTP Request Handler
# ─────────────────────────────────────────────────────────────────────────────

def _make_handler(watcher: "_WatcherThread") -> type:
    class FRHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(WORKSPACE_ROOT / "reports"), **kwargs)

        def log_message(self, fmt: str, *args: Any) -> None:  # type: ignore
            # Suppress noisy access logs; only print errors
            if args and str(args[1]) not in ("200", "304"):
                super().log_message(fmt, *args)

        def _send_json(self, data: Any, status: int = 200) -> None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def _send_cors_preflight(self) -> None:
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_OPTIONS(self) -> None:  # noqa: N802
            self._send_cors_preflight()

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/api/frs" or self.path.startswith("/api/frs?"):
                self._send_json({"frs": watcher.frs, "stale": watcher.stale})
            elif self.path in ("/", "/fr_dashboard.html"):
                self.path = "/fr_dashboard.html"
                super().do_GET()
            else:
                super().do_GET()

        def do_POST(self) -> None:  # noqa: N802
            if self.path == "/signoff":
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length)
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except json.JSONDecodeError:
                    self._send_json({"ok": False, "error": "Invalid JSON"}, 400)
                    return

                pr_number = payload.get("pr_number")
                fr_id = payload.get("fr_id", "")

                if not pr_number or not isinstance(pr_number, int):
                    self._send_json({"ok": False, "error": "pr_number must be an integer"}, 400)
                    return
                if not fr_id or not isinstance(fr_id, str):
                    self._send_json({"ok": False, "error": "fr_id must be a non-empty string"}, 400)
                    return

                result = approve_pr(pr_number, fr_id)
                status = 200 if result["ok"] else 502
                self._send_json(result, status)
            else:
                self.send_error(HTTPStatus.NOT_FOUND)

    return FRHandler


# ─────────────────────────────────────────────────────────────────────────────
# Port Check
# ─────────────────────────────────────────────────────────────────────────────

def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Main Entry Point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="FR Ledger Panel Server")
    parser.add_argument("--port", type=int, default=7474, help="HTTP port (default: 7474)")
    args = parser.parse_args()
    port: int = args.port

    if _port_in_use(port):
        print(
            f"[fr-server] Port {port} is already in use. "
            "Another instance may be running. Exiting.",
            file=sys.stderr,
        )
        sys.exit(0)

    print(f"[fr-server] Starting FR Ledger Panel on http://localhost:{port}/", flush=True)
    print(f"[fr-server] Watching {REGISTRY_FILE}", flush=True)
    print(f"[fr-server] Watching {LEDGERS_DIR}", flush=True)
    if _WATCHDOG_AVAILABLE:
        print("[fr-server] File watching: watchdog (inotify)", flush=True)
    else:
        print("[fr-server] File watching: polling (3 s) — install watchdog for inotify", flush=True)

    watcher = _start_watcher()
    handler_class = _make_handler(watcher)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler_class)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[fr-server] Shutting down.", flush=True)
    finally:
        server.server_close()
        watcher.stop()


if __name__ == "__main__":
    main()
