from pathlib import Path


ROOT = Path(__file__).parents[1]
AGENTS = ROOT / ".github" / "agents"
INSTRUCTIONS = ROOT / ".github" / "instructions"


def _read_agent(name: str) -> str:
    return (AGENTS / name).read_text(encoding="utf-8")


def test_shared_guidance_documents_worktree_aware_heartmusic_db_access() -> None:
    guidance = (INSTRUCTIONS / "hygiene-base.instructions.md").read_text(encoding="utf-8")

    assert "heartmusic.db" in guidance
    assert "use_worktree_aware_db_path" in guidance
    assert ".worktrees/<branch>" in guidance


def test_reviewer_defines_security_fallback_when_subagent_invocation_is_unavailable() -> None:
    reviewer = _read_agent("⊕workspace-reviewer.agent.md")

    assert "subagent invocation is unavailable" in reviewer.lower()
    assert "run the security checks inline" in reviewer.lower()
    assert "record" in reviewer.lower() and "security" in reviewer.lower()


def test_architecture_reviewer_documents_explicit_user_direction_state_exception() -> None:
    reviewer = _read_agent("⊕workspace-architecture-reviewer.agent.md")

    assert "explicit user direction" in reviewer.lower()
    assert "fr_cli.py update-state" in reviewer
    assert "state-transition" in reviewer


def test_architecture_reviewer_records_diagram_handoff_as_ledger_delegation() -> None:
    reviewer = _read_agent("⊕workspace-architecture-reviewer.agent.md")

    assert "event-type `delegation`" in reviewer.lower()
    assert "⊕workspace-architecture-beautifier" in reviewer
    assert "fr_cli.py record-event" in reviewer


def test_light_tier_contracts_require_uniform_proof_artifacts() -> None:
    light_contracts = "\n".join(
        (
            _read_agent("⊕workspace-reviewer-light.agent.md"),
            _read_agent("⊕workspace-tdd-light.agent.md"),
            _read_agent("⊕workspace-qa-light.agent.md"),
        )
    ).lower()

    assert "every acceptance criterion" in light_contracts
    assert "proof artifact" in light_contracts
    assert "light tier" in light_contracts


def test_shared_flow_allows_absent_subject_profile_in_branch_worktrees() -> None:
    flow = (INSTRUCTIONS / "feature-request-flow.instructions.md").read_text(encoding="utf-8")
    normalized_flow = " ".join(flow.lower().split())

    assert "subject_profile.json" in normalized_flow
    assert "may be absent in branch worktrees" in normalized_flow
    assert "db-backed `subject.height_cm`" in normalized_flow


def test_discovery_contract_matches_discover_todos_capital_mapping() -> None:
    discovery = _read_agent("⊕workspace-discovery.agent.md")
    normalized_discovery = " ".join(discovery.lower().split())

    assert "capital" in normalized_discovery
    assert "only valid with `--mode tech-debt`" in normalized_discovery
    assert "not valid for default epic/story discovery" in normalized_discovery