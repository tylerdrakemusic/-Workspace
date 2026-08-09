"""Offline Copilot cost calculation and refreshable GitHub pricing snapshots."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import tempfile
from typing import Any, Callable
from urllib.request import urlopen


AI_CREDIT_USD = Decimal("0.01")
PRICING_SOURCE_URL = (
    "https://docs.github.com/en/copilot/reference/copilot-billing/"
    "models-and-pricing#pricing-tables"
)
DEFAULT_SNAPSHOT_PATH = Path(__file__).resolve().parents[1] / "data" / "copilot_pricing_snapshot.json"
_REQUIRED_RATE_KEYS = ("input", "output", "cache_read", "cache_write")


class PricingRefreshError(ValueError):
    """Raised when a pricing response cannot produce a valid snapshot."""


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


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _number(value: str, *, allow_empty: bool = False) -> str:
    value = _clean(value).replace(",", "")
    if not value or value.lower() in {"n/a", "not applicable", "-", "—"}:
        if allow_empty:
            return "0"
        raise PricingRefreshError("pricing table contains a missing rate")
    value = value.replace("$", "")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise PricingRefreshError(f"invalid pricing rate: {value!r}") from exc
    if not number.is_finite() or number < 0:
        raise PricingRefreshError(f"invalid pricing rate: {value!r}")
    return format(number, "f")


class _PricingTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.models: dict[str, dict[str, str]] = {}
        self.provider = "Unknown"
        self._table = False
        self._row: list[str] | None = None
        self._cell = False
        self._header: list[str] | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"h3", "h4"}:
            self._text = []
        elif tag == "table":
            self._table = True
            self._header = None
        elif self._table and tag == "tr":
            self._row = []
        elif self._row is not None and tag in {"th", "td"}:
            self._cell = True
            self._text = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"h3", "h4"} and self._text:
            heading = _clean("".join(self._text))
            if heading.lower() in {"openai", "anthropic", "google", "microsoft", "xai", "moonshot ai", "moonshot"}:
                self.provider = heading
        elif self._row is not None and tag in {"th", "td"} and self._cell:
            self._row.append(_clean("".join(self._text)))
            self._cell = False
        elif self._table and tag == "tr" and self._row is not None:
            if self._header is None:
                self._header = [cell.lower() for cell in self._row]
            else:
                self._consume_row(self._row)
            self._row = None
        elif tag == "table":
            self._table = False

    def handle_data(self, data: str) -> None:
        self._text.append(data)

    def _consume_row(self, row: list[str]) -> None:
        if not self._header or len(row) < len(self._header):
            return
        values = dict(zip(self._header, row))
        model = values.get("model", "")
        if not model:
            return
        try:
            rates = {
                "input": _number(values.get("input", "")),
                "output": _number(values.get("output", "")),
                "cache_read": _number(values.get("cached input", values.get("cache read", "")), allow_empty=True),
                "cache_write": _number(values.get("cache write", ""), allow_empty=True),
            }
        except PricingRefreshError:
            return
        self.models[model] = {**rates, "provider": self.provider}


def parse_pricing_html(html: str, *, effective_date: str | None = None) -> dict[str, Any]:
    """Parse GitHub's pricing tables into a validated snapshot."""
    parser = _PricingTableParser()
    parser.feed(html)
    if not parser.models:
        raise PricingRefreshError("pricing table was not found or contained no valid model rows")
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "schema_version": 1,
        "source_url": PRICING_SOURCE_URL,
        "retrieved_at": retrieved_at,
        "effective_date": effective_date or retrieved_at[:10],
        "currency": "USD",
        "unit": "USD per 1 million tokens",
        "models": dict(sorted(parser.models.items())),
    }


def _validate_snapshot(snapshot: Any) -> dict[str, Any]:
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != 1:
        raise PricingRefreshError("invalid pricing snapshot schema")
    if snapshot.get("source_url") != PRICING_SOURCE_URL or snapshot.get("currency") != "USD":
        raise PricingRefreshError("pricing snapshot provenance is invalid")
    models = snapshot.get("models")
    if not isinstance(models, dict) or not models:
        raise PricingRefreshError("pricing snapshot has no models")
    for model, rates in models.items():
        if not isinstance(model, str) or not isinstance(rates, dict):
            raise PricingRefreshError("pricing snapshot model row is invalid")
        if any(key not in rates for key in _REQUIRED_RATE_KEYS):
            raise PricingRefreshError(f"pricing snapshot row is incomplete: {model}")
        for key in _REQUIRED_RATE_KEYS:
            _number(str(rates[key]))
    return snapshot


def load_pricing_snapshot(path: Path = DEFAULT_SNAPSHOT_PATH) -> dict[str, Any]:
    """Load and validate the persisted pricing snapshot."""
    try:
        with path.open(encoding="utf-8") as handle:
            return _validate_snapshot(json.load(handle))
    except (OSError, json.JSONDecodeError) as exc:
        raise PricingRefreshError(f"unable to load pricing snapshot: {path}") from exc


def refresh_pricing(
    fetcher: Callable[[], str] | None = None,
    path: Path = DEFAULT_SNAPSHOT_PATH,
    *,
    effective_date: str | None = None,
) -> dict[str, Any]:
    """Fetch, validate, and atomically persist the official pricing snapshot."""
    try:
        if fetcher is None:
            with urlopen(PRICING_SOURCE_URL, timeout=30) as response:  # nosec B310
                html = response.read().decode("utf-8")
        else:
            html = fetcher()
        snapshot = _validate_snapshot(parse_pricing_html(html, effective_date=effective_date))
    except (OSError, UnicodeError, PricingRefreshError, ValueError) as exc:
        raise PricingRefreshError(f"pricing table refresh failed: {exc}") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(snapshot, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary_path = Path(handle.name)
    temporary_path.replace(path)
    return snapshot


def _token_count(usage: dict[str, Any], *names: str) -> Decimal:
    for name in names:
        if usage.get(name) is not None:
            return Decimal(str(usage[name]))
    return Decimal("0")


def _model_name(model: str, models: dict[str, Any]) -> str | None:
    key = re.sub(r"[^a-z0-9]", "", model.lower())
    for name in models:
        if re.sub(r"[^a-z0-9]", "", name.lower()) == key:
            return name
    return None


def calculate_copilot_cost(
    model: str, usage: dict[str, Any], *, snapshot_path: Path = DEFAULT_SNAPSHOT_PATH
) -> CopilotCost:
    """Calculate cost from the persisted snapshot without network access."""
    try:
        snapshot = load_pricing_snapshot(snapshot_path)
    except PricingRefreshError:
        return CopilotCost("unavailable", None, None, model)
    canonical_model = _model_name(model, snapshot["models"])
    if canonical_model is None:
        return CopilotCost("unavailable", None, None, model)
    rates = snapshot["models"][canonical_model]
    total = sum(
        (
            _token_count(usage, "input_tokens", "prompt_tokens") * Decimal(rates["input"]),
            _token_count(usage, "output_tokens", "completion_tokens") * Decimal(rates["output"]),
            _token_count(usage, "cache_read_input_tokens", "cached_input_tokens") * Decimal(rates["cache_read"]),
            _token_count(usage, "cache_creation_input_tokens", "cache_write_input_tokens") * Decimal(rates["cache_write"]),
        ),
        Decimal("0"),
    ) / Decimal("1000000")
    total = total.quantize(Decimal("0.00001"))
    rate_snapshot = {key: str(rates[key]) for key in _REQUIRED_RATE_KEYS}
    rate_snapshot["currency"] = snapshot["currency"]
    return CopilotCost(
        "estimated", total, total / AI_CREDIT_USD, canonical_model,
        pricing_source_url=snapshot["source_url"],
        pricing_version=snapshot["retrieved_at"],
        pricing_effective_date=snapshot["effective_date"],
        rate_snapshot=rate_snapshot,
    )