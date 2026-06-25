# Sierra Sample Eval

Sample video:

- https://www.youtube.com/watch?v=uCKhOmth2ms
- Fixture: [eval/fixtures/sierra_harness_podcast.json](../eval/fixtures/sierra_harness_podcast.json)

Purpose:

Use this podcast as the first repeatable sample for the full Memexai loop:

1. ingest or reuse a canonical YouTube video
2. grant the current user access through `user_videos`
3. extract source labels, concepts, edges, TLDR, and study guide artifacts
4. discover categories through MCP
5. retrieve exact timestamped moments with `category_filters`
6. build a repo-aware agent brief with caller-supplied `repo_context`
7. persist only personal overlay notes/concepts

The fixture intentionally does not store transcript text in the repo. Live transcript, embedding,
and source-knowledge generation should happen through the normal ingestion pipeline.

## Offline Contract Eval

Run the deterministic offline eval without Supabase, Gemini, or transcript download:

```bash
python scripts/run_sierra_sample_eval.py --pretty
```

This seeds an in-memory Supabase-shaped store from the fixture and exercises the same helper
contracts used by MCP:

- user access through `user_videos`, not duplicated video rows
- `list_context_categories`
- `get_video_context`
- `build_context_bundle` with `category_filters`
- `build_agent_brief` with caller-supplied `repo_context`
- overlay note/concept writes that leave source video context unchanged

Use this as the cheap regression check before running the live ingestion path below.

## Run Path

Use an MCP token with:

- `context:read`
- `overlay:write`
- `ingest:write` only if the agent will queue the video

Queue the video:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "queue_youtube_ingestion",
    "arguments": {
      "url": "https://www.youtube.com/watch?v=uCKhOmth2ms",
      "created_by_client": "sierra-sample-fixture"
    }
  }
}
```

Poll the ingestion job until it completes:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "get_ingestion_job",
    "arguments": {
      "job_id": "JOB_ID"
    }
  }
}
```

Discover categories:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "list_context_categories",
    "arguments": {
      "limit": 100
    }
  }
}
```

Run filtered timestamp search:

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "search_video_moments",
    "arguments": {
      "query": "how should we build an eval harness for production AI agents?",
      "retrieval_mode": "hybrid",
      "category_filters": {
        "task_fit": ["implementation plan", "eval harness"],
        "maturity": ["production pattern", "case study"]
      },
      "limit": 5
    }
  }
}
```

Build a repo-aware brief:

```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "tools/call",
  "params": {
    "name": "build_agent_brief",
    "arguments": {
      "query": "apply Sierra-style agent harness lessons to Memexai workflow orchestration",
      "repo_context": {
        "source": "agent-mcp",
        "repo": "GhostPeony/memexai",
        "files": ["backend/mcp_adapter.py", "backend/context.py", "backend/workflows.py"],
        "locations": [
          "backend/context.py:734 build_agent_brief",
          "backend/mcp_adapter.py:1938 search_video_moments"
        ],
        "entrypoints": ["POST /mcp", "POST /api/context/bundle"],
        "symbols": ["build_agent_brief", "run_capture_sync_workflow", "search_video_moments"],
        "features": ["workflow orchestration", "MCP context server", "agent brief generation"],
        "dependencies": ["Supabase Postgres with pgvector", "FastAPI", "Cloudflare Workflows"],
        "commands": ["python -m pytest tests/test_mcp_adapter.py tests/test_context_overlay.py -q"],
        "tests": ["tests/test_mcp_adapter.py", "tests/test_context_overlay.py"],
        "constraints": ["source video context is read-only", "search is user-scoped"]
      },
      "category_filters": {
        "task_fit": ["implementation plan"],
        "topic": ["agent architecture", "workflow design"]
      },
      "limit": 8
    }
  }
}
```

## Pass Criteria

- Ingestion returns either newly indexed chunks or a reused canonical video access grant.
- `list_context_categories` includes labels for Sierra, agent architecture, production pattern, and either eval harness or implementation plan.
- `search_video_moments` returns timestamped clips from `uCKhOmth2ms` with access provenance (`accessScope`, `accessSource`, `accessReason`).
- `build_agent_brief` returns source refs, repo fit, implementation guidance, and at least one workflow or eval recommendation.
- Overlay tools can save personal takeaways without mutating source transcripts, labels, concepts, chunks, or generated artifacts.

## Failure Modes To Watch

- No transcript or captions available: ingestion should fail gracefully and record the reason.
- Weak labels: category discovery does not expose useful `task_fit`, `topic`, `method`, or `maturity` facets.
- Search misses: broad semantic search works but filtered search returns nothing because labels are too narrow.
- Brief lacks citations: agent brief should not turn the podcast into a spec without source refs.
- Duplicate compute: a second user ingesting the same video should get access to the existing canonical video instead of re-embedding it.
