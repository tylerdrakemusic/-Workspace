from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
PICKER_PROMPT = WORKSPACE_ROOT / ".github" / "prompts" / "sigmacapital-picker-flow.prompt.md"
ORCHESTRATOR = WORKSPACE_ROOT / ".github" / "agents" / "Σcapital-orchestrator.agent.md"


def test_open_order_replacement_workflow_is_proposal_only():
    prompt = PICKER_PROMPT.read_text(encoding="utf-8")
    orchestrator = ORCHESTRATOR.read_text(encoding="utf-8")
    combined = f"{prompt}\n{orchestrator}".lower()

    for field in (
        "account reference",
        "symbol",
        "side",
        "logical execution id",
        "current broker order id",
        "replacement intent",
        "proposed replacement fields",
        "rationale/evidence",
        "validation status",
        "operator-review status",
    ):
        assert field in combined

    assert "agentic open-order replacement proposal" in combined
    assert "no live write" in combined
    assert "only capital trade gate performs human-confirmed execution" in combined
    assert "capital pr #106" in combined
    assert "service execution" in combined
    assert "must not place, cancel, or replace live orders" in combined

    for forbidden in (
        "automatically place",
        "automated cancellation",
        "automated replacement",
        "workspace agent may place live orders",
    ):
        assert forbidden not in combined