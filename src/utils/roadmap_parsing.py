"""Parsing and project-name normalization for roadmap data."""
from __future__ import annotations

import re
from typing import Any

UNMAPPED_PROJECT = "Unmapped"
CANONICAL_PROJECTS = ["∞Life", "❤Music", "⟨ψ⟩Quantum", "👁AI-Manifest", "⊕Workspace", "ΣCapital"]

_PROJECT_KEYWORDS: list[tuple[str, str]] = [
    ("infinitelife", "∞Life"),
    ("psiquantum", "⟨ψ⟩Quantum"),
    ("sigmacapital", "ΣCapital"),
    ("heartmusic", "❤Music"),
    ("oplusworkspace", "⊕Workspace"),
    ("aimanifest", "👁AI-Manifest"),
    ("inflife", "∞Life"),
    ("quantum", "⟨ψ⟩Quantum"),
    ("workspace", "⊕Workspace"),
    ("music", "❤Music"),
    ("capital", "ΣCapital"),
    ("life", "∞Life"),
]
_NON_LETTER_RE = re.compile(r"[^a-z]")
_DEPENDS_ON_RE = re.compile(
    r"Depends on:\s*([A-Za-z0-9_,\s-]*FR-\d{8}-[\w-]+[A-Za-z0-9_,\s-]*)",
    re.IGNORECASE,
)
_FR_ID_RE = re.compile(r"FR-\d{8}-[\w-]+")


def _normalize_project_token(raw: str) -> str:
    return _NON_LETTER_RE.sub("", raw.lower())


def canonicalize_project(raw: str | None) -> str:
    """Map a raw project alias to a canonical project name."""
    if not raw or not raw.strip():
        return UNMAPPED_PROJECT
    token = _normalize_project_token(raw)
    if not token:
        return UNMAPPED_PROJECT
    for keyword, canonical in _PROJECT_KEYWORDS:
        if keyword in token:
            return canonical
    return UNMAPPED_PROJECT


def parse_dependencies(text: str | None) -> list[str]:
    """Extract de-duplicated FR IDs from dependency markers."""
    if not text:
        return []
    found: list[str] = []
    for match in _DEPENDS_ON_RE.finditer(text):
        for fr_id in _FR_ID_RE.findall(match.group(1)):
            if fr_id not in found:
                found.append(fr_id)
    return found


def extract_fr_dependencies(fr: dict[str, Any]) -> list[str]:
    """Collect dependency IDs from an FR's text fields."""
    dependencies: list[str] = []
    for field in ("title", "acceptance_criteria", "concurrency_notes"):
        for fr_id in parse_dependencies(fr.get(field)):
            if fr_id not in dependencies and fr_id != fr.get("id"):
                dependencies.append(fr_id)
    return dependencies


def extract_todo_fr_references(todo_text: str | None) -> list[str]:
    """Extract de-duplicated FR IDs from todo text."""
    if not todo_text:
        return []
    found: list[str] = []
    for fr_id in _FR_ID_RE.findall(todo_text):
        if fr_id not in found:
            found.append(fr_id)
    return found