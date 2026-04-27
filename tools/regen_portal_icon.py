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

    # Preview config without regenerating:
    python tools/regen_portal_icon.py --show-prompt
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import date
from pathlib import Path

# ── paths ──────────────────────────────────────────────────────────────────────
WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE_ROOT))

CONFIG_FILE = WORKSPACE_ROOT / "src" / "data" / "portal_icon_config.json"
PORTAL_HTML = WORKSPACE_ROOT / "reports" / "portal.html"
ICON_PNG    = WORKSPACE_ROOT / "src" / "data" / "portal_icon.png"
ICON_ICO    = WORKSPACE_ROOT / "src" / "data" / "portal_icon.ico"

# ICO sizes to embed
ICO_SIZES = [(16, 16), (32, 32), (48, 48), (256, 256)]

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
    # Copy / rename to canonical portal_icon.png
    import shutil
    shutil.copy2(raw_path, ICON_PNG)
    print(f"✔ PNG saved → {ICON_PNG}")
    return ICON_PNG


def _build_ico(png_path: Path) -> Path:
    from PIL import Image

    img = Image.open(png_path).convert("RGBA")
    img.save(ICON_ICO, format="ICO", sizes=ICO_SIZES)
    print(f"✔ ICO saved → {ICON_ICO} ({ICON_ICO.stat().st_size:,} bytes)")
    return ICON_ICO


def _inject_favicon(ico_path: Path, prompt: str) -> None:
    ico_b64 = base64.b64encode(ico_path.read_bytes()).decode("ascii")
    favicon_tag = (
        f'<link rel="icon" type="image/x-icon" '
        f'href="data:image/x-icon;base64,{ico_b64}">'
    )
    prompt_meta = (
        f'<meta name="portal-icon-prompt" content="{_escape_attr(prompt)}">'
    )

    html = PORTAL_HTML.read_text(encoding="utf-8")

    # Strip any existing favicon / prompt meta lines
    lines = html.splitlines(keepends=True)
    cleaned = [
        l for l in lines
        if 'rel="icon"' not in l and 'portal-icon-prompt' not in l
    ]
    html = "".join(cleaned)

    # Inject after charset meta
    anchor = '<meta charset="utf-8">'
    replacement = f'{anchor}\n{favicon_tag}\n{prompt_meta}'
    if anchor not in html:
        print("⚠  Could not find charset anchor in portal.html — favicon NOT injected.")
        return
    html = html.replace(anchor, replacement, 1)

    # Also update the sigil tooltip data-attribute if present
    html = _update_sigil_tooltip(html, prompt)

    PORTAL_HTML.write_text(html, encoding="utf-8")
    print(f"✔ Favicon re-injected → {PORTAL_HTML.name}")


def _escape_attr(s: str) -> str:
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def _update_sigil_tooltip(html: str, prompt: str) -> str:
    """Update the data-icon-prompt attribute on the .sigil span if present."""
    import re
    escaped = _escape_attr(prompt)
    # Replace existing data-icon-prompt
    html = re.sub(
        r'(<span[^>]*class="sigil"[^>]*)data-icon-prompt="[^"]*"',
        rf'\1data-icon-prompt="{escaped}"',
        html,
    )
    # Add data-icon-prompt if not present
    if 'data-icon-prompt' not in html:
        html = html.replace(
            '<span class="sigil">⊕</span>',
            f'<span class="sigil" data-icon-prompt="{escaped}" title="Icon prompt: {escaped}">⊕</span>',
        )
    return html


def _refresh_shortcut(ico_path: Path) -> None:
    import os
    desktop = Path(os.path.expanduser("~")) / "Desktop"
    shortcut_path = desktop / "\u2295 Workspace Portal.lnk"
    try:
        import win32com.client  # type: ignore[import]
        shell = win32com.client.Dispatch("WScript.Shell")
        sc = shell.CreateShortcut(str(shortcut_path))
        sc.TargetPath       = "powershell.exe"
        sc.Arguments        = (
            r'-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden '
            r'-File "f:\⊕Workspace\open_portal.ps1"'
        )
        sc.WorkingDirectory = str(WORKSPACE_ROOT)
        sc.IconLocation     = f"{ico_path},0"
        sc.Description      = "\u2295 Workspace Portal \u2014 unified project dashboard"
        sc.Save()
        print(f"\u2714 Desktop shortcut refreshed \u2192 {shortcut_path.name}")
    except Exception as exc:
        print(f"\u26a0  Could not refresh desktop shortcut: {exc}")


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Regenerate the ⊕ Workspace Portal icon from a configurable DALL-E 3 prompt."
    )
    parser.add_argument("--prompt", metavar="TEXT", help="New generation prompt (saves to config)")
    parser.add_argument("--show-prompt", action="store_true", help="Print current stored prompt and exit")
    parser.add_argument("--skip-shortcut", action="store_true", help="Skip desktop shortcut refresh")
    args = parser.parse_args()

    cfg = _load_config()

    if args.show_prompt:
        print("Current stored prompt:")
        print(cfg.get("prompt", "(none)"))
        return

    prompt = args.prompt or cfg.get("prompt", "")
    if not prompt:
        print("Error: no prompt configured. Run with --prompt 'your prompt here'")
        sys.exit(1)

    if args.prompt:
        cfg["prompt"] = args.prompt

    cfg["generated_at"] = date.today().isoformat()
    _save_config(cfg)

    print("\n⊕ Portal Icon Regeneration")
    print("=" * 50)

    print("\n[1/4] Generating image via DALL-E 3 …")
    _generate_image(prompt, cfg)

    print("\n[2/4] Building multi-resolution ICO …")
    _build_ico(ICON_PNG)

    print("\n[3/4] Re-injecting favicon + prompt into portal.html …")
    _inject_favicon(ICON_ICO, prompt)

    if not args.skip_shortcut:
        print("\n[4/4] Refreshing desktop shortcut …")
        _refresh_shortcut(ICON_ICO)

    print("\n✔ Done. Reload portal.html in your browser to see the new icon.")


if __name__ == "__main__":
    main()
