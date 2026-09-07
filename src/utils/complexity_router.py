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

from dataclasses import dataclass
from typing import Literal

Tier = Literal["light", "standard", "heavy"]
RoutingPath = Literal["normal", "recycled-light", "bounded-fix"]

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


@dataclass(frozen=True)
class BoundedFixEvidence:
    """Evidence required before a rejected FR may use the bounded-fix path."""

    files_changed: int
    project_count: int
    has_schema_change: bool
    has_dependency_change: bool
    has_agent_change: bool
    has_integration_change: bool
    has_authentication_change: bool
    has_secret_change: bool
    has_security_change: bool
    defect_classification: str
    focused_tests_passed: bool
    cross_module_change: bool
    contract_changed: bool


@dataclass(frozen=True)
class RoutingDecision:
    """Selected FR rework path and the gates that remain mandatory."""

    tier: Tier
    path: RoutingPath
    bypasses: tuple[str, ...] = ()
    preserved_gates: tuple[str, ...] = (
        "approval",
        "merge",
        "soak",
        "signoff",
    )
    evidence: tuple[str, ...] = ()
    rejection_reason: str = ""


def _bounded_fix_rejection(evidence: BoundedFixEvidence) -> str:
    """Return the first failed bounded-fix condition, or an empty string."""
    checks = (
        (evidence.files_changed <= _LIGHT_MAX_FILES, "more than 2 changed files"),
        (evidence.project_count == 1, "multiple projects"),
        (not evidence.has_schema_change, "schema change"),
        (not evidence.has_dependency_change, "dependency change"),
        (not evidence.has_agent_change, "agent change"),
        (not evidence.has_integration_change, "integration change"),
        (not evidence.has_authentication_change, "authentication change"),
        (not evidence.has_secret_change, "secret change"),
        (not evidence.has_security_change, "security-sensitive change"),
        (evidence.defect_classification == "localized", "non-localized defect"),
        (evidence.focused_tests_passed, "focused tests did not pass"),
        (not evidence.cross_module_change, "cross-module change"),
        (not evidence.contract_changed, "user-facing contract change"),
    )
    for passed, reason in checks:
        if not passed:
            return reason
    return ""


def select_routing_path(
    *,
    initial_tier: Tier,
    current_state: str,
    bounded_fix: BoundedFixEvidence | None = None,
) -> RoutingDecision:
    """Select normal, recycled-light, or eligible bounded-fix routing.

    ``CHANGES_REQUESTED`` is deliberately treated as a sticky light-tier
    recycling signal.  It is evaluated on every call, so repeated recycling
    cannot restore the original heavy or standard tier.
    """
    recycled = current_state == "CHANGES_REQUESTED"
    tier: Tier = "light" if recycled else initial_tier
    path: RoutingPath = "recycled-light" if recycled else "normal"
    evidence = ("state=CHANGES_REQUESTED",) if recycled else ()

    if bounded_fix is not None:
        if not recycled:
            return RoutingDecision(
                tier=tier,
                path=path,
                evidence=evidence,
                rejection_reason="bounded-fix requires CHANGES_REQUESTED state",
            )
        rejection_reason = _bounded_fix_rejection(bounded_fix)
        if not rejection_reason:
            return RoutingDecision(
                tier="light",
                path="bounded-fix",
                bypasses=("FUNCTIONAL_QA", "ARCHITECTURE_REVIEW"),
                evidence=("bounded-fix eligibility checks passed",),
            )
        return RoutingDecision(
            tier=tier,
            path=path,
            evidence=evidence,
            rejection_reason=rejection_reason,
        )

    return RoutingDecision(tier=tier, path=path, evidence=evidence)


def format_routing_event(decision: RoutingDecision) -> str:
    """Format auditable routing evidence for ``fr_cli.py record-event``."""
    evidence = "; ".join(decision.evidence) or "initial complexity assessment"
    summary = f"ROUTING_PATH: {decision.path}; TIER: {decision.tier}; EVIDENCE: {evidence}"
    if decision.rejection_reason:
        summary += f"; BOUNDED_BYPASS_REJECTED: {decision.rejection_reason}"
    if decision.bypasses:
        summary += f"; BYPASSES: {', '.join(decision.bypasses)}"
    summary += f"; PRESERVED_GATES: {', '.join(decision.preserved_gates)}"
    return summary


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
