"""
complexity_router.py — FR complexity assessment for tiered model routing.

Used by orchestrators and the overseer to select the correct model tier
(light / standard / heavy) before delegating TDD, QA, and Review work.

Tiers map to the following model matrix:
  light    (0.33x)  — Claude Haiku 4.5   / GPT-5.4 mini   / Gemini 3 Flash
  standard (1x)     — Claude Sonnet 4.6  / GPT-5.3-Codex  / Gemini 2.5 Pro
  heavy    (premium)— Claude Opus 4.8    / GPT-5.5        / Gemini 3.1 Pro
"""
from __future__ import annotations

from typing import Literal

Tier = Literal["light", "standard", "heavy"]

# Thresholds
_LIGHT_MAX_FILES = 2
_STANDARD_MAX_FILES = 10


def assess_tier(
    *,
    files_changed: int,
    has_new_schema: bool,
    has_new_agents: bool,
    project_count: int,
    is_security_sensitive: bool,
) -> Tier:
    """Return the complexity tier for a feature request.

    Heavy signals (any one → heavy):
      - 10+ files changed
      - new DB schema (tables or columns)
      - new agents or integrations introduced
      - spans 3+ projects
      - security-sensitive (health data, auth, secrets)

    Light signals (all must be true → light):
      - ≤2 files changed
      - no schema changes, no new agents, single project, not security-sensitive

    Everything else → standard.
    """
    # Heavy gate — any hard signal escalates immediately
    if (
        files_changed > _STANDARD_MAX_FILES
        or has_new_schema
        or has_new_agents
        or project_count >= 3
        or is_security_sensitive
    ):
        return "heavy"

    # Light gate — must satisfy ALL conditions
    if (
        files_changed <= _LIGHT_MAX_FILES
        and not has_new_schema
        and not has_new_agents
        and project_count == 1
        and not is_security_sensitive
    ):
        return "light"

    return "standard"


# ── CLI helper (not required by agents — for manual inspection) ───────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Assess FR complexity tier")
    parser.add_argument("--files", type=int, default=1, help="Number of files changed")
    parser.add_argument("--new-schema", action="store_true")
    parser.add_argument("--new-agents", action="store_true")
    parser.add_argument("--projects", type=int, default=1)
    parser.add_argument("--security", action="store_true")
    args = parser.parse_args()

    tier = assess_tier(
        files_changed=args.files,
        has_new_schema=args.new_schema,
        has_new_agents=args.new_agents,
        project_count=args.projects,
        is_security_sensitive=args.security,
    )
    print(tier)
