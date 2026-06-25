# Retrieval And Ingestion Hardening Plan

Status: hard-concerns plan after hosted migration, retrieval evals, and external-brain outbox slice

## Problem Statement

Memexai should become a better knowledge base for agents and humans learning from YouTube on
any topic, not just a vector search box over transcript chunks. AI/ML research is an important
motivating workflow, but the product must work just as well for cooking, repairs, history, music,
fitness, business, science, product, education, and other saved-video libraries. The current hosted
MCP shape is useful, but the retrieval layer is too narrow: `search_video_moments` is vector-first,
source knowledge is generated once at ingestion, and agents have limited ways to search by keyword,
concept, claim, artifact, or learning map.

Local evidence: the legacy `backend/channel_chroma_db` corpus contains 30 videos and 3,587 chunks,
including "China, Robotics, & Open-Source AI," Sam Altman/OpenAI infrastructure interviews, Zipline,
DeepMind, GPUs/TPUs, Deel, Base Power, and other research/product videos. Vector retrieval returned
unrelated TED procrastination clips for obvious AI/robotics queries in an earlier check, while
direct lexical inspection found the right chunks immediately:

- "China Robotics Open-Source AI" matched `b0iJZS9HgJA` around the open-source AI/China discussion.
- "OpenAI infrastructure compute spend" matched `2P27Ef-LLuQ` around infrastructure and compute.
- "Zipline autonomous delivery engineering scaling" matched `fZNLLYzjB2w` around Zipline scale and
  safety.

The real saved-video library has since been imported into hosted Supabase for the eval user by
reusing local Chroma embeddings, so hosted MCP keyword search can now be tested against real saved
video data without duplicating embedding spend. The Sierra harness podcast remains the repeatable
fixture for source-knowledge, study-guide, and repo-aware brief evaluation. Vector-only retrieval is
still a warning, not a corner case: it will fail users exactly when their phrasing does not match
the embedding space or the index was built under stale settings.

Dry-run import evidence from `python scripts/legacy_chroma_supabase_import.py --limit-videos 5`:

- 30 videos
- 3,587 chunks
- 117,986 transcript seconds, or 32.77 hours
- 1,991,014 transcript characters
- roughly 497,754 embedding tokens
- 57 embedding batches at 64 chunks per batch
- 0 digest LLM calls by default; source-knowledge digestion should run as a separate quota-gated
  workflow after base import

Hosted import evidence:

- 30 canonical videos
- 3,587 chunks
- 3,587 transcript lines
- 30 `user_videos` grants for the eval user
- 24 videos imported and 6 existing videos reused during the apply run
- Chroma vectors were reused from the local collection, avoiding new Gemini embedding calls for the
  migration

## Product Bar

The user should be able to save or sync YouTube videos into a personal knowledge library, then ask
any agent:

- "Find the moments about eval harnesses and product loops."
- "Which clips explain how to fix this appliance error?"
- "Turn this cooking playlist into a weekend practice plan."
- "Compare the advice across these guitar lessons."
- "Pull the key dates and people from these history lectures."
- "Turn these videos into a study guide."
- "Apply the best ideas to this repo or project."
- "What did I save that is relevant to my next talk or article?"

The agent should not need full transcripts by default. It should discover the library, pick a
search mode, retrieve bounded evidence, cite timestamps, and ask for deeper context only when the
user's task justifies the token cost.

## Hard Concerns

1. Vector-only search is not trustworthy enough.
   - Semantic search can miss literal entities, product names, acronyms, and exact phrases.
   - A bad index or embedding mismatch can make every result look plausible but wrong.
   - Agent workflows need fallback search modes, not only better embeddings.

2. Ingestion can get expensive.
   - Long videos multiply transcript chunks, embedding calls, and LLM extraction cost.
   - Playlist/channel imports can explode spend if agents have `ingest:write`.
   - Knowledge extraction should be bounded and resumable, not an unmetered side effect.

3. MCP can burn tokens if tools return too much.
   - Full transcripts and large study guides should be opt-in.
   - Default tools should return compact evidence, digests, labels, and next-call guidance.
   - Agents should see estimated token/char sizes before requesting heavy context.

4. Users need low-friction capture.
   - The product is only useful if users can keep saving to YouTube playlists.
   - Existing saved playlists and new topic inbox playlists should feed the same pipeline.
   - Empty-library onboarding is fatal; an agent connected to no videos is not magical.

5. The product can accidentally overfit to AI/developer workflows.
   - Repo-aware briefs and implementation plans should be advanced workflows, not the whole product.
   - Labels, digests, and tools must handle how-to videos, lectures, interviews, demos, reviews,
     lessons, documentaries, and entertainment analysis.
   - Evaluation needs non-AI queries so retrieval quality is not tuned only for AI/product videos.

## Retrieval Architecture

### Phase 1: Hybrid Candidate Generation

Add `search_video_moments` retrieval modes:

- `hybrid` default: vector + full-text + metadata/category matches. Implemented as the default timestamp-search lane with `search_chunks_hybrid`.
- `semantic`: current pgvector behavior for concept-ish queries. Implemented.
- `keyword`: exact phrase/entity/acronym search over transcript chunks and titles. Implemented.
- `concept`: search source concepts, labels, entities, methods, and generated artifacts. Implemented through `search_video_concepts`.
- `artifact`: search TLDR/study guides/action items before transcript chunks. Implemented through `search_video_concepts` for generated artifacts.

Implementation shape:

1. Add Postgres full-text search support for `chunks.content`, `videos.title`, and likely
   `source_concepts.name/summary`.
2. Add a `search_chunks_hybrid` RPC that returns candidate rows with:
   - `semanticRank`
   - `keywordRank`
   - `metadataRank`
   - `rrfScore`
   - `matchType`
   - current `accessScope`, `accessSource`, `accessReason`
3. Use reciprocal rank fusion rather than picking one ranking source.
4. Keep the current user-grant gate inside every candidate source.
5. Return "why this matched" so agents can distinguish exact phrase hits from semantic guesses.

Acceptance criteria:

- A query for "China Robotics Open-Source AI" returns the matching video above unrelated clips.
- A query for "OpenAI infrastructure compute spend" returns the Sam Altman infrastructure segment.
- No search mode can return videos outside `user_videos` or `user_channels`.

### Phase 2: Reranking And Query Planning

Add a cheap query planner before retrieval:

- Detect entity-heavy queries and prefer `hybrid` or `keyword`.
- Detect broad learning goals and search concepts/artifacts first.
- Detect project or implementation requests and pair video search with repo-context readiness only
  when relevant.

Add optional reranking:

- Start with deterministic scoring: RRF + title/category boosts + recency/source quality.
- Later add bounded LLM rerank for top 20 candidates only, returning top 5 clips.
- Never send full transcripts to rerank.

Acceptance criteria:

- Reranker input is capped by chars/tokens.
- The response includes `retrievalPlan` and `retrievalBudget`.
- Tests cover keyword-only, vector-only, hybrid, and category-filtered behavior.

## Agent Search Surfaces

Keep `search_video_moments`, but add narrower tools so agents do not overuse one giant search call:

- `search_transcript_text`: keyword/entity/phrase search with timestamp clips.
- `search_video_concepts`: concept/claim/method/tool/entity search over source knowledge. Implemented for source concepts and generated artifacts with compact response budgets.
- `search_learning_artifacts`: TLDR/study guide/action-item search.
- `get_knowledge_map`: compact map of videos, concepts, entities, and recommended search paths.
- `estimate_context_cost`: returns approximate chars/tokens for a proposed tool call.

Default MCP guidance should become:

1. `get_mcp_session`
2. `list_video_library`
3. `list_context_categories`
4. `get_knowledge_map` or `search_video_concepts`
5. `search_video_moments` for timestamp evidence
6. `get_video_context` only for deeper follow-up

Acceptance criteria:

- Agents can search concepts without pulling transcript chunks.
- Agents can keyword-search an exact term without paying for a new embedding.
- Every heavy response has a compact default and an explicit deeper mode.

## Gbrain-Style Video Digestion

Treat each ingested video like a durable knowledge object, closer to meeting transcript digestion:

### Digestion Layers

- `source`: canonical video metadata, channel, duration, transcript seconds.
- `segments`: transcript chunks/windows with timestamps.
- `claims`: factual claims and advice, each with timestamp evidence.
- `concepts`: methods, tools, entities, frameworks, pitfalls, implementation notes.
- `artifacts`: TLDR, study guide, action items, article/talk angles, project/repo-application notes.
- `knowledge map`: cross-video themes, entity clusters, repeated concepts, contradictions.
- `personal overlay`: user notes, preferences, durable takeaways, project relevance.

### Ingestion Workflow

1. Fetch transcript and metadata.
2. Store transcript lines/chunks.
3. Embed transcript chunks.
4. Run a cheap source digest on bounded transcript excerpts.
5. Generate labels/concepts/artifacts with source refs.
6. Optionally run cross-video/library digest asynchronously.
7. Expose job/workflow state over MCP.

Acceptance criteria:

- Base ingestion succeeds even if digest generation fails.
- Digests cite timestamp refs.
- Cross-video digest is async and quota-gated.
- Agents can search digests first, then retrieve exact clips.

## External Brain Sync

Memexai should not assume it is the user's only brain. Many users will already have a
personal agent, local memory system, gbrain-style database, or team knowledge graph. In that setup,
Memexai should act as the canonical saved-video source system and expose compact, governed
sync surfaces.

Principles:

- External brains pull through MCP, not direct database access.
- Source video context remains read-only: transcripts, chunks, labels, concepts, and artifacts are
  not mutated by downstream brains.
- Personalization flows into the overlay: notes, preferences, project relevance, and durable
  takeaways can be written back through overlay tools.
- Sync payloads should default to compact source refs, concepts, artifacts, timestamps, and access
  provenance rather than full transcripts.
- Every synced object needs stable IDs, `updated_at`/version semantics, and source refs so external
  brains can dedupe, revoke, and refresh safely.

Current MCP discovery surface:

- `context://brain-sync-contract`
- `context://brain-digest`
- `get_brain_sync_contract`
- `export_brain_digest`

Current sync surfaces:

- Incremental digest export with cursor, `since`, `max_chars`/`max_context_tokens`, object filters,
  access provenance, and transcript-off by default.
- External-brain sync outbox rows for `video.ingested`, `knowledge.published`,
  `overlay.note.created`, and `capture_source.synced`. These are compact event pointers that should
  lead consumers back to `export_brain_digest` for changed objects.

Planned sync surfaces:

- Delivery worker/webhook dispatch for queued `external_brain_sync_events`.
- Portable JSONL/NDJSON export for users or teams that want a local central brain.

Acceptance criteria:

- A personal brain can discover the sync contract without reading the database.
- A personal brain can pull compact changed objects with `export_brain_digest` or
  `context://brain-digest`.
- Default sync stays compact enough for agent memory systems.
- Revoking an MCP token or video grant clearly stops future sync access.
- Overlay writes are separated from canonical video source knowledge.

## Cost And Token Controls

### Ingestion Spend Controls

- Keep dedupe-by-YouTube-ID before any embedding call.
- Enforce per-user video and transcript-second quotas before embedding.
- Add per-job estimated cost fields:
  - discovered videos
  - videos already indexed
  - videos to embed
  - transcript seconds
  - estimated embedding tokens/chars
  - estimated digest LLM calls
- Require `allow_bulk=true` for playlist/channel ingestion over MCP.
- Add a future `digest_level`: `none`, `basic`, `standard`, `deep`. Implemented as
  `digest_depth` for hosted/API/MCP ingestion with matching cost estimates; web UI controls remain
  a follow-up.

### MCP Token Controls

- Default response budget: compact.
- Add `detail_level`: `compact`, `standard`, `deep`.
- Add `max_chars` or `max_context_tokens` where useful.
- Include `estimatedResponseChars` in heavy tool responses.
- Refuse or truncate runaway calls with guidance for narrower follow-up.
- Current MCP budgeted surfaces: `search_video_concepts`, `search_transcript_text`,
  `search_video_moments`, `get_video_context`, `build_context_bundle`, and
  `build_agent_brief`, plus `export_brain_digest`.
- `get_video_context` omits transcript lines/chunks by default over MCP; callers must pass
  `include_transcript: true` and a larger detail budget for deeper source inspection.

Recommended defaults:

- `search_video_moments`: 5 clips, 240-char snippets, no full answer unless requested.
- `get_video_context`: transcript lines capped; source concepts/artifacts prioritized.
- `build_agent_brief`: source highlights + citations + target map, not full transcript.
- `knowledge_map`: library-level summary capped to agent-readable themes.

Acceptance criteria:

- A normal agent search should stay under roughly 2k-4k response tokens.
- Full transcript retrieval must require an explicit deeper call.
- Bulk ingestion should show estimated cost before expensive work starts.

## Evaluation Plan

Use the old 30-video corpus, the Sierra fixture, and the universal-topic fixture as the first
retrieval benchmark.

Implemented `eval/fixtures/video_retrieval_queries.json` with:

- query
- expected video IDs
- optional expected timestamp ranges
- required match type (`keyword`, `semantic`, `concept`, `artifact`)
- notes on why the answer should match

Initial benchmark queries:

- "China Robotics Open-Source AI"
- "OpenAI infrastructure compute spend"
- "Zipline engineering scaling autonomous delivery"
- "agent harness eval workflow"
- "Sierra product harness loops"
- "how to turn saved videos into implementation plans"
- "how do I revive a sourdough starter"
- "compare beginner guitar practice routines"
- "which history lecture explains the causes of the Meiji Restoration"
- "troubleshoot a leaking faucet cartridge"

The synthetic cross-topic starter fixture lives at `eval/fixtures/universal_video_retrieval.json`
and should remain in the eval set until real user-consented multi-domain saved-video corpora replace
it.

Run the deterministic baseline with:

```bash
python scripts/evaluate_video_retrieval.py
```

Metrics:

- Recall@5 by expected video.
- MRR by expected video.
- Timestamp hit if a range is known.
- Wrong-video rate.
- Average response chars/tokens.
- Estimated cost per query.

Release gate:

- Hybrid search must beat vector-only on entity-heavy and exact-title/entity queries.
- No eval query should return only obviously unrelated videos.

## First Implementation Slices

1. Migrate or reingest the 30-video local corpus into Supabase.
   - Needed to test hosted MCP against real saved-video data.
   - Created the first realistic eval dataset.
   - Done with `scripts/legacy_chroma_supabase_import.py --apply --create-eval-user`, reusing local
     Chroma embeddings instead of spending new Gemini embedding quota.

2. Add full-text indexes and `search_chunks_hybrid` RPC.
   - Keep existing `search_chunks` until hybrid is proven.
   - Add tests that user grants still gate every candidate.

3. Add retrieval modes to `search_video_moments`.
   - `mode=hybrid` as default.
   - `mode=keyword` for no-embedding exact searches.
   - Return `retrievalPlan`, `matchType`, and `retrievalBudget`.

4. Add `search_video_concepts` over source concepts/artifacts.
   - This is the topic-agnostic first search surface.
   - Agents should search concepts before transcript chunks for broad learning tasks.

5. Add context-budget fields.
   - Tool schemas should expose `detail_level` and bounded defaults.
   - Responses should include estimated size/cost hints.

6. Add retrieval eval fixture and script.
   - Run the same query set against deterministic keyword/concept baselines first, then live
     hybrid/semantic retrieval when embedding quota is available.
   - Use eval output to decide whether reranking is required now or later.
   - Include non-AI topics so retrieval does not overfit to developer/research videos.
   - Done for the offline lexical baseline; live hybrid/semantic checks should run once embedding
     quota or BYOK is available.
