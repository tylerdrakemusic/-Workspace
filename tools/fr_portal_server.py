#!/usr/bin/env python3
"""
⊕ FR Portal Server — serves the workspace so the FR board can sign off FRs.

Extends `http.server.SimpleHTTPRequestHandler` to:
  - GET any static file under the project root (like `python -m http.server`)
  - POST /fr/signoff/<FR-ID>   → invoke tools.fr_signoff.signoff(), regenerate
                                  the FR dashboard, and redirect back to it.

Usage:
    C:\\G\\python.exe tools/fr_portal_server.py              # http://localhost:8765/
    C:\\G\\python.exe tools/fr_portal_server.py --port 9000
    C:\\G\\python.exe tools/fr_portal_server.py --bind 0.0.0.0

Security posture: binds to 127.0.0.1 by default. The signoff endpoint performs
a single-purpose file rewrite via fr_signoff.signoff(); it cannot traverse
outside .github/FR_LEDGERS and rejects FR IDs containing path separators.
"""
from __future__ import annotations

import argparse
import html as html_mod
import http.server
import json
import re
import socketserver
import subprocess
import sys
import urllib.parse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_PATH = "/reports/fr_dashboard.html"

sys.path.insert(0, str(PROJECT_ROOT / "tools"))
import fr_signoff  # noqa: E402 — local import after sys.path tweak

_FR_ID_RE = re.compile(r"^FR-[\w\-.]+$")


def _regenerate_dashboard() -> tuple[bool, str]:
    try:
        r = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "tools" / "fr_dashboard.py")],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30,
        )
        return r.returncode == 0, (r.stderr or r.stdout)[:500]
    except Exception as exc:  # noqa: BLE001 — surface to client
        return False, f"{type(exc).__name__}: {exc}"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

    # ── CORS / cache headers for dashboard ──────────────────────────────
    def end_headers(self):
        # Discourage caching so freshly regenerated dashboards always load.
        if self.path.endswith(".html"):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):  # quieter logs
        sys.stderr.write(f"[portal] {self.address_string()} - {fmt % args}\n")

    # ── POST /fr/signoff/<FR-ID> ────────────────────────────────────────
    def do_POST(self):  # noqa: N802 — stdlib naming
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path

        if path.startswith("/fr/signoff/"):
            fr_id = path[len("/fr/signoff/"):].strip("/")
            return self._handle_signoff(fr_id)

        self.send_error(404, "unknown POST endpoint")

    def _handle_signoff(self, fr_id: str):
        # Parse optional form body (note).
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        note = ""
        if body:
            try:
                form = urllib.parse.parse_qs(body.decode("utf-8", "replace"))
                note = (form.get("note") or [""])[0][:240]
            except Exception:  # noqa: BLE001
                note = ""

        if not _FR_ID_RE.match(fr_id):
            return self._respond_html(400, fr_id, False, "Invalid FR id")

        try:
            result = fr_signoff.signoff(fr_id, note=note, backfill=False)
        except SystemExit as exc:
            return self._respond_html(409, fr_id, False, str(exc))
        except Exception as exc:  # noqa: BLE001
            return self._respond_html(500, fr_id, False, f"{type(exc).__name__}: {exc}")

        ok, msg = _regenerate_dashboard()
        detail = f"{result['previous_state']} → SIGNED_OFF @ {result['signed_off_at']}"
        if not ok:
            detail += f" (dashboard regen warning: {msg})"

        # If client accepts JSON (fetch/XHR), respond JSON; else redirect.
        accept = self.headers.get("Accept", "")
        if "application/json" in accept:
            payload = json.dumps({"ok": True, "result": result, "dashboard_ok": ok}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        # Browser form POST → redirect back to dashboard with a flash param.
        target = f"{DASHBOARD_PATH}?signed_off={urllib.parse.quote(fr_id)}"
        self.send_response(303)
        self.send_header("Location", target)
        self.end_headers()

    def _respond_html(self, status: int, fr_id: str, ok: bool, message: str):
        color = "#10b981" if ok else "#ef4444"
        body = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>FR signoff</title>
<style>body{{font-family:system-ui;background:#0a0d12;color:#e2e8f0;padding:2rem;}}
a{{color:#6366f1;}} .box{{border:1px solid #1e2530;background:#151a22;padding:1.5rem;border-radius:8px;max-width:640px;}}
h1{{font-size:1.2rem;color:{color};}}
code{{background:#1b2230;padding:.1rem .4rem;border-radius:3px;}}
</style></head><body>
<div class="box">
<h1>{'Signed off' if ok else 'Signoff failed'}: <code>{html_mod.escape(fr_id)}</code></h1>
<p>{html_mod.escape(message)}</p>
<p><a href="{DASHBOARD_PATH}">← back to FR Board</a></p>
</div></body></html>"""
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> int:
    parser = argparse.ArgumentParser(description="⊕ FR Portal Server")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--bind", default="127.0.0.1")
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    with ThreadingServer((args.bind, args.port), Handler) as httpd:
        print(f"⊕ FR portal serving {PROJECT_ROOT} on http://{args.bind}:{args.port}")
        print(f"  FR Board → http://{args.bind}:{args.port}{DASHBOARD_PATH}")
        print("  Press Ctrl-C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n⊕ stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
