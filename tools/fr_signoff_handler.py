#!/usr/bin/env python3
"""
⊕ FR Signoff Protocol Handler — invoked by Windows when Tyler clicks a
`frsignoff:FR-xxxx` link in the static portal.

Flow:
  1. Parse URL argument: frsignoff:FR-ID[?note=...]
  2. Call fr_signoff.signoff(FR-ID, note)
  3. Regenerate fr_dashboard.html and portal.html
  4. git add / commit / push --force-with-lease origin main
  5. Show a tkinter toast (auto-closing) with success/failure

Registered via tools/register_frsignoff_protocol.ps1. Run with pythonw.exe
for a console-free launch from the browser.

Security:
  - FR id validated against strict regex.
  - Only invokes fr_signoff.signoff() (can only mutate .github/FR_LEDGERS/).
  - Commit message + push target are hard-coded; no shell=True anywhere.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import traceback
import urllib.parse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LEDGER_DIR = PROJECT_ROOT / ".github" / "FR_LEDGERS"
LOG_FILE = PROJECT_ROOT / "logs" / "fr_signoff_handler.log"

sys.path.insert(0, str(PROJECT_ROOT / "tools"))
import fr_signoff  # noqa: E402

_FR_ID_RE = re.compile(r"^FR-[\w\-.]+$")
_URL_RE = re.compile(r"^frsignoff:(?P<rest>.+)$", re.IGNORECASE)


def _log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(msg.rstrip() + "\n")


def _parse(arg: str) -> tuple[str, str]:
    m = _URL_RE.match(arg.strip())
    if not m:
        raise ValueError(f"not a frsignoff: URL: {arg!r}")
    rest = m.group("rest").rstrip("/")
    if "?" in rest:
        fr_id, qs = rest.split("?", 1)
        note = (urllib.parse.parse_qs(qs).get("note") or [""])[0][:240]
    else:
        fr_id, note = rest, ""
    fr_id = urllib.parse.unquote(fr_id).strip()
    note = urllib.parse.unquote(note).strip()
    if not _FR_ID_RE.match(fr_id):
        raise ValueError(f"invalid FR id: {fr_id!r}")
    return fr_id, note


def _run(cmd: list[str], *, cwd: Path = PROJECT_ROOT) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    # Suppress the console-window flash when invoked from pythonw.exe.
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    r = subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120,
        env=env, creationflags=flags,
    )
    out = (r.stdout + r.stderr).strip()
    return r.returncode, out


def _regenerate() -> list[str]:
    warnings: list[str] = []
    rc, out = _run([sys.executable, str(PROJECT_ROOT / "tools" / "fr_dashboard.py")])
    if rc != 0:
        warnings.append(f"fr_dashboard.py rc={rc}: {out[:200]}")
    portal = PROJECT_ROOT / "tools" / "dashboard_portal.py"
    if portal.is_file():
        rc, out = _run([sys.executable, str(portal)])
        if rc != 0:
            warnings.append(f"dashboard_portal.py rc={rc}: {out[:200]}")
    return warnings


def _git_commit_and_push(fr_id: str, ledger_path: Path) -> list[str]:
    """Commit the ledger + regenerated dashboards, push with --force-with-lease.

    Returns a list of step summaries for the toast.
    """
    steps: list[str] = []

    # Stage: ledger + reports
    rc, out = _run(["git", "add", "--",
                    str(ledger_path.relative_to(PROJECT_ROOT)),
                    "reports/fr_dashboard.html",
                    "reports/portal.html"])
    if rc != 0:
        steps.append(f"git add failed: {out[:200]}")
        return steps

    # Anything to commit?
    rc, out = _run(["git", "diff", "--cached", "--quiet"])
    if rc == 0:
        steps.append("No staged changes (already committed?).")
    else:
        msg = f"chore(fr): sign off {fr_id}"
        rc, out = _run(["git", "commit", "-m", msg])
        if rc != 0:
            steps.append(f"git commit failed: {out[:200]}")
            return steps
        steps.append(f"Committed: {msg}")

    # Push with force-with-lease
    rc, out = _run(["git", "push", "--force-with-lease", "origin", "HEAD:main"])
    if rc != 0:
        steps.append(f"git push failed: {out[:200]}")
        return steps
    steps.append("Pushed to origin/main (--force-with-lease).")
    return steps


def _toast_messagebox(title: str, body: str, *, ok: bool, auto_close_ms: int) -> bool:
    """Reliable native toast via user32.MessageBoxTimeoutW (undocumented since XP).

    Returns True if the call succeeded, False otherwise.
    """
    try:
        import ctypes
        from ctypes import wintypes
    except Exception as exc:  # noqa: BLE001
        _log(f"messagebox ctypes import failed: {exc}")
        return False
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        MessageBoxTimeoutW = user32.MessageBoxTimeoutW
        MessageBoxTimeoutW.argtypes = [
            wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR,
            wintypes.UINT, wintypes.WORD, wintypes.DWORD,
        ]
        MessageBoxTimeoutW.restype = wintypes.INT
        # MB_ICONINFORMATION=0x40, MB_ICONERROR=0x10, MB_TOPMOST=0x40000, MB_SETFOREGROUND=0x10000
        flags = (0x40 if ok else 0x10) | 0x40000 | 0x10000
        MessageBoxTimeoutW(None, body, title, flags, 0, int(auto_close_ms))
        return True
    except Exception as exc:  # noqa: BLE001
        _log(f"MessageBoxTimeoutW failed: {exc}")
        return False


def _toast(title: str, body: str, *, ok: bool = True, auto_close_ms: int = 5000) -> None:
    """Show a small auto-closing popup. Prefers native MessageBoxTimeoutW."""
    if _toast_messagebox(title, body, ok=ok, auto_close_ms=auto_close_ms):
        return

    # Fallback: tkinter. Captures traceback into the log if it fails.
    try:
        import tkinter as tk  # noqa: WPS433
    except Exception as exc:  # noqa: BLE001
        _log(f"tkinter import failed: {exc}")
        return
    try:
        root = tk.Tk()
        root.title(title)
        root.configure(bg="#0a0d12")
        try:
            root.attributes("-topmost", True)
        except tk.TclError:
            pass
        w, h = 460, 180
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        root.geometry(f"{w}x{h}+{sw - w - 30}+{sh - h - 80}")
        bar_color = "#10b981" if ok else "#ef4444"
        tk.Frame(root, bg=bar_color, height=4).pack(fill="x", side="top")
        tk.Label(root, text=title, bg="#0a0d12", fg=bar_color,
                 font=("Segoe UI", 12, "bold"), anchor="w", padx=16,
                 pady=(10, 2)).pack(fill="x")
        tk.Label(root, text=body, bg="#0a0d12", fg="#e2e8f0",
                 font=("Segoe UI", 9), anchor="nw", justify="left", padx=16,
                 wraplength=w - 32).pack(fill="both", expand=True)
        root.after(auto_close_ms, root.destroy)
        root.mainloop()
    except Exception as exc:  # noqa: BLE001
        _log("tk toast crashed:\n" + traceback.format_exc())
        _log(f"tk toast body was: {title} | {body[:200]}")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        _toast("FR signoff", "No URL argument supplied.", ok=False)
        return 2

    url = argv[1]
    _log(f"--- invoked with {url!r} ---")

    try:
        fr_id, note = _parse(url)
    except ValueError as exc:
        _log(f"parse error: {exc}")
        _toast("FR signoff", f"Invalid URL:\n{exc}", ok=False)
        return 2

    ledger_path = LEDGER_DIR / f"{fr_id}.md"
    if not ledger_path.is_file():
        # Fallback to glob (fr_signoff also does this internally)
        matches = list(LEDGER_DIR.glob(f"{fr_id}*.md"))
        if len(matches) == 1:
            ledger_path = matches[0]
        else:
            _toast("FR signoff", f"Ledger not found for {fr_id}", ok=False)
            return 1

    try:
        result = fr_signoff.signoff(fr_id, note=note, backfill=False)
    except SystemExit as exc:
        _log(f"signoff refused: {exc}")
        _toast("FR signoff refused", str(exc), ok=False)
        return 1
    except Exception as exc:  # noqa: BLE001
        _log("signoff crashed:\n" + traceback.format_exc())
        _toast("FR signoff crashed", f"{type(exc).__name__}: {exc}", ok=False)
        return 1

    warnings = _regenerate()
    git_steps = _git_commit_and_push(fr_id, ledger_path)

    _log(f"signoff ok: {result}")
    for w in warnings:
        _log("WARN: " + w)
    for s in git_steps:
        _log("GIT: " + s)

    prev = result.get("previous_state", "?")
    ts = result.get("signed_off_at", "?")
    git_ok = all(not s.startswith("git ") or "failed" not in s for s in git_steps)
    body_lines = [
        f"{fr_id}",
        f"{prev} → SIGNED_OFF",
        f"At: {ts}",
        "",
    ]
    body_lines.extend(git_steps)
    if warnings:
        body_lines.append("")
        body_lines.extend("⚠ " + w for w in warnings)
    _toast("✓ FR signed off" if git_ok else "⚠ FR signed off (push issue)",
           "\n".join(body_lines), ok=git_ok)

    # Re-open portal so Tyler sees the refreshed dashboard without a manual F5.
    portal = PROJECT_ROOT / "reports" / "portal.html"
    if portal.is_file():
        try:
            os.startfile(str(portal))  # noqa: S606 — fixed path, not user input
        except Exception as exc:  # noqa: BLE001
            _log(f"portal open failed: {exc}")

    return 0 if git_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
