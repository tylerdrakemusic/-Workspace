from decimal import Decimal
import sqlite3
import asyncio
from argparse import Namespace

from copilot_cost import calculate_copilot_cost
from migrate_fr_cost import COST_COLUMNS, migrate
from fr_cost_lifecycle import capture_baseline, finalize_cost, reconcile_cost
import fr_cli


def test_calculate_copilot_cost_includes_cached_input_and_write_tokens() -> None:
    result = calculate_copilot_cost(
        model="claude-sonnet-4-6",
        usage={
            "input_tokens": 1_000_000,
            "output_tokens": 500_000,
            "cache_read_input_tokens": 250_000,
            "cache_creation_input_tokens": 100_000,
        },
    )

    assert result.status == "estimated"
    assert result.ai_credits == result.usd / Decimal("0.01")
    assert result.usd == Decimal("10.95")


def test_calculate_copilot_cost_marks_unknown_model_unavailable() -> None:
    result = calculate_copilot_cost(model="unpublished-model", usage={"input_tokens": 1})

    assert result.status == "unavailable"
    assert result.usd is None
    assert result.ai_credits is None


def test_calculate_copilot_cost_exposes_rate_provenance() -> None:
    result = calculate_copilot_cost(
        model="claude-sonnet-4-6", usage={"input_tokens": 1_000_000}
    )

    assert result.pricing_source_url
    assert result.pricing_version
    assert result.pricing_effective_date
    assert result.rate_snapshot["currency"] == "USD"


def test_cost_migration_adds_nullable_lifecycle_columns_idempotently() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE feature_requests (id TEXT PRIMARY KEY, title TEXT NOT NULL)")
    conn.execute("INSERT INTO feature_requests VALUES ('FR-old', 'legacy')")

    migrate(conn)
    migrate(conn)

    columns = {row[1] for row in conn.execute("PRAGMA table_info(feature_requests)")}
    assert set(COST_COLUMNS) <= columns
    row = conn.execute("SELECT title, cost_status FROM feature_requests WHERE id='FR-old'").fetchone()
    assert row == ("legacy", None)


def _cost_conn() -> sqlite3.Connection:
    class KeepOpenConnection(sqlite3.Connection):
        def close(self) -> None:
            self.commit()

    conn = sqlite3.connect(":memory:", factory=KeepOpenConnection)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE feature_requests (id TEXT PRIMARY KEY, title TEXT NOT NULL, type TEXT, risk TEXT, "
        "projects TEXT, state TEXT, branch TEXT, prs TEXT, owner TEXT, opened_at TEXT, updated_at TEXT, "
        "merged_at TEXT, signed_off_at TEXT, closed_at TEXT, cycle_timer_run_id TEXT)"
    )
    conn.execute("INSERT INTO feature_requests (id, title, type) VALUES ('FR-1', 'test', 'feature')")
    conn.execute(
        "CREATE TABLE fr_events (fr_id TEXT, ts TEXT, agent TEXT, event_type TEXT, "
        "summary TEXT, details TEXT, next_action TEXT)"
    )
    migrate(conn)
    return conn


def test_lifecycle_finalization_persists_current_session_delta() -> None:
    conn = _cost_conn()
    capture_baseline(conn, "FR-1", "claude-sonnet-4-6", {"input_tokens": 100})

    result = finalize_cost(
        conn,
        "FR-1",
        "claude-sonnet-4-6",
        {"input_tokens": 1_000_100, "output_tokens": 500_000},
        source="telemetry",
    )

    row = conn.execute(
        "SELECT ai_credits_estimated, usd_cost_estimated, cost_status, cost_source, "
        "cost_finalized_at FROM feature_requests WHERE id='FR-1'"
    ).fetchone()
    assert result.status == "estimated"
    assert row[2:] == ("estimated", "telemetry", row[4])
    assert row[0] == float(result.ai_credits)
    assert row[1] == float(result.usd)

    provenance = conn.execute(
        "SELECT cost_pricing_source_url, cost_pricing_version, "
        "cost_pricing_effective_date, cost_rate_snapshot_json "
        "FROM feature_requests WHERE id='FR-1'"
    ).fetchone()
    assert provenance[0] == result.pricing_source_url
    assert provenance[1] == result.pricing_version
    assert provenance[2] == result.pricing_effective_date
    assert '"currency": "USD"' in provenance[3]


def test_reconciliation_uses_github_first_and_requires_operator_fallback() -> None:
    async def github_usage() -> dict[str, int]:
        return {"model": "claude-sonnet-4-6", "input_tokens": 10, "output_tokens": 20}

    github_result = asyncio.run(
        reconcile_cost(github_usage, operator_confirmation=None)
    )
    assert github_result == (
        "github",
        {"model": "claude-sonnet-4-6", "input_tokens": 10, "output_tokens": 20},
    )

    async def unavailable() -> None:
        raise RuntimeError("GitHub unavailable")

    assert asyncio.run(reconcile_cost(unavailable, operator_confirmation=False)) == (
        "unavailable",
        None,
    )
    assert asyncio.run(reconcile_cost(unavailable, operator_confirmation=True)) == (
        "operator",
        None,
    )


def test_reconciliation_rejects_empty_and_malformed_github_telemetry() -> None:
    async def empty_usage() -> dict:
        return {}

    async def malformed_usage() -> dict:
        return {"model": "claude-sonnet-4-6", "input_tokens": "not-a-number"}

    assert asyncio.run(reconcile_cost(empty_usage, operator_confirmation=None)) == (
        "unavailable",
        None,
    )
    assert asyncio.run(reconcile_cost(malformed_usage, operator_confirmation=None)) == (
        "unavailable",
        None,
    )
    assert asyncio.run(reconcile_cost(empty_usage, operator_confirmation=True)) == (
        "operator",
        None,
    )


def test_cli_cost_commands_persist_and_report_cost(monkeypatch, capsys) -> None:
    conn = _cost_conn()
    monkeypatch.setattr(fr_cli, "_conn", lambda: conn)

    fr_cli.cmd_cost_baseline(
        Namespace(fr_id="FR-1", model="claude-sonnet-4-6", usage_json='{"input_tokens": 100}')
    )
    fr_cli.cmd_cost_finalize(
        Namespace(
            fr_id="FR-1",
            model="claude-sonnet-4-6",
            usage_json='{"input_tokens": 1100, "output_tokens": 1000}',
            source="telemetry",
        )
    )

    output = capsys.readouterr().out
    assert "estimated" in output
    assert "AI credits" in output


def test_cli_get_displays_persisted_cost_fields(monkeypatch, capsys) -> None:
    conn = _cost_conn()
    conn.execute(
        "UPDATE feature_requests SET ai_credits_estimated=2.5, usd_cost_estimated=.025, "
        "cost_status='estimated', cost_source='github' WHERE id='FR-1'"
    )
    conn.commit()
    monkeypatch.setattr(fr_cli, "_conn", lambda: conn)

    fr_cli.cmd_get(Namespace(fr_id="FR-1"))

    output = capsys.readouterr().out
    assert "AI credits: 2.5" in output
    assert "USD cost:   0.025" in output
    assert "Cost source: github" in output


def test_merge_transition_finalizes_cost_when_usage_is_supplied(monkeypatch, capsys) -> None:
    conn = _cost_conn()
    capture_baseline(conn, "FR-1", "claude-sonnet-4-6", {"input_tokens": 100})
    conn.execute(
        "INSERT INTO fr_events VALUES ('FR-1', '2026-08-08T00:00:00Z', 'reviewer', "
        "'review', 'ARCHITECTURE_REVIEW:PASS', NULL, NULL)"
    )
    conn.commit()
    monkeypatch.setattr(fr_cli, "_conn", lambda: conn)

    fr_cli.cmd_update_state(
        Namespace(
            fr_id="FR-1", new_state="MERGED", branch=None, prs=None, merged_at=None,
            signed_off_at=None, owner=None, cycle_timer=None,
            cost_model="claude-sonnet-4-6",
            cost_usage_json='{"input_tokens": 1100, "output_tokens": 1000}',
            cost_source="github",
        )
    )

    row = conn.execute(
        "SELECT state, cost_status, cost_source FROM feature_requests WHERE id='FR-1'"
    ).fetchone()
    assert tuple(row) == ("MERGED", "estimated", "github")
    assert "AI credits" in capsys.readouterr().out


def test_async_merge_does_not_finalize_from_supplied_usage_without_reconciliation(
    monkeypatch, capsys
) -> None:
    conn = _cost_conn()
    capture_baseline(conn, "FR-1", "claude-sonnet-4-6", {"input_tokens": 100})
    conn.execute(
        "INSERT INTO fr_events VALUES ('FR-1', '2026-08-08T00:00:00Z', 'reviewer', "
        "'review', 'ARCHITECTURE_REVIEW:PASS', NULL, NULL)"
    )
    conn.commit()
    monkeypatch.setattr(fr_cli, "_conn", lambda: conn)

    fr_cli.cmd_update_state(
        Namespace(
            fr_id="FR-1", new_state="MERGED", branch=None, prs=None, merged_at=None,
            signed_off_at=None, owner=None, cycle_timer=None,
            cost_model="claude-sonnet-4-6",
            cost_usage_json='{"input_tokens": 1100, "output_tokens": 1000}',
            cost_source="github", cost_async=True,
            cost_github_usage_json=None, cost_operator_confirmed=False,
        )
    )

    row = conn.execute(
        "SELECT state, cost_status, cost_source FROM feature_requests WHERE id='FR-1'"
    ).fetchone()
    assert tuple(row) == ("MERGED", "pending", None)
    assert "reconciliation" in capsys.readouterr().out.lower()