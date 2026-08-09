#!/usr/bin/env python3
"""Local-only Gmail OAuth bootstrap for the dedicated service mailbox.

FR-20260808-dedicated-service-email.

╔═══════════════════════════════════════════════════════════════════════════╗
║  MANUAL, HUMAN-ONLY TOOL. AGENTS MUST NEVER INVOKE THIS AUTOMATICALLY.     ║
╚═══════════════════════════════════════════════════════════════════════════╝

This CLI performs the *one-time* OAuth consent that mints the base64
authorized-user token consumed at run time by ``integrations.gmail`` via the
``GMAIL_SERVICE_TOKEN`` environment variable. It is intentionally separate from
the runtime Gmail client: the client only ever *reads* an already-minted token
and never runs a consent flow.

What it does
------------
1. Loads a Desktop OAuth client from either a ``--client-json`` file *or* the
   ``GMAIL_OAUTH_CLIENT_ID`` / ``GMAIL_OAUTH_CLIENT_SECRET`` environment
   variables (env vars take a client-secret JSON's place — no secret is read
   from or written to the repo).
2. Requests **only** the existing Gmail scopes the capability already uses:
   ``gmail.readonly`` and ``gmail.send`` (imported from the policy module — no
   new scope is introduced here).
3. Opens the local consent flow so the human signs in to the service mailbox
   (e.g. ``hello.fromtea@gmail.com``) and grants access.
4. Builds the OAuth *authorized-user* JSON (client id/secret + refresh token),
   base64-encodes it in memory, and hands it to ``GMAIL_SERVICE_TOKEN`` either
   by setting the current-user environment variable directly (``--set-user-env``)
   or by copying it to the clipboard (``--clipboard``).

Safety
------
The token is **never** printed to stdout, written to disk, or committed. Only a
short, non-reversible sha256 fingerprint and its length are shown so you can
verify the transfer. This module imports no Google libraries at import time.

Usage
-----
    # Option A — env vars (recommended; no client-secret file on disk):
    setx GMAIL_OAUTH_CLIENT_ID    "<desktop-client-id>"
    setx GMAIL_OAUTH_CLIENT_SECRET "<desktop-client-secret>"
    #   open a NEW terminal so the setx values are visible, then:
    C:\\G\\python.exe tools\\gmail_oauth_bootstrap.py --set-user-env

    # Option B — Desktop client JSON downloaded from Google Cloud Console:
    C:\\G\\python.exe tools\\gmail_oauth_bootstrap.py --client-json C:\\path\\client_secret.json --clipboard

After it finishes, open a NEW terminal so ``GMAIL_SERVICE_TOKEN`` is visible,
then set ``GMAIL_SERVICE_ADDRESS`` to the mailbox address.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

_CLIENT_ID_ENV = "GMAIL_OAUTH_CLIENT_ID"  # nosec B105 - env var name, not a secret
_CLIENT_SECRET_ENV = "GMAIL_OAUTH_CLIENT_SECRET"  # nosec B105 - env var name
_TARGET_ENV = "GMAIL_SERVICE_TOKEN"  # nosec B105 - env var name, not a secret

_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
_TOKEN_URI = "https://oauth2.googleapis.com/token"  # nosec B105 - public OAuth endpoint URL, not a secret


# ---------------------------------------------------------------------------
# Scope selection — reuse the capability's existing scopes, add nothing new.
# ---------------------------------------------------------------------------


def bootstrap_scopes() -> list[str]:
    """Return exactly the Gmail scopes the runtime capability already uses."""
    from integrations.gmail.policy import ALL_SCOPES  # noqa: PLC0415

    return list(ALL_SCOPES)


# ---------------------------------------------------------------------------
# Client-config loading (Desktop JSON file OR the two env vars).
# ---------------------------------------------------------------------------


def load_client_config(client_json_path: str | None = None) -> dict:
    """Return an installed-app client config for the OAuth flow.

    Priority: an explicit ``client_json_path`` (a Desktop OAuth client secret
    downloaded from Google Cloud Console), else the ``GMAIL_OAUTH_CLIENT_ID`` /
    ``GMAIL_OAUTH_CLIENT_SECRET`` environment variables. Raises if neither is
    available. No secret is ever read from the repository.
    """
    if client_json_path:
        path = Path(client_json_path)
        if not path.is_file():
            raise FileNotFoundError(f"OAuth client JSON not found: {client_json_path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        block = data.get("installed") or data.get("web")
        if not block or not block.get("client_id") or not block.get("client_secret"):
            raise ValueError(
                "OAuth client JSON is missing an 'installed'/'web' block with "
                "client_id and client_secret. Download a *Desktop* OAuth client "
                "from Google Cloud Console."
            )
        block.setdefault("auth_uri", _AUTH_URI)
        block.setdefault("token_uri", _TOKEN_URI)
        block.setdefault("redirect_uris", ["http://localhost"])
        return {"installed": block}

    client_id = os.environ.get(_CLIENT_ID_ENV)
    client_secret = os.environ.get(_CLIENT_SECRET_ENV)
    if not client_id or not client_secret:
        raise EnvironmentError(
            f"No OAuth client available. Either pass --client-json <path> to a "
            f"Desktop OAuth client, or set both {_CLIENT_ID_ENV} and "
            f"{_CLIENT_SECRET_ENV} environment variables."
        )
    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": _AUTH_URI,
            "token_uri": _TOKEN_URI,
            "redirect_uris": ["http://localhost"],
        }
    }


# ---------------------------------------------------------------------------
# Consent flow (isolated so it can be mocked; imports google lazily).
# ---------------------------------------------------------------------------


def run_consent_flow(client_config: dict, scopes, open_browser: bool = True):
    """Run the local OAuth consent flow and return google-auth credentials.

    Requests offline access + a consent prompt so a refresh token is issued.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: PLC0415

    flow = InstalledAppFlow.from_client_config(client_config, scopes=list(scopes))
    return flow.run_local_server(
        port=0,
        open_browser=open_browser,
        access_type="offline",
        prompt="consent",
    )


# ---------------------------------------------------------------------------
# Authorized-user JSON + base64 encoding (in memory only).
# ---------------------------------------------------------------------------


def credentials_to_authorized_user(creds) -> dict:
    """Build the OAuth authorized-user dict the runtime client consumes."""
    refresh = getattr(creds, "refresh_token", None)
    if not refresh:
        raise ValueError(
            "OAuth flow returned no refresh token. Re-run consent — the client "
            "must request offline access with a fresh consent prompt."
        )
    return {
        "type": "authorized_user",
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "refresh_token": refresh,
        "token_uri": getattr(creds, "token_uri", _TOKEN_URI),
        "scopes": list(getattr(creds, "scopes", []) or []),
    }


def encode_authorized_user(authorized_user: dict) -> str:
    """Base64-encode the authorized-user JSON (matches the runtime decoder)."""
    return base64.b64encode(
        json.dumps(authorized_user).encode("utf-8")
    ).decode("ascii")


def token_fingerprint(encoded: str) -> str:
    """Return a short, non-reversible sha256 prefix of the *encoded* token.

    Lets the human verify the transfer without ever disclosing the token.
    """
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:8]


# ---------------------------------------------------------------------------
# Safe emission — set env var or copy to clipboard; never print the token.
# ---------------------------------------------------------------------------


def _broadcast_env_change() -> None:
    """Best-effort broadcast so new processes see the updated user env."""
    try:
        import ctypes  # noqa: PLC0415

        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x1A
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment", 0x2, 5000, None
        )
    except Exception:  # nosec B110 - cosmetic notify; new shells still pick up the var
        pass


def set_user_env_var(name: str, value: str) -> None:
    """Set a current-user environment variable via the registry.

    Uses ``winreg`` (not ``setx``) so the secret value never appears on a
    command line, in shell history, or in a process listing.
    """
    import winreg  # noqa: PLC0415

    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE
    ) as key:
        winreg.SetValueEx(key, name, 0, winreg.REG_EXPAND_SZ, value)
    _broadcast_env_change()


def copy_to_clipboard(value: str) -> None:
    """Copy *value* to the clipboard without a subprocess/pipe (no disk, no log)."""
    import tkinter  # noqa: PLC0415

    root = tkinter.Tk()
    root.withdraw()
    root.clipboard_clear()
    root.clipboard_append(value)
    root.update()
    root.destroy()


def emit_token(encoded: str, *, mode: str = "instructions", target_env: str = _TARGET_ENV) -> str:
    """Transfer the encoded token to ``target_env`` by the chosen *mode*.

    ``mode`` is one of ``env`` (set the user env var directly), ``clipboard``
    (copy for manual paste), or ``instructions`` (show guidance only). The token
    itself is never printed. Returns the verification fingerprint.
    """
    fp = token_fingerprint(encoded)
    n = len(encoded)
    if mode == "env":
        set_user_env_var(target_env, encoded)
        print(
            f"[gmail-oauth-bootstrap] {target_env} set for the current user "
            f"(len={n}, sha256[:8]={fp}). Open a NEW terminal for it to take effect."
        )
    elif mode == "clipboard":
        copy_to_clipboard(encoded)
        print(
            f"[gmail-oauth-bootstrap] token copied to clipboard "
            f"(len={n}, sha256[:8]={fp}). Paste it into {target_env} via "
            "System > Environment Variables, then clear your clipboard."
        )
    else:
        print(
            f"[gmail-oauth-bootstrap] token ready (len={n}, sha256[:8]={fp}). "
            "It was NOT printed. Re-run with --set-user-env to set it directly, "
            "or --clipboard to copy it for manual paste."
        )
    return fp


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="gmail_oauth_bootstrap",
        description=(
            "Local-only, human-run OAuth bootstrap for the dedicated service "
            "mailbox. Mints GMAIL_SERVICE_TOKEN. Agents must not run this."
        ),
    )
    parser.add_argument(
        "--client-json",
        help="Path to a Desktop OAuth client JSON (alternative to the "
        "GMAIL_OAUTH_CLIENT_ID/GMAIL_OAUTH_CLIENT_SECRET env vars).",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--set-user-env",
        action="store_true",
        help="Set GMAIL_SERVICE_TOKEN for the current user (via the registry).",
    )
    group.add_argument(
        "--clipboard",
        action="store_true",
        help="Copy GMAIL_SERVICE_TOKEN to the clipboard for manual paste.",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not auto-open a browser; print the consent URL instead.",
    )
    args = parser.parse_args(argv)

    client_config = load_client_config(args.client_json)
    scopes = bootstrap_scopes()
    creds = run_consent_flow(client_config, scopes, open_browser=not args.no_browser)
    authorized_user = credentials_to_authorized_user(creds)
    encoded = encode_authorized_user(authorized_user)

    mode = "env" if args.set_user_env else "clipboard" if args.clipboard else "instructions"
    emit_token(encoded, mode=mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
