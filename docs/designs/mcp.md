# MCP server (2026-10-30)

Lets Claude (claude.ai, Desktop, Code) and ChatGPT read and change Meridian. Code: `meridian/mcp.py`.

- Address: `https://<meridian>/mcp` (Streamable HTTP, JSON replies). Shown in Settings → AI assistants (MCP).
- Sign-in: OAuth 2.1 with dynamic client registration and PKCE (S256). Discovery at `/.well-known/oauth-protected-resource`
  and `/.well-known/oauth-authorization-server`. The consent page at `/oauth/authorize` asks for the Meridian login (or uses the
  browser's session) and names where it will return to. Codes last 10 minutes and work once; access tokens 1 hour; refresh
  tokens 30 days and rotate on use. Only hashes are stored (`mcp_clients`, `mcp_codes`, `mcp_tokens`).
- Permissions: the same for everyone (the team's choice): an assistant can do what its person can do in Meridian, except
  change logins or passwords (`/api/login`, `/api/logout`, `/api/account`, `/api/people`) or disconnect apps (`/api/mcp`).
- Tools: `list_events`, `get_event`, `change_event` (every Events change, described for the model), `list_endpoints` and
  `call_api` (the rest of the API, from its OpenAPI description). Tool calls run in-process through the API and its sign-in
  middleware (`scope["meridian.person"]`), so the screens' checks apply. Each call is logged in `mcp_log` for 90 days.
- Settings lists connected apps per person with Disconnect, which deletes their tokens.
