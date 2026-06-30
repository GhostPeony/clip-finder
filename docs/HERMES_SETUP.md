# Hermes Setup

Memexai should be exposed to Hermes as a native HTTP MCP server plus a small routing skill.

## Local Paths

Example local desktop paths:

- Hermes home: `C:\Users\<you>\AppData\Local\hermes`
- Config: `C:\Users\<you>\AppData\Local\hermes\config.yaml`
- Skills: `C:\Users\<you>\AppData\Local\hermes\skills`

When using a remote Hermes launcher where another machine runs the backend process, configure that remote Hermes environment too:

- `/home/<you>/.hermes/config.yaml`
- `/home/<you>/.hermes/skills/memexai-context/SKILL.md`

## Skill

Versioned repo copy:

- [integrations/hermes/memexai-context/SKILL.md](../integrations/hermes/memexai-context/SKILL.md)

Local desktop install target:

```text
C:\Users\<you>\AppData\Local\hermes\skills\memexai-context\SKILL.md
```

The skill is only a routing layer. The MCP server remains the source of truth.

## MCP Server

Use the example snippet:

- [integrations/hermes/mcp_servers.memexai.example.yaml](../integrations/hermes/mcp_servers.memexai.example.yaml)

The web app Settings modal also shows this env-var config block and can copy it directly.
After creating a token, Settings additionally shows a one-time config with the raw token for
immediate setup. The token creation response and Settings modal also expose a complete JSON setup
bundle with the MCP endpoint, discovery URLs, first recommended MCP calls, the one-time credential,
and the user-scoped search access rules.

Add it under the top-level `mcp_servers:` key in the Hermes config used by the agent process:

```yaml
mcp_servers:
  memexai:
    url: 'https://api.memexai.xyz/mcp'
    headers:
      Authorization: 'Bearer ${MEMEXAI_MCP_TOKEN}'
    timeout: 180
    connect_timeout: 30
```

For local development, point `url` at the local backend `/mcp` endpoint.

## Token Scopes

Use the narrowest token that fits the task:

- `context:read`: default for search, context bundles, briefs, categories, jobs, and workflows.
- `overlay:write`: optional for durable notes and personal concepts.
- `ingest:write`: optional for user-approved YouTube URL ingestion.

Playlist and channel ingestion still require explicit `allow_bulk: true`.

After Hermes connects, call `get_mcp_session` first. It returns the token's effective scopes,
allowed capabilities, guardrails, and the recommended next MCP call without reading source data.
If the user gives Hermes the Settings "setup bundle", use its `firstCalls` and `accessModel`
fields before searching. In particular, `accessModel.searchScope` must remain
`current_user_grants`; shared canonical videos are reusable only after `user_videos` or
`user_channels` grants make them visible to the token owner.

## Repo Context

The preferred workflow is low friction:

1. Hermes calls `get_mcp_session` to confirm scopes and safe next calls.
2. Hermes reads `context://agent-quickstart` or calls `get_agent_quickstart` for the current flow.
3. Hermes inspects the codebase with its existing repo/filesystem/GitHub tools.
4. Hermes reads `context://repo-context-contract` or calls `get_repo_context_contract` when it needs the current schema.
5. Hermes passes compact `repo_context` into `build_context_bundle` or `build_agent_brief`.
6. Memexai uses that repo context for the current answer without storing it as source truth.

The most useful `repo_context` includes inspected files, symbols, locations, entrypoints, key dependencies, verified commands, relevant tests, deployment facts, active changes to preserve, feature areas, and constraints. Keep it compact; pass references and facts rather than file dumps. The contract response includes `jsonSchema`, and `validate_repo_context`, `build_context_bundle`, and `build_agent_brief` expose the same schema in their MCP tool definitions.

`validate_repo_context` returns `readiness.level` and `next_mcp_call`. For implementation plans, prefer `implementation_ready`; otherwise follow `readiness.suggestedAgentNextSteps` with Hermes' existing repo tools, then validate again.

`build_agent_brief` also includes readiness in `repoContextValidation` and puts repo-inspection work at the top of `suggestedNextActions` when the supplied repo context is still partial.
When the brief is ready, use `repoFit.targetMap` to map saved-video concepts onto concrete files,
symbols, locations, commands, tests, runtime targets, constraints, and open questions without
re-parsing the flat `candidateTouchpoints` list.

## Search Access

Search is scoped to the MCP token owner's granted library, not the unauthenticated global corpus.
Canonical video rows can be shared across users for cost efficiency, but a clip is returned only
through `user_videos` or `user_channels`. Hermes should inspect `accessScope`, `accessSource`, and
`accessReason` on search clips, library videos, and video context when explaining why a reused or
shared video is available.

Preferred retrieval order: call `search_video_concepts` with `retrieval_mode: "hybrid"` for indexed
source reports, concepts, report sections, aliases, and timestamp refs; call
`get_video_knowledge_map` for candidate videos; then call `search_video_moments` with
`retrieval_mode: "hybrid"` for timestamped evidence. Use `search_transcript_text` or
`retrieval_mode: "keyword"` for exact terms or zero embedding spend, and use `detail_level`,
`max_chars`, or `max_context_tokens` when the agent needs to stay inside a smaller context budget.
