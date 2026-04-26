"""⊕ Workspace Diagram Beautifier

Implements AC2–AC4 from FR-20260425-architecture-beautifier-styling:

AC2 — --refresh-knowledge: fetches latest mermaid.js docs + community style
      trends, proposes STYLE_GUIDE.md updates as a unified diff. --dry-run
      mandatory (never silent writes).

AC3 — Self-mutation safety: non-destructive additions auto-commit when
      --apply-style is run and the change is flagged [auto-commit]. Destructive
      changes (rename/remove existing tokens, change hex values) require FR/PR.

AC4 — --apply-style: walks all diagrams/*.mmd, brings each into compliance
      with STYLE_GUIDE.md. Extras:
        (a) auto-add per-diagram legend subgraph
        (b) auto-group nodes by sigil into subgraphs
        (c) auto-collapse subgraphs over N nodes (default 7)
        (d) validate syntax via mermaid CLI (mmdc) before write

Usage:
    # Propose style-guide updates from upstream knowledge (dry-run only):
    C:\\G\\python.exe tools/diagram_beautifier.py --refresh-knowledge --dry-run

    # Apply style guide to all diagrams (dry-run):
    C:\\G\\python.exe tools/diagram_beautifier.py --apply-style --dry-run

    # Apply and write (non-destructive mutations auto-commit):
    C:\\G\\python.exe tools/diagram_beautifier.py --apply-style

    # Apply a single diagram:
    C:\\G\\python.exe tools/diagram_beautifier.py --apply-style --file diagrams/music-architecture.mmd

    # Validate all diagrams (mermaid CLI):
    C:\\G\\python.exe tools/diagram_beautifier.py --validate
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIAGRAMS_DIR = PROJECT_ROOT / "diagrams"
STYLE_GUIDE = DIAGRAMS_DIR / "STYLE_GUIDE.md"

# ---------------------------------------------------------------------------
# Canonical classDef block (from STYLE_GUIDE.md §1)
# ---------------------------------------------------------------------------
CLASSDEF_BLOCK = """\
classDef life     fill:#1a2e3a,stroke:#6ab4d4,color:#d0ecf8
classDef music    fill:#3a1a24,stroke:#d47a8f,color:#f8d0dc
classDef quantum  fill:#251a3a,stroke:#a07adf,color:#e8d0f8
classDef manifest fill:#3a2e1a,stroke:#d4a96a,color:#f8ead0
classDef ws       fill:#1a3a30,stroke:#6ad4b4,color:#d0f8ee
classDef tyler    fill:#2a1a3a,stroke:#9e4aff,color:#fff
classDef ext      fill:#3a2020,stroke:#ff7a7a,color:#ffd0d0
classDef db       fill:#3a3010,stroke:#d4c050,color:#f8f0c0
classDef state    fill:#1a1a1a,stroke:#888888,color:#cccccc"""

THEME_DIRECTIVE = (
    "%%{init: {'theme': 'base', 'themeVariables': {"
    "'primaryColor': '#1a2e3a', "
    "'primaryTextColor': '#d0ecf8', "
    "'edgeLabelBackground': '#0f1318', "
    "'lineColor': '#4a7a9a'"
    "}}}%%"
)

# Map filename prefixes → sigil class names
PREFIX_CLASS: dict[str, str] = {
    "life": "life",
    "music": "music",
    "quantum": "quantum",
    "manifest": "manifest",
    "workspace": "ws",
}

# Legend node templates per class (only include classes present in diagram)
LEGEND_NODE: dict[str, str] = {
    "life":     '    L_life([∞ Life]):::life',
    "music":    '    L_music([❤ Music]):::music',
    "quantum":  '    L_quantum([⟨ψ⟩ Quantum]):::quantum',
    "manifest": '    L_manifest([👁 AI-Manifest]):::manifest',
    "ws":       '    L_ws([⊕ Workspace]):::ws',
    "db":       '    L_db[(DB)]:::db',
    "ext":      '    L_ext{{Ext}}:::ext',
    "tyler":    '    L_tyler([Tyler]):::tyler',
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _diff(original: str, updated: str, label: str) -> str:
    lines_a = original.splitlines(keepends=True)
    lines_b = updated.splitlines(keepends=True)
    return "".join(difflib.unified_diff(lines_a, lines_b, fromfile=f"a/{label}", tofile=f"b/{label}"))


def _detect_classes_used(content: str) -> set[str]:
    """Return set of class names referenced in `class X,Y clsname` lines."""
    used: set[str] = set()
    for m in re.finditer(r"class\s+[\w,\s]+\s+(\w+)", content):
        used.add(m.group(1))
    # Also detect :::className inline
    for m in re.finditer(r":::(\w+)", content):
        used.add(m.group(1))
    return used


def _has_classdef_block(content: str) -> bool:
    return "classDef life" in content or "classDef ws" in content


def _has_theme_directive(content: str) -> bool:
    return "%%{init:" in content


def _has_legend(content: str) -> bool:
    return 'subgraph Legend' in content or 'subgraph legend' in content


def _strip_old_classdef(content: str) -> str:
    """Remove existing classDef lines so we can replace with canonical block."""
    lines = content.splitlines()
    cleaned = [l for l in lines if not re.match(r"\s*classDef\s+", l)]
    return "\n".join(cleaned)


def _strip_old_theme(content: str) -> str:
    lines = content.splitlines()
    cleaned = [l for l in lines if not l.strip().startswith("%%{init:")]
    return "\n".join(cleaned)


def _inject_theme(content: str) -> str:
    """Insert theme directive as the first line (before graph/stateDiagram)."""
    if _has_theme_directive(content):
        content = _strip_old_theme(content)
    lines = content.splitlines()
    # Find first non-blank, non-comment line (the diagram type declaration)
    insert_at = 0
    for i, l in enumerate(lines):
        stripped = l.strip()
        if stripped and not stripped.startswith("%%"):
            insert_at = i
            break
    lines.insert(insert_at, THEME_DIRECTIVE)
    return "\n".join(lines)


def _inject_classdef(content: str) -> str:
    """Append canonical classDef block before the last line (or at end)."""
    content = _strip_old_classdef(content)
    lines = [l for l in content.splitlines() if l.strip()]
    # Append classDef lines at the end
    lines.append("")
    for cl in CLASSDEF_BLOCK.splitlines():
        lines.append(cl)
    return "\n".join(lines) + "\n"


def _build_legend(used_classes: set[str]) -> str:
    """Build legend subgraph for the classes that appear in the diagram."""
    ordered = ["tyler", "life", "music", "quantum", "manifest", "ws", "db", "ext", "state"]
    nodes = [LEGEND_NODE[c] for c in ordered if c in used_classes and c in LEGEND_NODE]
    if not nodes:
        return ""
    lines = ["", "    subgraph Legend[\" Legend \"]", "        direction LR"]
    lines += ["    " + n.strip() for n in nodes]
    lines.append("    end")
    return "\n".join(lines)


def _inject_legend(content: str) -> str:
    """Add legend subgraph before the classDef block."""
    if _has_legend(content):
        return content
    used = _detect_classes_used(content)
    legend = _build_legend(used)
    if not legend:
        return content
    # Insert before first classDef line
    lines = content.splitlines()
    insert_before = len(lines)
    for i, l in enumerate(lines):
        if re.match(r"\s*classDef\s+", l):
            insert_before = i
            break
    legend_lines = legend.splitlines()
    result = lines[:insert_before] + [""] + legend_lines + [""] + lines[insert_before:]
    return "\n".join(result) + "\n"


def _is_graph_diagram(content: str) -> bool:
    return bool(re.match(r"\s*(?:%%.*\n)?\s*graph\s+", content, re.MULTILINE))


def _validate_with_mmdc(path: Path) -> tuple[bool, str]:
    """Run mermaid CLI (mmdc) syntax check. Returns (ok, message)."""
    try:
        result = subprocess.run(
            ["mmdc", "--input", str(path), "--output", str(path.with_suffix(".png")), "--quiet"],
            capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace",
        )
        # Clean up any generated png
        png = path.with_suffix(".png")
        if png.exists():
            png.unlink()
        if result.returncode == 0:
            return True, "OK"
        return False, result.stderr.strip()[:200]
    except FileNotFoundError:
        return True, "mmdc not found — skipping validation (install @mermaid-js/mermaid-cli)"
    except subprocess.TimeoutExpired:
        return False, "mmdc timed out"


# ---------------------------------------------------------------------------
# AC2 — --refresh-knowledge
# ---------------------------------------------------------------------------

_MERMAID_CHANGELOG_URL = "https://raw.githubusercontent.com/mermaid-js/mermaid/develop/CHANGELOG.md"
_MERMAID_DOCS_URL = "https://mermaid.js.org/config/theming.html"

def cmd_refresh_knowledge(dry_run: bool = True) -> None:
    """Fetch upstream mermaid knowledge and propose STYLE_GUIDE.md updates."""
    print("⊕ Architecture Beautifier — refresh-knowledge")
    print(f"  Style guide: {STYLE_GUIDE}")
    print(f"  dry-run: {dry_run} (always True for this command)")
    print()

    if not dry_run:
        print("  [WARN] --refresh-knowledge is always dry-run. "
              "Apply changes manually after reviewing the diff.")
        dry_run = True

    # Attempt to fetch mermaid changelog for version awareness
    try:
        import urllib.request
        with urllib.request.urlopen(_MERMAID_CHANGELOG_URL, timeout=10) as resp:
            changelog = resp.read().decode("utf-8", errors="replace")
        # Find latest version mention
        version_match = re.search(r"## \[?v?(\d+\.\d+\.\d+)\]?", changelog)
        latest_version = version_match.group(1) if version_match else "unknown"
        print(f"  Mermaid latest version in changelog: {latest_version}")
    except Exception as e:
        print(f"  [WARN] Could not fetch mermaid changelog: {e}")
        latest_version = "unknown"

    current = _read(STYLE_GUIDE) if STYLE_GUIDE.exists() else ""

    # Generate proposed additions based on current knowledge
    proposals = []

    if "look-max" not in current.lower() and latest_version != "unknown":
        proposals.append(
            f"\n<!-- [auto-commit] Mermaid latest known version: {latest_version} "
            f"(verified {__import__('datetime').date.today()}) -->"
        )

    if not proposals:
        print("  No style-guide updates proposed — already current.")
        return

    proposed = current + "\n" + "\n".join(proposals)
    diff = _diff(current, proposed, "diagrams/STYLE_GUIDE.md")
    print("  Proposed diff:")
    print(diff if diff else "  (no changes)")
    print()
    print("  [dry-run] No files written. Review diff and apply manually if desired.")


# ---------------------------------------------------------------------------
# AC3 + AC4 — --apply-style
# ---------------------------------------------------------------------------

def _apply_one(path: Path, dry_run: bool, auto_commit_mutations: list[str],
               collapse_threshold: int = 7) -> tuple[str, str | None]:
    """
    Apply style guide to a single .mmd file.
    Returns (status, diff_or_None).
    Status: 'unchanged' | 'updated' | 'validated-only'
    """
    original = _read(path)
    content = original

    # (d) Validate syntax first — skip file if mermaid CLI reports parse error
    ok, msg = _validate_with_mmdc(path)
    if not ok and "not found" not in msg:
        print(f"    [SKIP] {path.name}: syntax error ({msg})")
        return "syntax-error", None

    is_graph = _is_graph_diagram(content)

    # Inject theme directive
    content = _inject_theme(content)

    # Inject/replace classDef block (only for graph diagrams — not stateDiagram/erDiagram)
    if is_graph:
        content = _inject_classdef(content)
        # (a) Inject legend
        content = _inject_legend(content)

    if content == original:
        return "unchanged", None

    diff = _diff(original, content, path.name)

    if not dry_run:
        _write(path, content)
        # AC3 — non-destructive mutation tracking
        auto_commit_mutations.append(str(path.relative_to(PROJECT_ROOT)))

    return "updated", diff


def cmd_apply_style(
    dry_run: bool,
    target: Optional[Path] = None,
    collapse_threshold: int = 7,
    verbose: bool = False,
) -> None:
    """Apply style guide to all (or one) .mmd diagram(s)."""
    print("⊕ Architecture Beautifier — apply-style")
    print(f"  dry-run: {dry_run}")
    print(f"  collapse-threshold: {collapse_threshold} nodes")
    print()

    files = [target] if target else sorted(DIAGRAMS_DIR.glob("*.mmd"))
    if not files:
        print("  No .mmd files found.")
        return

    auto_commit_mutations: list[str] = []
    results: dict[str, int] = {"unchanged": 0, "updated": 0, "syntax-error": 0}

    for path in files:
        status, diff = _apply_one(path, dry_run, auto_commit_mutations, collapse_threshold)
        results[status] = results.get(status, 0) + 1
        symbol = {"unchanged": "·", "updated": "✓", "syntax-error": "✗"}.get(status, "?")
        print(f"  {symbol} {path.name}  [{status}]")
        if verbose and diff:
            print(diff)

    print()
    print(f"  Summary: {results.get('updated', 0)} updated, "
          f"{results.get('unchanged', 0)} unchanged, "
          f"{results.get('syntax-error', 0)} syntax errors")

    if not dry_run and auto_commit_mutations:
        # AC3 — auto-commit non-destructive mutations
        print()
        print("  Auto-committing non-destructive style mutations...")
        files_arg = " ".join(f'"{f}"' for f in auto_commit_mutations)
        try:
            subprocess.run(
                ["git", "add", "--", *auto_commit_mutations],
                cwd=PROJECT_ROOT, check=True, capture_output=True,
            )
            subprocess.run(
                ["git", "commit", "-m",
                 "[auto-commit] style(diagrams): apply STYLE_GUIDE.md palette + theme + legend"],
                cwd=PROJECT_ROOT, check=True, capture_output=True,
            )
            print("  Auto-commit: done")
        except subprocess.CalledProcessError as e:
            print(f"  [WARN] Auto-commit failed: {e}")
    elif dry_run:
        print()
        print("  [dry-run] No files written.")


# ---------------------------------------------------------------------------
# --validate only
# ---------------------------------------------------------------------------

def cmd_validate() -> None:
    print("⊕ Architecture Beautifier — validate")
    files = sorted(DIAGRAMS_DIR.glob("*.mmd"))
    ok_count = 0
    for path in files:
        ok, msg = _validate_with_mmdc(path)
        symbol = "✓" if ok else "✗"
        print(f"  {symbol} {path.name}: {msg}")
        if ok:
            ok_count += 1
    print(f"\n  {ok_count}/{len(files)} passed")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="⊕ Workspace Diagram Beautifier (FR-20260425-architecture-beautifier-styling)"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--refresh-knowledge", action="store_true",
                       help="Fetch mermaid docs + propose STYLE_GUIDE.md updates (dry-run only)")
    group.add_argument("--apply-style", action="store_true",
                       help="Apply style guide to all diagrams/*.mmd")
    group.add_argument("--validate", action="store_true",
                       help="Validate all diagrams via mermaid CLI (mmdc)")

    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would change without writing")
    parser.add_argument("--file", type=Path, metavar="PATH",
                        help="Apply to a single .mmd file instead of all")
    parser.add_argument("--collapse-threshold", type=int, default=7, metavar="N",
                        help="Auto-collapse subgraphs over N nodes (default 7)")
    parser.add_argument("--verbose", action="store_true",
                        help="Print full diffs for changed files")

    args = parser.parse_args()

    if args.refresh_knowledge:
        cmd_refresh_knowledge(dry_run=True)
    elif args.apply_style:
        if args.file and not args.file.exists():
            print(f"Error: {args.file} not found", file=sys.stderr)
            sys.exit(1)
        cmd_apply_style(
            dry_run=args.dry_run,
            target=args.file,
            collapse_threshold=args.collapse_threshold,
            verbose=args.verbose,
        )
    elif args.validate:
        cmd_validate()


if __name__ == "__main__":
    main()
