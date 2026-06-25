# Ingestion Cost Risk

Status: guardrail notes for agent-submitted YouTube ingestion.

## Short Answer

Bulk submission through MCP is not inherently cheaper than manual submission.

The benefit is operational:

- users and agents do not copy/paste the same links repeatedly
- the backend can dedupe before embedding
- ingestion can run as durable queued work instead of blocking the chat/session
- future batch embedding or batch extraction can reduce model costs
- agents can check job status and use the new knowledge after indexing

The risk is blast radius:

- a single video is bounded
- a playlist can contain dozens or hundreds of videos
- a channel can be much larger and may include stale, low-value, or duplicate content

For the user journey, the cleanest default is not "bulk upload everything through chat." It is "save videos where you already watch them, then let Memexai sync the user's approved capture source." MCP bulk submission is best reserved for trusted agents that are explicitly acting on the user's current instruction.

## Cost Surfaces

The main cost surfaces are:

- Gemini embeddings for transcript chunks
- Gemini LLM extraction for source labels, concepts, edges, TLDRs, and study guides
- Supabase/Postgres row and index growth for videos, chunks, transcript lines, labels, concepts, edges, artifacts, jobs, and events
- Supabase disk and egress when agents repeatedly retrieve large context payloads
- worker/container runtime time while transcript fetching and indexing runs
- YouTube API quota for playlist/channel sync and metadata operations

YouTube quota is usually the smaller risk for basic playlist reads. Google documents that every YouTube Data API request costs at least one quota point and that default projects get 10,000 units per day for most endpoints. The expensive part for Memexai is what happens after discovery: transcript processing, embeddings, extraction, storage, and future retrieval.

Gemini pricing makes batching worth considering later. As of the current official pricing page, `gemini-embedding-001` is listed at $0.15 per 1M input tokens for standard calls and $0.075 per 1M input tokens for batch calls. That means bulk ingestion can become cheaper per token only if the backend actually routes suitable work through batch APIs.

For the current hosted extraction path, the relevant standard Gemini prices are:

- `gemini-embedding-001`: $0.15 per 1M input tokens, or $0.075 per 1M input tokens through batch.
- `gemini-3.1-flash-lite`: $0.25 per 1M text input tokens and $1.50 per 1M output tokens.

The ingestion estimator now reports:

- `estimatedDigestInputTokens`
- `estimatedDigestOutputTokenBudget`
- `estimatedModelCostUsd.embeddingStandardUsd`
- `estimatedModelCostUsd.embeddingBatchUsd`
- `estimatedModelCostUsd.digestInputUsd`
- `estimatedModelCostUsd.digestOutputBudgetUsd`
- `estimatedModelCostUsd.totalStandardUpperBoundUsd`

The digest output estimate is intentionally an upper bound because it uses the selected depth's `max_output_tokens`. Actual cost should be lower when the model emits fewer tokens.

Using the current assumptions of a 15-minute new video, 16 transcript chars/second, and `gemini-3.1-flash-lite` digestion:

| Depth      | Generated at ingestion                                     | Approx standard model cost per new video |
| ---------- | ---------------------------------------------------------- | ---------------------------------------- |
| `none`     | Transcript chunks and embeddings only                      | ~$0.00054                                |
| `basic`    | Compact labels, core concepts, TLDR                        | ~$0.00294 upper bound                    |
| `standard` | Source-backed one-page report, topic/claim cards, timeline | ~$0.01118 upper bound                    |
| `deep`     | Larger source-backed report and richer extraction budget   | ~$0.02115 upper bound                    |

These numbers exclude Supabase storage/egress, worker runtime, YouTube quota, and any model spend by the calling MCP agent after retrieval.

## Ingestion vs MCP Generation Policy

The default product split should be:

- Ingestion generates reusable navigation and evidence once for every indexed video: transcript chunks, embeddings, source labels, topic/claim cards, timestamped evidence refs, timeline entries, and a source-backed report.
- MCP agents generate task-specific synthesis on demand: repo/application briefs, cross-video synthesis, user-specific recommendations, implementation plans, and long narrative reports tailored to the current conversation.

Recommended defaults:

- Every indexed video: `standard`, because the saved-source page should have a consistent analysis contract regardless of whether the video came from a single URL, playlist, channel, or agent submission.
- Short videos: keep the same sections but scale the report down to the transcript's substance; a 3-minute video should not pretend to need a 3,000-word report.
- Long/dense videos: allow `standard` to produce a longer source report, and use `deep` when the user or agent explicitly wants the larger transcript window and output budget.
- Cost-saving mode: `basic` or `none` only when the user explicitly chooses cheaper/lighter ingestion, not as the default for bulk sources.
- Already indexed video: grant access to existing source context; do not regenerate unless the artifact version or digest depth is stale.

This keeps Memexai from paying repeatedly for custom summaries while still giving agents a fast map that is materially better than scanning the transcript.

Supabase pricing also makes storage caps important. The Pro plan pricing page currently lists 8 GB included database disk per project, then usage-based disk charges, plus egress allowances and overages.

## Product Guardrails

Current guardrails:

- `ingest:write` is opt-in; default MCP tokens do not include it.
- Source context remains read-only even for tokens with `ingest:write`.
- Queued hosted ingestion jobs store a conservative `cost_estimate` object with discovered videos,
  already-indexed videos, videos still needing embedding, estimated transcript seconds,
  embedding chars/tokens, selected digest depth, digest LLM calls, and a low/medium/high risk label.
- Videos are canonical by YouTube ID. If a submitted video is already indexed, the backend grants
  user access to the existing `videos/chunks/source_*` rows through `user_videos` instead of
  fetching transcripts and generating embeddings again.
- MCP single-video submission is allowed with `queue_youtube_ingestion`.
- MCP playlist and channel submission requires `allow_bulk: true`.
- MCP submissions can set `digest_depth`:
  - `none`: transcript/search rows only; no LLM source-knowledge extraction.
  - `basic`: compact labels, core concepts, and TLDR.
  - `standard`: labels, concepts, edges, TLDR, and study guide.
  - `deep`: larger transcript/output budget for richer digestion.
- Playlist capture sync dedupes discovered video IDs before queueing ingestion jobs.
- Playlist capture sync queues only a bounded number of single-video jobs per sync.
- Playlist capture sync returns a sync-level `costEstimate` for the discovered queue candidates,
  while each queued video job receives its own per-video estimate.
- Active hosted ingestion jobs are capped per user.
- Existing hosted index quotas still apply during ingestion.
- Agents can read job status through MCP instead of retrying blindly.

Recommended next guardrails:

- Add per-user monthly queued-video and queued-transcript-hour caps before playlist sync.
- Use stored `cost_estimate` data to ask for confirmation above a threshold before approving
  larger playlist/channel batches.
- Add user-facing digest-depth controls in the web ingestion UI after agent defaults are proven.
- Add per-agent token audit logs for queue submissions.
- Add dedupe-first dry runs for playlist/channel submissions.
- Add admin alerts for high skip/failure rates and unusual bulk submissions.
- Route large, non-urgent embedding work through batch processing when the product can tolerate latency.

## User Journey

The best user journey is:

1. User creates an MCP token.
2. Default token allows `context:read` and `overlay:write`.
3. User optionally enables `ingest:write` for agents they trust.
4. In a chat, the user says “save this YouTube video to my knowledge base.”
5. The agent calls `queue_youtube_ingestion`.
6. For playlists or channels, the agent asks a second confirmation and then calls with `allow_bulk: true`.
7. The backend creates a durable ingestion job and processes it in the hosted runner.
8. The agent checks `get_ingestion_job`.
9. After completion, the agent uses `list_context_categories`, `search_video_moments`, or `build_agent_brief`.

This keeps the experience agent-friendly without making every agent token a blank check.

For YouTube-native capture, the best user journey is:

1. User creates or selects a dedicated "Memexai Inbox" playlist.
2. User saves videos to that playlist while staying on YouTube.
3. Memexai syncs that capture source.
4. The sync stores discovered item status and queues only the allowed number of ingestion jobs.
5. The user or agent reads `context://capture-sources`, `list_ingestion_jobs`, and `context://library` to see when those videos become usable context.

## References

- Gemini API pricing: https://ai.google.dev/gemini-api/docs/pricing
- YouTube Data API quota costs: https://developers.google.com/youtube/v3/determine_quota_cost
- Supabase pricing: https://supabase.com/pricing
