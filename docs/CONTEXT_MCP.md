# Context MCP Direction

Status: first backend, ingestion, and MCP adapter slice in progress

## Product Boundary

Memexai should expose a context MCP for agents, not a source-editing MCP.

Agents may read:

- indexed videos in the user's library
- transcript chunks and transcript lines
- generated source concepts and source edges
- study guides and other knowledge artifacts
- the user's personal notes and personalized concepts

Agents may write only to the personal overlay:

- agent notes
- personal concepts
- links between personal context and source references
- user or agent preferences about relevance

External personal brains should treat Memexai as a source MCP, not as the only memory
database. They should pull compact video digests, category maps, timestamp refs, and provenance
through MCP, then store their own subjective memory separately. When they need to preserve a
takeaway inside Memexai, they should write to the personal overlay only.

Agents must not rewrite source transcripts, generated source concepts, videos, chunks, or existing ingestion jobs through MCP. With explicit `ingest:write`, agents may create new queued ingestion jobs from YouTube links the user provided or approved.

Source storage is canonical and shared; access is user-scoped. A YouTube video should be embedded
once in `videos`, `chunks`, and source knowledge tables, then made visible to accounts through
`user_channels` for channel-level access or `user_videos` for precise video-level grants. This lets
two users benefit from the same stored embeddings without letting unrelated saved videos bleed into
another user's searches.

Search never runs over the unauthenticated global corpus. The default search mode is "current user
grants": a row is eligible only when the MCP token owner has channel access or a precise video grant.
Future team, organization, or public-discoverable search should add explicit grants and provenance
rather than querying every canonical video row.
Search clips, library videos, and full video context include `accessScope`, `accessSource`, and
`accessReason` so agents can distinguish channel-wide context from a saved/reused single-video
grant.

## Ingestion-Time Knowledge

After transcript chunks are embedded and stored, ingestion now runs a bounded source-knowledge pass.

It writes:

- `transcript_lines`: timestamped transcript rows derived from stored chunks
- `source_labels`: video-level labels for domains, task fit, entities, tools, difficulty, and other agent-search facets
- `source_concepts`: key concepts, methods, algorithms, claims, tools, implementation notes, and pitfalls
- `source_edges`: relationships between extracted concepts
- `knowledge_artifacts`: system-generated TLDR and study guide artifacts

This pass is failure-safe. If the LLM extraction fails or the knowledge tables are unavailable, base video indexing still completes with transcript chunks and embeddings.

Ingestion supports `digest_depth` so users and agents can choose the cost/richness tradeoff:

- `none`: store transcript lines and searchable chunks only; skip LLM source-knowledge extraction.
- `basic`: generate compact labels, core concepts, and a TLDR.
- `standard`: generate labels, concepts, relationships, TLDR, and a study guide.
- `deep`: use a larger transcript/output budget for richer source knowledge.

## Repo Context

The lowest-friction path is to let agents bring repository context through their own MCP setup first.

For example, a coding agent may already have GitHub, filesystem, or code-index MCP access. In that case, it can call Memexai with a short `repo_context` payload when asking for a context bundle. The backend treats that repo context as request-supplied context, not stored source truth.

Hosted GitHub connection should remain optional:

- Use it later for users who want persistent repo summaries.
- Prefer a GitHub App with selected-repository read permissions.
- Do not require GitHub connection before an agent can use video knowledge with its own repo context.

## Current Backend Contract

The REST contract behind the MCP adapter is:

- `GET /api/videos/{video_id}/context`
- `GET /api/context/notes`
- `POST /api/context/notes`
- `POST /api/context/personal-concepts`
- `POST /api/context/bundle`

`/api/context/bundle` returns source context, personal overlay context, optional request-supplied `repo_context`, and optional `category_filters` so an agent can bring repo metadata from MCP without forcing a hosted repo integration.

`category_filters` use the source-label taxonomy exposed by `list_context_categories` and
`context://categories`. They can be passed to `search_video_concepts`, `search_video_moments`,
`build_context_bundle`, and `build_agent_brief`. Values within one facet are OR; different facets
are AND. Example:

```json
{
  "task_fit": ["product spec"],
  "tool": ["MCP"]
}
```

Agents can validate a compact repo payload before building a bundle:

- REST: `POST /api/context/repo-context/validate`
- MCP resource: `context://repo-context-contract`
- MCP resource: `context://repo-context-workflow`
- MCP tool: `get_repo_context_contract`
- MCP tool: `get_repo_context_workflow`
- MCP: `validate_repo_context`

Agents and personal brains can discover the external-brain sync contract separately:

- MCP resource: `context://brain-sync-contract`
- MCP resource: `context://brain-digest`
- MCP tool: `get_brain_sync_contract`
- MCP tool: `export_brain_digest`

This contract describes compact pull surfaces, the current incremental digest export, the available
outbound sync outbox event types, source provenance requirements, and overlay-only write rules for
centralized brain systems. `export_brain_digest` and `context://brain-digest` return compact changed
videos, labels, concepts, artifacts, notes, and personal concepts with an opaque `nextCursor`,
optional `since` and `objects` filters, access provenance, and response-budget metadata. Raw
transcripts are omitted by default. Webhook delivery from the queued outbox remains a follow-up
worker/integration task.

`context://repo-context-contract` and `get_repo_context_contract` return the self-describing schema
without reading or storing any repo data. The validator normalizes `source`, `repo`, `branch`,
`files`, `locations`, `entrypoints`, `modules`, `symbols`, `features`, `dependencies`, `commands`,
`tests`, `deployment`, `active_changes`, `constraints`, and `open_questions`, preserves small extra
fields under `extra`, and returns warnings for missing recommended fields. It does not store
repository data.

The contract includes a `jsonSchema` object, and the MCP input schemas for `validate_repo_context`,
`build_context_bundle`, and `build_agent_brief` embed the same schema. MCP clients can use that to
render repo-context forms or validate agent-built payloads before calling Memexai.

`validate_repo_context` also returns `readiness`:

- `missing`: no usable repo context was provided.
- `partial`: valid payload, but the agent should inspect more repo details first.
- `brief_ready`: enough for a repo-aware study guide, spec, or product brief.
- `implementation_ready`: enough for an implementation plan with verification and runtime constraints.

Agents should check `readiness.suggestedAgentNextSteps` and use their own filesystem, GitHub, or
code-index MCP tools to fill missing files, symbols, locations, entrypoints, commands, tests,
dependencies, deployment facts, or active-change notes before asking for implementation guidance.

`build_agent_brief` passes the same readiness into `repoContextValidation` and leads
`suggestedNextActions` with repo-inspection steps when `repo_context` is not implementation-ready.
It also returns `repoFit.targetMap`, a grouped, agent-friendly map of repo, branch, features,
files, symbols, locations, commands, tests, runtime targets, constraints, and open questions. Use
that structured map for implementation planning instead of re-parsing the legacy flat
`repoFit.candidateTouchpoints` list.

Machine-readable discovery surfaces also expose `repoContextWorkflow.collectPromptExpectedOutput`.
Agents can fetch that workflow directly through `context://repo-context-workflow` or
`get_repo_context_workflow` without database access.
After `prompts/get collect_repo_context`, agents should return:

- normalized `repo_context`
- `readiness.level`
- `readiness.missingSignals`
- `readiness.suggestedAgentNextSteps`
- any `open_questions`
- `next_mcp_call`, copied from `validate_repo_context`

## MCP Contract

The backend now exposes a stateless MCP JSON-RPC endpoint at:

- `POST /mcp`

Public agent discovery endpoints:

- `GET /llms.txt`: concise agent guide.
- `GET /llms-full.txt`: detailed agent guide.
- `GET /mcp.json`: MCP discovery manifest.
- `GET /.well-known/mcp.json`: well-known alias for the MCP discovery manifest.

The manifest includes machine-readable access, retrieval, storage, repo-context, and onboarding
guidance so agents can discover that source data is canonical/shared, search is user-scoped,
`category_filters` are available, Supabase is the hosted default, and caller-supplied
`repo_context` is preferred over forcing a hosted GitHub connection. The same manifest includes
the repo-context readiness gate and expected output shape for `collect_repo_context`. Its
`auth.setupBundle` provides copyable agent setup metadata: endpoint URLs, Hermes config, first MCP
calls, and the same `current_user_grants` access model used by search. The authenticated token
creation endpoint returns the same bundle with a one-time credential so a user or agent can set up
MCP without piecing together several snippets.

It supports:

- `initialize`
- `ping`
- `resources/list`
- `resources/read`
- `prompts/list`
- `prompts/get`
- `tools/list`
- `tools/call`
- `notifications/*` as no-response notifications

Read-only MCP resources:

- `context://agent-quickstart`: machine-readable first steps for connected agents.
- `context://brain-sync-contract`: contract for syncing compact saved-video knowledge into an external personal brain.
- `context://brain-digest`: compact incremental digest for external personal brains.
- `context://library`: indexed channels and recent saved videos available to the current account.
- `context://repo-context-contract`: schema for caller-supplied repo context.
- `context://repo-context-workflow`: readiness gate and expected output for caller-supplied repo context collection.
- `context://capture-sources`: standing YouTube inputs such as a user-selected playlist, including recent discovered/queued item status.
- `context://categories`: browsable source labels, facets, and personal concepts for agent discovery.
- `context://notes`: recent personal overlay notes.
- `context://workflows`: recent durable platform workflow runs.
- `context://workflow/{workflowInstanceId}`: one workflow run with step and artifact status.
- `context://video/{videoId}`: transcript-derived context for a saved video.

Agent workflow prompts:

- `study_guide_from_saved_video`: produce a TLDR, study guide, questions, and action items with timestamp citations.
- `repo_implementation_brief`: combine saved-video knowledge with repo context supplied by the calling agent's own repo/filesystem/GitHub MCP.
- `collect_repo_context`: inspect the caller's repo with existing repo tools, build compact `repo_context`, and validate readiness before requesting a brief.
- `categorize_saved_video`: inspect a saved video and produce agent-friendly labels such as topic, methods, tools, difficulty, and project applicability.
- `capture_personal_context`: preserve durable user-specific takeaways through overlay notes or personal concepts only.

The first tool set is intentionally small:

- `get_mcp_session`: return effective token scopes, allowed capabilities, guardrails, and recommended next MCP calls without reading the database.
- `get_agent_quickstart`: return machine-readable first steps for using Memexai MCP safely.
- `get_brain_sync_contract`: return the machine-readable contract for external personal-brain sync.
- `export_brain_digest`: return a compact incremental digest for external personal brains with cursor, `since`, object filters, access provenance, and response budgets.
- `list_video_library`: list indexed channels and recent saved videos so an agent can discover usable `videoId` values.
- `list_capture_sources`: list standing YouTube capture sources that can feed future ingestion jobs, plus recent item status.
- `list_context_categories`: list source labels, concept categories, facets, and personal concepts before searching.
- `list_ingestion_jobs`: list recent hosted ingestion jobs so an agent can check submitted YouTube links.
- `get_ingestion_job`: read one hosted ingestion job and its events.
- `list_workflow_runs`: list recent durable platform workflow runs.
- `get_workflow_run`: read one workflow run with step and artifact status.
- `get_repo_context_contract`: read the compact repo_context schema agents should populate from their own repo/filesystem/GitHub MCP tools.
- `get_repo_context_workflow`: read the repo-context collection workflow, readiness gate, and `collect_repo_context` expected output without storing repo data.
- `validate_repo_context`: validate and normalize caller-supplied repo context before building a bundle or brief.
- `search_video_concepts`: search indexed source concepts, TLDRs, source reports, report sections, aliases, and timestamp refs. `retrieval_mode` supports `hybrid` by default, `semantic`, and `keyword`; keyword mode makes zero embedding calls and all modes avoid LLM calls.
- `get_video_knowledge_map`: inspect a compact navigable table of contents for one video, including report sections, concepts, people/orgs/tools, claims, decisions, timeline cues, timestamp refs, and suggested follow-up queries.
- `search_video_moments`: search the user's indexed transcript chunks and return timestamped clips with access provenance. `retrieval_mode` supports `hybrid` (default vector + keyword/title fusion), `semantic`, and `keyword`, optionally narrowed by `category_filters`; pass `youtube_video_id`/`video_id` for known-video questions.
- `get_transcript_window`: read a bounded transcript slice for one saved video between `start_seconds` and `end_seconds` after search or a video map identifies the relevant timestamp.
- `get_video_context`: read source-derived concepts, edges, and artifacts for a video in the user's library. Transcript lines/chunks are omitted by default over MCP; pass `include_transcript: true` with `detail_level`/`max_chars` only when maps, search clips, and transcript windows are insufficient.
- `list_agent_notes`: read recent personal overlay notes.
- `add_context_note`: write an agent note to the personal overlay only.
- `upsert_personal_concept`: write or update a user-specific concept in the personal overlay only.
- `build_context_bundle`: return agent-friendly source concepts/artifacts, personal notes/concepts, and optional `repo_context` supplied by the calling agent.
- `build_agent_brief`: compose a spec/prompt-oriented brief from saved video knowledge, personal overlay, and optional `repo_context`.
- `queue_youtube_ingestion`: with `ingest:write`, submit a YouTube video, playlist, channel, or Shorts URL into the user's hosted ingestion queue.

Blocked by design:

- source transcript mutation
- source concept or edge mutation
- destructive library actions
- editing, cancelling, or reprioritizing existing ingestion jobs

`/mcp` accepts either the app's normal Supabase bearer token or a dedicated MCP bearer token.

MCP token management API:

- `GET /api/mcp/tokens`: list active token metadata
- `POST /api/mcp/tokens`: create a token and return the raw token once
- `DELETE /api/mcp/tokens/{token_id}`: revoke a token

Stored tokens are hashed. The database keeps only `token_hash`, a display prefix, scopes, and usage metadata.

Workflow status API:

- `GET /api/workflows/definitions`: list visible platform workflow definitions.
- `GET /api/workflows/instances`: list recent user-scoped workflow runs.
- `GET /api/workflows/instances/{instance_id}`: read one workflow run with step and artifact details.

Workflow runs are the long-running platform status layer for capture sync, video ingestion, knowledge release, evals, and durable agent briefs. Agents should poll workflow handles instead of blocking on long-running work.

Capture source API:

- `GET /api/capture/sources`: list user-selected YouTube capture sources.
- `POST /api/capture/sources`: create a playlist capture source from a YouTube playlist URL.
- `POST /api/capture/sources/{source_id}/sync`: scan the playlist, dedupe discovered videos, and queue a bounded number of video ingestion jobs.

The first sync implementation is intentionally manual and bounded. It supports the low-friction public-playlist workflow now, while keeping private playlist OAuth, scheduled polling, and agent-triggered capture sync as later scoped work.

Initial scopes:

- `context:read`: allows resource reads, semantic moment search, source context, and bundle reads
- `overlay:write`: allows agent notes and personal concept writes
- `ingest:write`: allows agents to queue YouTube URLs found in chat sessions for hosted ingestion

Resource discovery example:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "resources/list"
}
```

Resource read example:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "resources/read",
  "params": {
    "uri": "context://video/VIDEO_ID"
  }
}
```

External brain digest example:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "export_brain_digest",
    "arguments": {
      "cursor": "NEXT_CURSOR_FROM_PREVIOUS_SYNC",
      "objects": ["videos", "concepts", "artifacts", "notes", "personal_concepts"],
      "detail_level": "compact",
      "max_chars": 6000
    }
  }
}
```

Category discovery example:

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "list_context_categories",
    "arguments": {
      "limit": 100
    }
  }
}
```

Filtered moment search example:

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "search_video_moments",
    "arguments": {
      "query": "how should I design an eval harness?",
      "retrieval_mode": "hybrid",
      "category_filters": {
        "task_fit": ["product spec"],
        "method": ["harness-driven development"]
      },
      "limit": 5
    }
  }
}
```

Budgeted source-knowledge search example:

```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "tools/call",
  "params": {
    "name": "search_video_concepts",
    "arguments": {
      "query": "eval harness production pitfalls study guide",
      "category_filters": {
        "task_fit": ["implementation plan"]
      },
      "retrieval_mode": "hybrid",
      "detail_level": "compact",
      "max_chars": 6000,
      "limit": 8
    }
  }
}
```

Candidate video map example:

```json
{
  "jsonrpc": "2.0",
  "id": 6,
  "method": "tools/call",
  "params": {
    "name": "get_video_knowledge_map",
    "arguments": {
      "youtube_video_id": "VIDEO_ID",
      "detail_level": "compact",
      "max_chars": 6000
    }
  }
}
```

Prompt example:

```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "prompts/get",
  "params": {
    "name": "repo_implementation_brief",
    "arguments": {
      "query": "apply Sierra-style evaluation harness ideas to my agent training gym",
      "repo_context_hint": "evaluation harness and agent workflow modules"
    }
  }
}
```

Library discovery example:

```json
{
  "jsonrpc": "2.0",
  "id": 6,
  "method": "tools/call",
  "params": {
    "name": "list_video_library",
    "arguments": {
      "limit": 50
    }
  }
}
```

Capture source discovery example:

```json
{
  "jsonrpc": "2.0",
  "id": 7,
  "method": "tools/call",
  "params": {
    "name": "list_capture_sources",
    "arguments": {
      "limit": 50
    }
  }
}
```

Example `tools/call` body:

```json
{
  "jsonrpc": "2.0",
  "id": 7,
  "method": "tools/call",
  "params": {
    "name": "search_video_moments",
    "arguments": {
      "query": "where did the speaker explain reward model evaluation loops?",
      "limit": 5
    }
  }
}
```

The `repo_implementation_brief` prompt tells the calling agent to inspect the repo with its own
tools, call `validate_repo_context`, follow `readiness.suggestedAgentNextSteps` until the payload is
strong enough, then call `build_agent_brief`.

Use the `collect_repo_context` prompt when the agent only needs to prepare a validated
`repo_context` payload first. It stops before `build_agent_brief` unless the user explicitly asks for
the implementation brief next.

Agents that need the exact collection flow can read `context://repo-context-workflow` or call
`get_repo_context_workflow` before requesting `prompts/get collect_repo_context`.

Repo-context workflow resource example:

```json
{
  "jsonrpc": "2.0",
  "id": 8,
  "method": "resources/read",
  "params": {
    "uri": "context://repo-context-workflow"
  }
}
```

Repo-context workflow tool example:

```json
{
  "jsonrpc": "2.0",
  "id": 9,
  "method": "tools/call",
  "params": {
    "name": "get_repo_context_workflow",
    "arguments": {}
  }
}
```

Repo-context bundle example:

```json
{
  "jsonrpc": "2.0",
  "id": 10,
  "method": "tools/call",
  "params": {
    "name": "build_context_bundle",
    "arguments": {
      "query": "apply this RLHF lesson to my training gym",
      "repo_context": {
        "source": "agent-mcp",
        "repo": "GhostPeony/open-model-gym",
        "files": ["backend/evals.py", "agents/harness.ts"],
        "locations": ["backend/evals.py:42 run_eval_suite"],
        "entrypoints": ["python backend/evals.py", "agents/harness.ts"],
        "symbols": ["run_eval_suite", "AgentHarness"],
        "features": ["evaluation harness", "reward model experiments"],
        "dependencies": ["Supabase", "OpenAI SDK"],
        "commands": ["python -m pytest tests/test_evals.py -q"],
        "tests": ["tests/test_evals.py"]
      },
      "limit": 8
    }
  }
}
```

Agent brief example:

```json
{
  "jsonrpc": "2.0",
  "id": 9,
  "method": "tools/call",
  "params": {
    "name": "build_agent_brief",
    "arguments": {
      "query": "turn reward model evaluation ideas into an implementation plan",
      "repo_context": {
        "source": "agent-mcp",
        "repo": "GhostPeony/open-model-gym",
        "files": ["backend/evals.py", "agents/harness.ts"],
        "locations": ["backend/evals.py:42 run_eval_suite"],
        "entrypoints": ["python backend/evals.py", "agents/harness.ts"],
        "symbols": ["run_eval_suite", "AgentHarness"],
        "features": ["evaluation harness", "reward model experiments"],
        "dependencies": ["Supabase", "OpenAI SDK"],
        "commands": ["python -m pytest tests/test_evals.py -q"],
        "tests": ["tests/test_evals.py"],
        "constraints": ["preserve existing training loop behavior"]
      },
      "limit": 8
    }
  }
}
```

Agent-submitted YouTube link example:

```json
{
  "jsonrpc": "2.0",
  "id": 10,
  "method": "tools/call",
  "params": {
    "name": "queue_youtube_ingestion",
    "arguments": {
      "url": "https://www.youtube.com/watch?v=uCKhOmth2ms",
      "created_by_client": "hermes"
    }
  }
}
```

This tool requires an MCP token that includes `ingest:write`. It creates a durable ingestion job, returns the job row, and the hosted FastAPI runtime schedules that job for background processing. It does not let an agent rewrite transcripts, source labels, source concepts, or generated artifacts.

The response includes `costEstimate`, a conservative preflight object with discovered videos,
already-indexed videos, videos still needing embedding, estimated transcript seconds,
embedding chars/tokens, selected `digestDepth`, digest LLM calls, and `riskLevel`. Agents should
inspect that object before asking the user to approve more bulk submissions.

For cost safety, playlist and channel URLs require `allow_bulk: true`:

```json
{
  "jsonrpc": "2.0",
  "id": 11,
  "method": "tools/call",
  "params": {
    "name": "queue_youtube_ingestion",
    "arguments": {
      "url": "https://www.youtube.com/playlist?list=PLAYLIST_ID",
      "allow_bulk": true,
      "digest_depth": "basic",
      "created_by_client": "hermes"
    }
  }
}
```

Agents should ask for explicit user approval before setting `allow_bulk` because playlist and channel ingestion can consume more model tokens, database storage, transcript quota, and worker time. For playlist/channel URLs that have not been discovered yet, the estimate is bounded by the hosted import cap and marked with `discoveredVideosEstimated: true`. The default analysis contract should remain `digest_depth: "standard"` for every indexed video; the report length scales to video duration and transcript substance. Use `basic` or `none` only when the user explicitly chooses a lighter/cost-saving import, and use `deep` when the user wants a larger transcript window/output budget for long or dense material.

Job status example:

```json
{
  "jsonrpc": "2.0",
  "id": 12,
  "method": "tools/call",
  "params": {
    "name": "get_ingestion_job",
    "arguments": {
      "job_id": "JOB_ID"
    }
  }
}
```

## Hermes Notes

The local Hermes install supports native MCP through the `mcp_servers` config key. Example local desktop paths are:

- `C:\Users\<you>\AppData\Local\hermes\config.yaml`
- `C:\Users\<you>\AppData\Local\hermes\skills\memexai-context\SKILL.md`

When using a remote Hermes launcher, the PC runs the GUI while another machine runs the backend through the tunnel. In that mode, configure the backend agent process too:

- `/home/<you>/.hermes/config.yaml`
- `/home/<you>/.hermes/skills/memexai-context/SKILL.md`

Repo-managed setup artifacts:

- [HERMES_SETUP.md](HERMES_SETUP.md)
- [../integrations/hermes/memexai-context/SKILL.md](../integrations/hermes/memexai-context/SKILL.md)
- [../integrations/hermes/mcp_servers.memexai.example.yaml](../integrations/hermes/mcp_servers.memexai.example.yaml)

Once the user creates an MCP token from the hosted app, the lowest-friction setup should be:

```yaml
mcp_servers:
  memexai:
    url: 'https://api.memexai.xyz/mcp'
    headers:
      Authorization: 'Bearer ${MEMEXAI_MCP_TOKEN}'
    timeout: 180
    connect_timeout: 30
```

Hermes prefixes discovered MCP tool names with the server name, so the tools should appear as names like:

- `mcp_memexai_get_mcp_session`
- `mcp_memexai_export_brain_digest`
- `mcp_memexai_list_video_library`
- `mcp_memexai_search_video_concepts`
- `mcp_memexai_search_video_moments`
- `mcp_memexai_build_agent_brief`

A Hermes skill makes sense as a routing/instruction layer, not as the data layer. The MCP server remains the source of truth.

The skill/plugin layer should describe agent behavior, for example:

- use `resources/list` and `context://library` when browsing available saved context as MCP resources
- call `get_mcp_session` first to confirm scopes, guardrails, and the recommended next MCP call
- call `export_brain_digest` or read `context://brain-digest` when syncing compact saved-video knowledge into an external personal brain
- use `context://capture-sources` or `list_capture_sources` to understand how new YouTube videos are expected to arrive over time
- inspect `recentItems` on capture sources to see whether saved videos are discovered, queued, skipped, failed, or linked to a durable ingestion job
- use `context://workflows`, `context://workflow/{workflowInstanceId}`, `list_workflow_runs`, or `get_workflow_run` when an action returns a durable workflow handle
- use `context://categories` or `list_context_categories` before broad retrieval when the agent does not know the user's library shape
- use `prompts/list` and `prompts/get` when the agent needs a ready workflow for repo-context collection, study guides, implementation briefs, categorization, or context capture
- call `list_video_library` first when the agent needs to discover what saved channels or videos are available
- call `queue_youtube_ingestion` only when the MCP token has `ingest:write` and the user provided or approved the YouTube URL in the current session
- set `allow_bulk: true` only after explicit approval for playlist or channel ingestion
- call `get_workflow_run`, `list_workflow_runs`, `get_ingestion_job`, or `list_ingestion_jobs` to follow up on queued ingestion status before assuming a new video is searchable
- call `build_context_bundle` before writing a product spec, implementation plan, or agent prompt that should use the user's saved video knowledge
- call `build_agent_brief` when the agent needs an actionable spec/prompt brief rather than raw context
- call `search_video_concepts` first with `retrieval_mode: "hybrid"` for source knowledge, then `get_video_knowledge_map` for candidate videos, then `search_video_moments` with `retrieval_mode: "hybrid"` when the agent needs timestamped evidence. For known-video questions, pass `youtube_video_id`/`video_id` to transcript and moment search. Use `search_transcript_text` or keyword retrieval for exact terms, and call `get_transcript_window` before `get_video_context/include_transcript`.
- pass repo details from the agent's own repo/filesystem/GitHub MCP as `repo_context`
- read `repoFit.targetMap` from agent briefs when mapping saved-video ideas onto files, symbols, commands, tests, and runtime constraints
- cite `source_refs` when turning a video idea into a spec or plan
- write durable takeaways only through `add_context_note` or `upsert_personal_concept`

The skill tells Hermes/Ponyo to use the `memexai` MCP server for saved-video knowledge, start with library discovery when no video is specified, prefer `build_agent_brief` for plans/specs, pass repo context from existing repo tools, and write only personal overlay notes or concepts.
