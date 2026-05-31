"""
TDD tests for FR-20260531-portal-force-restart.

Tests verify:
1. restart_servers.ps1 exists in tools/
2. Script content contains required patterns (static analysis)
3. WorkspacePortal/open_portal.ps1 calls restart_servers.ps1 before launch_portal.ps1
"""
import re
import pytest
from pathlib import Path

WORKTREE = Path(__file__).parent.parent
TOOLS_DIR = WORKTREE / "tools"
RESTART_SCRIPT = TOOLS_DIR / "restart_servers.ps1"
PORTAL_SERVERS_JSON = TOOLS_DIR / "portal_servers.json"
DESKTOP_OPEN_PORTAL = Path(r"C:\Users\tyler\AppData\Local\WorkspacePortal\open_portal.ps1")


class TestRestartServersExists:
    def test_restart_servers_ps1_exists(self):
        assert RESTART_SCRIPT.exists(), (
            f"restart_servers.ps1 not found at {RESTART_SCRIPT}"
        )


class TestRestartServersContent:
    def setup_method(self):
        assert RESTART_SCRIPT.exists(), "restart_servers.ps1 must exist for content tests"
        self.content = RESTART_SCRIPT.read_text(encoding="utf-8")

    def test_reads_portal_servers_json_relative_path(self):
        """Script must read portal_servers.json via a relative path from $PSScriptRoot."""
        assert "PSScriptRoot" in self.content, "Must use $PSScriptRoot for relative path"
        assert "portal_servers.json" in self.content, "Must reference portal_servers.json"

    def test_filters_enabled_servers(self):
        """Script must filter servers where enabled -eq $true."""
        assert "enabled" in self.content.lower(), "Must check enabled property"

    def test_uses_get_nettcpconnection(self):
        """Script must use Get-NetTCPConnection to detect listening ports."""
        assert "Get-NetTCPConnection" in self.content, (
            "Must use Get-NetTCPConnection to detect listening ports"
        )

    def test_uses_stop_process(self):
        """Script must call Stop-Process to kill the owning PID."""
        assert "Stop-Process" in self.content, "Must call Stop-Process to kill processes"

    def test_logs_killed_message(self):
        """Script must log 'killed PID' when a process is stopped."""
        assert re.search(r"killed\s+PID", self.content, re.IGNORECASE), (
            "Must log 'killed PID XXXX' when a process is stopped"
        )

    def test_logs_skipping_message(self):
        """Script must log 'not running, skipping' when port is free."""
        assert re.search(r"not running.*skip", self.content, re.IGNORECASE), (
            "Must log 'not running, skipping' when port is not occupied"
        )

    def test_has_header_comment(self):
        """Script must have a header comment explaining its purpose."""
        # First non-empty line should be a comment
        lines = [l.strip() for l in self.content.splitlines() if l.strip()]
        assert lines[0].startswith("#"), "First line must be a comment header"

    def test_no_server_starts(self):
        """Script must only kill processes — it must not start any servers."""
        # Should not invoke launch_portal or any start_ scripts
        assert "launch_portal" not in self.content, (
            "restart_servers.ps1 must not call launch_portal.ps1"
        )
        assert "Start-Process" not in self.content, (
            "restart_servers.ps1 must not start any processes"
        )

    def test_error_action_silent_on_stop(self):
        """Stop-Process must use -ErrorAction SilentlyContinue."""
        assert re.search(r"Stop-Process.*-ErrorAction\s+SilentlyContinue", self.content, re.IGNORECASE) or \
               re.search(r"SilentlyContinue.*Stop-Process", self.content, re.IGNORECASE), (
            "Stop-Process must use -ErrorAction SilentlyContinue"
        )


@pytest.mark.skipif(
    not DESKTOP_OPEN_PORTAL.exists(),
    reason="Desktop open_portal.ps1 is machine-specific — skip when not on Tyler's workstation",
)
class TestOpenPortalUpdated:
    def setup_method(self):
        self.content = DESKTOP_OPEN_PORTAL.read_text(encoding="utf-8")

    def test_calls_restart_servers_first(self):
        """open_portal.ps1 must call restart_servers.ps1."""
        assert "restart_servers.ps1" in self.content, (
            "open_portal.ps1 must call restart_servers.ps1"
        )

    def test_calls_launch_portal(self):
        """open_portal.ps1 must still call launch_portal.ps1."""
        assert "launch_portal.ps1" in self.content, (
            "open_portal.ps1 must still call launch_portal.ps1"
        )

    def test_restart_before_launch(self):
        """restart_servers.ps1 must appear before launch_portal.ps1 in the file."""
        restart_pos = self.content.find("restart_servers.ps1")
        launch_pos = self.content.find("launch_portal.ps1")
        assert restart_pos < launch_pos, (
            "restart_servers.ps1 must be called before launch_portal.ps1"
        )
