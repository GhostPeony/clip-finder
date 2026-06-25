# MCP OAuth Onboarding

Status: first implementation slice.

Memexai supports two MCP auth paths:

1. Dashboard-created bearer tokens for manual setup.
2. OAuth-native MCP onboarding for clients that can discover and authorize remote MCP servers.

The OAuth path is the preferred product direction because it lets Codex, Claude Code, Claude custom connectors, and similar desktop or hosted agent clients connect without first opening the Memexai dashboard. The agent client should be able to initiate the connection, open the user's browser for sign-in/approval, and receive its scoped MCP credential without the user manually creating a token in Settings.

For a paid or user-specific remote MCP, some credential is expected. Local STDIO MCP servers can often use environment variables or local credentials, but remote MCP servers that expose private user data should authenticate the user and issue a scoped access token. The product goal is not "no token"; it is "no manual dashboard token copy/paste unless the client cannot do OAuth."

## Flow

1. Agent client discovers `https://api.memexai.xyz/mcp`.
2. Memexai returns a `WWW-Authenticate` challenge with protected-resource metadata.
3. Client reads:
   - `/.well-known/oauth-protected-resource/mcp`
   - `/.well-known/oauth-authorization-server`
4. Client dynamically registers at `/oauth/register`.
5. Client opens `/oauth/authorize?...`.
6. Memexai redirects the user to the app route `/mcp/authorize?...`.
7. User signs in with Google if needed. If this is a new user and hosted auth allows signups, this creates the Memexai account during the agent-initiated flow.
8. User approves the agent request.
9. Browser redirects back to the agent's registered callback with an authorization code.
10. Client exchanges the code at `/oauth/token`.
11. Memexai returns an opaque bearer token backed by the existing `mcp_tokens` table.
12. Agent calls `get_mcp_session`.

## Security Shape

- Authorization Code with PKCE `S256` only.
- Dynamic clients are public clients with `token_endpoint_auth_method=none`.
- Redirect URIs must be HTTPS or localhost loopback HTTP.
- Authorization codes are hashed at rest.
- Codes expire after 10 minutes and are single-use.
- OAuth-issued MCP access tokens expire after 30 days.
- Default scopes are `context:read overlay:write`.
- `ingest:write` is allowed only when requested and approved.

## Current Scope

Implemented:

- OAuth protected-resource metadata.
- OAuth authorization-server metadata.
- Dynamic client registration.
- Authorization approval page.
- Authorization code creation.
- Token exchange into scoped MCP bearer token.
- MCP `WWW-Authenticate` challenge.

Not yet implemented:

- OAuth refresh tokens.
- OAuth Client ID Metadata Document support for newer MCP clients that prefer it over Dynamic Client Registration.
- User-facing connected-agent list separate from MCP token list.
- During-agent-auth YouTube connection prompt.
- Client logo/client name polish beyond registration metadata.
- Revocation UI grouped by OAuth client.

## Product Next Step

Fold this into FTUE:

- Landing CTA: "Connect your agent."
- Agent opens Memexai OAuth.
- User signs in.
- User approves MCP access.
- Memexai then prompts for YouTube read access and playlist setup.

That turns the agent itself into the onboarding surface.
