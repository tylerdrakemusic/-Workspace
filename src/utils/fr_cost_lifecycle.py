"""FR-session cost baseline, finalization, and reconciliation helpers."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Awaitable, Callable

from copilot_cost import CopilotCost, calculate_copilot_cost


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def capture_baseline(conn: Any, fr_id: str, model: str, usage: dict[str, Any]) -> None:
    """Persist the current-session model and cumulative usage baseline."""
    conn.execute(
        "UPDATE feature_requests SET cost_baseline_json=?, cost_status=? WHERE id=?",
        (json.dumps({"model": model, "usage": usage}, sort_keys=True), "pending", fr_id),
    )
    conn.commit()


def _delta_usage(baseline: dict[str, Any], final: dict[str, Any]) -> dict[str, Any]:
    keys = set(baseline) | set(final)
    return {key: max(0, int(final.get(key, 0)) - int(baseline.get(key, 0))) for key in keys}


def cost_report(fr_id: str, result: CopilotCost) -> str:
    """Format the chat-facing message emitted after cost persistence."""
    if result.status == "unavailable":
        return f"[FR cost] {fr_id}: cost unavailable for model {result.model}."
    return f"[FR cost] {fr_id}: estimated {result.ai_credits} AI credits (${result.usd})."


def finalize_cost(
    conn: Any,
    fr_id: str,
    model: str,
    usage: dict[str, Any],
    *,
    source: str,
    reporter: Callable[[str], None] | None = None,
) -> CopilotCost:
    """Calculate and persist final cost from the current-session usage delta."""
    row = conn.execute(
        "SELECT cost_baseline_json FROM feature_requests WHERE id=?", (fr_id,)
    ).fetchone()
    baseline = json.loads(row[0]) if row and row[0] else {"model": model, "usage": {}}
    result = calculate_copilot_cost(model, _delta_usage(baseline.get("usage", {}), usage))
    conn.execute(
        "UPDATE feature_requests SET ai_credits_estimated=?, usd_cost_estimated=?, "
        "cost_status=?, cost_source=?, cost_finalized_at=?, "
        "cost_pricing_source_url=?, cost_pricing_version=?, cost_pricing_effective_date=?, "
        "cost_rate_snapshot_json=? WHERE id=?",
        (float(result.ai_credits) if result.ai_credits is not None else None,
         float(result.usd) if result.usd is not None else None,
         result.status, source, _now(), result.pricing_source_url,
         result.pricing_version, result.pricing_effective_date,
         json.dumps(result.rate_snapshot, sort_keys=True) if result.rate_snapshot else None,
         fr_id),
    )
    conn.commit()
    if reporter:
        reporter(cost_report(fr_id, result))
    return result


async def reconcile_cost(
    github_usage: Callable[[], Awaitable[dict[str, Any]]],
    *,
    operator_confirmation: bool | None,
) -> tuple[str, dict[str, Any] | None]:
    """Try GitHub telemetry first, then require explicit operator confirmation."""
    try:
        usage = await github_usage()
        if not _usable_github_usage(usage):
            raise ValueError("GitHub telemetry is empty or malformed")
        return "github", usage
    except Exception:
        if operator_confirmation:
            return "operator", None
        return "unavailable", None


def _usable_github_usage(usage: Any) -> bool:
    if not isinstance(usage, dict) or not isinstance(usage.get("model"), str):
        return False
    if not usage["model"].strip():
        return False
    token_names = (
        "input_tokens", "prompt_tokens", "output_tokens", "completion_tokens",
        "cache_read_input_tokens", "cached_input_tokens",
        "cache_creation_input_tokens", "cache_write_input_tokens",
    )
    found = False
    for name in token_names:
        if name not in usage:
            continue
        try:
            value = Decimal(str(usage[name]))
        except (InvalidOperation, TypeError, ValueError):
            return False
        if not value.is_finite() or value < 0:
            return False
        found = True
    return found