from pathlib import Path


def test_standalone_recalibration_prompt_defines_manual_review_flow():
    prompt_path = (
        Path(__file__).parents[1]
        / ".github"
        / "prompts"
        / "sigmacapital-oco-recalibration.prompt.md"
    )
    prompt = prompt_path.read_text(encoding="utf-8")

    assert "manual-only" in prompt
    assert "previewed" in prompt
    assert "fresh" in prompt
    assert "Stop" in prompt and "Target" in prompt
    assert "never" in prompt.lower() and "autom" in prompt.lower()
    assert "trade_candidates" in prompt