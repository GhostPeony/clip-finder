---
name: memexai-context
description: Use Memexai MCP as a saved-video knowledge base for timestamped evidence, study guides, repo-aware implementation briefs, and personal overlay notes.
version: 0.1.0
author: Ghost Peony
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [memexai, mcp, youtube, knowledge-base, repo-context, agent-briefs]
---

# Memexai Context

Use this skill when the user wants to learn from saved YouTube videos, find exact timestamped moments, turn video concepts into a product spec or agent prompt, or apply saved-video ideas to a codebase.

Memexai is the context source. Your own repo, filesystem, GitHub, or code-index tools are the repo source. Prefer combining them at request time through `repo_context` instead of asking the user to connect GitHub inside Memexai.

## Setup

Memexai should be configured as a Hermes MCP server named `memexai`.

```yaml
mcp_servers:
  memexai:
    url: 'https://api.memexai.xyz/mcp'
    headers:
      Authorization: 'Bearer ${MEMEXAI_MCP_TOKEN}'
    timeout: 180
    connect_timeout: 30
```

Use the production API URL when available. For local development, use the local FastAPI `/mcp` endpoint instead.
The Memexai Settings modal can copy a complete setup bundle after token creation. If the user
provides that JSON, use its `mcpEndpoint`, `firstCalls`, and `accessModel` fields instead of
guessing the next MCP calls.

Required token scopes:

- `context:read`: browse saved videos, categories, workflows, source context, searches, and briefs.
- `overlay:write`: write personal notes and user-specific concepts only.
- `ingest:write`: optional; queue user-provided or user-approved YouTube links.

## Core Rules

- Treat source video context as read-only.
- Treat search as current-user granted context, not a global corpus search.
- Treat `accessModel.searchScope = current_user_grants` from the setup bundle or manifest as a hard boundary.
- Inspect `accessScope`, `accessSource`, and `accessReason` on returned clips, library videos, and video context when explaining why a shared canonical video is available.
- Do not rewrite transcripts, chunks, source labels, source concepts, source edges, videos, or generated knowledge artifacts.
- Use `add_context_note` or `upsert_personal_concept` for durable personalized takeaways.
- Use `queue_youtube_ingestion` only when the user provided or approved the URL in the current session.
- Set `allow_bulk: true` for playlist or channel ingestion only after explicit user approval.
- If a tool returns an ingestion job or workflow handle, poll status before assuming new video context is searchable.
- Cite `source_refs` or timestamped clips when turning video knowledge into specs, plans, or prompts.

## Standard Flow

1. Discover available context:
   - Call `get_mcp_session` first to confirm token scopes, guardrails, and the recommended next MCP call.
   - Read `context://agent-quickstart` or call `get_agent_quickstart` when orienting a new session.
   - Read `context://library` or call `list_video_library`.
   - Read `context://categories` or call `list_context_categories` when the topic is broad.
   - Read `context://capture-sources` or call `list_capture_sources` to understand standing YouTube inputs.

2. Retrieve evidence:
   - Use `search_video_concepts` first for compact source concepts, TLDRs, study guides, methods, tools, entities, and pitfalls without embedding or LLM spend.
   - Use `search_transcript_text` for exact names, acronyms, product terms, and phrases without embedding or LLM spend.
   - Use `search_video_moments` with `retrieval_mode: "hybrid"` for timestamped clips after the cheaper searches identify the right topic or claim. Use `retrieval_mode: "semantic"` or `"keyword"` for narrower follow-up.
   - Treat returned `accessScope`, `accessSource`, and `accessReason` as the provenance for why a clip, library video, or full video context is visible to this account.
   - Use `category_filters` when the library is broad.
   - Use `get_video_context` when a known video needs source concepts or artifacts. Transcript lines/chunks are omitted by default; pass `include_transcript: true` with a larger `detail_level` only for deeper source inspection.

3. Build an actionable answer:
   - Use `build_agent_brief` for product specs, implementation plans, repo-aware briefs, and agent prompts.
   - Use `build_context_bundle` when you need raw source context plus personal overlay context.
   - Use `prompts/get` for the `collect_repo_context`, `study_guide_from_saved_video`, `repo_implementation_brief`, `categorize_saved_video`, or `capture_personal_context` prompt scaffolds.
   - Use `get_repo_context_workflow` or `context://repo-context-workflow` when you need the readiness gate and exact output shape for repo-context collection.
   - Use `collect_repo_context` when you need to prepare and validate repo_context before asking for video-derived implementation guidance.
   - For `repo_implementation_brief`, follow the prompt's `validate_repo_context` and readiness loop before drafting implementation steps.

4. Persist only the user's overlay:
   - Use `add_context_note` for durable takeaways.
   - Use `upsert_personal_concept` for personalized concepts like "Sierra-style harness loop".

## Repo Context

When working in a codebase, inspect the repo using your existing tools first. Then pass a compact `repo_context` object to Memexai.
If you are not sure which MCP call should come next, call `get_mcp_session`, read `context://agent-quickstart`, or call `get_agent_quickstart`.
If you need the current schema, read `context://repo-context-contract` or call `get_repo_context_contract`.
If you need the collection flow, read `context://repo-context-workflow` or call `get_repo_context_workflow`.

Recommended shape:

```json
{
  "source": "agent-mcp",
  "repo": "owner/name or local project name",
  "branch": "optional branch or ref",
  "files": ["backend/context.py", "backend/workflows.py"],
  "locations": ["backend/context.py:734 build_agent_brief"],
  "entrypoints": ["POST /api/context/bundle", "workers/orchestrator/src/index.ts"],
  "modules": ["MCP adapter", "workflow orchestration"],
  "symbols": ["build_agent_brief", "run_capture_sync_workflow"],
  "features": ["agent brief generation", "source knowledge extraction"],
  "dependencies": ["Supabase", "Cloudflare Workflows", "Gemini embeddings"],
  "commands": ["python -m pytest tests/test_mcp_adapter.py -q", "npm test -- --run"],
  "tests": ["tests/test_mcp_adapter.py", "tests/test_context_overlay.py"],
  "deployment": ["FastAPI backend", "Cloudflare queue consumer", "Supabase Postgres"],
  "active_changes": ["preserve user edits in the current worktree"],
  "constraints": ["source context is read-only", "search is user-scoped"],
  "open_questions": ["Which eval should gate this workflow?"]
}
```

Call `validate_repo_context` when you are unsure whether your payload is well-formed. For implementation plans, prefer `readiness.level = "implementation_ready"`; if validation returns `partial`, follow `readiness.suggestedAgentNextSteps` with your existing repo tools and validate again. Use `next_mcp_call` as the machine-readable next step. `build_agent_brief` repeats readiness in `repoContextValidation`, places repo-inspection steps first in `suggestedNextActions` when the repo context is thin, and returns `repoFit.targetMap` for grouped files, symbols, locations, commands, tests, runtime targets, constraints, and open questions.

## Category Filters

Use filters after discovering labels with `list_context_categories`.

Semantics:

- labels within one facet are OR
- different facets are AND
- matching is case-insensitive exact label matching after normalization

Example:

```json
{
  "task_fit": ["implementation plan", "eval harness"],
  "topic": ["agent architecture"],
  "maturity": ["production pattern", "case study"]
}
```

Good facets for agent work:

- `task_fit`
- `topic`
- `method`
- `tool`
- `entity`
- `difficulty`
- `maturity`
- `evidence_quality`

## Tool Name Hints

Hermes usually prefixes MCP tools with the server name. Expect names like:

- `mcp_memexai_list_video_library`
- `mcp_memexai_list_context_categories`
- `mcp_memexai_search_video_concepts`
- `mcp_memexai_search_transcript_text`
- `mcp_memexai_search_video_moments`
- `mcp_memexai_build_context_bundle`
- `mcp_memexai_build_agent_brief`
- `mcp_memexai_queue_youtube_ingestion`
- `mcp_memexai_get_ingestion_job`

If a prefixed tool is unavailable, inspect the MCP server's tool list before continuing.

## Sierra Sample

For a high-signal test of the whole workflow, use the Sierra podcast fixture:

- video URL: `https://www.youtube.com/watch?v=uCKhOmth2ms`
- query: `apply Sierra-style agent harness lessons to Memexai workflow orchestration`
- repo features: `workflow orchestration`, `MCP context server`, `agent brief generation`

Expected behavior:

- Ingestion either indexes the video or reuses the canonical video and grants user access.
- Categories include Sierra, agent architecture, production pattern, and implementation-plan or eval-harness labels.
- Concept search returns compact source concepts/artifacts before timestamp search returns evidence.
- `build_agent_brief` returns repo fit, `repoFit.targetMap`, source refs, and actionable workflow/eval guidance.
