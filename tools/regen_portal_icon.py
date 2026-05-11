"""Regenerate the ⊕ Workspace Portal icon.

Reads the prompt from src/data/portal_icon_config.json (or accepts --prompt to
override and save a new prompt). Generates a new image via DALL-E 3, converts
to multi-resolution ICO, re-injects the favicon into reports/portal.html, and
refreshes the desktop shortcut.

Usage
-----
    # Regenerate with the stored prompt:
    python tools/regen_portal_icon.py

    # Use a new prompt (saves it to config):
    python tools/regen_portal_icon.py --prompt "neon quantum rings on black void"

    # Quantum-vary the aesthetics each run:
    python tools/regen_portal_icon.py --vary

    # Preview config without regenerating:
    python tools/regen_portal_icon.py --show-prompt
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import sys
import urllib.parse
from datetime import date
from pathlib import Path

# ── paths ──────────────────────────────────────────────────────────────────────
WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE_ROOT))

CONFIG_FILE = WORKSPACE_ROOT / "src" / "data" / "portal_icon_config.json"
PORTAL_HTML = WORKSPACE_ROOT / "reports" / "portal.html"
ICON_PNG    = WORKSPACE_ROOT / "src" / "data" / "portal_icon.png"
ICON_ICO    = WORKSPACE_ROOT / "src" / "data" / "portal_icon.ico"

ICO_SIZES = [(16, 16), (32, 32), (48, 48), (256, 256)]

# ── quantum prompt variation ───────────────────────────────────────────────────

_STYLE_POOLS: dict[str, list[str]] = {
    "palette": [
        "electric indigo and violet",
        "electric teal and magenta",
        "deep amber and gold",
        "neon cyan and cobalt blue",
        "crimson and rose gold",
        "emerald green and silver",
        "ultraviolet and ice white",
    ],
    "texture": [
        "geometric precision, minimal",
        "crystalline faceted surface",
        "liquid metal ripple",
        "holographic iridescent sheen",
        "circuit-board engraved lines",
        "frosted glass depth",
        "particle field, scattered light",
    ],
    "glow": [
        "radiating luminous halo",
        "pulsing core light",
        "diffuse nebula glow",
        "sharp laser-edge emission",
        "soft bioluminescent bloom",
    ],
    "background": [
        "dark space, deep navy and black",
        "void black with faint star field",
        "dark cosmic nebula",
        "obsidian gradient",
        "deep charcoal with subtle grid",
    ],
}

_PROMPT_TEMPLATE = (
    "A striking circular icon for a unified software workspace portal. "
    "{background} background. "
    "A glowing circled-plus symbol (oplus, \u2295) with {palette} light, {glow}. "
    "{texture} design, tech aesthetic. "
    "The symbol should appear luminous, like a portal or gateway. "
    "No text. Square composition. Dark cosmic theme."
)


def _build_varied_prompt(base_prompt: str) -> str:
    """Return a quantum-varied prompt. Falls back to secrets.choice if quantum_rt unavailable."""
    import secrets
    import importlib
    try:
        for candidate in [r"f:\executedcode", r"f:\⟨ψ⟩Quantum\src\core"]:
            if candidate not in sys.path:
                sys.path.insert(0, candidate)
        _qrt = importlib.import_module("quantum_rt")
        _pick = _qrt.qhoice
        source = "quantum_rt"
    except Exception:
        _pick = secrets.choice
        source = "secrets.choice (fallback)"
    varied = _PROMPT_TEMPLATE.format(
        background=_pick(_STYLE_POOLS["background"]),
        palette=_pick(_STYLE_POOLS["palette"]),
        glow=_pick(_STYLE_POOLS["glow"]),
        texture=_pick(_STYLE_POOLS["texture"]),
    )
    print(f"  variation: {source}")
    return varied


# ── helpers ────────────────────────────────────────────────────────────────────

def _load_config() -> dict:
    if CONFIG_FILE.is_file():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    return {
        "prompt": "",
        "model": "dall-e-3",
        "size": "1024x1024",
        "quality": "hd",
        "generated_at": "",
        "cooldown_days": 3,
        "icon_png": "src/data/portal_icon.png",
        "icon_ico": "src/data/portal_icon.ico",
    }


def _save_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _generate_image(prompt: str, cfg: dict) -> Path:
    from src.integrations.dalle3.client import DallE3Client

    print(f"  model  : {cfg['model']}")
    print(f"  size   : {cfg['size']}")
    print(f"  quality: {cfg['quality']}")
    print(f"  prompt : {prompt[:120]}{'...' if len(prompt) > 120 else ''}")
    print()

    client = DallE3Client()
    raw_path = client.generate_image(
        prompt,
        output_dir=ICON_PNG.parent,
        size=cfg["size"],
        quality=cfg["quality"],
    )
    shutil.copy2(raw_path, ICON_PNG)
    print(f"\u2714 PNG saved \u2192 {ICON_PNG}")
    return ICON_PNG


def _build_ico(png_path: Path) -> Path:
    from PIL import Image

    img = Image.open(png_path).convert("RGBA")
    img.save(ICON_ICO, format="ICO", sizes=ICO_SIZES)
    raw = ICON_ICO.read_bytes()
    # ICO header: reserved=0, type=1, count>=1
    if not (len(raw) >= 6 and raw[0:4] == b"\x00\x00\x01\x00" and int.from_bytes(raw[4:6], "little") >= 1):
        raise RuntimeError(f"Generated ICO appears invalid: {ICON_ICO}")
    print(f"\u2714 ICO saved \u2192 {ICON_ICO} ({ICON_ICO.stat().st_size:,} bytes)")
    return ICON_ICO


def _escape_attr(s: str) -> str:
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def _update_sigil_tooltip(html: str, prompt: str) -> str:
    import re
    escaped = _escape_attr(prompt)
    html = re.sub(
        r'(<span[^>]*class="sigil"[^>]*)data-icon-prompt="[^"]*"',
        rf'\1data-icon-prompt="{escaped}"',
        html,
    )
    if 'data-icon-prompt="' not in html:
        html = html.replace(
            '<span class="sigil">\u2295</span>',
            f'<span class="sigil" data-icon-prompt="{escaped}" title="Icon prompt: {escaped}">\u2295</span>',
        )
    return html


def _inject_favicon(ico_path: Path, prompt: str) -> None:
    ico_b64 = base64.b64encode(ico_path.read_bytes()).decode("ascii")
    icon_version = f"{ico_path.stat().st_mtime_ns:x}-{ico_path.stat().st_size:x}"
    favicon_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        '<rect width="64" height="64" rx="14" fill="#0f1318"/>'
        '<circle cx="32" cy="32" r="20" fill="none" stroke="#8bd5ff" stroke-width="4"/>'
        '<text x="32" y="39" text-anchor="middle" font-size="28" '
        'font-family="Segoe UI, sans-serif" fill="#8bd5ff">⊕</text>'
        '</svg>'
    )
    favicon_svg_href = "data:image/svg+xml;utf8," + urllib.parse.quote(favicon_svg, safe="")
    favicon_ico_href = f"portal_icon.ico?v={icon_version}"
    favicon_tags = "\n".join([
        f'<link rel="icon" type="image/svg+xml" href="{favicon_svg_href}">',
        f'<link rel="icon" type="image/x-icon" href="{favicon_ico_href}">',
        f'<link rel="alternate icon" type="image/x-icon" href="data:image/x-icon;base64,{ico_b64}">',
        f'<meta name="portal-icon-status" content="ok">',
    ])
    prompt_meta = f'<meta name="portal-icon-prompt" content="{_escape_attr(prompt)}">'

    html = PORTAL_HTML.read_text(encoding="utf-8")
    lines = html.splitlines(keepends=True)
    html = "".join(l for l in lines if 'rel="icon"' not in l and "portal-icon-prompt" not in l)

    anchor = '<meta charset="utf-8">'
    if anchor not in html:
        print("\u26a0  Could not find charset anchor in portal.html \u2014 favicon NOT injected.")
        return
    html = html.replace(anchor, f"{anchor}\n{favicon_tags}\n{prompt_meta}", 1)
    html = _update_sigil_tooltip(html, prompt)
    PORTAL_HTML.write_text(html, encoding="utf-8")
    # Keep icon assets next to portal.html so local static servers resolve them.
    portal_dir = PORTAL_HTML.parent
    shutil.copy2(ico_path, portal_dir / "portal_icon.ico")
    shutil.copy2(ico_path, portal_dir / "favicon.ico")
    print(f"\u2714 Favicon re-injected \u2192 {PORTAL_HTML.name}")


def _refresh_shortcut(ico_path: Path) -> None:
    """Rebuild desktop shortcut with all three WScript.Shell Unicode workarounds.

    1. ASCII temp filename → rename to Unicode via Path.rename()
    2. Stage ICO to ASCII path (WScript.Shell silently drops Unicode IconLocation)
    3. Stage PS1 launcher to ASCII path (WScript.Shell corrupts Unicode in Arguments)
    """
    desktop    = Path(os.path.expanduser("~")) / "Desktop"
    tmp_lnk    = desktop / "_workspace_portal_tmp.lnk"
    final_lnk  = desktop / "\u2295 Workspace Portal.lnk"
    staging    = Path(os.environ["LOCALAPPDATA"]) / "WorkspacePortal"
    staging.mkdir(parents=True, exist_ok=True)
    staged_ico = staging / "portal_icon.ico"
    staged_ps1 = staging / "open_portal.ps1"
    shutil.copy2(ico_path, staged_ico)
    # BOM (utf-8-sig) required so PowerShell 5.1 reads the ⊕/❤ paths correctly.
    # Also starts the three ❤Music servers if they aren't already listening.
    launcher_lines = [
        # Music Dashboard :5050
        '$music = Get-NetTCPConnection -LocalPort 5050 -ErrorAction SilentlyContinue',
        'if (-not $music) {',
        '    Start-Process "C:\\G\\python.exe" -ArgumentList "f:\\❤Music\\src\\analysis\\music_dashboard.py","--port","5050" -WindowStyle Hidden',
        '}',
        # TJD Radio :8100
        '$radio = Get-NetTCPConnection -LocalPort 8100 -ErrorAction SilentlyContinue',
        'if (-not $radio) {',
        '    Start-Process "C:\\G\\python.exe" -ArgumentList "f:\\❤Music\\src\\radio\\tjd_radio.py","--port","8100" -WindowStyle Hidden',
        '}',
        # Guitar Trainer :5055
        '$guitar = Get-NetTCPConnection -LocalPort 5055 -ErrorAction SilentlyContinue',
        'if (-not $guitar) {',
        '    Start-Process "C:\\G\\python.exe" -ArgumentList "f:\\❤Music\\src\\training\\musician_training_ui.py","--port","5055" -WindowStyle Hidden',
        '}',
        # FR server :7474
        '$fr = Get-NetTCPConnection -LocalPort 7474 -ErrorAction SilentlyContinue',
        'if (-not $fr) {',
        '    Start-Process "C:\\G\\python.exe" -ArgumentList "f:\\⊕Workspace\\src\\utils\\fr_server.py" -WindowStyle Hidden',
        '}',
        # Open the portal
        f'Start-Process "{WORKSPACE_ROOT / "reports" / "portal.html"}"',
    ]
    staged_ps1.write_text("\n".join(launcher_lines) + "\n", encoding="utf-8-sig")
    for lnk in (tmp_lnk, final_lnk):
        if lnk.exists():
            lnk.unlink()
    try:
        import ctypes
        import subprocess
        import win32com.client  # type: ignore[import]

        powershell = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
        shell = win32com.client.Dispatch("WScript.Shell")
        sc = shell.CreateShortcut(str(tmp_lnk))
        sc.TargetPath       = powershell
        sc.Arguments        = f'-WindowStyle Hidden -NonInteractive -File "{staged_ps1}"'
        sc.WindowStyle      = 7
        sc.WorkingDirectory = str(WORKSPACE_ROOT / "reports")
        sc.IconLocation     = f"{staged_ico},0"
        sc.Description      = "\u2295 Workspace Portal \u2014 unified project dashboard"
        sc.Save()
        tmp_lnk.rename(final_lnk)
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
        subprocess.run(["ie4uinit.exe", "-show"], capture_output=True)
        print(f"\u2714 Desktop shortcut refreshed + icon cache flushed \u2192 {final_lnk.name}")
    except Exception as exc:
        print(f"\u26a0  Could not refresh desktop shortcut: {exc}")


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Regenerate the \u2295 Workspace Portal icon from a configurable DALL-E 3 prompt."
    )
    parser.add_argument("--prompt", metavar="TEXT", help="New generation prompt (saves to config)")
    parser.add_argument("--vary", action="store_true",
                        help="Quantum-vary the prompt aesthetics each run (does not overwrite stored prompt)")
    parser.add_argument("--show-prompt", action="store_true", help="Print current stored prompt and exit")
    parser.add_argument("--skip-shortcut", action="store_true", help="Skip desktop shortcut refresh")
    args = parser.parse_args()

    cfg = _load_config()

    if args.show_prompt:
        print("Current stored prompt:")
        print(cfg.get("prompt", "(none)"))
        return

    base_prompt = args.prompt or cfg.get("prompt", "")
    if not base_prompt:
        print("Error: no prompt configured. Run with --prompt 'your prompt here'")
        sys.exit(1)

    if args.prompt:
        cfg["prompt"] = args.prompt

    prompt = _build_varied_prompt(base_prompt) if args.vary else base_prompt
    cfg["generated_at"] = date.today().isoformat()
    _save_config(cfg)

    print("\n\u2295 Portal Icon Regeneration")
    print("=" * 50)

    print("\n[1/4] Generating image via DALL-E 3 \u2026")
    _generate_image(prompt, cfg)

    print("\n[2/4] Building multi-resolution ICO \u2026")
    _build_ico(ICON_PNG)

    print("\n[3/4] Re-injecting favicon + prompt into portal.html \u2026")
    _inject_favicon(ICON_ICO, prompt)

    if not args.skip_shortcut:
        print("\n[4/4] Refreshing desktop shortcut \u2026")
        _refresh_shortcut(ICON_ICO)

    print("\n\u2714 Done. Reload portal.html in your browser to see the new icon.")


if __name__ == "__main__":
    main()
