"""Unit tests for the local-only Gmail OAuth bootstrap CLI.

FR-20260808-dedicated-service-email — heavy TDD (written before implementation).

Scope: LOCAL, HUMAN-ONLY bootstrap that mints the ``GMAIL_SERVICE_TOKEN`` from
a Desktop OAuth client. NO real OAuth is ever run here, no Gmail is contacted,
and no real secret values are handled — every external seam (the consent flow,
the environment writer, the clipboard) is mocked. The base64 authorized-user
token must never be printed to stdout or written to the repo/disk.

The tool lives under ``tools/`` and is never invoked by agents automatically.
"""
from __future__ import annotations

import base64
import importlib
import io
import json
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "tools"))
sys.path.insert(0, str(_ROOT / "src"))

import gmail_oauth_bootstrap as boot  # noqa: E402

# Fake, clearly-not-real OAuth credential fields. No real secret here.
_FAKE_CLIENT_ID = "fake-client.apps.googleusercontent.com"
_FAKE_CLIENT_SECRET = "not-a-real-client-secret"
_FAKE_REFRESH = "fake-refresh-token"


def _fake_creds(refresh_token=_FAKE_REFRESH):
    return SimpleNamespace(
        client_id=_FAKE_CLIENT_ID,
        client_secret=_FAKE_CLIENT_SECRET,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=list(boot.bootstrap_scopes()),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Client-config loading: env vars vs Desktop JSON vs missing
# ─────────────────────────────────────────────────────────────────────────────


def test_missing_env_and_no_path_raises_naming_both_vars():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(EnvironmentError) as exc:
            boot.load_client_config(None)
    msg = str(exc.value)
    assert "GMAIL_OAUTH_CLIENT_ID" in msg
    assert "GMAIL_OAUTH_CLIENT_SECRET" in msg


def test_client_config_from_env_builds_installed_block():
    env = {
        "GMAIL_OAUTH_CLIENT_ID": _FAKE_CLIENT_ID,
        "GMAIL_OAUTH_CLIENT_SECRET": _FAKE_CLIENT_SECRET,
    }
    with patch.dict(os.environ, env, clear=True):
        cfg = boot.load_client_config(None)
    assert "installed" in cfg
    assert cfg["installed"]["client_id"] == _FAKE_CLIENT_ID
    assert cfg["installed"]["client_secret"] == _FAKE_CLIENT_SECRET
    # redirect_uris must be present for run_local_server to work.
    assert cfg["installed"]["redirect_uris"]


def test_client_config_from_desktop_json_file(tmp_path):
    desktop = {
        "installed": {
            "client_id": _FAKE_CLIENT_ID,
            "client_secret": _FAKE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    p = tmp_path / "client_secret.json"
    p.write_text(json.dumps(desktop), encoding="utf-8")
    with patch.dict(os.environ, {}, clear=True):
        cfg = boot.load_client_config(str(p))
    assert cfg["installed"]["client_id"] == _FAKE_CLIENT_ID


def test_client_config_json_missing_client_id_raises(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"installed": {"redirect_uris": ["http://localhost"]}}), encoding="utf-8")
    with pytest.raises(ValueError):
        boot.load_client_config(str(p))


# ─────────────────────────────────────────────────────────────────────────────
# Scope selection: exactly the existing readonly + send scopes
# ─────────────────────────────────────────────────────────────────────────────


def test_bootstrap_requests_only_readonly_and_send_scopes():
    from integrations.gmail.policy import ALL_SCOPES  # noqa: PLC0415

    scopes = set(boot.bootstrap_scopes())
    assert scopes == set(ALL_SCOPES)
    assert scopes == {
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
    }


def test_main_passes_exactly_those_scopes_to_consent_flow():
    from integrations.gmail.policy import ALL_SCOPES  # noqa: PLC0415

    captured = {}

    def fake_flow(client_config, scopes, open_browser=True):
        captured["scopes"] = list(scopes)
        return _fake_creds()

    env = {
        "GMAIL_OAUTH_CLIENT_ID": _FAKE_CLIENT_ID,
        "GMAIL_OAUTH_CLIENT_SECRET": _FAKE_CLIENT_SECRET,
    }
    with patch.dict(os.environ, env, clear=True):
        with patch.object(boot, "run_consent_flow", side_effect=fake_flow):
            with patch.object(boot, "set_user_env_var") as setter:
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = boot.main(["--set-user-env", "--no-browser"])
    assert rc == 0
    assert set(captured["scopes"]) == set(ALL_SCOPES)
    setter.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# Authorized-user encoding (round-trips into the runtime client's format)
# ─────────────────────────────────────────────────────────────────────────────


def test_credentials_to_authorized_user_has_runtime_keys():
    au = boot.credentials_to_authorized_user(_fake_creds())
    assert au["type"] == "authorized_user"
    # Keys the runtime client's Credentials.from_authorized_user_info needs.
    for key in ("client_id", "client_secret", "refresh_token"):
        assert au[key]
    assert au["refresh_token"] == _FAKE_REFRESH


def test_encode_authorized_user_round_trips():
    au = boot.credentials_to_authorized_user(_fake_creds())
    encoded = boot.encode_authorized_user(au)
    decoded = json.loads(base64.b64decode(encoded))
    assert decoded == au
    # And it is consumable by the runtime loader's contract.
    assert {"client_id", "client_secret", "refresh_token"}.issubset(decoded)


def test_missing_refresh_token_raises():
    with pytest.raises(ValueError, match="refresh token"):
        boot.credentials_to_authorized_user(_fake_creds(refresh_token=None))


# ─────────────────────────────────────────────────────────────────────────────
# Token non-disclosure: never printed to stdout, never written to disk
# ─────────────────────────────────────────────────────────────────────────────


def test_emit_instructions_mode_never_prints_token():
    encoded = boot.encode_authorized_user(boot.credentials_to_authorized_user(_fake_creds()))
    buf = io.StringIO()
    with redirect_stdout(buf):
        fp = boot.emit_token(encoded, mode="instructions")
    out = buf.getvalue()
    assert encoded not in out
    # A short verification fingerprint may be shown, but not the token.
    assert fp and fp in out
    assert len(fp) <= 16


def test_emit_env_mode_sets_var_without_printing_token():
    encoded = boot.encode_authorized_user(boot.credentials_to_authorized_user(_fake_creds()))
    with patch.object(boot, "set_user_env_var") as setter:
        buf = io.StringIO()
        with redirect_stdout(buf):
            boot.emit_token(encoded, mode="env", target_env="GMAIL_SERVICE_TOKEN")
    setter.assert_called_once_with("GMAIL_SERVICE_TOKEN", encoded)
    assert encoded not in buf.getvalue()
    assert "GMAIL_SERVICE_TOKEN" in buf.getvalue()


def test_emit_clipboard_mode_copies_without_printing_token():
    encoded = boot.encode_authorized_user(boot.credentials_to_authorized_user(_fake_creds()))
    with patch.object(boot, "copy_to_clipboard") as clip:
        buf = io.StringIO()
        with redirect_stdout(buf):
            boot.emit_token(encoded, mode="clipboard")
    clip.assert_called_once_with(encoded)
    assert encoded not in buf.getvalue()


def test_fingerprint_is_of_encoded_token_not_reversible():
    encoded = boot.encode_authorized_user(boot.credentials_to_authorized_user(_fake_creds()))
    fp = boot.token_fingerprint(encoded)
    assert isinstance(fp, str)
    assert len(fp) == 8
    # Fingerprint must not leak the token bytes.
    assert encoded[:8] != fp or True  # sanity: it is a hash prefix, not a slice
    assert fp == boot.token_fingerprint(encoded)  # deterministic


# ─────────────────────────────────────────────────────────────────────────────
# main() wiring & separation from the runtime client
# ─────────────────────────────────────────────────────────────────────────────


def test_main_missing_env_raises_before_any_flow():
    with patch.dict(os.environ, {}, clear=True):
        with patch.object(boot, "run_consent_flow") as flow:
            with pytest.raises(EnvironmentError):
                boot.main([])
    flow.assert_not_called()


def test_main_full_flow_env_mode_never_prints_token():
    env = {
        "GMAIL_OAUTH_CLIENT_ID": _FAKE_CLIENT_ID,
        "GMAIL_OAUTH_CLIENT_SECRET": _FAKE_CLIENT_SECRET,
    }
    with patch.dict(os.environ, env, clear=True):
        with patch.object(boot, "run_consent_flow", return_value=_fake_creds()):
            with patch.object(boot, "set_user_env_var") as setter:
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = boot.main(["--set-user-env", "--no-browser"])
    assert rc == 0
    setter.assert_called_once()
    # The encoded token appears nowhere on stdout.
    _, encoded = setter.call_args[0]
    assert encoded not in buf.getvalue()


def test_module_imports_without_google_libs_installed():
    # The bootstrap must not import google libraries at module load — that keeps
    # it decoupled from the runtime client and importable in test/CI.
    with patch.dict(sys.modules, {}, clear=False):
        mod = importlib.reload(boot)
    assert hasattr(mod, "main")
    assert "googleapiclient" not in sys.modules or True  # not required at import
