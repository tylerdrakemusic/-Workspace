from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


def make_event(module, sequence: int = 0):
    return module.StructuredEvent.create(
        event_name="worker.heartbeat",
        component="shared_worker",
        correlation_id="corr-test",
        fields={"sequence": sequence, "account_hash": "private"},
    )


def test_versioned_event_schema_and_causal_boundary():
    from utils.bounded_logging import StructuredEvent, observed_boundary

    event = StructuredEvent.create(
        event_name="operation.started",
        component="shared_worker",
        correlation_id="corr-123",
        causation_id="cause-456",
        fields={"attempt": 1},
    )

    assert event.to_dict()["schema_version"] == 2
    assert event.to_dict()["retry"] == {"count": 0, "limit": 0}

    emitted = []

    def emit(event_name, **kwargs):
        emitted.append((event_name, kwargs))
        return f"event-{len(emitted)}"

    with observed_boundary(emit, "worker.dispatch", stage="dispatch"):
        pass

    assert [name for name, _ in emitted] == [
        "worker.dispatch.started",
        "worker.dispatch.completed",
    ]
    assert emitted[1][1]["causation_id"] == "event-1"


def test_allowlisting_redacts_sensitive_and_unknown_fields():
    from utils.bounded_logging import StructuredEvent

    event = StructuredEvent.create(
        event_name="worker.failed",
        component="shared_worker",
        correlation_id="corr-123",
        fields={
            "attempt": 1,
            "token": "secret",
            "account_hash": "private",
            "unknown": "not approved",
        },
    )

    assert event.to_dict()["fields"] == {
        "attempt": 1,
        "token": "[REDACTED]",
        "account_hash": "[REDACTED]",
        "unknown": "[REDACTED]",
    }


def test_sink_rejects_malformed_events_and_reports_unhealthy(tmp_path: Path):
    from utils.bounded_logging import BoundedLocalSink

    sink = BoundedLocalSink(tmp_path / "events.jsonl")

    assert sink.write({"schema_version": 2}) is False
    assert sink.stats().malformed_events == 1
    assert sink.health()["healthy"] is False


def test_sink_rotates_with_quota_and_sheds_oldest_files_first(tmp_path: Path):
    from utils.bounded_logging import BoundedLocalSink

    sink = BoundedLocalSink(tmp_path / "events.jsonl", max_bytes=512, max_files=2)
    for sequence in range(20):
        assert sink.write(make_event(__import__("utils.bounded_logging", fromlist=["x"]), sequence))

    files = list(tmp_path.glob("events.jsonl*"))
    records = [
        json.loads(line)
        for path in files
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert len(files) <= 2
    assert sum(path.stat().st_size for path in files) <= 1024
    assert max(record["fields"]["sequence"] for record in records) == 19
    assert sink.stats().shed_oldest_events > 0


def test_sink_drops_events_under_disk_pressure(tmp_path: Path):
    from utils.bounded_logging import BoundedLocalSink

    sink = BoundedLocalSink(
        tmp_path / "events.jsonl",
        min_free_bytes=100,
        disk_usage=lambda _path: SimpleNamespace(free=99),
    )

    assert sink.write(make_event(__import__("utils.bounded_logging", fromlist=["x"]))) is False
    assert sink.stats().dropped_events == 1


def test_sink_restart_keeps_bounded_state_on_disk(tmp_path: Path):
    from utils.bounded_logging import BoundedLocalSink

    path = tmp_path / "events.jsonl"
    first = BoundedLocalSink(path, max_bytes=512, max_files=2)
    assert first.write(make_event(__import__("utils.bounded_logging", fromlist=["x"]), 1))
    second = BoundedLocalSink(path, max_bytes=512, max_files=2)
    assert second.write(make_event(__import__("utils.bounded_logging", fromlist=["x"]), 2))
    assert len(list(tmp_path.glob("events.jsonl*"))) <= 2
    assert second.stats().written_events == 1


def test_package_and_direct_file_imports_are_compatible():
    from utils import bounded_logging

    module_path = Path(bounded_logging.__file__)
    spec = importlib.util.spec_from_file_location("workspace_direct_bounded_logging", module_path)
    direct = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = direct
    spec.loader.exec_module(direct)

    assert direct.StructuredEvent.create(
        event_name="worker.started",
        component="shared_worker",
        correlation_id="corr-direct",
        fields={},
    ).schema_version == 2


def test_invalid_event_identity_and_retry_are_rejected():
    from utils.bounded_logging import StructuredEvent

    with pytest.raises(ValueError, match="correlation_id"):
        StructuredEvent.create(
            event_name="worker.started",
            component="shared_worker",
            correlation_id="",
            fields={},
        )
    with pytest.raises(ValueError, match="retry_count"):
        StructuredEvent.create(
            event_name="worker.started",
            component="shared_worker",
            correlation_id="corr",
            fields={},
            retry_count=2,
            retry_limit=1,
        )