#!/usr/bin/env python3
"""
⊕ FR Portal Server — serves the full workspace portal over HTTP.

Serves `F:\\` (the parent of all five project roots) so portal.html iframes
referencing `file:///f:/<project>/reports/*.html` keep working when the portal
is loaded over HTTP. Endpoints:

  GET  /                              → redirect to ⊕Workspace/reports/portal.html
  GET  /favicon.ico                   → 204 (silences browser noise)
  GET  /<project>/reports/...         → normal static file
  GET  /⊕Workspace/reports/portal.html
                                      → served with inline rewrite of
                                        `file:///F:/...` URIs to absolute HTTP
                                        paths on this server.
  POST /fr/signoff/<FR-ID>            → invoke fr_signoff.signoff(), regenerate
                                        the FR dashboard + portal, redirect
                                        back with a flash param.

Usage:
    C:\\G\\python.exe tools/fr_portal_server.py              # http://127.0.0.1:8765/
    C:\\G\\python.exe tools/fr_portal_server.py --port 9000
    C:\\G\\python.exe tools/fr_portal_server.py --bind 0.0.0.0 --open

Security posture: binds to 127.0.0.1 by default. Signoff path is validated
against a strict regex and can only mutate files under
`⊕Workspace/.github/FR_LEDGERS/`.
"""
from __future__ import annotations

import argparse
import html as html_mod
import http.server
import json
import os
import re
import socketserver
import subprocess
import sys
import urllib.parse
import webbrowser
from pathlib import Path

# All five project roots live directly under F:\. Serving that parent as the
# HTTP document root lets one tab reach every project's dashboards.
WORKSPACE_PROJECT = Path(__file__).resolve().parent.parent        # F:\⊕Workspace
SERVE_ROOT = WORKSPACE_PROJECT.parent                             # F:\
PORTAL_URL_PATH = f"/{WORKSPACE_PROJECT.name}/reports/portal.html"
FR_DASHBOARD_URL_PATH = f"/{WORKSPACE_PROJECT.name}/reports/fr_dashboard.html"

sys.path.insert(0, str(WORKSPACE_PROJECT / "tools"))
import fr_signoff  # noqa: E402 — local import after sys.path tweak

_FR_ID_RE = re.compile(r"^FR-[\w\-.]+$")

# Matches file:///F:/..., file:///f:/..., and their %-encoded equivalents.
# Captures the part after the drive letter so we can turn it into a URL path.
_FILE_URI_RE = re.compile(r"""file:///[Ff](?::|%3[Aa])/([^"'\s>]+)""")


def _rewrite_file_uris(html: str) -> str:
    """Rewrite `file:///F:/…` URIs embedded in HTML to absolute server paths.

    The captured group is the path relative to F:\\ (already URL-encoded, e.g.
    `%E2%8A%95Workspace/...`), so we just prefix with `/`.
    """
    return _FILE_URI_RE.sub(lambda m: "/" + m.group(1), html)


def _regenerate_dashboard() -> tuple[bool, str]:
    try:
        r = subprocess.run(
            [sys.executable, str(WORKSPACE_PROJECT / "tools" / "fr_dashboard.py")],
            cwd=str(WORKSPACE_PROJECT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30,
        )
        return r.returncode == 0, (r.stderr or r.stdout)[:500]
    except Exception as exc:  # noqa: BLE001 — surface to client
        return False, f"{type(exc).__name__}: {exc}"


def _regenerate_portal() -> tuple[bool, str]:
    """Best-effort portal refresh so the FR pane always reflects the latest HTML."""
    script = WORKSPACE_PROJECT / "tools" / "dashboard_portal.py"
    if not script.is_file():
        return True, "(dashboard_portal.py not found — skipped)"
    try:
        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")
        r = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(WORKSPACE_PROJECT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=60, env=env,
        )
        return r.returncode == 0, (r.stderr or r.stdout)[:500]
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SERVE_ROOT), **kwargs)

    def end_headers(self):
        # Discourage caching so freshly regenerated dashboards always load.
        if self.path.endswith(".html") or self.path.endswith("/"):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):  # quieter logs
        sys.stderr.write(f"[portal] {self.address_string()} - {fmt % args}\n")

    # ── GET ──────────────────────────────────────────────────────────────
    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path

        if path in ("", "/"):
            self.send_response(302)
            self.send_header("Location", PORTAL_URL_PATH)
            self.end_headers()
            return

        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        decoded = urllib.parse.unquote(path)
        if decoded.endswith("/reports/portal.html"):
            return self._serve_portal(decoded)

        return super().do_GET()

    def _serve_portal(self, decoded_path: str):
        fs_path = SERVE_ROOT / decoded_path.lstrip("/")
        if not fs_path.is_file():
            self.send_error(404, "portal.html not found")
            return
        try:
            raw = fs_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            self.send_error(500, f"read error: {exc}")
            return
        body = _rewrite_file_uris(raw).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

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

        ok_dash, msg_dash = _regenerate_dashboard()
        ok_portal, msg_portal = _regenerate_portal()

        warnings = []
        if not ok_dash:
            warnings.append(f"dashboard regen warning: {msg_dash}")
        if not ok_portal:
            warnings.append(f"portal regen warning: {msg_portal}")

        accept = self.headers.get("Accept", "")
        if "application/json" in accept:
            payload = json.dumps({
                "ok": True,
                "result": result,
                "dashboard_ok": ok_dash,
                "portal_ok": ok_portal,
                "warnings": warnings,
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        # Redirect back to whichever surface originated the POST so the FR
        # panel reloads with the flash param. Portal takes precedence.
        referer = self.headers.get("Referer", "") or ""
        target_base = PORTAL_URL_PATH if "/reports/portal.html" in referer else FR_DASHBOARD_URL_PATH
        target = f"{target_base}?signed_off={urllib.parse.quote(fr_id)}"
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
<p><a href="{PORTAL_URL_PATH}">← back to Portal</a> · <a href="{FR_DASHBOARD_URL_PATH}">FR Board</a></p>
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
    parser.add_argument("--open", dest="open_browser", action="store_true",
                        help="Open the portal in the default browser after startup")
    parser.add_argument("--no-open", dest="open_browser", action="store_false")
    parser.set_defaults(open_browser=False)
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    with ThreadingServer((args.bind, args.port), Handler) as httpd:
        base = f"http://{args.bind}:{args.port}"
        print(f"⊕ FR portal serving {SERVE_ROOT} on {base}")
        print(f"  Portal   → {base}{PORTAL_URL_PATH}")
        print(f"  FR Board → {base}{FR_DASHBOARD_URL_PATH}")
        print("  Press Ctrl-C to stop.")
        if args.open_browser:
            try:
                webbrowser.open(f"{base}{PORTAL_URL_PATH}")
            except Exception:  # noqa: BLE001
                pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n⊕ stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
