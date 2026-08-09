"""Cost calculation for model telemetry recorded during FR work."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


AI_CREDIT_USD = Decimal("0.01")


@dataclass(frozen=True)
class CopilotCost:
    """Calculated cost and its confidence status."""

    status: str
    usd: Decimal | None
    ai_credits: Decimal | None
    model: str
    pricing_source_url: str | None = None
    pricing_version: str | None = None
    pricing_effective_date: str | None = None
    rate_snapshot: dict[str, str] | None = None


_RATES_PER_MILLION: dict[str, dict[str, Decimal]] = {
    "claude-sonnet-4-6": {
        "input": Decimal("3"),
        "output": Decimal("15"),
        "cache_read": Decimal("0.30"),
        "cache_write": Decimal("3.75"),
    },
}

_RATE_PROVENANCE = {
    "claude-sonnet-4-6": {
        "source_url": "https://www.anthropic.com/pricing",
        "version": "2026-04-01",
        "effective_date": "2026-04-01",
        "currency": "USD",
    },
}


def _token_count(usage: dict[str, Any], *names: str) -> Decimal:
    for name in names:
        if usage.get(name) is not None:
            return Decimal(str(usage[name]))
    return Decimal("0")


def calculate_copilot_cost(model: str, usage: dict[str, Any]) -> CopilotCost:
    """Calculate estimated USD and AI credits from token usage telemetry."""
    rates = _RATES_PER_MILLION.get(model)
    if rates is None:
        return CopilotCost("unavailable", None, None, model)
    provenance = _RATE_PROVENANCE[model]
    rate_snapshot = {
        "input": str(rates["input"]),
        "output": str(rates["output"]),
        "cache_read": str(rates["cache_read"]),
        "cache_write": str(rates["cache_write"]),
        "currency": provenance["currency"],
    }

    total = (
        _token_count(usage, "input_tokens", "prompt_tokens") * rates["input"]
        + _token_count(usage, "output_tokens", "completion_tokens") * rates["output"]
        + _token_count(usage, "cache_read_input_tokens", "cached_input_tokens") * rates["cache_read"]
        + _token_count(usage, "cache_creation_input_tokens", "cache_write_input_tokens") * rates["cache_write"]
    ) / Decimal("1000000")
    total = total.quantize(Decimal("0.00001"))
    return CopilotCost(
        "estimated", total, total / AI_CREDIT_USD, model,
        pricing_source_url=provenance["source_url"],
        pricing_version=provenance["version"],
        pricing_effective_date=provenance["effective_date"],
        rate_snapshot=rate_snapshot,
    )