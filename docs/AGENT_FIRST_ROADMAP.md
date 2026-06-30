# Agent-First Roadmap

Status: planning notes from parallel research, ready to turn into implementation slices.

See [AGENT_FIRST_DECISIONS.md](AGENT_FIRST_DECISIONS.md) for the current decision record on
YouTube capture, access gating, retrieval organization, hosted storage, agent onboarding, and cost
guardrails.

See [RETRIEVAL_AND_INGESTION_HARDENING_PLAN.md](RETRIEVAL_AND_INGESTION_HARDENING_PLAN.md)
for the current hard-concerns plan covering hybrid search, gbrain-style video digestion, MCP
search surfaces, ingestion quotas, and token budgets.

See [BYO_AGENT_RUNTIME_AND_STORAGE.md](BYO_AGENT_RUNTIME_AND_STORAGE.md) for the future direction
on user-owned Codex/Hermes runtimes, BYOK model spend, local Postgres/pgvector sidecars, and
user-owned Supabase/Postgres storage.

Important product boundary: AI/ML videos are a strong early use case, but Memexai should be
universally useful for saved YouTube knowledge across topics such as cooking, repairs, history,
music, fitness, education, business, science, product, and research.

## Decisions

- Keep Supabase/Postgres with pgvector as the hosted default.
- Do not expose database selection to normal hosted users yet.
- Let agents bring repository context through their own repo/filesystem/GitHub MCP.
- Add DB/vector provider seams internally before offering enterprise or self-hosted storage choices.
- Use a dedicated YouTube playlist as the lowest-friction saved-video capture path.
- Treat Watch Later and watch history as unavailable for API-based capture.
- Keep source video context read-only; agents may write only personal overlays unless granted explicit ingest/capture scopes.
- Let agents queue YouTube URLs from chat sessions through a separate `ingest:write` MCP scope.
- Require explicit bulk approval for playlist/channel submissions over MCP.

## YouTube Capture

Recommended flow:

1. User connects YouTube capture once.
2. App requests incremental YouTube OAuth with read-only access.
3. User selects or creates an "Memexai Inbox" playlist.
4. User stays on YouTube and saves videos into that playlist.
5. Memexai polls the playlist, de-duplicates video IDs, and creates ingestion jobs.

Fallbacks:

- Public playlist URL: no OAuth, but weaker privacy.
- Liked videos: possible but too noisy to use as the default intent signal.
- Browser extension: useful later for one-click capture and current timestamp capture.
- PWA share target: useful later for mobile, but not automatic.
- Channel push notifications: useful for trusted-channel monitoring, not personal saved-video intent.

Official references:

- YouTube Data API overview: https://developers.google.com/youtube/v3/docs
- OAuth server-side and offline access: https://developers.google.com/youtube/v3/guides/auth/server-side-web-apps
- `playlists.list` with `mine=true`: https://developers.google.com/youtube/v3/docs/playlists/list
- `playlistItems.list`: https://developers.google.com/youtube/v3/docs/playlistItems/list
- `videos.list` with `myRating=like`: https://developers.google.com/youtube/v3/docs/videos/list
- Quota costs: https://developers.google.com/youtube/v3/determine_quota_cost
- YouTube push notifications: https://developers.google.com/youtube/v3/guides/push_notifications

Schema candidates:

- `youtube_connections`: encrypted refresh token, scopes, channel/account metadata, sync status.
- `capture_sources`: playlist URL/ID, source type, enabled flag, last sync.
- `capture_items`: discovered video IDs, playlist item IDs, added time, ingestion status, skip reason.

First slice implemented:

- `youtube_capture_sources` and `youtube_capture_items` migrations.
- Authenticated REST API to create/list user playlist capture sources.
- Manual playlist sync endpoint that scans a capture playlist, dedupes video IDs into `youtube_capture_items`, and queues only a bounded number of single-video ingestion jobs.
- Read-only MCP `context://capture-sources` and `list_capture_sources` so agents can see standing YouTube inputs.
- Read-only MCP capture-source status includes recent discovered/queued items so agents can understand progress without mutating source context.
- Private playlist OAuth, scheduled polling, and agent-triggered capture sync remain future work.

## Categorization

Use layered categories instead of a flat tag list.

Recommended labels:

- `domain`: cooking, repairs, history, music, fitness, education, business, science, AI/ML, product.
- `content_type`: podcast, lecture, tutorial, demo, documentary, review, interview, walkthrough.
- `task_fit`: study guide, lesson plan, troubleshooting, buying decision, writing outline, project plan, implementation plan.
- `entities`: people, places, companies, products, tools, materials, papers, models, locations, named systems.
- `method`: procedures, techniques, practice routines, diagnostic workflows, frameworks, algorithms.
- `tool`: software, physical tools, materials, models, frameworks, platforms.
- `difficulty`: introductory, intermediate, advanced, expert.
- `maturity`: introductory overview, field-tested, case study, research, speculative, cautionary.
- `evidence_quality`: direct explanation, demo-backed, anecdotal, expert opinion, implementation detail.

Pipeline changes:

- Add a `source-knowledge-v2` extraction shape with video-level labels, chunk labels, entities, confidence, and evidence refs.
- Keep source labels read-only and let agents add personalized labels through overlay notes/concepts.
- Add category discovery over MCP so agents can browse available labels before searching.

First slice implemented:

- `source_labels` migration for read-only, ingestion-generated video labels.
- ingestion writes normalized `source_labels` from `source-knowledge-v2` extraction.
- `context://categories` and `list_context_categories` expose source facets and personal concepts to agents.

Retrieval strategy:

1. Candidate generation from semantic vector search, full-text search, metadata filters, and graph neighbors.
2. Merge candidates with reciprocal rank fusion.
3. Rerank the top candidates later with a lightweight LLM or reranker.
4. Preserve timestamp citations through every stage.

Reference:

- Supabase hybrid search: https://supabase.com/docs/guides/ai/hybrid-search

Current hard concern:

- The local 30-video legacy corpus proved that vector-only search can return confidently wrong
  results for entity-heavy AI/robotics queries even when lexical matches exist. That corpus has now
  been migrated into hosted Supabase for the eval user, and hosted MCP keyword search can query it.
  Hybrid/semantic live smoke still depends on available embedding quota or BYOK.
- The roadmap must not tune only for AI/developer videos. Retrieval evals and labels need
  non-AI domains such as cooking, repair, history, music, health/fitness, and buying research.

Next retrieval implementation slices:

1. Migrate or reingest the 30-video local corpus into Supabase so MCP can test against real data. Done.
2. Add full-text indexes and a `search_chunks_hybrid` RPC with reciprocal-rank fusion. Done.
3. Add `retrieval_mode=hybrid|semantic|keyword` to `search_video_moments`; use `search_video_concepts` for concept/artifact retrieval. Done.
4. Add a `search_video_concepts` MCP tool over source concepts, labels, and knowledge artifacts. Done.
5. Add response budget fields such as `detail_level`, `max_chars`, and estimated response size. Done.
6. Add retrieval eval fixtures and compare keyword/hybrid/concept search against expected video IDs and timestamps. Done for the offline lexical baseline.
7. Add universal-topic eval coverage so study guides and timestamp search work outside AI/ML. Done as a synthetic starter fixture.

## Storage And Agent Access

Hosted default:

- Supabase auth, RLS, Postgres, pgvector, migrations, usage logs, MCP token records, and overlay data remain together.

Not now:

- User-selectable DB in the normal hosted product.
- BYO vector database during onboarding.

Later:

- Data export.
- Enterprise/BYO storage.
- Optional vector sidecar for scale, such as Qdrant, Pinecone, Weaviate, Cloudflare Vectorize, or Turso/libSQL.
- Local Postgres/pgvector sidecar for users who want Codex/Hermes to run against their own machine.
- User-owned Supabase/Postgres only after migrations, security checks, and support boundaries are clear.

Agent-first access:

- Add agent-readable docs: `/llms.txt`, `/llms-full.txt`, `/mcp.json`, and MCP quickstart.
- Consider `POST /api/agent/signup` with human email, agent name, OTP verification, workspace creation, and MCP token provisioning.
- Keep default MCP scopes to `context:read` and `overlay:write`.
- Support `ingest:write` as an explicit opt-in scope for agents that may submit YouTube links into the hosted ingestion queue.
- Add explicit future scopes for `capture:write` and `youtube:sync`.
- Expose MCP job-status tools so agents can check ingestion progress without sending the user back to the dashboard.

BYO agent runtime:

- Do not design hosted Memexai around storing raw Codex ChatGPT subscription tokens.
- Let users use Codex by configuring the Codex CLI/app/cloud environment with Memexai MCP.
- For hosted Memexai model calls, prefer BYOK API keys rather than "spend my ChatGPT/Codex subscription from your server."
- Add a future Codex setup bundle like the Hermes bundle: MCP config snippet, first calls, and clear auth boundaries.
- Local sidecar mode should let Codex/Hermes use a local Postgres/pgvector brain without requiring the hosted DB.

External brain sync:

- Treat Memexai as the canonical saved-video source system for users who already have a
  personal agent brain, gbrain-style memory, or team knowledge graph.
- Expose `context://brain-sync-contract` and `get_brain_sync_contract` so those systems can discover
  compact pull surfaces, provenance requirements, and overlay-only write rules.
- Keep synced payloads compact by default: video IDs, timestamps, category maps, concepts, artifacts,
  and access provenance before raw transcripts.
- Add incremental digest export with cursors, `since`, object filters, and response budgets. Done.
- Add optional outbound sync outbox events for connected personal brains after ingestion, knowledge
  publishing, overlay note creation, and capture-source sync. Done.
- Add delivery workers/webhook dispatch for queued external-brain sync events. Pending.

First slice implemented:

- Public `/llms.txt` and `/llms-full.txt` agent guides.
- Public `/mcp.json` and `/.well-known/mcp.json` MCP discovery manifests.
- Manifest guidance tells agents to use their own repo/filesystem/GitHub MCP first, then pass compact `repo_context` into Memexai.
- `get_mcp_session` lets agents confirm effective scopes, guardrails, and safe next calls immediately after connecting.
- `repo_context.symbols` lets repo-aware agents pass precise functions, classes, components, workflows, tools, or tests without storing source code.
- `repo_context.locations` lets agents pass compact path/symbol/line anchors from repo MCP tools without sending file contents.
- `build_agent_brief` returns `repoFit.targetMap` so agents can consume repo targets by category instead of re-parsing a flat touchpoint list.
- Source-context RLS now honors precise `user_videos` grants as well as channel grants, and the linked Supabase project has migrations 001-013 applied.
- Hermes routing skill and MCP config snippet live under `integrations/hermes/`, with the skill install path documented in [HERMES_SETUP.md](HERMES_SETUP.md).

References:

- Supabase RAG with permissions: https://supabase.com/docs/guides/ai/rag-with-permissions
- Supabase pgvector: https://supabase.com/docs/guides/database/extensions/pgvector
- AgentMail agent onboarding: https://www.agentmail.to/docs/agent-onboarding

## Dependency Cleanup

Completed safe cleanup:

- Removed `sse-starlette`; the server uses FastAPI `StreamingResponse`.
- Removed the local Chroma runtime path from the hosted fork: `backend/ingest_chroma.py`,
  `backend/rag_chroma.py`, and `requirements-local.txt`.
- `SEARCHTUBE_STORAGE=local` now fails fast; the only supported storage mode is Supabase
  Postgres/pgvector.

Do not remove yet:

- `langchain-google-genai`: hosted embeddings, answers, and knowledge extraction still import it.

Recommended order:

1. Keep hosted deployments on `requirements.txt` only.
2. Split Python runtime dependencies from dev dependencies.
3. Later, consider replacing LangChain wrappers with native Google GenAI SDK as a migration.

## Sample Fixture

Use this Sierra product/eval-harness podcast as the first concrete evaluation fixture:

- https://www.youtube.com/watch?v=uCKhOmth2ms
- Fixture: [eval/fixtures/sierra_harness_podcast.json](../eval/fixtures/sierra_harness_podcast.json)
- Runbook: [SIERRA_SAMPLE_EVAL.md](SIERRA_SAMPLE_EVAL.md)

Expected eval coverage:

- study guide quality
- categorization labels
- exact timestamp search
- repo-aware implementation brief
- agent overlay notes/personal concepts
