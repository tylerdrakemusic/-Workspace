"""
Quantum Model Selector — SessionStart / SubagentStart hook.

Reads the agent context from stdin, uses qhoice() from the ⟨ψ⟩Quantum
quantum random library to pick a preferred model for this session, and
injects it as a systemMessage. The model: arrays in each agent's
frontmatter remain the VS Code availability fallback; this script provides
the quantum-randomized runtime preference layer on top.

Output contract (VS Code hooks):
    stdout → JSON with optional 'systemMessage' and 'continue' fields
    exit 0 → success (non-blocking)
    exit 2 → blocking error
"""

import json
import sys
import os

# ---------------------------------------------------------------------------
# Model pools — parallel structures to the frontmatter arrays.
# Ordering within a pool does NOT imply priority; qhoice selects uniformly.
# ---------------------------------------------------------------------------
MODEL_POOLS: dict[str, list[str]] = {
    "orchestrator": [
        "claude-sonnet-4-5",
        "gpt-4o",
        "gemini-2.5-pro",
    ],
    "research": [
        "claude-sonnet-4-5",
        "gpt-4o",
        "gemini-2.5-pro",
    ],
    "risk": [
        "claude-sonnet-4-5",
        "gpt-4o",
        "gemini-2.5-pro",
    ],
    "brainstorm": [
        "claude-sonnet-4-5",
        "gpt-4o",
        "gemini-2.5-pro",
    ],
    "specialist": [
        "gpt-4o",
        "gemini-2.5-pro",
        "claude-sonnet-4-5",
    ],
    "hygiene": [
        "gemini-2.0-flash",
        "gpt-4o-mini",
        "claude-haiku-3-5",
    ],
    "alignment": [
        "gemini-2.0-flash",
        "gpt-4o-mini",
        "claude-haiku-3-5",
    ],
    "doer": [
        "gemini-2.0-flash",
        "gpt-4o-mini",
        "claude-haiku-3-5",
    ],
}

# Agent name → tier mapping (sigil-prefixed names as declared in frontmatter)
AGENT_TIERS: dict[str, str] = {
    "∞life-orchestrator":       "orchestrator",
    "❤music-orchestrator":      "orchestrator",
    "⟨ψ⟩quantum-orchestrator":  "orchestrator",
    "⊕workspace-overseer":      "orchestrator",
    "∞life-research":           "research",
    "⟨ψ⟩quantum-research":      "research",
    "∞life-risk":               "risk",
    "∞life-brainstorm":         "brainstorm",
    "∞life-data-analytics":     "specialist",
    "∞life-budget":             "specialist",
    "❤music-catalog":           "specialist",
    "❤music-production":        "specialist",
    "❤music-performance":       "specialist",
    "⊕workspace-ci":            "specialist",
    "∞life-hygiene":            "hygiene",
    "❤music-hygiene":           "hygiene",
    "⟨ψ⟩quantum-hygiene":       "hygiene",
    "⊕workspace-alignment":     "alignment",
    "⊕workspace-doer":          "doer",
}

DEFAULT_TIER = "orchestrator"


def _load_qrandom():
    """Import qhoice from the ⟨ψ⟩Quantum runtime, adding its src/ to path."""
    quantum_src = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "executedcode", "⟨ψ⟩Quantum", "src"
    )
    quantum_src = os.path.normpath(quantum_src)
    if quantum_src not in sys.path:
        sys.path.insert(0, quantum_src)
    from core.quantum_rt import qhoice  # noqa: PLC0415
    return qhoice


def _fallback_choice(lst: list[str]) -> str:
    """os.urandom-based fallback if quantum runtime is unavailable."""
    import struct
    raw = os.urandom(4)
    idx = struct.unpack(">I", raw)[0] % len(lst)
    return lst[idx]


def main() -> None:
    # --- Read hook input ---
    try:
        raw = sys.stdin.read()
        hook_input: dict = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, OSError):
        hook_input = {}

    # --- Determine agent name from hook context ---
    # VS Code may surface the agent/mode name in different fields depending on
    # the event type; check common candidates defensively.
    agent_name: str = (
        hook_input.get("agentName")
        or hook_input.get("agent")
        or hook_input.get("mode")
        or hook_input.get("subagentName")
        or ""
    ).strip()

    tier = AGENT_TIERS.get(agent_name, DEFAULT_TIER)
    pool = MODEL_POOLS[tier]

    # --- Quantum model selection ---
    try:
        qhoice = _load_qrandom()
        selected: str = qhoice(pool)
    except Exception:
        selected = _fallback_choice(pool)

    # --- Inject systemMessage ---
    message = (
        f"[Quantum Model Selection] For this session your quantum-randomized "
        f"preferred model is: **{selected}**. "
        f"Use it as your primary reasoning model. "
        f"If it is unavailable, fall back to the next available model in your "
        f"frontmatter `model:` array. "
        f"Agent tier: {tier}. Pool: {pool}."
    )

    output = {
        "continue": True,
        "systemMessage": message,
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
