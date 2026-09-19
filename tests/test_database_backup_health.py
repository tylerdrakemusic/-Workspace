from __future__ import annotations

from datetime import datetime, timezone
import json

import pytest

from src.utils import database_backup_observability as observability
from tools import dashboard_portal
from tools import fr_portal_server


NOW = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)


def _evaluate(**overrides: object) -> dict:
    observation = {
        "task": {"registered": True, "enabled": True, "last_run_result": 0},
        "generation": {
            "status": "succeeded",
            "completed_at": "2026-09-18T02:00:00Z",
            "covered_targets": ["workspace", "workspace-fr-ledgers"],
        },
        "approved_targets": ["workspace", "workspace-fr-ledgers"],
        "checked_at": NOW,
    }
    observation.update(overrides)
    return observability.evaluate_backup_health(**observation)


def test_backup_health_is_healthy_when_task_and_recent_generation_cover_scope() -> None:
    result = _evaluate()

    assert result["state"] == "Healthy"
    assert result["last_success_age_seconds"] == 36000
    assert result["failure_categories"] == []


@pytest.mark.parametrize(
    "override,category",
    [
        ({"generation": None}, "missing_evidence"),
        (
            {"generation": {"status": "succeeded", "completed_at": "2026-09-16T11:59:00Z", "covered_targets": ["workspace", "workspace-fr-ledgers"]}},
            "stale_evidence",
        ),
        (
            {"generation": {"status": "succeeded", "completed_at": "2026-09-18T02:00:00Z", "covered_targets": ["workspace"]}},
            "scope_incomplete",
        ),
    ],
)
def test_backup_health_is_attention_for_working_probe_with_incomplete_evidence(
    override: dict[str, object], category: str
) -> None:
    result = _evaluate(**override)

    assert result["state"] == "Attention"
    assert category in result["failure_categories"]


def test_backup_health_is_unavailable_when_probe_cannot_read_inputs() -> None:
    result = fr_portal_server.database_backup_health_payload(
        probe=lambda: (_ for _ in ()).throw(OSError("private path and secret"))
    )

    assert result["state"] == "Unavailable"
    assert result["failure_categories"] == ["probe_failure"]
    assert "private" not in json.dumps(result).lower()
    assert "secret" not in json.dumps(result).lower()


def test_backup_health_filters_denied_targets_before_evaluating_scope() -> None:
    result = _evaluate(
        approved_targets=["workspace"],
        generation={
            "status": "succeeded",
            "completed_at": "2026-09-18T02:00:00Z",
            "covered_targets": ["workspace", "denied-database"],
        },
    )

    assert result["state"] == "Healthy"


def test_backup_health_browser_contract_is_redacted_to_aggregate_fields() -> None:
    result = _evaluate(
        generation={
            "status": "failed",
            "completed_at": "2026-09-18T02:00:00Z",
            "covered_targets": ["workspace"],
            "path": "F:/private/workspace.db",
            "database": "workspace.db",
            "log": "WORKSPACE_DB_KEY leaked",
        },
    )

    assert set(result) == {
        "state",
        "checked_at",
        "last_success_age_seconds",
        "failure_categories",
    }
    serialized = json.dumps(result)
    for forbidden in ("private", "workspace.db", "WORKSPACE_DB_KEY", "F:/"):
        assert forbidden not in serialized


def test_portal_widget_preserves_ai_health_and_fetches_backup_health_on_load() -> None:
    html = dashboard_portal._render_api_health_widget(
        [{"name": "elevenlabs", "label": "ElevenLabs", "status": "up"}],
        include_backup_health=True,
    )

    assert "AI Health" in html
    assert "DB Backup Health" in html
    assert "/api/health/database-backup" in html
    assert "fetch(" in html


def test_portal_widget_keeps_backup_section_when_ai_probe_has_no_rows() -> None:
    html = dashboard_portal._render_api_health_widget([], include_backup_health=True)

    assert "DB Backup Health" in html