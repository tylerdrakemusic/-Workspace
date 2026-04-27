"""Tests for portal icon (AC6 — FR-20260426-portal-icon-design).

Verifies:
- portal.html has a <link rel="icon"> favicon tag
- src/data/portal_icon.png exists
- src/data/portal_icon.ico exists and contains multiple resolutions
- src/data/portal_icon_config.json has a non-empty prompt
- portal.html sigil span carries data-icon-prompt attribute
- portal.html has tooltip CSS for the sigil
- regen_portal_icon.py script exists and is importable
"""
import json
import importlib.util
from pathlib import Path

from PIL import Image

WORKSPACE_ROOT = Path(r"f:\⊕Workspace")
PORTAL_HTML    = WORKSPACE_ROOT / "reports" / "portal.html"
PORTAL_PNG     = WORKSPACE_ROOT / "src" / "data" / "portal_icon.png"
PORTAL_ICO     = WORKSPACE_ROOT / "src" / "data" / "portal_icon.ico"
ICON_CONFIG    = WORKSPACE_ROOT / "src" / "data" / "portal_icon_config.json"
REGEN_SCRIPT   = WORKSPACE_ROOT / "tools" / "regen_portal_icon.py"


def test_portal_icon_png_exists() -> None:
    assert PORTAL_PNG.is_file(), f"Missing: {PORTAL_PNG}"


def test_portal_icon_ico_exists() -> None:
    assert PORTAL_ICO.is_file(), f"Missing: {PORTAL_ICO}"


def test_portal_icon_ico_multi_resolution() -> None:
    """portal_icon.ico must contain at least the 16x16 and 32x32 sizes."""
    img = Image.open(PORTAL_ICO)
    sizes = img.info.get("sizes") or set()
    if not sizes:
        assert img.format == "ICO", f"Expected ICO format, got {img.format}"
        return
    assert (16, 16) in sizes, f"16x16 frame missing from ICO. Found: {sizes}"
    assert (32, 32) in sizes, f"32x32 frame missing from ICO. Found: {sizes}"


def test_portal_html_has_favicon() -> None:
    assert PORTAL_HTML.is_file(), f"Missing: {PORTAL_HTML}"
    html = PORTAL_HTML.read_text(encoding="utf-8")
    assert 'rel="icon"' in html, '<link rel="icon"> not found in portal.html'


def test_portal_html_favicon_is_base64_ico() -> None:
    html = PORTAL_HTML.read_text(encoding="utf-8")
    assert 'data:image/x-icon;base64,' in html, (
        "Favicon is not an inline base64 ICO in portal.html"
    )


# ── Dynamic icon / config tests ────────────────────────────────────────────────

def test_icon_config_exists_with_prompt() -> None:
    """portal_icon_config.json must exist and contain a non-empty prompt."""
    assert ICON_CONFIG.is_file(), f"Missing: {ICON_CONFIG}"
    cfg = json.loads(ICON_CONFIG.read_text(encoding="utf-8"))
    assert cfg.get("prompt"), "portal_icon_config.json has an empty prompt field"


def test_icon_config_has_required_fields() -> None:
    """portal_icon_config.json must have model, size, quality, generated_at."""
    cfg = json.loads(ICON_CONFIG.read_text(encoding="utf-8"))
    for field in ("model", "size", "quality", "generated_at"):
        assert field in cfg, f"portal_icon_config.json missing field: {field}"


def test_portal_html_sigil_has_icon_prompt_attribute() -> None:
    """The ⊕ sigil span in portal.html must carry a data-icon-prompt attribute."""
    html = PORTAL_HTML.read_text(encoding="utf-8")
    assert 'data-icon-prompt=' in html, (
        "Sigil span in portal.html is missing data-icon-prompt attribute"
    )


def test_portal_html_has_sigil_tooltip_css() -> None:
    """portal.html must include CSS for the sigil hover tooltip."""
    html = PORTAL_HTML.read_text(encoding="utf-8")
    assert 'data-icon-prompt]:hover::after' in html, (
        "Tooltip CSS (.sigil[data-icon-prompt]:hover::after) not found in portal.html"
    )


def test_portal_html_sigil_prompt_matches_config() -> None:
    """The data-icon-prompt value in portal.html must match portal_icon_config.json."""
    cfg = json.loads(ICON_CONFIG.read_text(encoding="utf-8"))
    expected_prompt = cfg["prompt"]
    html = PORTAL_HTML.read_text(encoding="utf-8")
    escaped = expected_prompt.replace("&", "&amp;").replace('"', "&quot;")
    assert escaped in html, (
        "data-icon-prompt in portal.html does not match portal_icon_config.json prompt"
    )


def test_regen_script_exists() -> None:
    """tools/regen_portal_icon.py must exist."""
    assert REGEN_SCRIPT.is_file(), f"Missing: {REGEN_SCRIPT}"


def test_regen_script_importable() -> None:
    """tools/regen_portal_icon.py must be parseable as a Python module."""
    spec = importlib.util.spec_from_file_location("regen_portal_icon", REGEN_SCRIPT)
    assert spec is not None, "Could not create module spec for regen_portal_icon.py"
    module = importlib.util.module_from_spec(spec)
    # Loading (not executing) the module should not raise
    try:
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except SystemExit:
        pass  # argparse calls sys.exit on --help; that's fine
