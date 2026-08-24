"""Regression tests for documented Playwright server health routes."""

import json
from pathlib import Path


def test_sigmacapital_manifest_uses_trade_gate_health_endpoint():
    manifest_path = Path(__file__).parents[1] / "src" / "config" / "playwright_servers.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["projects"]["ΣCapital"]["health_url"] == "http://127.0.0.1:7475/health"