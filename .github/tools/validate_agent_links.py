"""Cross-repo agent/instruction link validator.

Scans all known agent and instruction locations, verifies inheritance links,
checks 'Known specialists' tables, and flags orphaned or phantom agents.

Run: C:\G\python.exe tools/validate_agent_links.py
"""

import os
import re
import sys
from pathlib import Path

# ── Known locations ──────────────────────────────────────────────────────────

AGENT_DIRS = [
    Path(r"f:\.github\agents"),
    Path(r"f:\superpowers\agents"),
]

INSTRUCTION_DIR = Path(r"f:\.github\instructions")

# Files that contain "Known specialists" tables or agent references
REFERENCE_FILES = [
    *INSTRUCTION_DIR.glob("*.instructions.md"),
    Path(r"f:\superpowers\AGENTS.md"),
    Path(r"f:\.github\copilot-instructions.md"),
    Path(r"f:\executedcode\∞Life\AGENT_STARTUP.md"),
    Path(r"f:\executedcode\❤Music\AGENT_STARTUP.md"),
    Path(r"f:\executedcode\⟨ψ⟩Quantum\AGENT_STARTUP.md"),
    Path(r"f:\executedcode\⊕Workspace\AGENT_STARTUP.md"),
]


def discover_agent_files() -> dict[str, Path]:
    """Return {agent_name: path} for all .agent.md and .md files in agent dirs."""
    agents = {}
    for d in AGENT_DIRS:
        if not d.exists():
            continue
        for f in d.iterdir():
            if f.suffix == ".md":
                stem = f.stem.replace(".agent", "")
                agents[stem] = f
    return agents


def discover_instruction_files() -> dict[str, Path]:
    """Return {filename: path} for all instruction files."""
    if not INSTRUCTION_DIR.exists():
        return {}
    return {f.name: f for f in INSTRUCTION_DIR.glob("*.instructions.md")}


def extract_frontmatter(path: Path) -> dict[str, str]:
    """Pull description and applyTo from YAML frontmatter."""
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    block = m.group(1)
    result = {}
    for key in ("description", "applyTo", "name"):
        km = re.search(rf'^{key}:\s*["\']?(.*?)["\']?\s*$', block, re.MULTILINE)
        if km:
            result[key] = km.group(1)
    return result


def extract_inherits(path: Path) -> list[str]:
    """Pull all <!-- inherits: ... --> comment paths."""
    text = path.read_text(encoding="utf-8", errors="replace")
    return re.findall(r"<!--\s*inherits:\s*(.*?)\s*-->", text)


def extract_specialist_references(path: Path) -> list[str]:
    """Pull agent names from Known specialists tables and agent references."""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    refs = []
    # Table rows like: | `∞life-research` | ...
    # Only match simple names (no paths, globs, or date placeholders)
    for m in re.findall(r"\|\s*`([^`]+)`\s*\|", text):
        if "/" not in m and "*" not in m and "." not in m and " " not in m:
            refs.append(m)
    # Table rows like: | **⟨ψ⟩quantum-orchestrator** | ...
    for m in re.findall(r"\|\s*\*\*([^*]+)\*\*\s*\|", text):
        if "/" not in m and "*" not in m and "." not in m and " " not in m:
            refs.append(m)
    # @agent references like: @∞life-risk
    refs.extend(re.findall(r"@([\w∞❤-]+(?:-\w+)+)", text))
    # Dedupe
    return list(set(refs))


def check_apply_to(pattern: str, all_files: list[Path]) -> list[Path]:
    """Check if an applyTo glob matches at least one existing file."""
    import fnmatch

    base = Path(r"f:\\")
    matches = []
    for f in all_files:
        try:
            rel = f.relative_to(base)
        except ValueError:
            continue
        if fnmatch.fnmatch(str(rel).replace("\\", "/"), pattern):
            matches.append(f)
    return matches


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    agents = discover_agent_files()
    instructions = discover_instruction_files()
    issues: list[str] = []
    warnings: list[str] = []

    print("=" * 60)
    print("AGENT LINK VALIDATION REPORT")
    print("=" * 60)

    # ── 1. Inventory ─────────────────────────────────────────────────────
    print(f"\nDiscovered {len(agents)} agent(s):")
    for name, path in sorted(agents.items()):
        print(f"  {name:30s}  {path}")
    print(f"\nDiscovered {len(instructions)} instruction(s):")
    for name, path in sorted(instructions.items()):
        print(f"  {name:45s}  {path}")

    # ── 2. Frontmatter checks ────────────────────────────────────────────
    print("\n── Frontmatter Checks ──")
    for name, path in sorted(agents.items()):
        fm = extract_frontmatter(path)
        if not fm.get("description"):
            issues.append(f"MISSING DESCRIPTION: {path}")

    for name, path in sorted(instructions.items()):
        fm = extract_frontmatter(path)
        if not fm.get("applyTo") and not fm.get("description"):
            warnings.append(f"NO applyTo OR description (never auto-loaded): {path}")

    # ── 3. Inheritance link checks ───────────────────────────────────────
    print("\n── Inheritance Links ──")
    for name, path in sorted(agents.items()):
        inherits = extract_inherits(path)
        if not inherits:
            warnings.append(f"NO INHERITANCE declared: {name} ({path})")
        for link in inherits:
            link_path = Path(link)
            if not link_path.exists():
                issues.append(f"BROKEN INHERIT: {name} → {link} (file not found)")
            else:
                print(f"  OK  {name} → {link_path.name}")

    # ── 4. Specialist table cross-check ──────────────────────────────────
    print("\n── Specialist Table Cross-Check ──")
    all_referenced: set[str] = set()
    for ref_file in REFERENCE_FILES:
        refs = extract_specialist_references(ref_file)
        all_referenced.update(refs)

    # Agents on disk but never referenced
    for name in sorted(agents):
        if name not in all_referenced:
            warnings.append(f"ORPHANED AGENT (on disk, never referenced): {name}")
        else:
            print(f"  OK  {name} referenced in docs")

    # Referenced in docs but no agent file
    instruction_stems = {n.replace(".instructions.md", "") for n in instructions}
    for ref in sorted(all_referenced):
        if ref not in agents:
            # Only flag things that look like agent names (contain hyphen)
            # Exclude instruction file stems (e.g. ∞life-python is an instruction, not an agent)
            if "-" in ref and ref not in instruction_stems:
                issues.append(f"PHANTOM AGENT (referenced in docs, no file): {ref}")

    # ── 5. applyTo validation ────────────────────────────────────────────
    print("\n── applyTo Pattern Checks ──")
    all_md_files = list(Path(r"f:\.github").rglob("*.md"))
    for name, path in sorted(instructions.items()):
        fm = extract_frontmatter(path)
        pattern = fm.get("applyTo")
        if pattern:
            matches = check_apply_to(pattern, all_md_files)
            if matches:
                print(f"  OK  {name}: '{pattern}' → {len(matches)} match(es)")
            else:
                warnings.append(f"applyTo MATCHES NOTHING: {name} pattern='{pattern}'")

    # ── Summary ──────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if issues:
        print(f"\n🔴 ISSUES ({len(issues)}):")
        for i in issues:
            print(f"  ✗ {i}")
    if warnings:
        print(f"\n🟡 WARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"  ⚠ {w}")
    if not issues and not warnings:
        print("\n✅ All agent links valid. No issues found.")

    total = len(issues) + len(warnings)
    print(f"\nTotal: {len(issues)} issue(s), {len(warnings)} warning(s)")
    print("=" * 60)
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
