# Hosted Product PRD

Working name: TBD  
Status: Draft  
Last updated: 2026-05-30

## One-Line Positioning

The product turns a creator's published video archive into searchable memory, so they can find the exact quote, topic, or moment they remember and jump straight to the timestamp.

## Product Thesis

Creators do not primarily need another automatic clipping tool. They need a reliable way to retrieve moments they already know are valuable but cannot find.

Most adjacent products compete on "AI finds viral clips for you" or "edit video by editing text." This product should own a narrower, more durable promise:

> I vaguely remember saying something. Find the exact moment.

That wedge is useful before editing, before repurposing, and before publishing. It makes the creator's archive usable again.

## Core Principle

**Search before generation.**

The product should not hallucinate content strategy or pretend every long video contains viral clips. Its first job is to make the creator's real spoken archive trustworthy, searchable, and citeable.

Every result should answer:

- What video did this come from?
- Where exactly does it start?
- Why did this match?
- Can I open, copy, export, or hand this to an editor immediately?

## Target User

Primary user:

- YouTube creators, podcasters, educators, coaches, commentators, and founder-led content teams with a growing library of long-form spoken content.

Best early adopter:

- A creator or operator with 50+ videos who regularly thinks, "I know I said this somewhere," then wastes time scrubbing, searching titles, or asking an editor to hunt manually.

Secondary users:

- Video editors who need to find source moments fast.
- Social media managers building quote/clip calendars.
- Researchers reviewing creator, interview, course, or webinar archives.

## Problem

Long-form video archives become inaccessible as they grow. YouTube titles, descriptions, chapters, and comments do not capture the actual spoken substance inside a channel.

Current workflow:

1. Remember an idea, phrase, answer, story, or quote.
2. Guess which video it was in.
3. Scrub through the timeline or search individual transcripts.
4. Copy a timestamp manually.
5. Send the link to an editor or use it in a post.

This is slow, unreliable, and gets worse as the archive grows.

## Market Context

The broader category is crowded with literal "AI video search" and "AI clip finder" tools. A quick landscape scan found products positioned around exact timestamps, transcript search, automatic clipping, and video editing:

- Pyntic: AI video transcript search and timestamp finder. <https://www.pyntic.com/>
- Reclipt: AI transcript insights and clip library. <https://www.reclipt.io/>
- MomentClip: Ctrl+F for YouTube videos. <https://momentclip.com/>
- Clivio: semantic video search and indexing. <https://clivio.ai/>
- SeekFrame: AI search across webinars, demos, and podcasts. <https://www.seekframe.io/>
- Riverside Magic Clips: automatic short clip generation. <https://riverside.com/clips>
- Descript: transcript-based audio/video editing. <https://www.descript.com/transcription>

Implication:

Do not position as "AI clip finder" or "automatic video clipping." Position as creator archive memory and exact-moment retrieval.

## Differentiation

| Category                 | What they promise                   | Product stance                                    |
| ------------------------ | ----------------------------------- | ------------------------------------------------- |
| Auto-clipping tools      | "We find viral moments for you"     | Let users find the moment they already want       |
| Text-based editors       | "Edit video like a document"        | Stay upstream of editing; retrieve source moments |
| Generic transcript tools | "Download/summarize one transcript" | Search an entire creator archive                  |
| YouTube search           | "Find videos"                       | Find exact spoken moments inside videos           |

## MVP Scope

The hosted MVP should do five things extremely well:

1. Authenticate a user.
2. Let them index a YouTube channel, playlist, or single video.
3. Extract captions/transcripts and store searchable timestamped chunks.
4. Let them search by natural language across their indexed archive.
5. Return exact timestamped clips with enough context to trust and reuse.

## Current Product Surface

Already implemented or partly implemented:

- YouTube URL detection for channel, playlist, video, short, embed, and watch URLs.
- Channel/video discovery with `scrapetube`.
- Transcript extraction with `youtube-transcript-api`.
- 60-second transcript chunking.
- Gemini text transcript embeddings with `models/gemini-embedding-001`.
- 768-dimensional vectors for Supabase `VECTOR(768)`.
- Retrieval task types:
  - `RETRIEVAL_DOCUMENT` for indexed chunks.
  - `RETRIEVAL_QUERY` for searches.
- Video title prepended to document embedding text.
- Supabase hosted storage path:
  - `channels`
  - `videos`
  - `chunks`
  - `user_channels`
  - `profiles`
- User-scoped search through Supabase RPC.
- Quota counters.
- Server-key mode.
- Optional encrypted BYOK mode.
- Supabase-only storage in the hosted fork; the old local Chroma mode has been removed.

## Transcription Extraction Method

Current method:

1. Detect YouTube URL type.
2. Use `scrapetube` to discover channel or playlist videos.
3. Use YouTube oEmbed for title/channel metadata when available.
4. Use `youtube-transcript-api` to fetch existing YouTube captions.
5. Convert transcript snippets into roughly 60-second chunks.
6. Store chunk text with start/end seconds.

Strengths:

- No YouTube Data API key required.
- Fast and cheap.
- Uses YouTube's existing timestamps.
- Good enough for public videos with captions.

Limitations:

- Fails when captions are disabled, unavailable, age-restricted, region-restricted, or blocked.
- Auto-caption quality varies.
- Current chunking is duration-only, not topic-aware.
- No overlap between chunks, so semantic context may split awkwardly.
- No transcript provenance field.
- No retry/backoff/job record for production ingestion.
- Channel identity can be weak for single-video or playlist imports.

Refinements:

- Add transcript source metadata:
  - `youtube_manual_caption`
  - `youtube_auto_caption`
  - `generated_transcription`
  - `imported_file`
- Add fallback transcript generation later using audio extraction + speech-to-text.
- Add chunk overlap, likely 10-15 seconds or 1-2 transcript snippets.
- Add sentence-aware chunk boundaries.
- Add topic/scene labels after baseline retrieval works.
- Store raw transcript lines separately from retrieval chunks.
- Move ingestion to background jobs with durable progress.
- Add retry/backoff for transcript and metadata fetches.
- Add "partial index" state when some channel videos fail.

## Embedding Method

Current method:

1. For indexing, embed each chunk with Gemini using:
   - model: `models/gemini-embedding-001`
   - dimensions: `768`
   - task type: `RETRIEVAL_DOCUMENT`
   - text: `video title + chunk text`
2. Store vectors in Supabase pgvector.
3. For search, embed the query using:
   - same model
   - same dimensionality
   - task type: `RETRIEVAL_QUERY`
4. Search the user's subscribed/indexed channels through the `search_chunks` RPC.
5. Filter out the first 120 seconds to avoid intros.

Model posture:

- Keep `models/gemini-embedding-001` as the text-transcript default while the schema is `VECTOR(768)`.
- Evaluate newer embedding families, including multimodal Gemini embeddings, only when the product adds audio/video/PDF understanding or a planned full re-embed.
- Use `gemini-3.1-flash-lite` for bounded extraction and answer generation; avoid deprecated Gemini 2.0 model IDs.

Strengths:

- Simple and cheap.
- Uses document/query task specialization.
- 768 dimensions keeps Supabase storage costs reasonable.
- Title-aware embeddings improve retrieval context.
- Compatible with local eval harness.

Limitations:

- Current answer field is empty in Supabase search path.
- Ranking is mostly vector similarity plus intro filtering.
- No hybrid lexical + semantic search.
- No reranker.
- No query expansion.
- No per-channel or date filters.
- No score explanation in the UI.
- No benchmark-driven model switch yet.

Refinements:

- Add hybrid retrieval:
  - semantic vector search
  - keyword/phrase search
  - exact quote boost
- Add reranking for top 20-50 chunks before returning top results.
- Add result grouping by video to avoid five near-duplicate chunks.
- Add confidence/why-this-matched snippets.
- Add filters:
  - channel
  - date range
  - video title
  - exclude intros/outros
  - exact phrase mode
- Evaluate embedding dimensions and candidate providers before switching defaults.
- Add query classes:
  - exact quote
  - topic
  - person/name/entity
  - "where did I say..."
  - "find clips about..."

## User Experience Requirements

Search results must feel verifiable, not magical.

Each result should show:

- Video thumbnail.
- Video title.
- Channel/source.
- Timestamp.
- Transcript excerpt.
- Similarity/relevance explanation in human terms.
- Copy timestamp link.
- Open on YouTube.
- Save to a clip list.

Ingestion must feel durable.

Users should see:

- Queued/running/complete/failed state.
- Total videos discovered.
- Videos indexed.
- Videos skipped.
- Reason for skipped videos.
- Estimated remaining work.
- Ability to leave the page and return.

## Hosted Product Requirements

Production hosted version should remove open-source dual-mode complexity and become opinionated:

- Supabase auth required.
- Supabase pgvector storage.
- Server Gemini key by default.
- BYOK disabled initially unless it becomes a pricing/usage differentiator.
- Quotas enforced before expensive work.
- Background ingestion jobs instead of request-bound SSE.
- Admin visibility into jobs, usage, failures, and spend.
- Clear billing/spend guardrails.

## Product Boundaries

Do:

- Search creator archives.
- Retrieve exact moments.
- Help users build clip lists.
- Export timestamps/transcripts.
- Hand off moments to editing workflows.

Do not, at MVP:

- Promise viral clip selection.
- Become a full video editor.
- Auto-post to social platforms.
- Generate videos.
- Replace Descript/Riverside/OpusClip.
- Support every video platform.

## Feature Directions

### Direction 1: Creator Memory

The product becomes a personal memory layer for everything the creator has said.

Features:

- "Where did I talk about X?"
- Saved searches.
- Topic collections.
- People/entity pages.
- Reusable quote bank.
- "I remember saying..." query mode.

Why it fits:

- Strongest differentiation.
- Search-first, not generation-first.
- Useful every week for creators with archives.

### Direction 2: Clip Queue

The product becomes the source-of-truth queue for editors and social teams.

Features:

- Save result to clip queue.
- Add notes and intended platform.
- Assign to editor.
- Export CSV/Notion/Linear/Trello.
- Mark status: found, clipped, edited, posted.

Why it fits:

- Converts retrieval into workflow value.
- Easier to monetize for teams.
- Avoids needing to build the editor immediately.

### Direction 3: Quote and Content Repurposing

The product turns found moments into reusable content assets.

Features:

- Copy quote with timestamp citation.
- Generate LinkedIn/X post draft from selected clip.
- Generate YouTube description/chapter ideas.
- Create "best quotes from this channel" collections.
- Export transcript snippets.

Why it fits:

- Extends search into output.
- Still grounded in real source clips.
- Good bridge to creator ROI.

### Direction 4: Assisted Clip Discovery

The product suggests candidate clips, but only after the search/retrieval foundation is trusted.

Features:

- "Find 10 strong clips about customer pain."
- Clip scoring based on specificity, payoff, clarity, emotion, and standalone context.
- Adjustable clip length.
- Include transcript rationale.

Why it fits:

- Competes more directly with AI clipping tools, so it should wait.
- Works better once the archive is indexed and retrieval quality is strong.

### Direction 5: Multimodal Search

The product moves beyond transcripts into visual/audio understanding.

Features:

- Search screen text/OCR.
- Search visual scenes.
- Detect slides, demos, faces, products, reactions.
- Find moments where something is shown but not said.

Why it fits:

- Big quality upgrade for tutorials, demos, streams, and product videos.
- More expensive and complex, so it should follow transcript-market validation.

## Recommended Roadmap

### Phase 1: Hosted Retrieval MVP

Goal: Make the hosted product reliable enough to use on a real creator channel.

Ship:

- Production-only hosted repo.
- Supabase auth.
- Server Gemini key.
- Background ingestion jobs.
- Channel/video/library/search.
- Durable ingestion status.
- Better skipped-video reporting.
- Save/copy/open timestamp actions.
- Basic quotas and admin usage visibility.

### Phase 2: Trust and Refinement

Goal: Make search results feel clearly better than manual transcript search.

Ship:

- Hybrid search.
- Chunk overlap and sentence-aware boundaries.
- Result grouping.
- Search filters.
- Match explanations.
- Retrieval eval dashboard/report.
- Saved searches.

### Phase 3: Workflow Layer

Goal: Turn found moments into creator/team workflow.

Ship:

- Clip queue.
- Notes/status/assignee.
- Export to CSV/Notion.
- Quote bank.
- Post draft generation from selected source moments.

### Phase 4: Discovery and Multimodal

Goal: Expand from known-item retrieval to assisted discovery.

Ship:

- Suggested clips by topic.
- Clip scoring.
- Visual/OCR search.
- Audio transcription fallback.
- Multi-platform ingest.

## Metrics

Activation:

- User connects or indexes first video/channel.
- First successful search returns at least one clicked result.

Core value:

- Searches per indexed channel.
- Result click-through rate.
- Timestamp copy rate.
- Saved clip rate.
- Time from query to copied/opened timestamp.

Ingestion quality:

- Videos discovered.
- Videos indexed.
- Videos skipped by reason.
- Transcript availability rate.
- Average chunks per video.

Retrieval quality:

- Query success rate.
- Recall@k on eval fixtures.
- MRR on eval fixtures.
- User thumbs up/down on result.

Business:

- Active indexed channels.
- Repeat weekly users.
- Quota hit rate.
- Cost per active user.
- Cost per indexed hour.

## Open Questions

- What is the first paid user profile: solo creator, editor, agency, educator, or B2B content team?
- Should the hosted product support BYOK, or should it stay server-key only with quotas?
- Should the initial product index only owned channels, or any public YouTube channel?
- Does the product need YouTube OAuth to verify channel ownership later?
- What is the right free quota that feels useful without creating runaway costs?
- Should "search whole channel" or "find clips for repurposing" be the landing-page promise?
- What production name best supports the memory/archive positioning?

## Naming Implication

Avoid names built around:

- Clip
- Finder
- Tube
- Transcript
- Search
- Frame
- Moment

The stronger naming territory is:

- Memory
- Archive
- Index
- Lode/mining
- Signal
- Thread
- Cue
- Mark
- Ledger

The name should support a future where the product searches more than YouTube transcripts: podcasts, courses, webinars, interviews, livestreams, and internal video libraries.

## Summary Recommendation

Position the hosted product as **searchable memory for creator archives**, not as an AI clipping tool.

The MVP should be production-opinionated:

- Supabase-only.
- Server-key only.
- Background ingestion.
- Exact timestamp search.
- Verifiable transcript excerpts.
- Save/copy/export workflows.

The product should earn trust through precise retrieval before expanding into clip generation, social drafting, or multimodal understanding.
