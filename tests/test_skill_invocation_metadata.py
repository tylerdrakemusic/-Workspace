"""Validate skill invocation metadata consumed by supported loaders."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = PROJECT_ROOT / ".github" / "skills"
ADAPTATIONS_ROOT = (
    PROJECT_ROOT
    / "tools"
    / "skill-sync-adaptations"
    / "davidondrej"
)


def _frontmatter(skill_path: Path) -> dict[str, object]:
    text = skill_path.read_text(encoding="utf-8")
    assert text.startswith("---")
    _, opening, remainder = text.partition("---")
    metadata_text, closing, _ = remainder.partition("---")
    assert opening and closing
    metadata = yaml.safe_load(metadata_text)
    assert isinstance(metadata, dict)
    return metadata


@pytest.mark.parametrize(
    ("skill_name", "expected_description"),
    [
        (
            "before-building",
            "Surface consequential choices in a proposed build. Invoke manually with /before-building.",
        ),
        (
            "decisions",
            "List uncertain decisions from the current work. Invoke manually with /decisions.",
        ),
    ],
)
def test_staged_adaptations_resolve_to_supported_manual_only_metadata(
    skill_name: str, expected_description: str
) -> None:
    metadata = _frontmatter(
        ADAPTATIONS_ROOT / skill_name / "SKILL.md"
    )

    assert metadata["user-invocable"] is True
    assert metadata["disable-model-invocation"] is True
    assert metadata["description"] == expected_description
    assert "triggers" not in metadata


def test_model_invoked_control_skill_remains_automatically_reachable() -> None:
    metadata = _frontmatter(SKILLS_ROOT / "test-driven-development" / "SKILL.md")

    assert metadata.get("disable-model-invocation", False) is False
    assert metadata.get("user-invocable", True) is True


def test_sync_config_pins_only_the_two_reviewed_adaptations() -> None:
    config = json.loads(
        (PROJECT_ROOT / "tools" / "skill-sync-config.json").read_text(
            encoding="utf-8"
        )
    )
    repo = next(
        item for item in config["repos"] if item["name"] == "davidondrej-skills"
    )
    adaptations = repo["reviewed_skill_adaptations"]

    assert set(adaptations) == {"thinking-and-docs/before-building", "thinking-and-docs/decisions"}
    for skill, adaptation in adaptations.items():
        staged_path = PROJECT_ROOT / adaptation["source_relative_path"]
        assert adaptation["sha256"] == hashlib.sha256(staged_path.read_bytes()).hexdigest()
