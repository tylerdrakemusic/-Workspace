import importlib.util
import json
import re
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "tools" / "fr_dashboard.py"
spec = importlib.util.spec_from_file_location("fr_dashboard", MODULE_PATH)
dashboard = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(dashboard)


def test_perf_run_adapter_parses_completed_fr_cycle_measurement():
    row = {
        "run_id": "run-1",
        "name": "fr-cycle-FR-20260904-example",
        "agent": "workspace-ci",
        "started_at": 100.0,
        "ended_at": 160.0,
        "status": "ok",
        "detail": "completed",
    }

    measurement = dashboard.adapt_perf_run(row)

    assert measurement == {
        "fr_id": "FR-20260904-example",
        "run_id": "run-1",
        "project": "⊕Workspace",
        "started_at": 100.0,
        "ended_at": 160.0,
        "duration_seconds": 60.0,
        "kind": "measurement",
        "status": "ok",
        "data_quality": "valid",
    }


def test_duplicate_timers_reconcile_to_earliest_start_and_latest_valid_end():
    rows = [
        {"run_id": "old", "name": "fr-cycle-FR-1-demo", "started_at": 100, "ended_at": 150, "status": "ok"},
        {"run_id": "duplicate", "name": "fr-cycle-FR-1-demo", "started_at": 110, "ended_at": 180, "status": "legacy"},
        {"run_id": "invalid", "name": "fr-cycle-FR-1-demo", "started_at": 90, "ended_at": 80, "status": "error"},
    ]

    result = dashboard.canonicalize_perf_runs([dashboard.adapt_perf_run(row) for row in rows])

    assert result["rows"][0]["started_at"] == 90
    assert result["rows"][0]["ended_at"] == 180
    assert result["rows"][0]["duration_seconds"] == 90
    assert result["rows"][0]["duplicate_count"] == 2
    assert result["rows"][0]["provenance_run_ids"] == ["invalid", "old", "duplicate"]
    assert result["counts"]["duplicates"] == 2
    assert result["counts"]["legacy"] == 1
    assert result["counts"]["invalid"] == 1


def test_active_and_invalid_cycles_are_disclosed_without_becoming_measurements():
    rows = [
        dashboard.adapt_perf_run({"run_id": "active", "name": "fr-cycle-FR-2-open", "started_at": 100}),
        dashboard.adapt_perf_run({"run_id": "bad", "name": "fr-cycle-FR-3-bad", "started_at": 100, "ended_at": 100}),
    ]

    result = dashboard.canonicalize_perf_runs(rows)

    assert [row["kind"] for row in result["rows"]] == ["active", "invalid"]
    assert result["counts"] == {"active": 1, "invalid": 1, "legacy": 0, "duplicates": 0, "measurements": 0}


def test_cycle_summaries_calculate_median_p75_and_project_filter():
    rows = [
        {"fr_id": "FR-1", "project": "Alpha", "started_at": 1, "ended_at": 2, "duration_seconds": 1, "kind": "measurement"},
        {"fr_id": "FR-2", "project": "Beta", "started_at": 2, "ended_at": 12, "duration_seconds": 10, "kind": "measurement"},
        {"fr_id": "FR-3", "project": "Alpha", "started_at": 3, "ended_at": 23, "duration_seconds": 20, "kind": "measurement"},
        {"fr_id": "FR-4", "project": "Alpha", "started_at": 4, "ended_at": 34, "duration_seconds": 30, "kind": "measurement"},
    ]

    filtered = dashboard.filter_cycle_rows(rows, project="Alpha")
    summary = dashboard.cycle_summary(filtered)

    assert [row["fr_id"] for row in filtered] == ["FR-1", "FR-3", "FR-4"]
    assert summary == {"sample": 3, "median_seconds": 20, "p75_seconds": 30}


def test_render_html_embeds_cycle_chart_controls_summaries_and_active_markers():
    html = dashboard.render_html(
        [],
        perf_runs={
            "rows": [
                {"fr_id": "FR-1", "project": "Alpha", "started_at": 1, "ended_at": 61, "duration_seconds": 60, "kind": "measurement"},
                {"fr_id": "FR-2", "project": "Beta", "started_at": 2, "ended_at": None, "duration_seconds": None, "kind": "active"},
            ],
            "counts": {"active": 1, "invalid": 0, "legacy": 0, "duplicates": 0, "measurements": 1},
        },
    )

    assert "Cycle time" in html
    assert "median" in html.lower()
    assert "p75" in html.lower()
    assert "project-filter" in html
    assert "active" in html.lower()
    assert "FR-2" in html
    assert "max-width: 900px" in html
    payload = re.search(r'<script id="cycle-data" type="application/json">(.*?)</script>', html, re.S).group(1)
    assert json.loads(payload)[1]["fr_id"] == "FR-2"


def test_render_html_escapes_chart_labels_and_renders_invalid_rows_explicitly():
    html = dashboard.render_html(
        [],
        perf_runs={
            "rows": [
                {
                    "fr_id": "<FR-unsafe>",
                    "project": 'Alpha" onclick="bad',
                    "duration_seconds": None,
                    "kind": "invalid",
                },
            ],
            "counts": {"active": 0, "invalid": 1, "legacy": 0, "duplicates": 0, "measurements": 0},
        },
    )

    assert "invalid duration" in html.lower()
    assert "escapeHtml(row.fr_id)" in html
    assert "escapeHtml(row.project)" in html
    assert "+ row.fr_id +" not in html
    assert "+ row.project +" not in html


def test_render_html_uses_interpolated_median_for_even_samples():
    html = dashboard.render_html(
        [],
        perf_runs={
            "rows": [
                {"fr_id": "FR-1", "project": "Alpha", "duration_seconds": 60, "kind": "measurement"},
                {"fr_id": "FR-2", "project": "Alpha", "duration_seconds": 180, "kind": "measurement"},
            ],
            "counts": {"active": 0, "invalid": 0, "legacy": 0, "duplicates": 0, "measurements": 2},
        },
    )

    assert "(measured.length - 1) / 2" not in html
    assert "measured.length / 2" in html