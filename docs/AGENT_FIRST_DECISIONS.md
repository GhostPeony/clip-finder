# Agent-First Product Decisions

Last verified: 2026-06-22

This document captures the current product decisions for turning saved YouTube videos into an agent-readable knowledge base. It is intentionally implementation-facing: if the product changes, migrations, MCP tools, workflows, and docs should change with it.

## 1. YouTube Capture Decision

Default marker: a dedicated user-selected YouTube playlist.

Why:

- It keeps the user inside YouTube. The user can save a useful video with normal YouTube behavior instead of copying links into a chat.
- It is explicit enough to mean "ingest this for my knowledge base," unlike likes, subscriptions, or watch history.
- It maps cleanly onto the current `youtube_capture_sources` and `youtube_capture_items` schema.
- It can start with public playlist URLs and later upgrade to private playlists through YouTube OAuth.

Rejected as default:

- Watch Later and watch history: not reliable API capture targets. YouTube's docs note that Watch Later listing is unsupported, and revision history says watch history and Watch Later are not accessible through the API.
- Liked videos: technically possible with authenticated `videos.list?myRating=like`, but it is a noisy intent signal. People like videos for many reasons that do not mean "turn this into durable agent context."
- Subscriptions: useful for trusted-channel monitoring later, but too broad for personal saved-video intent.
- Browser extension or PWA share target: good future capture affordances, but not the first durable sync primitive.

Recurring sync design:

- Public beta: user adds a playlist URL, then clicks "sync" manually. The backend scans playlist items, dedupes by YouTube video ID, records capture items, and queues bounded single-video ingestion jobs.
- Private playlist upgrade: request incremental YouTube OAuth only when the user enables private playlist capture. Use a read-only YouTube scope, store encrypted refresh tokens, and call `playlists.list` with `mine=true` so the user can select an inbox playlist.
- Polling cadence: default every 30-60 minutes per active source, with jitter. Poll slower for idle sources and pause after repeated API or auth failures.
- Dedupe: use `youtube_capture_items` for source-level discovery dedupe and `user_videos` for final access grants to canonical indexed videos.
- Job creation: capture sync creates durable workflow state, then dispatches video-level ingestion jobs. Agents poll workflow/job handles instead of waiting on ingestion.

References:

- YouTube `playlists.list` supports authenticated `mine=true` and costs 1 quota unit: https://developers.google.com/youtube/v3/docs/playlists/list
- YouTube `playlistItems.list` returns playlist videos and costs 1 quota unit: https://developers.google.com/youtube/v3/docs/playlistItems/list
- YouTube quota costs: https://developers.google.com/youtube/v3/determine_quota_cost
- YouTube revision history on Watch Later/watch history API access: https://developers.google.com/youtube/v3/revision_history

## 2. Access And Reuse Decision

Source video context is canonical and shared; visibility is user-scoped.

Implementation rule:

- Store a YouTube video, transcript chunks, transcript lines, source labels, source concepts, edges, and generated artifacts once.
- Grant user visibility through `user_videos` for precise video-level access and `user_channels` for channel-level access.
- Search, bundle, and MCP context tools must always apply user access grants before returning chunks, concepts, artifacts, or labels.
- Source-context RLS policies must allow either access path, so direct reads of transcript-derived context, labels, concepts, edges, and artifacts remain consistent with MCP search and bundle behavior.
- Search results, library videos, and full video context should include `accessScope`, `accessSource`, and `accessReason` so agents know whether a hit came from a channel grant, explicit video grant, or both.
- If a second user ingests an already-indexed video, grant access and skip transcript/embedding recompute.
- Treat search corpus selection as an explicit scope decision, not as a side effect of canonical storage. The default scope is the user's granted library. Future team, organization, or public-discoverable search must use explicit grants/membership and return provenance fields rather than querying every canonical video row.
- An already-indexed video becomes searchable for another user only after capture, ingestion, or an approved agent action creates a `user_videos` grant, typically with `access_source = shared_existing`.

This keeps compute and storage efficient without muddying a user's library with unrelated videos someone else ingested.

## 3. Categorization And Retrieval Decision

Use layered facets plus semantic retrieval, not a flat tag pile.

Current facets:

- `domain`
- `content_type`
- `task_fit`
- `entity`
- `tool`
- `method`
- `difficulty`
- `maturity`
- `evidence_quality`

Current retrieval path:

- semantic pgvector search over transcript chunks
- user-scoped visibility gating through `user_videos` and `user_channels`
- `category_filters` over `source_labels`
- MCP category discovery through `context://categories` and `list_context_categories`
- repo-aware synthesis through caller-supplied `repo_context`

Recommended next retrieval upgrades, in order:

1. Hybrid search: combine pgvector semantic search with Postgres full-text search for exact names, API identifiers, acronyms, and paper/model names.
2. Reciprocal-rank fusion: merge semantic, keyword, category, and graph candidates without over-trusting one retriever.
3. Reranking: rerank the top 20-50 candidates with a lightweight model only when a brief/spec needs higher precision.
4. Graph expansion: after initial retrieval, pull nearby source concepts, entities, methods, tools, and evidence refs.
5. Topic clusters: use clustering for browsing and library organization, not as the primary access-control or citation mechanism.

References:

- Supabase hybrid search combines `tsvector` keyword search and pgvector semantic search: https://supabase.com/docs/guides/ai/hybrid-search
- Supabase RAG permissions show why access filtering should live with retrieval, including many-to-many document ownership patterns: https://supabase.com/docs/guides/ai/rag-with-permissions

## 4. Storage Decision

Hosted default: Supabase Postgres with pgvector.

Do not ask normal hosted users to choose a database.

Why:

- Users and agents want context, not database setup.
- Supabase keeps auth, RLS-style permission joins, vector search, relational source knowledge, personal overlays, usage quotas, workflow state, and MCP token metadata together.
- The current access model needs relational joins between canonical source rows and user visibility grants.
- MCP is the right user-facing abstraction for agents. Agents should connect to Memexai as a context service, not choose where its vectors live.

What to offer later:

- data export
- enterprise BYO storage
- optional dedicated vector sidecar if pgvector becomes a measured bottleneck

Cloudflare Vectorize note:

- Vectorize is a credible later sidecar for vector search, especially near Cloudflare Workers, but today it would split vectors away from the relational access model. Its metadata filtering is useful, but it has metadata-index limits and does not replace Postgres joins, source knowledge graphs, usage tables, or workflow records.

References:

- Supabase pgvector and AI docs: https://supabase.com/docs/guides/ai
- Supabase RAG permissions: https://supabase.com/docs/guides/ai/rag-with-permissions
- Cloudflare Vectorize overview: https://developers.cloudflare.com/vectorize/
- Cloudflare Vectorize metadata filtering: https://developers.cloudflare.com/vectorize/reference/metadata-filtering/

## 5. Agent-First Onboarding Decision

Default onboarding: public discovery docs plus scoped MCP bearer tokens.

Current flow:

1. Agent discovers `/mcp.json`, `/.well-known/mcp.json`, `/llms.txt`, or `/llms-full.txt`.
2. User creates a scoped MCP token in Settings.
3. Agent configures the streamable HTTP MCP endpoint with that bearer token.
4. Agent calls `get_mcp_session` to confirm effective scopes, guardrails, and the recommended next MCP call.
5. Agent starts with `context:read`; uses `overlay:write` for notes/concepts; uses `ingest:write` only when the user explicitly wants agent-submitted URLs.
6. Agent uses its own repo/filesystem/GitHub MCP tools and passes compact `repo_context` into Memexai, including files, symbols, locations, entrypoints, dependencies, commands, tests, active changes, features, and constraints when available.

Why this beats mandatory GitHub connection:

- Many coding agents already have repo context through their own MCP/tooling.
- Requiring a hosted GitHub App before generating a useful brief adds friction and consent complexity.
- Request-supplied repo context is safer: Memexai can use it for the current brief without storing repository source truth.

Future agent-light signup:

- Add an agent-assisted token bootstrap only after the normal Settings token flow is stable.
- Consider a service-account/workspace model for teams.
- Add narrower future scopes like `capture:write` and `youtube:sync` rather than expanding broad write access.

Reference:

- AgentMail's agent onboarding is a useful pattern: publish simple MCP config, make API keys/tokens the setup primitive, and design the product so agents can act without a human driving every UI step: https://www.agentmail.to/docs/agent-onboarding

## 6. Cost And Bulk Submission Decision

Agents may queue YouTube URLs only with `ingest:write`.

Guardrails:

- Single-video URLs are allowed with scoped write access.
- Playlist and channel URLs require explicit `allow_bulk=true`.
- Hosted quotas cap active jobs, monthly searches, indexed/accessed videos, transcript seconds, and result counts.
- Ingestion checks canonical video reuse before expensive transcript/embedding work when possible.
- Capture sync queues bounded batches rather than importing an entire playlist without limits.

Bulk submissions can be cost-effective when they amortize agent setup and let the queue batch work, but the user journey should be explicit: "watchlist playlist sync" for standing intent, and `allow_bulk=true` only after approval for one-off bulk imports.
