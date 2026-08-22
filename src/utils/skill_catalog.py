"""Load and validate the canonical local skill inventory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_ENTRY_FIELDS = {
    "name",
    "provenance",
    "invocation_mode",
    "purpose",
    "overlap_candidates",
    "audience",
    "disposition",
    "canonical_id",
}
REQUIRED_STRING_FIELDS = {
    "name",
    "provenance",
    "invocation_mode",
    "purpose",
    "audience",
    "disposition",
    "canonical_id",
}


def load_catalog(path: Path) -> dict[str, Any]:
    """Load a UTF-8 JSON skill catalog."""
    with path.open(encoding="utf-8") as catalog_file:
        return json.load(catalog_file)


def validate_catalog(catalog: dict[str, Any], skills_root: Path) -> list[str]:
    """Return validation errors for a catalog and its local skill directory."""
    errors: list[str] = []
    entries = catalog.get("skills")
    if not isinstance(entries, list):
        return ["catalog.skills must be a list"]

    local_names = sorted(path.parent.name for path in skills_root.glob("*/SKILL.md"))
    names = [entry.get("name") for entry in entries if isinstance(entry, dict)]
    missing_local_names = sorted(set(local_names) - set(names))
    extra_catalog_names = sorted(set(names) - set(local_names))
    for name in missing_local_names:
        errors.append(f"catalog entry missing local skill directory: {name}")
    for name in extra_catalog_names:
        errors.append(f"catalog entry has no local skill directory: {name}")

    canonical_ids: set[str] = set()
    skill_names: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"skills[{index}] must be an object")
            continue
        missing = REQUIRED_ENTRY_FIELDS - entry.keys()
        if missing:
            errors.append(f"skills[{index}] missing fields: {', '.join(sorted(missing))}")
        for field in sorted(REQUIRED_STRING_FIELDS & entry.keys()):
            if not isinstance(entry[field], str) or not entry[field].strip():
                errors.append(f"skills[{index}].{field} must be a non-empty string")
        name = entry.get("name")
        if name in skill_names:
            errors.append(f"duplicate skill name: {name}")
        elif isinstance(name, str):
            skill_names.add(name)
        canonical_id = entry.get("canonical_id")
        if canonical_id in canonical_ids:
            errors.append(f"duplicate canonical_id: {canonical_id}")
        elif isinstance(canonical_id, str):
            canonical_ids.add(canonical_id)
        if not isinstance(entry.get("overlap_candidates"), list):
            errors.append(f"skills[{index}].overlap_candidates must be a list")

    sync_entries = catalog.get("external_sync", [])
    if not isinstance(sync_entries, list):
        errors.append("external_sync must be a list")
        sync_entries = []
    valid_sync_entries: list[dict[str, Any]] = []
    for index, item in enumerate(sync_entries):
        if not isinstance(item, dict):
            errors.append(f"external_sync[{index}] must be an object")
            continue
        mapping_is_valid = True
        for field in ("source", "target"):
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(
                    f"external_sync[{index}].{field} must be a non-empty string"
                )
                mapping_is_valid = False
        if mapping_is_valid:
            valid_sync_entries.append(item)
    sync_sources = [item.get("source") for item in valid_sync_entries]
    if len(sync_sources) != len(set(sync_sources)):
        for source in sorted({source for source in sync_sources if sync_sources.count(source) > 1}):
            errors.append(f"duplicate external synchronization source: {source}")
    sync_pairs = [(item.get("source"), item.get("target")) for item in valid_sync_entries]
    if len(sync_pairs) != len(set(sync_pairs)):
        errors.append("duplicate external synchronization mapping")
    if len({item.get("target") for item in valid_sync_entries}) != len(valid_sync_entries):
        errors.append("external synchronization targets must be unique")
    return errors