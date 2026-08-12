#!/usr/bin/env python3
"""
⊕ Dashboard Registry — Spec-driven discovery and manifest builder

Scans all project roots for dashboard.json spec files, validates them,
and produces a unified manifest. Used by the portal renderer and the
dashboard agent.

Usage:
    C:\\G\\python.exe tools/dashboard_registry.py              # print manifest
    C:\\G\\python.exe tools/dashboard_registry.py --json        # JSON output
    C:\\G\\python.exe tools/dashboard_registry.py --validate    # validate specs only
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Derive workspace root dynamically: this file is tools/dashboard_registry.py
# inside one of the project repos; its parent.parent.parent is the root that
# contains all sibling project directories.
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Known project roots — discovered dynamically via AGENT_STARTUP.md presence
REQUIRED_SPEC_FIELDS = {"id", "title", "type", "category"}
VALID_TYPES = {"static_html", "living_html", "flask_app", "console", "inline_html"}


def _is_git_worktree_root(project_root: Path) -> bool:
    """Return True for a git worktree clone root that should not be treated as an independent project."""
    git_file = project_root / ".git"
    if not git_file.exists() or not git_file.is_file():
        return False
    try:
        contents = git_file.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    if not contents.startswith("gitdir:"):
        return False
    gitdir = contents.split(":", 1)[1].strip().replace("\\", "/")
    return ".git/worktrees/" in gitdir


def discover_projects() -> list[Path]:
    """Find all project directories containing AGENT_STARTUP.md."""
    if WORKSPACE_ROOT == PROJECT_ROOT.parent and _is_git_worktree_root(PROJECT_ROOT):
        return [PROJECT_ROOT]
    projects = []
    for child in sorted(WORKSPACE_ROOT.iterdir()):
        if not child.is_dir():
            continue
        if _is_git_worktree_root(child):
            continue
        if (child / "AGENT_STARTUP.md").exists():
            projects.append(child)
    return projects


def load_spec(project_root: Path) -> dict[str, Any] | None:
    """Load and validate a project's dashboard.json spec."""
    spec_path = project_root / "dashboard.json"
    if not spec_path.exists():
        return None
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"  [WARN] Invalid JSON in {spec_path}: {e}", file=sys.stderr)
        return None
    return spec


def validate_spec(spec: dict[str, Any], project_root: Path) -> list[str]:
    """Validate a dashboard spec. Returns list of error messages."""
    errors = []
    if "project" not in spec:
        errors.append("Missing 'project' field")
    if "dashboards" not in spec or not isinstance(spec["dashboards"], list):
        errors.append("Missing or invalid 'dashboards' array")
        return errors
    for i, dash in enumerate(spec["dashboards"]):
        prefix = f"dashboards[{i}]"
        missing = REQUIRED_SPEC_FIELDS - set(dash.keys())
        if missing:
            errors.append(f"{prefix}: missing fields {missing}")
        if dash.get("type") not in VALID_TYPES:
            errors.append(f"{prefix}: invalid type '{dash.get('type')}' (must be one of {VALID_TYPES})")
        gen = dash.get("generator", "")
        if gen and not (project_root / gen).exists():
            errors.append(f"{prefix}: generator not found: {project_root / gen}")
        if dash.get("type") == "static_html" and "output" in dash:
            # output path is relative to project root — just warn if missing
            out = project_root / dash["output"]
            if not out.exists():
                errors.append(f"{prefix}: output file not yet generated: {out}")
    return errors


def build_manifest(validate_only: bool = False) -> dict[str, Any]:
    """Discover all projects, load specs, build unified manifest."""
    projects = discover_projects()
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "workspace_root": str(WORKSPACE_ROOT),
        "projects": [],
        "dashboards": [],
        "errors": [],
    }

    for proj in projects:
        spec = load_spec(proj)
        if spec is None:
            manifest["projects"].append({
                "name": proj.name,
                "path": str(proj),
                "has_spec": False,
                "dashboard_count": 0,
            })
            continue

        errors = validate_spec(spec, proj)
        if errors:
            manifest["errors"].extend([f"{proj.name}: {e}" for e in errors])

        manifest["projects"].append({
            "name": spec.get("project", proj.name),
            "sigil": spec.get("sigil", ""),
            "path": str(proj),
            "has_spec": True,
            "dashboard_count": len(spec.get("dashboards", [])),
        })

        for dash in spec.get("dashboards", []):
            entry = {
                **dash,
                "project": spec.get("project", proj.name),
                "sigil": spec.get("sigil", ""),
                "project_root": str(proj),
            }
            # Resolve absolute paths for output files
            if "output" in dash:
                entry["output_abs"] = str(proj / dash["output"])
            if "generator" in dash:
                entry["generator_abs"] = str(proj / dash["generator"])
            manifest["dashboards"].append(entry)

    # Sort by priority (ascending). Dashboards without a priority field sort last.
    manifest["dashboards"].sort(key=lambda d: d.get("priority", 9999))

    return manifest


def print_manifest(manifest: dict[str, Any]) -> None:
    """Pretty-print manifest to console."""
    print(f"⊕ Dashboard Registry — {manifest['generated_at']}")
    print(f"  Workspace: {manifest['workspace_root']}")
    print()

    print(f"Projects ({len(manifest['projects'])}):")
    for p in manifest["projects"]:
        sigil = p.get("sigil", "")
        check = "✓" if p["has_spec"] else "✗"
        count = p["dashboard_count"]
        print(f"  [{check}] {p['name']}: {count} dashboard(s)")
    print()

    print(f"Dashboards ({len(manifest['dashboards'])}):")
    for d in manifest["dashboards"]:
        icon = d.get("icon", "📊")
        print(f"  {icon} {d['project']} / {d['title']}")
        print(f"     type={d['type']}  category={d['category']}")
        if "output_abs" in d:
            exists = Path(d["output_abs"]).exists()
            print(f"     output={d['output_abs']} {'[OK]' if exists else '[MISSING]'}")
        if "url" in d:
            print(f"     url={d['url']}")
    print()

    if manifest["errors"]:
        print(f"Validation Errors ({len(manifest['errors'])}):")
        for e in manifest["errors"]:
            print(f"  ⚠ {e}")
    else:
        print("  No validation errors.")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="⊕ Dashboard Registry")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--validate", action="store_true", help="Validate specs only")
    args = parser.parse_args()

    manifest = build_manifest(validate_only=args.validate)

    if args.json:
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
    else:
        print_manifest(manifest)

    if manifest["errors"] and args.validate:
        sys.exit(1)


if __name__ == "__main__":
    main()
