#!/usr/bin/env python3
"""
⊕ Copilot Usage Monitor — tracks GitHub Copilot chat session usage across all
VS Code workspaces. Parses JSONL session files + models.json to produce
an interactive HTML dashboard with:
  - Token usage tracking (prompt + output tokens per session)
  - Sessions over time (daily bar chart)
  - Model usage distribution (pie chart)
  - Agent mode breakdown
  - Premium request estimation via billing multipliers
  - Per-session inventory with close/delete buttons
  - Interactive --serve mode with REST API

Data sources:
  %APPDATA%/Code/User/workspaceStorage/*/chatSessions/*.jsonl
  %APPDATA%/Code/User/workspaceStorage/*/GitHub.copilot-chat/debug-logs/*/models.json

Usage:
    C:\\G\\python.exe tools/copilot_usage_monitor.py              # generate + open
    C:\\G\\python.exe tools/copilot_usage_monitor.py --no-open    # generate only
    C:\\G\\python.exe tools/copilot_usage_monitor.py --json       # JSON report
    C:\\G\\python.exe tools/copilot_usage_monitor.py --serve      # interactive server
    C:\\G\\python.exe tools/copilot_usage_monitor.py --serve --port 5070
"""

import argparse
import html as html_mod
import json
import os
import shutil
import sys
import webbrowser
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import urllib.parse

# ── Brave registration ────────────────────────────────────────
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
OUT_PATH = PROJECT_ROOT / "reports" / "copilot_usage_dashboard.html"
VSCODE_STORAGE = Path(os.environ.get("APPDATA", "")) / "Code" / "User" / "workspaceStorage"


def _esc(val) -> str:
    return html_mod.escape(str(val)) if val else ""


# ── Data Collection ───────────────────────────────────────────

def load_models_catalog() -> dict[str, dict]:
    """Load the most recent models.json for billing multipliers."""
    catalog: dict[str, dict] = {}
    if not VSCODE_STORAGE.exists():
        return catalog
    models_files = sorted(
        VSCODE_STORAGE.glob("*/GitHub.copilot-chat/debug-logs/*/models.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not models_files:
        return catalog
    try:
        data = json.loads(models_files[0].read_text(encoding="utf-8"))
        for m in data:
            mid = m.get("id", "")
            catalog[mid] = {
                "name": m.get("name", mid),
                "vendor": m.get("vendor", "unknown"),
                "multiplier": m.get("billing", {}).get("multiplier", 0),
                "is_premium": m.get("billing", {}).get("is_premium", False),
                "max_context": m.get("capabilities", {}).get("limits", {}).get("max_context_window_tokens", 0),
                "max_output": m.get("capabilities", {}).get("limits", {}).get("max_output_tokens", 0),
            }
    except Exception:
        pass
    return catalog


def collect_sessions() -> list[dict]:
    """Scan all workspace chat session JSONL files, extract metadata + token counts."""
    sessions: list[dict] = []
    if not VSCODE_STORAGE.exists():
        return sessions

    # Build workspace label cache from workspace.json files
    ws_label_cache: dict[str, str] = {}
    for ws_dir in VSCODE_STORAGE.iterdir():
        ws_json = ws_dir / "workspace.json"
        if ws_json.exists():
            try:
                data = json.loads(ws_json.read_text(encoding="utf-8"))
                folder = data.get("folder", data.get("workspace", ""))
                if folder:
                    import urllib.parse
                    decoded = urllib.parse.unquote(folder)
                    label = decoded.split("/")[-1].split("\\")[-1] or ws_dir.name[:12]
                    ws_label_cache[ws_dir.name] = label
            except Exception:
                pass

    for jsonl_path in VSCODE_STORAGE.glob("*/chatSessions/*.jsonl"):
        try:
            workspace_id = jsonl_path.parent.parent.name
            lines = []
            with open(jsonl_path, "r", encoding="utf-8") as fh:
                for raw_line in fh:
                    raw_line = raw_line.strip()
                    if raw_line:
                        try:
                            lines.append(json.loads(raw_line))
                        except json.JSONDecodeError:
                            continue

            if not lines:
                continue

            # First line (kind=0) is the session header
            obj = lines[0]
            if obj.get("kind") != 0:
                continue
            v = obj.get("v", {})
            creation_ms = v.get("creationDate", 0)
            if not creation_ms:
                continue

            created_dt = datetime.fromtimestamp(creation_ms / 1000, tz=timezone.utc)
            requests = v.get("requests", [])
            title = v.get("customTitle", "")
            session_id = v.get("sessionId", jsonl_path.stem)

            # Extract per-request metadata
            models_used: list[str] = []
            modes_used: list[str] = []
            timestamps: list[int] = []
            for req in requests:
                model_id = req.get("modelId", "")
                if model_id:
                    models_used.append(model_id.replace("copilot/", ""))
                mode_info = req.get("modeInfo", {})
                if isinstance(mode_info, dict):
                    mode_kind = mode_info.get("kind", "")
                    if mode_kind:
                        modes_used.append(mode_kind)
                ts = req.get("timestamp", 0)
                if ts:
                    timestamps.append(ts)

            # Extract token data from kind=1 lines (response metadata)
            prompt_tokens = 0
            output_tokens = 0
            for line in lines:
                if line.get("kind") == 1:
                    lv = line.get("v", {})
                    if isinstance(lv, dict):
                        meta = lv.get("metadata", {})
                        if isinstance(meta, dict):
                            prompt_tokens += meta.get("promptTokens", 0) or 0
                            output_tokens += meta.get("outputTokens", 0) or 0

            # Session duration estimate
            duration_min = 0.0
            if len(timestamps) >= 2:
                duration_min = (max(timestamps) - min(timestamps)) / 60000
            elif len(timestamps) == 1 and creation_ms:
                duration_min = (timestamps[0] - creation_ms) / 60000

            ws_label = ws_label_cache.get(workspace_id, workspace_id[:12])
            sessions.append({
                "session_id": session_id,
                "workspace_id": workspace_id,
                "workspace_label": ws_label,
                "title": title or "(untitled)",
                "created": created_dt.isoformat(),
                "created_date": created_dt.strftime("%Y-%m-%d"),
                "created_time": created_dt.strftime("%H:%M"),
                "turn_count": len(requests),
                "models": list(set(models_used)) if models_used else ["(none)"],
                "primary_model": models_used[0] if models_used else "(none)",
                "modes": list(set(modes_used)) if modes_used else ["(none)"],
                "primary_mode": modes_used[0] if modes_used else "(none)",
                "duration_min": round(duration_min, 1),
                "file_size_kb": round(jsonl_path.stat().st_size / 1024, 1),
                "prompt_tokens": prompt_tokens,
                "output_tokens": output_tokens,
                "total_tokens": prompt_tokens + output_tokens,
                "file_path": str(jsonl_path),
            })
        except Exception:
            continue

    sessions.sort(key=lambda s: s["created"], reverse=True)
    return sessions


def compute_metrics(sessions: list[dict], catalog: dict[str, dict]) -> dict:
    """Aggregate sessions into dashboard metrics."""
    total = len(sessions)
    total_turns = sum(s["turn_count"] for s in sessions)
    active_sessions = [s for s in sessions if s["turn_count"] > 0]
    empty_sessions = total - len(active_sessions)

    # Token totals
    total_prompt_tokens = sum(s.get("prompt_tokens", 0) for s in sessions)
    total_output_tokens = sum(s.get("output_tokens", 0) for s in sessions)
    total_tokens = total_prompt_tokens + total_output_tokens

    # Per-model token breakdown
    model_tokens: dict[str, dict] = defaultdict(lambda: {"prompt": 0, "output": 0})
    for s in active_sessions:
        model = s["primary_model"]
        model_tokens[model]["prompt"] += s.get("prompt_tokens", 0)
        model_tokens[model]["output"] += s.get("output_tokens", 0)

    # Sessions per day
    daily: Counter[str] = Counter()
    for s in sessions:
        daily[s["created_date"]] += 1

    # Model distribution (from active sessions only)
    model_counter: Counter[str] = Counter()
    for s in active_sessions:
        model_counter[s["primary_model"]] += 1

    # Mode distribution
    mode_counter: Counter[str] = Counter()
    for s in active_sessions:
        mode_counter[s["primary_mode"]] += 1

    # Premium request estimation
    premium_requests = 0
    for s in active_sessions:
        for model in s["models"]:
            entry = catalog.get(model, {})
            mult = entry.get("multiplier", 1)
            if mult > 0:
                premium_requests += mult
            else:
                premium_requests += 1  # count as 1 if free/unknown

    # Hourly activity pattern
    hourly: Counter[int] = Counter()
    for s in sessions:
        try:
            h = int(s["created_time"].split(":")[0])
            hourly[h] += 1
        except Exception:
            pass

    # Duration stats
    durations = [s["duration_min"] for s in active_sessions if s["duration_min"] > 0]
    avg_duration = sum(durations) / len(durations) if durations else 0

    # Date range
    dates = sorted(daily.keys())
    date_range = f"{dates[0]} → {dates[-1]}" if dates else "—"

    # Workspace distribution
    ws_counter: Counter[str] = Counter()
    for s in sessions:
        ws_counter[s["workspace_id"][:8]] += 1

    # Daily token usage
    daily_tokens: dict[str, dict] = defaultdict(lambda: {"prompt": 0, "output": 0})
    for s in sessions:
        daily_tokens[s["created_date"]]["prompt"] += s.get("prompt_tokens", 0)
        daily_tokens[s["created_date"]]["output"] += s.get("output_tokens", 0)

    # Activity stats
    now_utc = datetime.now(timezone.utc)
    today_str = now_utc.strftime("%Y-%m-%d")
    today_sessions = sum(1 for s in sessions if s["created_date"] == today_str)
    week_ago_str = (now_utc - timedelta(days=7)).strftime("%Y-%m-%d")
    week_sessions = sum(1 for s in sessions if s["created_date"] >= week_ago_str)
    today_turns = sum(s["turn_count"] for s in sessions if s["created_date"] == today_str)
    today_tokens = sum(s.get("total_tokens", 0) for s in sessions if s["created_date"] == today_str)

    # Activity streak (consecutive days ending today or yesterday)
    streak = 0
    check = now_utc.date()
    daily_set = set(daily.keys())
    if check.strftime("%Y-%m-%d") not in daily_set:
        check -= timedelta(days=1)
    while check.strftime("%Y-%m-%d") in daily_set:
        streak += 1
        check -= timedelta(days=1)

    # Budget tracking (GitHub Copilot Pro = 300 premium/month)
    budget_cap = 300
    budget_remaining = max(budget_cap - premium_requests, 0)
    budget_pct = min(premium_requests / budget_cap * 100, 100) if budget_cap > 0 else 0

    # Last 30 days activity grid
    activity_30d = {}
    for i in range(30):
        d = (now_utc - timedelta(days=29 - i)).strftime("%Y-%m-%d")
        activity_30d[d] = daily.get(d, 0)

    return {
        "generated_at": datetime.now().isoformat(),
        "total_sessions": total,
        "active_sessions": len(active_sessions),
        "empty_sessions": empty_sessions,
        "total_turns": total_turns,
        "avg_turns": round(total_turns / len(active_sessions), 1) if active_sessions else 0,
        "avg_duration_min": round(avg_duration, 1),
        "premium_requests_est": round(premium_requests, 1),
        "total_prompt_tokens": total_prompt_tokens,
        "total_output_tokens": total_output_tokens,
        "total_tokens": total_tokens,
        "model_tokens": {k: dict(v) for k, v in model_tokens.items()},
        "daily_tokens": {k: dict(v) for k, v in sorted(daily_tokens.items())},
        "daily": dict(sorted(daily.items())),
        "model_dist": dict(model_counter.most_common()),
        "mode_dist": dict(mode_counter.most_common()),
        "hourly": {str(h): hourly[h] for h in range(24)},
        "date_range": date_range,
        "workspace_dist": dict(ws_counter.most_common()),
        "today_sessions": today_sessions,
        "week_sessions": week_sessions,
        "today_turns": today_turns,
        "today_tokens": today_tokens,
        "activity_streak": streak,
        "budget_cap": budget_cap,
        "budget_remaining": round(budget_remaining, 1),
        "budget_pct": round(budget_pct, 1),
        "activity_30d": activity_30d,
        "sessions": sessions,
    }


# ── HTML Dashboard ────────────────────────────────────────────

def render_dashboard(metrics: dict, catalog: dict[str, dict]) -> str:
    generated = metrics["generated_at"][:19]
    total = metrics["total_sessions"]
    active = metrics["active_sessions"]
    turns = metrics["total_turns"]
    avg_turns = metrics["avg_turns"]
    avg_dur = metrics["avg_duration_min"]
    premium = metrics["premium_requests_est"]
    total_tokens = metrics["total_tokens"]
    prompt_tokens = metrics["total_prompt_tokens"]
    output_tokens = metrics["total_output_tokens"]
    today_sessions = metrics["today_sessions"]
    week_sessions = metrics["week_sessions"]
    today_turns = metrics["today_turns"]
    today_tokens = metrics["today_tokens"]
    streak = metrics["activity_streak"]
    budget_cap = metrics["budget_cap"]
    budget_remaining = metrics["budget_remaining"]
    budget_pct = metrics["budget_pct"]
    activity_30d = metrics["activity_30d"]

    # Budget gauge SVG values
    budget_dash = round(314 * min(budget_pct / 100, 1), 1)
    if budget_pct < 50:
        budget_color = "#10b981"
    elif budget_pct < 80:
        budget_color = "#f59e0b"
    else:
        budget_color = "#ef4444"
    activity_30d_json = json.dumps(activity_30d)

    # Format token numbers
    def _fmt_tokens(n: int) -> str:
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n / 1_000:.1f}K"
        return str(n)

    # Daily chart data
    daily = metrics["daily"]
    daily_labels = json.dumps(list(daily.keys()))
    daily_values = json.dumps(list(daily.values()))

    # Daily token data
    daily_tokens = metrics.get("daily_tokens", {})
    daily_prompt_tokens = json.dumps([daily_tokens.get(d, {}).get("prompt", 0) for d in daily.keys()])
    daily_output_tokens = json.dumps([daily_tokens.get(d, {}).get("output", 0) for d in daily.keys()])

    # Model distribution
    model_dist = metrics["model_dist"]
    model_labels = json.dumps(list(model_dist.keys()))
    model_values = json.dumps(list(model_dist.values()))

    # Mode distribution
    mode_dist = metrics["mode_dist"]
    mode_labels = json.dumps(list(mode_dist.keys()))
    mode_values = json.dumps(list(mode_dist.values()))

    # Hourly heatmap
    hourly = metrics["hourly"]
    hourly_values = json.dumps([hourly.get(str(h), 0) for h in range(24)])

    # Model color map
    model_colors = {
        "claude-opus-4.6": "#c084fc",
        "claude-opus-4.7": "#a855f7",
        "claude-opus-4.5": "#9333ea",
        "claude-sonnet-4.6": "#818cf8",
        "claude-sonnet-4.5": "#6366f1",
        "claude-sonnet-4": "#4f46e5",
        "claude-haiku-4.5": "#a5b4fc",
        "gpt-5.4": "#22d3ee",
        "gpt-5.4-mini": "#67e8f9",
        "gpt-5.2": "#06b6d4",
        "gpt-5.2-codex": "#0891b2",
        "gpt-5.3-codex": "#0e7490",
        "gpt-4.1": "#2dd4bf",
        "gpt-4o": "#34d399",
        "gemini-2.5-pro": "#fbbf24",
        "gemini-3-flash-preview": "#f59e0b",
        "gemini-3.1-pro-preview": "#d97706",
    }
    colors_list = [model_colors.get(m, "#94a3b8") for m in model_dist.keys()]
    model_colors_json = json.dumps(colors_list)

    # Determine current workspace ID (most sessions belong to it)
    from collections import Counter as _Counter
    ws_counts = _Counter(s["workspace_id"] for s in metrics["sessions"])
    current_ws_id = ws_counts.most_common(1)[0][0] if ws_counts else ""

    # Session inventory rows
    rows_html = ""
    for s in metrics["sessions"][:200]:
        model_badge = _esc(s["primary_model"])
        mode_cls = "mode-agent" if s["primary_mode"] == "agent" else "mode-other"
        turn_cls = "val-ok" if s["turn_count"] > 0 else "val-muted"
        pt = s.get("prompt_tokens", 0)
        ot = s.get("output_tokens", 0)
        tt = pt + ot
        token_display = _fmt_tokens(tt) if tt > 0 else "—"
        token_detail = f"{_fmt_tokens(pt)} in / {_fmt_tokens(ot)} out" if tt > 0 else ""
        sid = _esc(s["session_id"])
        ws_label = _esc(s.get("workspace_label", s["workspace_id"][:12]))
        ws_id = _esc(s["workspace_id"])
        rows_html += f"""<tr data-session-id="{sid}" data-workspace="{ws_id}" data-date="{_esc(s['created_date'])}" data-turns="{s['turn_count']}">
  <td class="cell-date">{_esc(s['created_date'])}<br><span class="time-sub">{_esc(s['created_time'])} UTC</span></td>
  <td class="cell-title">{_esc(s['title'])}</td>
  <td class="{turn_cls}">{s['turn_count']}</td>
  <td><span class="model-badge">{model_badge}</span></td>
  <td><span class="mode-badge {mode_cls}">{_esc(s['primary_mode'])}</span></td>
  <td class="token-cell" title="{token_detail}">{token_display}</td>
  <td>{s['duration_min']:.0f}m</td>
  <td class="val-muted">{s['file_size_kb']:.0f} KB</td>
  <td class="val-muted" style="font-size:0.7rem" title="{ws_id}">{ws_label}</td>
  <td><button class="close-btn" onclick="closeSession('{sid}', this)">Delete</button></td>
</tr>"""

    # Premium model table
    premium_rows = ""
    used_models = set()
    for s in metrics["sessions"]:
        for m in s["models"]:
            used_models.add(m)
    for mid in sorted(used_models):
        if mid == "(none)":
            continue
        entry = catalog.get(mid, {})
        name = entry.get("name", mid)
        mult = entry.get("multiplier", "?")
        vendor = entry.get("vendor", "?")
        premium_rows += f"<tr><td>{_esc(name)}</td><td>{_esc(vendor)}</td><td class='val-info'>{mult}x</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="300">
<title>⊕ Copilot Usage Monitor</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  :root {{
    --bg: #0f172a; --surface: #1e293b; --border: #334155; --text: #f1f5f9;
    --muted: #64748b; --accent: #818cf8; --success: #10b981; --warning: #f59e0b;
    --danger: #ef4444; --cyan: #22d3ee; --purple: #a78bfa;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg); color: var(--text); padding: 1.5rem;
    line-height: 1.6;
  }}
  .header {{
    display: flex; align-items: center; gap: 1rem;
    margin-bottom: 2rem; padding-bottom: 1rem;
    border-bottom: 1px solid var(--border);
  }}
  .header h1 {{ font-size: 1.75rem; font-weight: 800; }}
  .header .sigil {{ font-size: 2rem; }}
  .header .meta {{ color: var(--muted); font-size: 0.8rem; margin-left: auto; text-align: right; }}

  /* ── Stat Cards ── */
  .stats-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 1rem; margin-bottom: 2rem;
  }}
  .stat-card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 1.2rem; text-align: center;
  }}
  .stat-val {{ font-size: 2rem; font-weight: 800; line-height: 1.2; }}
  .stat-label {{ font-size: 0.75rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; margin-top: 0.3rem; }}
  .val-ok {{ color: var(--success); }}
  .val-warn {{ color: var(--warning); }}
  .val-info {{ color: var(--cyan); }}
  .val-accent {{ color: var(--accent); }}
  .val-purple {{ color: var(--purple); }}
  .val-muted {{ color: var(--muted); }}
  .val-token {{ color: #f472b6; }}
  .val-token-in {{ color: #fb923c; }}
  .val-token-out {{ color: #34d399; }}
  .token-highlight {{ border-color: rgba(244,114,182,0.3); }}
  .token-cell {{ color: #f472b6; font-weight: 600; font-variant-numeric: tabular-nums; }}

  /* ── Charts ── */
  .charts-row {{
    display: grid; grid-template-columns: 2fr 1fr; gap: 1.5rem;
    margin-bottom: 2rem;
  }}
  .chart-card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 1.2rem;
  }}
  .chart-card h3 {{
    font-size: 0.9rem; color: var(--muted); margin-bottom: 0.8rem;
    text-transform: uppercase; letter-spacing: 0.04em;
  }}
  .chart-canvas {{ max-height: 260px; }}

  /* ── Hourly Heatmap ── */
  .heatmap-row {{
    display: flex; gap: 3px; margin-bottom: 2rem;
    justify-content: center;
  }}
  .heat-cell {{
    width: 28px; height: 36px; border-radius: 4px;
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; font-size: 0.6rem; color: var(--muted);
    transition: transform 0.1s;
  }}
  .heat-cell:hover {{ transform: scale(1.15); }}
  .heat-val {{ font-size: 0.7rem; font-weight: 700; }}

  /* ── Two-Col Layout ── */
  .two-col {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;
    margin-bottom: 2rem;
  }}

  /* ── Tables ── */
  .section {{ margin-bottom: 2rem; }}
  .section h3 {{
    font-size: 0.9rem; color: var(--muted); margin-bottom: 0.8rem;
    text-transform: uppercase; letter-spacing: 0.04em;
  }}
  table {{
    width: 100%; border-collapse: collapse;
    background: var(--surface); border-radius: 10px; overflow: hidden;
  }}
  th, td {{ padding: 0.6rem 0.8rem; text-align: left; border-bottom: 1px solid var(--border); }}
  th {{ background: rgba(255,255,255,0.03); color: var(--muted); font-weight: 600; font-size: 0.75rem; text-transform: uppercase; }}
  td {{ font-size: 0.85rem; }}
  .cell-date {{ white-space: nowrap; }}
  .cell-title {{ max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .time-sub {{ color: var(--muted); font-size: 0.7rem; }}
  .model-badge {{
    background: rgba(129,140,248,0.15); color: var(--accent);
    padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; white-space: nowrap;
  }}
  .mode-badge {{
    padding: 2px 8px; border-radius: 12px; font-size: 0.75rem;
  }}
  .mode-agent {{ background: rgba(16,185,129,0.15); color: var(--success); }}
  .mode-other {{ background: rgba(100,116,139,0.15); color: var(--muted); }}

  .scroll-table {{ max-height: 500px; overflow-y: auto; border-radius: 10px; border: 1px solid var(--border); }}

  /* Budget gauge */
  .budget-row {{
    display: grid; grid-template-columns: 260px 1fr; gap: 1.5rem;
    margin-bottom: 2rem;
  }}
  .budget-gauge {{ display: flex; flex-direction: column; align-items: center; }}
  .budget-bar {{
    height: 8px; border-radius: 4px; background: var(--border);
    overflow: hidden; width: 100%; margin-top: 0.5rem;
  }}
  .budget-fill {{ height: 100%; border-radius: 4px; transition: width 0.3s; }}

  /* Activity grid */
  .activity-grid {{
    display: flex; gap: 3px; flex-wrap: wrap; margin-top: 0.5rem;
  }}
  .activity-cell {{
    width: 18px; height: 18px; border-radius: 3px;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.55rem; font-weight: 600; cursor: default;
    transition: transform 0.1s;
  }}
  .activity-cell:hover {{ transform: scale(1.25); }}

  /* Close/Delete buttons */
  .close-btn {{
    background: rgba(239,68,68,0.1);
    color: var(--danger);
    border: 1px solid rgba(239,68,68,0.3);
    border-radius: 6px;
    padding: 0.2rem 0.6rem;
    font-size: 0.7rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
    white-space: nowrap;
  }}
  .close-btn:hover {{
    background: var(--danger);
    color: white;
    border-color: var(--danger);
  }}
  .close-btn:disabled {{
    opacity: 0.4;
    cursor: not-allowed;
  }}
  .close-btn.done {{
    background: rgba(16,185,129,0.1);
    color: var(--success);
    border-color: rgba(16,185,129,0.3);
  }}
  .inv-filter {{
    background: var(--surface); color: var(--muted);
    border: 1px solid var(--border); border-radius: 6px;
    padding: 0.25rem 0.75rem; font-size: 0.75rem; font-weight: 600;
    cursor: pointer; transition: all 0.15s;
  }}
  .inv-filter:hover {{ color: var(--text); border-color: var(--accent); }}
  .inv-filter.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}

  @media (max-width: 900px) {{
    .charts-row, .two-col {{ grid-template-columns: 1fr; }}
    .stats-grid {{ grid-template-columns: repeat(3, 1fr); }}
  }}
</style>
</head>
<body>

<div class="header">
  <span class="sigil">⊕</span>
  <div>
    <h1>Copilot Usage Monitor</h1>
    <div style="color: var(--muted); font-size: 0.85rem;">Session analytics across all VS Code workspaces</div>
  </div>
  <div class="meta">
    Generated: {_esc(generated)}<br>
    Date range: {_esc(metrics['date_range'])}
  </div>
</div>

<!-- Budget + Activity Row -->
<div class="budget-row">
  <div class="chart-card" style="text-align: center; padding: 1.5rem;">
    <h3>Monthly Premium Budget</h3>
    <div class="budget-gauge">
      <svg viewBox="0 0 120 120" width="150" height="150">
        <circle cx="60" cy="60" r="50" fill="none" stroke="var(--border)" stroke-width="10"/>
        <circle cx="60" cy="60" r="50" fill="none" stroke="{budget_color}" stroke-width="10"
          stroke-dasharray="{budget_dash} 314" stroke-linecap="round"
          transform="rotate(-90 60 60)"/>
        <text x="60" y="54" text-anchor="middle" fill="var(--text)" font-size="22" font-weight="800">{premium:.0f}</text>
        <text x="60" y="70" text-anchor="middle" fill="var(--muted)" font-size="10">of {budget_cap}</text>
      </svg>
    </div>
    <div style="color: {budget_color}; font-size: 0.85rem; font-weight: 700;">{budget_pct:.0f}% used</div>
    <div style="color: var(--muted); font-size: 0.75rem;">{budget_remaining:.0f} remaining this month</div>
  </div>
  <div>
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.8rem; margin-bottom: 1rem;">
      <div class="stat-card">
        <div class="stat-val val-ok">{today_sessions}</div>
        <div class="stat-label">Today</div>
      </div>
      <div class="stat-card">
        <div class="stat-val val-info">{today_turns}</div>
        <div class="stat-label">Today Turns</div>
      </div>
      <div class="stat-card">
        <div class="stat-val val-purple">{week_sessions}</div>
        <div class="stat-label">Last 7 Days</div>
      </div>
      <div class="stat-card">
        <div class="stat-val val-warn">{streak}</div>
        <div class="stat-label">Day Streak 🔥</div>
      </div>
    </div>
    <div class="chart-card">
      <h3>Activity — Last 30 Days</h3>
      <div class="activity-grid" id="activityGrid"></div>
    </div>
  </div>
</div>

<!-- Stat Cards -->
<div class="stats-grid">
  <div class="stat-card" title="All historical sessions across all VS Code workspace windows (not currently open sessions).">
    <div class="stat-val val-accent">{total}</div>
    <div class="stat-label">All Sessions (all workspaces)</div>
  </div>
  <div class="stat-card" title="Historical sessions with ≥1 turn. Not a count of currently open IDE sessions.">
    <div class="stat-val val-ok">{active}</div>
    <div class="stat-label">With Turns</div>
  </div>
  <div class="stat-card">
    <div class="stat-val val-info">{turns}</div>
    <div class="stat-label">Total Turns</div>
  </div>
  <div class="stat-card">
    <div class="stat-val val-purple">{avg_turns}</div>
    <div class="stat-label">Avg Turns / Session</div>
  </div>
  <div class="stat-card">
    <div class="stat-val val-warn">{avg_dur:.0f}m</div>
    <div class="stat-label">Avg Duration</div>
  </div>
  <div class="stat-card">
    <div class="stat-val val-accent">{premium:.0f}</div>
    <div class="stat-label">Premium Req (est)</div>
  </div>
  <div class="stat-card token-highlight">
    <div class="stat-val val-token">{_fmt_tokens(total_tokens)}</div>
    <div class="stat-label">Total Tokens</div>
  </div>
  <div class="stat-card">
    <div class="stat-val val-token-in">{_fmt_tokens(prompt_tokens)}</div>
    <div class="stat-label">Prompt (Input)</div>
  </div>
  <div class="stat-card">
    <div class="stat-val val-token-out">{_fmt_tokens(output_tokens)}</div>
    <div class="stat-label">Output Tokens</div>
  </div>
  <div class="stat-card">
    <div class="stat-val val-token">{_fmt_tokens(today_tokens)}</div>
    <div class="stat-label">Today Tokens</div>
  </div>
</div>

<!-- Charts Row -->
<div class="charts-row">
  <div class="chart-card">
    <h3>Sessions per Day</h3>
    <canvas id="dailyChart" class="chart-canvas"></canvas>
  </div>
  <div class="chart-card">
    <h3>Model Distribution</h3>
    <canvas id="modelChart" class="chart-canvas"></canvas>
  </div>
</div>

<!-- Token Usage Chart -->
<div class="chart-card" style="margin-bottom: 2rem;">
  <h3>Daily Token Usage (Prompt vs Output)</h3>
  <canvas id="tokenChart" style="max-height:240px;"></canvas>
</div>

<!-- Hourly Activity Heatmap -->
<div class="chart-card" style="margin-bottom: 2rem;">
  <h3>Activity by Hour (UTC)</h3>
  <div class="heatmap-row" id="heatmap"></div>
</div>

<!-- Two-Col: Mode + Models Catalog -->
<div class="two-col">
  <div class="chart-card">
    <h3>Agent Mode Breakdown</h3>
    <canvas id="modeChart" style="max-height:220px;"></canvas>
  </div>
  <div class="chart-card">
    <h3>Models Used — Billing Multiplier</h3>
    <div class="scroll-table" style="max-height:220px;">
      <table>
        <thead><tr><th>Model</th><th>Vendor</th><th>Multiplier</th></tr></thead>
        <tbody>{premium_rows}</tbody>
      </table>
    </div>
  </div>
</div>

<!-- Session Inventory -->
<div class="section">
  <h3>Session Inventory (newest first) <span style="color:var(--muted);font-size:0.75rem;font-weight:400">— historical sessions across all VS Code workspaces, not currently open IDE sessions</span></h3>
  <div style="display:flex;gap:0.5rem;flex-wrap:wrap;margin-bottom:0.75rem;align-items:center">
    <button class="inv-filter active" onclick="filterSessions('all', this)">All ({total})</button>
    <button class="inv-filter" onclick="filterSessions('current', this)">Current Workspace</button>
    <button class="inv-filter" onclick="filterSessions('today', this)">Today</button>
    <button class="inv-filter" onclick="filterSessions('withturns', this)">With Turns</button>
    <button class="inv-filter" onclick="filterSessions('empty', this)">Empty</button>
    <span id="inv-count" style="color:var(--muted);font-size:0.8rem;margin-left:auto"></span>
  </div>
  <div class="scroll-table">
    <table id="session-table">
      <thead>
        <tr><th>Date</th><th>Title</th><th>Turns</th><th>Model</th><th>Mode</th><th>Tokens</th><th>Duration</th><th>Size</th><th>Workspace</th><th>Actions</th></tr>
      </thead>
      <tbody id="session-tbody">{rows_html}</tbody>
    </table>
  </div>
</div>

<script>
  // ── Daily Sessions Bar Chart ──
  const dailyCtx = document.getElementById('dailyChart').getContext('2d');
  new Chart(dailyCtx, {{
    type: 'bar',
    data: {{
      labels: {daily_labels},
      datasets: [{{ label: 'Sessions', data: {daily_values},
        backgroundColor: 'rgba(129,140,248,0.6)', borderColor: '#818cf8',
        borderWidth: 1, borderRadius: 4 }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ ticks: {{ color: '#64748b', maxRotation: 45 }}, grid: {{ color: '#1e293b' }} }},
        y: {{ ticks: {{ color: '#64748b', stepSize: 1 }}, grid: {{ color: '#334155' }}, beginAtZero: true }}
      }}
    }}
  }});

  // ── Model Doughnut Chart ──
  const modelCtx = document.getElementById('modelChart').getContext('2d');
  new Chart(modelCtx, {{
    type: 'doughnut',
    data: {{
      labels: {model_labels},
      datasets: [{{ data: {model_values}, backgroundColor: {model_colors_json},
        borderWidth: 0, hoverOffset: 8 }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{
        legend: {{ position: 'bottom', labels: {{ color: '#94a3b8', padding: 8, font: {{ size: 11 }} }} }}
      }},
      cutout: '55%'
    }}
  }});

  // ── Mode Bar Chart ──
  const modeCtx = document.getElementById('modeChart').getContext('2d');
  const modeColors = {{ 'agent': '#10b981', 'edit': '#f59e0b', 'ask': '#818cf8', 'chat': '#22d3ee' }};
  const mLabels = {mode_labels};
  const mColors = mLabels.map(l => modeColors[l] || '#64748b');
  new Chart(modeCtx, {{
    type: 'bar',
    data: {{
      labels: mLabels,
      datasets: [{{ data: {mode_values}, backgroundColor: mColors, borderRadius: 6, barPercentage: 0.5 }}]
    }},
    options: {{
      indexAxis: 'y', responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ ticks: {{ color: '#64748b' }}, grid: {{ color: '#334155' }}, beginAtZero: true }},
        y: {{ ticks: {{ color: '#f1f5f9' }}, grid: {{ display: false }} }}
      }}
    }}
  }});

  // ── Token Usage Stacked Bar Chart ──
  const tokenCtx = document.getElementById('tokenChart').getContext('2d');
  new Chart(tokenCtx, {{
    type: 'bar',
    data: {{
      labels: {daily_labels},
      datasets: [
        {{ label: 'Prompt (input)', data: {daily_prompt_tokens},
          backgroundColor: 'rgba(251,146,60,0.7)', borderRadius: 4, stack: 'tokens' }},
        {{ label: 'Output', data: {daily_output_tokens},
          backgroundColor: 'rgba(52,211,153,0.7)', borderRadius: 4, stack: 'tokens' }}
      ]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{
        legend: {{ position: 'top', labels: {{ color: '#94a3b8', font: {{ size: 11 }} }} }},
        tooltip: {{ callbacks: {{ label: ctx => ctx.dataset.label + ': ' + ctx.parsed.y.toLocaleString() + ' tokens' }} }}
      }},
      scales: {{
        x: {{ stacked: true, ticks: {{ color: '#64748b', maxRotation: 45 }}, grid: {{ color: '#1e293b' }} }},
        y: {{ stacked: true, ticks: {{ color: '#64748b', callback: v => v >= 1000 ? (v/1000).toFixed(0)+'k' : v }}, grid: {{ color: '#334155' }}, beginAtZero: true }}
      }}
    }}
  }});

  // ── Hourly Heatmap ──
  const hourlyData = {hourly_values};
  const maxH = Math.max(...hourlyData, 1);
  const heatmap = document.getElementById('heatmap');
  for (let h = 0; h < 24; h++) {{
    const v = hourlyData[h];
    const intensity = v / maxH;
    const bg = v === 0 ? 'rgba(100,116,139,0.1)' :
      `rgba(129,140,248,${{(0.15 + intensity * 0.75).toFixed(2)}})`;
    const cell = document.createElement('div');
    cell.className = 'heat-cell';
    cell.style.background = bg;
    cell.innerHTML = `<span class="heat-val" style="color:${{v > 0 ? '#f1f5f9' : 'var(--muted)'}}">${{v}}</span>${{String(h).padStart(2,'0')}}h`;
    cell.title = `${{String(h).padStart(2,'0')}}:00 UTC — ${{v}} session(s)`;
    heatmap.appendChild(cell);
  }}

  // ── Close/Delete Session ──
  async function closeSession(sessionId, btn) {{
    if (!confirm('Delete this session JSONL file? This cannot be undone.')) return;
    btn.disabled = true;
    btn.textContent = '...';
    try {{
      const resp = await fetch('/api/delete', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ session_id: sessionId }})
      }});
      const data = await resp.json();
      if (data.ok) {{
        btn.textContent = 'Deleted';
        btn.classList.add('done');
        const row = btn.closest('tr');
        if (row) row.style.opacity = '0.4';
      }} else {{
        alert('Delete failed: ' + (data.error || 'unknown'));
        btn.disabled = false;
        btn.textContent = 'Delete';
      }}
    }} catch (e) {{
      // Static mode fallback — no server running
      const cmd = `del "${{sessionId}}"`;
      prompt('No server running. Delete manually:', cmd);
      btn.disabled = false;
      btn.textContent = 'Delete';
    }}
  }}

  // ── Session Inventory Filter ──
  const CURRENT_WS_ID = "{current_ws_id}";
  const TODAY = new Date().toISOString().slice(0, 10);
  function filterSessions(mode, btn) {{
    document.querySelectorAll('.inv-filter').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const rows = document.querySelectorAll('#session-tbody tr');
    let visible = 0;
    rows.forEach(row => {{
      const ws = row.dataset.workspace || '';
      const date = row.dataset.date || '';
      const turns = parseInt(row.dataset.turns || '0', 10);
      let show = true;
      if (mode === 'current') show = ws === CURRENT_WS_ID;
      else if (mode === 'today') show = date === TODAY;
      else if (mode === 'withturns') show = turns > 0;
      else if (mode === 'empty') show = turns === 0;
      row.style.display = show ? '' : 'none';
      if (show) visible++;
    }});
    const cnt = document.getElementById('inv-count');
    if (cnt) cnt.textContent = visible + ' session' + (visible !== 1 ? 's' : '') + ' shown';
  }}
  // Init count
  document.getElementById('inv-count').textContent = document.querySelectorAll('#session-tbody tr').length + ' sessions shown';

  // ── Activity Grid (Last 30 Days) ──
  const activityData = {activity_30d_json};
  const actGrid = document.getElementById('activityGrid');
  const maxAct = Math.max(...Object.values(activityData), 1);
  Object.entries(activityData).forEach(([date, count]) => {{
    const intensity = count / maxAct;
    let bg;
    if (count === 0) bg = 'rgba(100,116,139,0.1)';
    else if (intensity < 0.33) bg = 'rgba(129,140,248,0.3)';
    else if (intensity < 0.66) bg = 'rgba(129,140,248,0.55)';
    else bg = 'rgba(129,140,248,0.85)';
    const cell = document.createElement('div');
    cell.className = 'activity-cell';
    cell.style.background = bg;
    cell.style.color = count > 0 ? '#f1f5f9' : 'var(--muted)';
    cell.textContent = count || '';
    cell.title = `${{date}}: ${{count}} session(s)`;
    actGrid.appendChild(cell);
  }});
</script>

</body>
</html>"""


# ── HTTP Server ───────────────────────────────────────────────

class CopilotHandler(BaseHTTPRequestHandler):
    """Live dashboard server with session delete API."""

    catalog: dict = {}
    sessions: list = []

    def log_message(self, fmt, *args):
        pass  # suppress default stderr logging

    def _json(self, obj, status: int = 200):
        body = json.dumps(obj, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html: str):
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/" or parsed.path == "":
            # Refresh data on each page load
            CopilotHandler.sessions = collect_sessions()
            metrics = compute_metrics(CopilotHandler.sessions, CopilotHandler.catalog)
            html = render_dashboard(metrics, CopilotHandler.catalog)
            self._html(html)
        elif parsed.path == "/api/sessions":
            CopilotHandler.sessions = collect_sessions()
            safe = [{k: v for k, v in s.items() if k != "file_path"} for s in CopilotHandler.sessions]
            self._json(safe)
        elif parsed.path == "/api/metrics":
            CopilotHandler.sessions = collect_sessions()
            metrics = compute_metrics(CopilotHandler.sessions, CopilotHandler.catalog)
            self._json(metrics)
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/delete":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            session_id = body.get("session_id", "")
            # Validate: find the session in known sessions
            target = None
            for s in CopilotHandler.sessions:
                if s.get("file_path") and Path(s["file_path"]).stem == session_id:
                    target = Path(s["file_path"])
                    break
                if s.get("session_id") == session_id and s.get("file_path"):
                    target = Path(s["file_path"])
                    break
            if not target or not target.exists():
                self._json({"ok": False, "error": "Session not found or already deleted"}, 404)
                return
            try:
                target.unlink()
                self._json({"ok": True, "deleted": str(target)})
            except OSError as e:
                self._json({"ok": False, "error": str(e)}, 500)
        else:
            self.send_error(404)


def serve_dashboard(port: int = 8077):
    """Start a live HTTP server for the Copilot usage dashboard."""
    CopilotHandler.catalog = load_models_catalog()
    CopilotHandler.sessions = collect_sessions()
    server = HTTPServer(("127.0.0.1", port), CopilotHandler)
    url = f"http://127.0.0.1:{port}"
    print(f"⊕ Copilot Usage Monitor — live at {url}")
    print(f"  Press Ctrl+C to stop")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⊕ Server stopped.")
        server.server_close()


# ── Main ──────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="⊕ Copilot Usage Monitor")
    parser.add_argument("--no-open", action="store_true", help="Generate without opening browser")
    parser.add_argument("--json", action="store_true", help="Output JSON metrics")
    parser.add_argument("--serve", action="store_true", help="Run interactive HTTP server")
    parser.add_argument("--port", type=int, default=8077, help="Server port (default: 8077)")
    args = parser.parse_args()

    if args.serve:
        serve_dashboard(args.port)
        return

    catalog = load_models_catalog()
    sessions = collect_sessions()
    metrics = compute_metrics(sessions, catalog)

    if args.json:
        print(json.dumps(metrics, indent=2, default=str))
        return

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    html = render_dashboard(metrics, catalog)
    OUT_PATH.write_text(html, encoding="utf-8")

    print(f"⊕ Copilot Usage Monitor")
    print(f"  {metrics['total_sessions']} sessions ({metrics['active_sessions']} active, {metrics['empty_sessions']} empty)")
    print(f"  {metrics['total_turns']} total turns, avg {metrics['avg_turns']}/session")
    print(f"  Premium requests (est): {metrics['premium_requests_est']:.0f}")
    print(f"  Models: {', '.join(metrics['model_dist'].keys()) or '(none)'}")
    print(f"  Date range: {metrics['date_range']}")
    print(f"  Dashboard: {OUT_PATH}")

    if not args.no_open:
        try:
            webbrowser.get("brave").open(OUT_PATH.as_uri())
        except Exception:
            webbrowser.open(OUT_PATH.as_uri())


if __name__ == "__main__":
    main()
