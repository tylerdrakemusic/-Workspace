# Governed Gmail Attachment Runtime Proof

- Feature request: `FR-20260906-governed-gmail-attachment-downloads`
- Worktree: `f:\⊕Workspace\.worktrees\feature-FR-20260906-governed-gmail-attachment-downloads`
- Run mode: deterministic local demo with `GMAIL_SERVICE_TOKEN` absent
- Gmail message data: not requested
- Secret values: not printed or persisted

## Command

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONPATH='src'
Remove-Item Env:GMAIL_SERVICE_TOKEN -ErrorAction SilentlyContinue
C:\G\python.exe -c "import json; from utils import gmail_mcp_server as g; print(json.dumps({'capability': g.capability_discovery(), 'health': g.capability_health(), 'registered_tools': sorted(g.mcp._tool_manager._tools)}, sort_keys=True))"
```

## Observed result

```json
{
  "capability_name": "dedicated-service-email",
  "attachment_actions": ["attachments"],
  "mcp_attachment_tools": ["list_attachments", "download_attachment"],
  "registered_tools": [
    "connectivity_test",
    "create_draft",
    "discover_capability",
    "download_attachment",
    "get_message",
    "health",
    "list_attachments",
    "read_messages",
    "search_messages",
    "send_draft"
  ],
  "health": {
    "available": false,
    "credential_env": "GMAIL_SERVICE_TOKEN",
    "reauthentication_required": true,
    "secrets_exposed": false,
    "state": "missing_credentials"
  }
}
```

This proves local capability discovery, MCP registration, and safe unavailable
health behavior. It does not claim mailbox reachability or attachment download
success because no credentials or real message data were supplied.