"""Auditable, metadata-only Copilot model inventory, selection, and dispatch.

This module deliberately has no knowledge of prompts, task payloads, agent YAML,
or an undocumented Copilot activation endpoint.  Integrations must implement
the small adapter protocols defined here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol, Sequence

try:
    from .copilot_cost import calculate_copilot_cost
except ImportError:
    from copilot_cost import calculate_copilot_cost


SCHEMA_VERSION = 1
ROLES = frozenset({"tdd", "qa", "review"})
TIERS = frozenset({"light", "standard", "heavy"})
FORBIDDEN_KEYS = frozenset({"prompt", "prompts", "task", "task_payload", "source_code", "output"})


class ContractValidationError(ValueError):
    """Raised when a versioned metadata contract is invalid."""


class UnsupportedCopilotError(RuntimeError):
    """Raised when no supported Copilot consumer is available."""


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ContractValidationError("timestamp is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractValidationError("timestamp is invalid") from exc
    return parsed.astimezone(timezone.utc)


def _metadata_only(value: Any, path: str = "record") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                raise ContractValidationError(f"metadata-only contract rejects {path}.{key}")
            _metadata_only(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _metadata_only(child, f"{path}[{index}]")


def _require_version(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ContractValidationError(f"schema_version must be {SCHEMA_VERSION}")
    _metadata_only(payload)
    return payload


def _tuple_strings(values: Any, allowed: frozenset[str], field_name: str) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)) or not values or not all(isinstance(v, str) for v in values):
        raise ContractValidationError(f"{field_name} must be a non-empty string list")
    result = tuple(sorted(set(values)))
    if not set(result) <= allowed:
        raise ContractValidationError(f"{field_name} contains an unsupported value")
    return result


@dataclass(frozen=True)
class ModelRecord:
    model_id: str
    provider: str
    roles: tuple[str, ...]
    tiers: tuple[str, ...]
    available: bool
    quality_floor: float = 0.0
    confidence: float = 0.0
    provider_health: float = 1.0
    pricing_version: str | None = None
    source: str = "supported-copilot-enumeration"

    def __post_init__(self) -> None:
        if not self.model_id.strip() or not self.provider.strip():
            raise ContractValidationError("model identity is required")
        _tuple_strings(self.roles, ROLES, "roles")
        _tuple_strings(self.tiers, TIERS, "tiers")
        for name, value in (("quality_floor", self.quality_floor), ("confidence", self.confidence), ("provider_health", self.provider_health)):
            if not 0 <= value <= 1:
                raise ContractValidationError(f"{name} must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Any) -> "ModelRecord":
        if not isinstance(payload, dict):
            raise ContractValidationError("model record must be an object")
        allowed = {"model_id", "provider", "roles", "tiers", "available", "quality_floor", "confidence", "provider_health", "pricing_version", "source"}
        if set(payload) - allowed:
            raise ContractValidationError("model record contains unknown metadata")
        try:
            return cls(**payload)
        except TypeError as exc:
            raise ContractValidationError("model record is incomplete") from exc


@dataclass(frozen=True)
class InventorySnapshot:
    captured_at: datetime
    source: str
    models: tuple[ModelRecord, ...]
    freshness_seconds: int = 3600
    status: str = "available"

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": SCHEMA_VERSION, "captured_at": _iso(self.captured_at), "source": self.source, "freshness_seconds": self.freshness_seconds, "status": self.status, "models": [model.to_dict() for model in self.models]}

    @classmethod
    def from_dict(cls, payload: Any) -> "InventorySnapshot":
        data = _require_version(payload)
        if not isinstance(data.get("models"), list):
            raise ContractValidationError("models must be a list")
        return cls(captured_at=_parse_time(data.get("captured_at")), source=str(data.get("source", "")), freshness_seconds=int(data.get("freshness_seconds", 3600)), status=str(data.get("status", "available")), models=tuple(ModelRecord.from_dict(model) for model in data["models"]))

    def is_fresh(self, now: datetime | None = None) -> bool:
        current = now or datetime.now(timezone.utc)
        return current.astimezone(timezone.utc) - self.captured_at <= timedelta(seconds=self.freshness_seconds)


@dataclass(frozen=True)
class BenchmarkEvidence:
    source_url: str
    benchmark_name: str
    benchmark_version: str
    methodology: str
    retrieved_at: datetime
    model_id: str
    role: str
    raw_score: float
    comparable: bool
    provenance: str
    normalized_score: float | None = None
    conflict_status: str = "none"

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["retrieved_at"] = _iso(self.retrieved_at)
        result["schema_version"] = SCHEMA_VERSION
        return result

    @classmethod
    def from_dict(cls, payload: Any) -> "BenchmarkEvidence":
        data = _require_version(payload)
        if not data.get("source_url") or not data.get("provenance") or not data.get("methodology"):
            raise ContractValidationError("benchmark provenance is required")
        if data.get("normalized_score") is not None and not data.get("comparable"):
            raise ContractValidationError("uncomparable evidence cannot be normalized")
        try:
            return cls(retrieved_at=_parse_time(data["retrieved_at"]), **{key: data[key] for key in ("source_url", "benchmark_name", "benchmark_version", "methodology", "model_id", "role", "raw_score", "comparable", "provenance")}, normalized_score=data.get("normalized_score"), conflict_status=data.get("conflict_status", "none"))
        except (KeyError, TypeError, ValueError) as exc:
            raise ContractValidationError("benchmark evidence is incomplete") from exc


class InventoryProvider(Protocol):
    def enumerate_models(self) -> InventorySnapshot: ...


class PreflightProvider(Protocol):
    def preflight(self, model_id: str, role: str, tier: str) -> bool: ...


class BenchmarkAdapter(Protocol):
    name: str

    def ingest(self, record: dict[str, Any]) -> BenchmarkEvidence: ...


class DelegationConsumer(Protocol):
    def delegate(self, manifest: "DelegationManifest") -> dict[str, Any]: ...


class UnsupportedDelegationConsumer:
    def delegate(self, manifest: "DelegationManifest") -> dict[str, Any]:
        raise UnsupportedCopilotError("supported Copilot delegation consumer is unavailable")


@dataclass
class CachedInventory:
    path: Path
    provider: InventoryProvider | None = None

    def refresh(self) -> InventorySnapshot:
        if self.provider is None:
            raise UnsupportedCopilotError("supported Copilot enumeration is unavailable")
        snapshot = self.provider.enumerate_models()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(snapshot.to_dict(), sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return snapshot

    def load(self) -> InventorySnapshot | None:
        try:
            return InventorySnapshot.from_dict(json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, ContractValidationError):
            return None

    def current(self, now: datetime | None = None) -> InventorySnapshot:
        cached = self.load()
        if cached and cached.is_fresh(now):
            return cached
        try:
            return self.refresh()
        except UnsupportedCopilotError:
            if cached:
                return InventorySnapshot(cached.captured_at, cached.source, cached.models, cached.freshness_seconds, "stale-fallback")
            raise


def live_preflight(provider: PreflightProvider | None, model_id: str, role: str, tier: str) -> bool:
    if provider is None:
        return False
    try:
        return bool(provider.preflight(model_id, role, tier))
    except Exception:
        return False


def ingest_benchmark(adapter: BenchmarkAdapter, record: dict[str, Any]) -> BenchmarkEvidence:
    try:
        evidence = adapter.ingest(record)
    except Exception as exc:
        raise ContractValidationError(f"benchmark evidence rejected: {exc}") from exc
    if not evidence.source_url or not evidence.provenance or not evidence.comparable:
        raise ContractValidationError("unverifiable or incomparable benchmark evidence rejected")
    return evidence


@dataclass(frozen=True)
class SelectionPolicy:
    quality_floor: float = 0.7
    confidence_floor: float = 0.6
    provider_health_floor: float = 0.7
    hysteresis_ratio: float = 0.05
    cooldown: timedelta = timedelta(minutes=30)
    retry_limit: int = 2


@dataclass(frozen=True)
class SelectionCandidate:
    model: ModelRecord
    role: str
    tier: str
    cost_per_accepted_outcome: Decimal
    latency_penalty: Decimal = Decimal("0")
    retry_penalty: Decimal = Decimal("0")
    reliability_penalty: Decimal = Decimal("0")
    load_penalty: Decimal = Decimal("0")
    benchmark_coverage: bool = True
    cooldown_until: datetime | None = None

    @property
    def score(self) -> Decimal:
        return self.cost_per_accepted_outcome + self.latency_penalty + self.retry_penalty + self.reliability_penalty + self.load_penalty


@dataclass(frozen=True)
class SelectionDecision:
    role: str
    tier: str
    model_id: str | None
    provider: str | None
    status: str
    reason: str
    considered: tuple[str, ...] = ()


def select_model(candidates: Iterable[SelectionCandidate], role: str, tier: str, *, now: datetime | None = None, previous: SelectionDecision | None = None, preferred_providers: set[str] | None = None, policy: SelectionPolicy = SelectionPolicy()) -> SelectionDecision:
    if role not in ROLES or tier not in TIERS:
        return SelectionDecision(role, tier, None, None, "rejected", "unsupported role or tier")
    current = now or datetime.now(timezone.utc)
    eligible = [candidate for candidate in candidates if candidate.role == role and candidate.tier == tier and candidate.model.available and candidate.benchmark_coverage and candidate.model.quality_floor >= policy.quality_floor and candidate.model.confidence >= policy.confidence_floor and candidate.model.provider_health >= policy.provider_health_floor and (candidate.cooldown_until is None or candidate.cooldown_until <= current)]
    if not eligible:
        return SelectionDecision(role, tier, None, None, "unavailable", "availability, quality, evidence, confidence, or provider-health gate failed")
    diverse = [candidate for candidate in eligible if not preferred_providers or candidate.model.provider not in preferred_providers]
    ranked = sorted(diverse or eligible, key=lambda candidate: (candidate.score, candidate.model.provider, candidate.model.model_id))
    winner = ranked[0]
    if previous and previous.model_id and previous.model_id != winner.model.model_id:
        old = next((candidate for candidate in eligible if candidate.model.model_id == previous.model_id), None)
        if old and winner.score >= old.score * (Decimal("1") - Decimal(str(policy.hysteresis_ratio))):
            winner = old
    return SelectionDecision(role, tier, winner.model.model_id, winner.model.provider, "selected", "quality-gated cost per accepted outcome with operational penalties", tuple(candidate.model.model_id for candidate in ranked))


@dataclass(frozen=True)
class ScopedOverride:
    fr_id: str
    role: str | None
    model_id: str
    reason: str
    expires_at: datetime

    def applies(self, fr_id: str, role: str) -> bool:
        return self.fr_id == fr_id and (self.role is None or self.role == role) and self.expires_at > datetime.now(timezone.utc)


@dataclass(frozen=True)
class FallbackRecord:
    selected_model: str | None
    attempted_models: tuple[str, ...]
    fallback_model: str | None
    reason: str


@dataclass(frozen=True)
class DelegationManifest:
    fr_id: str
    role: str
    tier: str
    model_id: str
    provider: str
    inventory_status: str
    selection_reason: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["schema_version"] = SCHEMA_VERSION
        result["created_at"] = _iso(self.created_at)
        return result


def dispatch(manifest: DelegationManifest, consumer: DelegationConsumer | None, *, failover: Sequence[DelegationManifest] = (), last_known_good: DelegationManifest | None = None, override: ScopedOverride | None = None, preflight: Callable[[DelegationManifest], bool] | None = None, retry_limit: int = 2) -> tuple[dict[str, Any] | None, FallbackRecord]:
    if manifest.inventory_status not in {"available", "stale-fallback"}:
        return None, FallbackRecord(manifest.model_id, (), None, "inventory is unavailable")
    if preflight is None:
        return None, FallbackRecord(manifest.model_id, (), None, "live preflight is required before activation")
    candidates = (manifest,) + tuple(failover)
    if override and override.applies(manifest.fr_id, manifest.role):
        if not override.reason.strip():
            return None, FallbackRecord(manifest.model_id, (), None, "scoped override requires a reason")
        candidates = tuple(candidate for candidate in candidates if candidate.model_id == override.model_id) or candidates
    attempted: list[str] = []
    for candidate in candidates:
        if preflight is not None and not preflight(candidate):
            continue
        attempted.append(candidate.model_id)
        if consumer is None:
            break
        for _ in range(max(0, retry_limit) + 1):
            try:
                return consumer.delegate(candidate), FallbackRecord(manifest.model_id, tuple(attempted), None, "selected model delegated")
            except Exception:
                continue
    if last_known_good and last_known_good.fr_id == manifest.fr_id and last_known_good.role == manifest.role and (preflight is None or preflight(last_known_good)) and consumer is not None:
        try:
            return consumer.delegate(last_known_good), FallbackRecord(manifest.model_id, tuple(attempted), last_known_good.model_id, "last-known-good fallback")
        except Exception:
            pass
    reason = "supported Copilot delegation consumer is unavailable" if consumer is None else "all bounded delegation attempts failed"
    return None, FallbackRecord(manifest.model_id, tuple(attempted), None, reason)


@dataclass(frozen=True)
class TelemetryRecord:
    fr_id: str
    role: str
    tier: str
    model_id: str
    provider: str
    latency_ms: int
    retries: int
    failed: bool
    accepted: bool
    usd_cost: Decimal | None = None
    pricing_source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["usd_cost"] = str(self.usd_cost) if self.usd_cost is not None else None
        result["schema_version"] = SCHEMA_VERSION
        return result


def observed_cost_per_accepted(records: Iterable[TelemetryRecord], model_id: str | None = None) -> Decimal | None:
    selected = [record for record in records if model_id is None or record.model_id == model_id]
    accepted = sum(record.accepted for record in selected)
    costs = [record.usd_cost for record in selected if record.usd_cost is not None]
    if not accepted or not costs:
        return None
    return sum(costs, Decimal("0")) / accepted


def telemetry_from_usage(*, fr_id: str, role: str, tier: str, model_id: str, provider: str, usage: dict[str, Any], latency_ms: int, retries: int, failed: bool, accepted: bool) -> TelemetryRecord:
    result = calculate_copilot_cost(model_id, usage)
    return TelemetryRecord(fr_id, role, tier, result.model, provider, max(0, latency_ms), max(0, retries), failed, accepted, result.usd, result.pricing_source_url)


def persist_telemetry(path: Path, record: TelemetryRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")


def shadow_replay(candidates: Iterable[SelectionCandidate], scenarios: Iterable[dict[str, Any]]) -> list[SelectionDecision]:
    previous: dict[tuple[str, str], SelectionDecision] = {}
    decisions: list[SelectionDecision] = []
    for scenario in scenarios:
        role, tier = scenario["role"], scenario["tier"]
        decision = select_model(candidates, role, tier, previous=previous.get((role, tier)), preferred_providers=set(scenario.get("preferred_providers", ())))
        previous[(role, tier)] = decision
        decisions.append(decision)
    return decisions


def manifest_fingerprint(manifest: DelegationManifest) -> str:
    return hashlib.sha256(json.dumps(manifest.to_dict(), sort_keys=True).encode("utf-8")).hexdigest()