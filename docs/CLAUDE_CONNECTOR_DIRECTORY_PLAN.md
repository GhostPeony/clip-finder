# Claude Connector Directory Plan

Status: planning checklist for submitting Memexai as an official Claude connector.

## Current User Setup

Until Memexai is listed in the Claude Connectors Directory, users should add it as a custom remote MCP connector:

1. Open Claude settings, then `Customize > Connectors`.
2. Choose `Add custom connector`.
3. Paste `https://api.memexai.xyz/mcp`.
4. Name it `Memexai`.
5. Connect, sign in with Google, approve Memexai access, then enable the connector in the chat.

Fallback for clients that do not complete remote MCP OAuth: create a scoped MCP token in Memexai Settings and configure the client with a bearer-token HTTP MCP header.

## Official Directory Path

Anthropic lists official connectors through the Claude Connectors Directory submission portal. For remote MCP servers, submission happens from a Claude Team or Enterprise organization admin area, not an individual Pro/Max account.

Required before submission:

- A production HTTPS MCP endpoint: `https://api.memexai.xyz/mcp`.
- OAuth 2.0 authentication for user-specific data.
- Working OAuth discovery, dynamic client registration or another Claude-supported auth mode.
- Public documentation with setup and usage instructions.
- Public privacy policy and support contact.
- Fully populated test account credentials for review.
- Stable icon and listing copy.
- Tool schemas with short names, accurate descriptions, `title`, and read/write safety annotations.
- Read and write tools split clearly. No catch-all generic API tool.
- Reasonable response sizes and actionable errors.
- WAF/CDN allow rules so Anthropic-hosted Claude traffic can reach `/mcp`.

## Memexai Readiness

Already present:

- Remote streamable HTTP MCP endpoint.
- Google-auth-backed OAuth approval route.
- OAuth protected-resource and authorization-server metadata.
- Dynamic client registration.
- Scoped MCP tokens stored through the existing `mcp_tokens` table.
- Public discovery endpoints: `/mcp.json`, `/.well-known/mcp.json`, `/llms.txt`, `/llms-full.txt`.
- Tool separation for read context, ingestion, project creation, and playlist sync.

Still needed before submission:

- Confirm every MCP tool advertises Claude-compatible `title` plus `readOnlyHint` or `destructiveHint`.
- Run MCP Inspector against production OAuth and every tool.
- Add Cloudflare WAF skip/allow rule for `/mcp` so generic Claude/agent traffic is not blocked.
- Prepare a fully populated reviewer test account with safe sample videos/projects.
- Publish customer-facing connector documentation and privacy/support links.
- Decide whether write tools are included in the first listing or whether v1 directory submission should be read-only plus explicit ingestion.
- Create listing copy, categories, icon, and support contact.
- Submit through Claude Team/Enterprise organization admin settings.

## Suggested Listing Copy

Name: `Memexai`

Tagline: `Search and cite your saved YouTube knowledge`

Description:

Memexai turns saved YouTube videos, playlists, and projects into timestamped source context for Claude. Claude can inspect your video library, search generated source reports and concepts, open video knowledge maps, retrieve exact transcript moments, and build briefs grounded in your saved videos.

Primary use cases:

- Search a personal video library without re-pasting links.
- Scope retrieval to projects such as courses, research topics, or implementation work.
- Pull timestamped evidence from saved YouTube videos.
- Queue a user-approved YouTube link or playlist sync when write access is enabled.

## Submission Notes

For the first submission, prefer the smallest defensible connector surface:

- Include read tools, project/library discovery, source-knowledge search, knowledge maps, transcript-moment search, and job status.
- Include write tools only if Anthropic review accepts the current confirmation model and destructive annotations.
- If write-tool review slows approval, submit a read-first connector and keep ingestion/sync available through custom connector or later listing update.
