# Production Hosted Setup

# Settings Capture Source Density Fix

- [x] Compact connected playlists in Settings so long URLs and video rows do not crowd Usage.
- [x] Keep Sync and Disconnect controls available without turning Settings into a management view.
- [x] Add regression coverage for hiding playlist/video detail in the modal.
- [x] Run focused frontend verification.

# Anonymous Auth And MCP Playlist Sync Assessment

- [x] Verify current Supabase anonymous sign-in behavior, conversion semantics, and security constraints from primary docs.
- [x] Inspect current Memexai auth/profile/quota assumptions for anonymous-user compatibility.
- [x] Inspect current MCP tools/resources and playlist capture sync implementation.
- [x] Assess whether an MCP agent can trigger project-linked playlist sync today, and identify the smallest missing product/engineering slice if not.
- [x] Summarize vulnerabilities, business case, free-tier friction reduction, and recommended path.

# MCP Agent Ingestion And Capture Sync

- [x] Research MCP tool/auth/security practices from Anthropic, Arcade, Unsloth, and the MCP specification.
- [x] Add scoped MCP permissions for agent-triggered capture-source sync.
- [x] Add scoped MCP project creation for authenticated agents.
- [x] Add scoped MCP playlist capture-source creation attached to a user project.
- [x] Add plan-aware user limit checks and project-target validation to MCP YouTube URL ingestion.
- [x] Add project assignment for successful single-video agent ingestion jobs.
- [x] Add an MCP capture-source sync tool with preview, explicit confirmation, workflow handles, and ingestion job handles.
- [x] Add focused regression tests for scopes, confirmation gates, user limits, project scoping, and agent-visible status handles.
- [x] Run focused verification and review the feature for MCP abuse paths.

# Library Topic/Report UX Correction

- [x] Map the current Library graph UI data shape for videos, topics, and artifacts.
- [x] Replace long topic/report feeds with a categorized, video-aware browsing structure.
- [x] Deduplicate repeated topics that point at the same video/timestamp window.
- [x] Show the source video clearly on every topic card and avoid timestamp-only context.
- [x] Group TLDR and source reports by video instead of repeating artifact cards in one scroll.
- [x] Add a persistent Library left menu for Videos, Topics, Reports, and Recent searches.
- [x] Add focused frontend tests for categorized topics, dedupe, report grouping, and menu routing.
- [x] Run focused frontend verification and production build.

# Library Performance And Caching Pass

- [x] Trace Library load routes and identify the per-video chunk-count N+1 query.
- [x] Add a bulk Supabase chunk-count RPC with a safe backend fallback path.
- [x] Add short private cache headers for stable authenticated Library JSON routes.
- [x] Add session-scoped stale cache helpers for Library, Library graph, and recent jobs.
- [x] Render cached Library and source graph data before background refresh.
- [x] Make the web Library graph payload compact and load full source reports on demand.
- [x] Remove the Library UI's latest-50-video browsing cap and batch-render large video/topic/report lists.
- [x] Split the Library knowledge browser into a lazy-loaded frontend chunk.
- [x] Add focused backend/frontend cache and bulk-count tests.
- [x] Run focused lint, typecheck, build, and test verification.

# Agent Discoverability Upgrade For Video Context

- [x] Add a Supabase `source_knowledge_index` schema and hybrid search RPC gated by `user_videos`/`user_channels`.
- [x] Build and refresh searchable rows for concepts, artifacts, report sections, aliases, and timestamp refs during ingestion.
- [x] Upgrade `search_video_concepts` to hybrid/semantic/keyword source-knowledge retrieval with compact MCP output and full `structuredContent`.
- [x] Add `get_video_knowledge_map` so agents can inspect a video table of contents before pulling clips or transcripts.
- [x] Add discoverability eval fixtures/tests for object recall, video recall, timestamp hits, wrong-video rate, response bytes, and transcript avoidance.
- [x] Run focused verification for backend indexing, MCP output, and eval behavior.

# Ingestion Report + Timestamp Topic Assessment

- [x] Trace backend transcript-to-TLDR/source-report/topic generation.
- [x] Trace REST/MCP/library payload shape for reports and timestamped topics.
- [x] Trace frontend rendering and topic-link UX for generated video artifacts.
- [x] Compare Library search behavior against the dashboard search workflow.
- [x] Verify suspected causes with focused tests or fixtures.
- [x] Summarize root causes and recommended fixes.
- [x] Keep Library smart search within the free result cap so it no longer asks the API for 6 clips.
- [x] Add source-ref fallbacks so concepts, labels, edges, and report bullets get transcript timestamp evidence when the model omits refs.
- [x] Add canonical-video source-knowledge refresh for reused videos so existing embeddings can still get upgraded reports/topics.
- [x] Guard reused-video refresh so empty replacement extraction does not delete existing generated context.
- [x] Upgrade `cadecr@gmail.com` to active Pro limits in Supabase while keeping free-user defaults/tests intact.
- [x] Backfill the production `cadecr@gmail.com` library so 6 stale videos now have regenerated reports and timestamped topics.
- [x] Verify with focused backend/frontend tests and production frontend build.

# Playlist Sync Pipeline Repair

- [x] Remove browser-native playlist sync confirmation and replace it with an in-app confirmation modal.
- [x] Drop the stale one-active-ingestion-job database index that blocks confirmed multi-video playlist sync.
- [x] Improve sync/job status messaging so failed workflow, queued, running, completed, and stuck states are visible.
- [x] Add regression tests for the modal confirmation flow and multi-job database/schema contract.
- [x] Repair the currently stuck production queued job and redeploy verified fixes.

# Production MCP OAuth And Retrieval Eval

- [x] Verify production MCP OAuth discovery, dynamic client registration, authorization redirect, and protected-resource challenge.
- [x] Create a temporary production-user MCP credential without exposing the raw token in chat.
- [x] Run production MCP retrieval calls against the user's library and measure latency/response size.
- [x] Compare MCP retrieval friction and context size against direct video/transcript copy-paste.
- [x] Capture product gaps for agent-native onboarding without dashboard token creation.
- [x] Guard source-knowledge refresh so production backfills cannot delete existing context when extraction fails.
- [x] Backfill stale sparse source reports/topics for the production test library and re-run MCP quality checks.
- [x] Reduce duplicated large MCP tool responses so `structuredContent` carries the full payload and text content stays compact.
- [ ] Add a Cloudflare security/WAF skip or equivalent allow rule for `/mcp` so bare Python/default agent HTTP clients are not blocked with Error 1010.
- [ ] Automate Cloudflare Container instance-id/version rotation so API deploys do not require a manual durable container name bump to pick up a new image immediately.

# Playlist Capture Sync Bug

- [x] Reproduce the reported playlist returning zero videos through the current capture discovery path.
- [x] Add a YouTube API/OAuth-aware playlist discovery path with a public extraction fallback.
- [x] Change playlist sync to preview all pending videos, ask for confirmation, and queue the confirmed count.
- [x] Add regression tests for the reported failure mode and sync token path.
- [x] Verify and deploy the API/runtime and frontend.

# Mobile Dashboard QA Pass

- [x] Reproduce the authenticated dashboard at mobile widths and capture evidence of the broken layout.
- [x] Patch the dashboard/app-shell layout so mobile controls, cards, and text fit without horizontal overflow.
- [x] Re-run mobile screenshots plus focused frontend verification.
- [x] Redeploy the frontend after the fix is verified.

# Current Production Blockers

- [x] Fix dashboard ingestion misclassifying `watch?v=...&list=...` YouTube video URLs as playlists with zero videos.
- [x] Harden single-video ingestion failures so Supabase response edge cases do not crash with `NoneType.data`, failed jobs show `1 failed`, and empty Library surfaces recent failed imports.
- [x] Fix direct video import regression where `user_videos.access_source='single_video'` violated the production Supabase check constraint.
- [x] Harden ingestion schema contracts for job source types, job statuses, event levels, and video access sources with backend guards and migration-sync tests.
- [x] Harden YouTube URL detection for timestamped video URLs, playlist-context watch URLs, Shorts, Live, embed/v links, mobile/no-scheme links, and channel URL variants.
- [x] Fix production Library showing empty after a successful mobile import when the deployed `count_chunks_for_video` RPC is missing.
- [x] Harden source graph reads so production schemas without legacy `videos.indexed_by` still return explicit saved-video grants.
- [x] Make the Library UI show a retry/error state instead of translating backend failures into an empty account.
- [ ] Decide whether older local/dev PC ingestion history should be migrated into the production account; recent production jobs are on the same user id across devices.
- [x] Enable Supabase Google OAuth provider for the linked `embedmoments` project; hosted smoke now gets a Google OAuth redirect.
- [x] Re-run hosted smoke after Google OAuth is enabled; public API surfaces, linked Supabase schema, and provider redirect pass locally.
- [x] Complete an interactive Google sign-in from the deployed Cloudflare Pages app after the custom domain/API runtime are wired.
- [x] Set `API_KEY_ENCRYPTION_KEY` in the backend runtime before testing Connect YouTube; YouTube OAuth token storage depends on it.
- [x] Set `MEMEXAI_APP_URL=https://memexai.xyz` in the backend runtime before testing MCP OAuth; agent approval redirects depend on it.
- [ ] Rotate the Cloudflare API token that was pasted into chat during deployment testing.
- [ ] Add real Cloudflare Pages frontend env vars for the production Supabase/API URLs.
- [x] Choose the production product name/domain: Memexai at `memexai.xyz`.
- [x] Re-authenticate Wrangler to Cade's personal Cloudflare account (`cadecr@gmail.com`) and create the personal `memexai` Pages project.
- [x] Deploy the frontend to Cloudflare Pages production at `https://memexai.pages.dev` with `VITE_API_URL=https://api.memexai.xyz`.
- [x] Create the personal Cloudflare Queue `memexai-ingestion` for hosted ingestion jobs.
- [x] Create the private `GhostPeony/memexai` GitHub repo and add it as the local `memexai` remote.
- [x] Attach `memexai.xyz` and `www.memexai.xyz` to the production Cloudflare Pages project.
- [x] Configure `api.memexai.xyz` for the production API/runtime.
- [x] Deploy a production FastAPI backend runtime through Cloudflare Containers.
- [x] Deploy the Cloudflare Container-backed `memexai-api` worker now that Workers Paid is enabled.
- [x] Bind `api.memexai.xyz` to the `memexai-api` Worker after the container worker is healthy.
- [x] Register/deploy the personal-account `workers.dev` route for `memexai-orchestrator`.
- [x] Set matching workflow/orchestrator secrets in Cloudflare Worker and backend runtime before enabling Cloudflare Workflow triggers.
- [ ] Deploy and supervise the queue consumer/backend runtime path in the chosen Cloudflare/container host.
- [x] Attach an HTTP pull consumer to the `memexai-ingestion` queue.
- [ ] Keep production ingestion on background API mode until the Python queue-consumer container is supervised and healthchecked in production.

# Agent-First Knowledge Base Steering

- [x] Research YouTube-native save workflows so users can mark videos on YouTube and have Memexai ingest them without repeated copy/paste.
- [x] Decide whether the best YouTube marker is a dedicated public/private playlist, liked videos, Watch Later, subscriptions, browser extension, or a share-to-Embed-Moments action.
- [x] Design recurring playlist sync for user-selected YouTube playlists, including OAuth scope, polling cadence, duplicate handling, and ingestion-job creation.
- [ ] Prototype a Chrome extension right-click capture flow so users can ingest the current YouTube video, link, article, or selected text into their knowledge base with labels/notes.
- [x] Add capture-source foundation for user-selected YouTube playlists (`youtube_capture_sources`, `youtube_capture_items`, REST create/list, MCP read surface).
- [x] Add a bounded manual playlist sync slice that discovers playlist videos, dedupes capture items, queues capped single-video ingestion jobs, and exposes recent item status to agents.
- [x] Add a reusable Connect YouTube OAuth slice with encrypted per-user provider-token storage, status endpoint, and Settings capture-inbox controls.
- [x] Add FTUE profile onboarding state fields and `GET/PATCH /api/onboarding/status` for resumable setup.
- [ ] Use stored YouTube OAuth grants to sync selected private/unlisted playlists through YouTube Data API instead of public-only scraping.
- [ ] Add first-time user setup that walks new users through Connect YouTube, choose/create a save playlist, and create/copy an MCP token for their agent.
- [ ] Add FTUE setup shell after first auth with persistent profile onboarding state, skip/resume, and activation checklist.
- [ ] Add FTUE YouTube connection step that reuses Connect YouTube status/action and explains the read-only permission boundary.
- [ ] Add FTUE playlist picker backed by YouTube Data API playlist listing, plus manual playlist URL fallback.
- [ ] Add FTUE first-import step that syncs the selected playlist, queues one eligible video by default, and shows job progress.
- [ ] Add FTUE agent setup step that creates/copies a tailored MCP setup bundle for Hermes, Codex, Claude Desktop, ChatGPT, or another MCP client.
- [ ] Keep a compact dashboard setup checklist visible until the user has a capture source, searchable video/job, and optional MCP token.
- [x] Add precise per-video access grants (`user_videos`) so already-indexed YouTube videos can be reused for new users without duplicate embedding compute.
- [x] Draft Cloudflare workflow orchestration architecture for capture sync, ingestion, knowledge release, briefs, monitors/evals, and MCP status handles.
- [x] Add workflow definition/instance/step/artifact schema and helpers so platform workflows can be versioned, inspected, and iterated.
- [x] Add hosted ingestion dispatch abstraction with local background fallback and direct Cloudflare Queue HTTP publishing mode.
- [x] Add pull-based Cloudflare Queue consumer module that processes ingestion messages with the shared hosted Python runner.
- [x] Add queue-consumer container/supervision scaffold with healthcheck and local compose profile.
- [x] Wrap manual capture-source sync in durable workflow state with step/artifact records and queued-job dispatch results.
- [ ] Deploy and supervise the queue consumer/runtime path in the chosen Cloudflare/container host.
- [x] Prototype Cloudflare Workflows as the coordinator for capture-source sync and video ingestion.
- [x] Add workflow status REST endpoints and MCP resources/tools so agents can poll durable workflow handles.
- [x] Design video categorization for agent searchability: source taxonomy, concept tags, entities, methods, tools, difficulty, task fit, and repo/applicability labels.
- [x] Add first source-label/category discovery slice for agents (`source_labels`, `context://categories`, `list_context_categories`).
- [x] Add a stable video category taxonomy and `category_filters` for agent context bundles/briefs.
- [x] Add category-filtered semantic moment search so agents can narrow timestamp retrieval by source-label facets.
- [x] Research proven retrieval organization patterns for agent-facing video knowledge: hybrid search, metadata filters, reranking, clustering/topic modeling, and knowledge graph traversal.
- [x] Evaluate whether hosted Supabase should remain the default DB/vector store or whether users/agents should be able to choose a storage backend.
- [x] Research agent-first signup/access patterns inspired by AgentMail: MCP-first access, agent-created accounts/tokens, service accounts, and human-light onboarding.
- [x] Add OAuth-native MCP onboarding so Codex/Claude-style clients can connect directly without a dashboard-created token.
- [ ] Add OAuth refresh tokens or silent re-authorization for long-lived MCP desktop client sessions.
- [ ] Add connected-agent management UI grouped by OAuth client, including revoke and last-used metadata.
- [ ] Add agent-auth FTUE handoff that prompts for YouTube read access and playlist setup after MCP OAuth approval.
- [x] Add public agent-readable discovery endpoints (`/llms.txt`, `/llms-full.txt`, `/mcp.json`, `/.well-known/mcp.json`).
- [x] Add machine-readable MCP agent quickstart (`context://agent-quickstart`, `get_agent_quickstart`) for low-friction onboarding.
- [x] Surface agent guide and MCP manifest links in Settings so users can hand setup URLs to Hermes/Claude/Codex.
- [x] Add and locally install a Hermes `memexai-context` skill plus MCP config snippet for low-friction agent setup.
- [x] Surface reusable env-var Hermes MCP config in Settings so users can copy setup without exposing stored tokens.
- [x] Return and surface a copyable MCP setup bundle with endpoint URLs, first calls, one-time token config, and user-scoped access rules.
- [x] Add repo_context validation/normalization so agents can bring compact repo data through their own MCP tools without a hosted GitHub connection.
- [x] Add explicit repo_context contract discovery over MCP (`context://repo-context-contract`, `get_repo_context_contract`).
- [x] Surface agent quickstart and repo_context first steps in Settings so users can hand agents the exact opening MCP calls.
- [x] Expand repo_context with codebase implementation signals: entrypoints, dependencies, commands, tests, deployment facts, and active changes.
- [x] Publish repo_context as reusable JSON Schema in MCP contracts, tool input schemas, and public discovery.
- [x] Add repo_context readiness guidance so agents know when to inspect more repo details before implementation briefs.
- [x] Make build_agent_brief surface repo_context readiness in suggested next actions so agents improve thin repo context before implementation planning.
- [x] Update repo_implementation_brief prompt to validate repo_context readiness before calling build_agent_brief for implementation plans.
- [x] Align Settings first steps, agent quickstart examples, and public docs around validate_repo_context before build_agent_brief.
- [x] Add a collect_repo_context MCP prompt so agents can prepare validated repo_context before requesting implementation briefs.
- [x] Surface collect_repo_context in agent quickstart examples, public manifest coverage, and Settings first steps.
- [x] Name collect_repo_context as the repo-context collection prompt in public MCP workflow metadata and agent guides.
- [x] Publish machine-readable collect_repo_context expected output and readiness gate metadata for lower-friction repo-via-MCP agents.
- [x] Add a dedicated repo-context workflow MCP resource/tool so agents can discover the repo-via-MCP flow without parsing broader quickstart docs.
- [x] Add copyable JSON-RPC examples for repo-context workflow resource/tool discovery.
- [x] Return machine-readable next_mcp_call guidance from repo_context validation so agents know what MCP call to make next.
- [x] Add MCP session introspection (`get_mcp_session`) so agents can confirm scopes, guardrails, and safe next calls immediately after connecting.
- [x] Add first-class `repo_context.symbols` support so repo MCP agents can pass precise functions/classes/components/workflows without storing source code.
- [x] Add first-class `repo_context.locations` support so repo MCP agents can pass compact path/symbol/line anchors without sending file contents.
- [x] Add grouped `repoFit.targetMap` output to agent briefs so repo MCP agents can consume files, symbols, locations, commands, tests, runtime targets, and constraints without re-parsing flat touchpoints.
- [x] Make semantic search access provenance explicit so user-scoped results can reuse shared canonical videos without muddying global vs granted context.
- [x] Extend access provenance to library and full video-context MCP surfaces so agents can explain channel, explicit video, and reused canonical grants before searching.
- [x] Reconcile source-context RLS policies so explicit `user_videos` grants can read transcript-derived context, labels, concepts, and artifacts.
- [x] Surface user-selected YouTube playlist capture sources in Settings with add/list/sync controls.
- [x] Add opt-in MCP `ingest:write` path so agents can queue YouTube links from chat sessions into hosted ingestion jobs.
- [x] Schedule MCP-queued ingestion jobs in the hosted FastAPI runtime and expose MCP job-status tools.
- [x] Add a bulk-ingestion guardrail so MCP playlist/channel submissions require explicit `allow_bulk`.
- [x] Document ingestion cost risk, cost surfaces, and recommended agent submission guardrails.
- [x] Investigate hosted dependency cleanup before removing anything: LangChain, ChromaDB, OSS-only scripts, and unused ingestion/search paths.
- [x] Remove the local Chroma runtime path from the hosted fork (`ingest_chroma.py`, `rag_chroma.py`, `requirements-local.txt`) and make Supabase the only storage mode.
- [x] Write a hard-concerns retrieval/ingestion plan for hybrid search, agent search modes, gbrain-style video digestion, quotas, and token budgets.
- [x] Add an external-brain sync direction so personal agents/centralized brain systems can pull compact video knowledge through MCP without direct DB access.
- [x] Expose a DB-free MCP brain sync contract (`context://brain-sync-contract`, `get_brain_sync_contract`) for external personal-brain setup.
- [x] Draft BYO agent runtime/storage architecture for Codex/Hermes subscriptions, BYOK model spend, local Postgres sidecars, and user-owned Supabase/Postgres.
- [x] Generalize the category taxonomy and knowledge-extraction prompt so Memexai is universal for saved YouTube topics, not AI/ML-only.
- [x] Add a dry-run/apply legacy Chroma-to-Supabase bridge script with cost estimates for the 30-video local corpus.
- [x] Migrate or reingest the 30-video legacy local corpus into Supabase so hosted MCP can be tested against real saved-video data.
- [x] Run `scripts/legacy_chroma_supabase_import.py --apply --create-eval-user` using reused local Chroma embeddings, avoiding duplicate Gemini embedding spend for the current 30-video corpus.
- [x] Add a retrieval eval fixture using the local 30-video corpus and Sierra sample, with expected video IDs/timestamp ranges for entity-heavy, conceptual, and implementation queries.
- [x] Add universal-topic retrieval eval cases across cooking, repair, history, music, fitness/health, shopping/reviews, and education so retrieval quality is not tuned only for AI/product videos.
- [x] Add Supabase full-text indexes and a `search_chunks_hybrid` RPC that fuses vector, keyword, title, and category candidates while preserving `user_videos`/`user_channels` access gates.
- [x] Add `search_video_moments` retrieval modes (`hybrid`, `semantic`, `keyword`) and return `retrievalPlan`, `matchType`, and `retrievalBudget`; concept/artifact retrieval is covered by `search_video_concepts`.
- [x] Add MCP concept/artifact search (`search_video_concepts` or equivalent) so agents can search source knowledge before pulling timestamp clips.
- [x] Add MCP response-budget controls (`detail_level`, `max_chars`/`max_context_tokens`, estimated response size) so default agent searches stay compact.
- [x] Add incremental external-brain digest export with per-user cursor, `since`, object filters, access provenance, and compact-by-default response budgets.
- [x] Add optional outbound sync outbox events for connected personal brains after ingestion, knowledge publishing, overlay note creation, and capture-source sync.
- [ ] Add outbound sync delivery worker/webhook dispatch for queued `external_brain_sync_events`.
- [x] Add Codex setup bundle in Settings (`~/.codex/config.toml` MCP snippet, first calls, auth boundary guidance) alongside Hermes setup.
- [ ] Add BYOK model-spend controls for embeddings and source-knowledge digestion so users can pay with API keys instead of platform model spend.
- [x] Research and decide whether Codex subscription usage can be connected only through a user-owned local runner/MCP client, or whether any safe hosted Codex-subscription passthrough exists.
- [x] Prototype read-only local Postgres/pgvector sidecar mirror so Codex/Hermes can search granted video context on the user's machine.
- [ ] Prototype local Postgres/pgvector ingestion mode after the read-only sidecar sync contract works.
- [ ] Add user-owned Supabase/Postgres checklist and migration runner only after local sidecar and hosted BYOK paths are stable.
- [x] Add ingestion cost-estimate fields for playlist/channel jobs: discovered videos, already-indexed videos, videos to embed, transcript seconds, embedding chars/tokens, and digest LLM calls.
- [x] Add optional digest depth (`none`, `basic`, `standard`, `deep`) so users and agents can choose cheaper or richer video digestion.
- [ ] Add web UI controls for digest depth after agent defaults and costs are validated.
- [x] Add Sierra podcast sample fixture and runbook for ingestion, categorization, study-guide, timestamp-search, and repo-aware brief evaluation.
- [x] Use the recent Sierra head-of-product harness podcast (`https://www.youtube.com/watch?v=uCKhOmth2ms`) as a sample ingestion, categorization, study-guide, and agent-brief test.

# Local Dev Server Bring-Up

- [x] Start backend with local auth bypass enabled.
- [x] Start Vite frontend with local auth bypass enabled.
- [x] Verify health/config endpoints and browser URL.

# Model Version Refresh

- [x] Update stale Gemini model references across docs and code comments.
- [x] Keep the transcript embedding default on the current text-only Gemini embedding model unless schema/vector dimensions are migrated.
- [x] Verify no deprecated Gemini 2.0 model references remain.
- [x] Run focused verification for model/config changes.

- [x] Create a production setup branch from merged `main`.
- [x] Keep Cloudflare auth/deploy actions blocked until the correct account is active.
- [x] Switch branch posture to hosted production fork instead of OSS-compatible mode.
- [x] Document the Cloudflare-first production architecture.
- [x] Add production env scaffolding and CORS origin configuration.
- [x] Add durable ingestion job schema and progress API.
- [x] Add a background ingestion runner suitable for a container/Queue consumer.
- [x] Surface hosted ingestion jobs in the frontend.
- [x] Add clearer skipped-video reasons and partial-success ingestion reporting.
- [x] Add hosted readiness check for required production env.
- [x] Add lint, format, security hygiene, CI, and safety/ethics docs.
- [x] Add hosted-mode smoke script for local public API surfaces, linked Supabase schema, and Google OAuth provider state.
- [ ] Verify Supabase hosted mode end-to-end locally. Automated hosted smoke passes public API, linked schema, and Google OAuth redirect checks; remaining blocker is interactive sign-in verification against the deployed app.
- [x] Link the repo to the `embedmoments` Supabase project (`favppxodzkmnjvhlrpbq`) and apply initial hosted schema migrations.
- [x] Add root Supabase CLI project scaffolding, standard migrations, and generated database types.
- [x] Authenticate Cloudflare with the production owner account using browser OAuth for `cadecr@gmail.com`.
- [x] Create Cloudflare Pages project and deploy frontend test to the personal Cloudflare account.
- [ ] Rotate the Cloudflare API token pasted into chat.
- [ ] Add real Cloudflare Pages frontend env vars for Supabase and API URL.
- [ ] Add `memexai.xyz`, `www.memexai.xyz`, and `api.memexai.xyz` after Cloudflare DNS/routes are ready.
- [ ] Move backend to Cloudflare Containers after runtime validation.

# Product Surface Refresh

- [x] Re-read the Claude Botanical Brutalism design system.
- [x] Replace the unauthenticated login-only gate with a polished public homepage.
- [x] Add a polished authenticated product dashboard/workbench.
- [x] Remove stale SearchTube/GitHub login UI from the hosted fork.
- [x] Verify the frontend and inspect it in browser.
- [x] Continue local-only UI/web polish before any further Cloudflare deployment.
- [x] Remove self-link product-domain nav from the homepage.
- [x] Improve homepage product story, use cases, and proof sections.
- [x] Refine dashboard hierarchy and softer Botanical Brutalist containers.
- [x] Sweep remaining UI pages, modals, and components for Memexai design consistency.
- [x] Replace grid-style textures with richer paper, ink, and botanical color depth.
- [x] Restyle library, indexing jobs, settings, result detail, answer, toast, and legacy ingestion surfaces.
- [x] Verify the refreshed UI locally across homepage, dashboard, library, jobs, and settings.
- [x] Rework landing hero away from faux UI illustration toward minimal brutalist architectural art.
- [x] Remove decorative landing-page badges, simplify hero CTAs, and add restrained reveal motion.
- [x] Slow the landing reveal and add scroll-triggered section/card reveals.
- [x] Replace the timestamp detail block with a video-to-timestamp-chunks scroll animation.
- [x] Simplify the chunking visual into a cleaner anime-inspired source-to-timestamps panel.
- [x] Remove stale graph/fake-video CSS so the simplified chunking visual is actually what renders.
- [x] Keep Supabase as the near-term hosted database decision; revisit Cloudflare-native DB only if Cloudflare adds relational vector storage or if Vectorize plus D1 becomes worth the integration tradeoff.

# Dashboard Context Engine Redesign

- [x] Reframe the authenticated dashboard from moment search to a video context engine workspace.
- [x] Surface YouTube capture status, capture sources, MCP agent access, onboarding readiness, jobs, usage, and library health on the dashboard.
- [x] Refresh app-shell/dashboard copy so Memexai reads as an agent-ready YouTube context layer, not a transcript paste/search tool.
- [x] Let signed-in users revisit the public homepage after authentication.
- [x] Update homepage title, metadata, CTA behavior, and product story for the expanded context-engine scope.
- [x] Keep dashboard actions wired to real product capabilities instead of placeholder panels.
- [x] Verify the redesigned dashboard with frontend tests, typecheck, build, and screenshot harness.

# Auth Beta

- [x] Add explicit Google OAuth redirects for Supabase hosted auth.
- [x] Keep beta auth to a single Google OAuth action.
- [x] Remove over-explaining auth mechanics from the landing page.
- [x] Harden backend Supabase bearer-token validation.
- [x] Verify unauthenticated landing, auth header, and backend 401 behavior.

# Free-Tier Quotas

- [x] Add hosted free-tier quota config with env overrides.
- [x] Add Supabase migration for monthly search, indexed video, transcript-second, and usage log fields.
- [x] Refactor quota helpers for monthly hosted searches, lifetime indexing/storage caps, and BYOK model-spend bypass.
- [x] Enforce transcript-hour and video caps in single-video, channel, and playlist ingestion.
- [x] Prevent shared-channel subscription quota bypass.
- [x] Enforce hosted result-limit cap and update `/api/usage`.
- [x] Update dashboard/settings usage UI and BYOK copy.
- [x] Add backend and frontend quota tests.
- [x] Run full verification and fix regressions.

# Design Overhaul - Modern Light Editorial (June 2026)

- [x] New design token system: text-safe deep accents (rose/teal/violet/leaf), soft layered shadows, hairline borders, `.card/.input/.chip/.eyebrow/.btn*/.link-quiet/.glow-wash` classes replacing all `botanical-*`/`brutal-*` classes.
- [x] Font swap: Cormorant Garamond -> Fraunces (editorial display serif); JetBrains Mono reduced to timestamps/code only.
- [x] Landing page redesigned: typographic hero, whitespace section rhythm, CSS-built product vignette (replaced brutalist PNGs), confident copy refresh.
- [x] App shell: backdrop-blur header, segmented pill nav, NEW mobile hamburger menu (previously no mobile nav), modernized footer/about/contact/results view.
- [x] All app views restyled: ProductDashboard, UnifiedSearchView, LibraryView, IngestionJobsView, SettingsModal (added dialog semantics + Escape close).
- [x] Accessibility: global :focus-visible, fixed reduced-motion CSS bug (was breaking toast centering), WCAG AA contrast for accent text, aria-labels on icon buttons.
- [x] Playwright screenshot harness: `npm run screenshots` captures all views at 1440px + 390px (scripts/screenshots.mjs).
- [x] Cleanup: deleted dead IngestionView.tsx, orphaned brutalist PNGs, all legacy CSS; zero `botanical-`/`brutal-` references remain.
- [x] Full `npm run verify` green (lint, format, typecheck, build, 13/13 tests, security, audit).

# Hosted Deploy Pending

- [x] Apply migrations 003-021 to the linked Supabase project with `npx supabase db push`, including hybrid search, quotas, MCP/context tables, access grants, category filters, workflow state, external-brain sync, YouTube OAuth, MCP OAuth, FTUE onboarding state, search provenance, and source-context RLS reconciliation.

# Current UI Correction Pass

- [x] Make the authenticated dashboard input/search-first with URL ingestion as the central work surface.
- [x] Remove the dashboard context-ready/setup container and move usage into the right-side support area.
- [x] Keep product education and playlist/agent value copy on the public landing page, not in the user dashboard.
- [x] Make the Memexai logo visibly render in the app shell, landing page, favicon, and touch icon.
- [x] Merge saved videos and generated source knowledge into one compact Library view instead of separate "Videos" and "Video Breakdown" surfaces.
- [x] Add intuitive Library search mode tabs for smart, semantic, and exact retrieval.
- [x] Remove nonessential Library metric cards and code-like/internal labels from the customer view.
- [x] Make generated guides open as readable modal artifacts instead of repeated timestamp links.
- [x] Make key ideas use human text links to source timestamps instead of repeated "Open video" actions.
- [x] Remove raw transcript-chunk "timestamped moments" as a primary Library section until they can be synthesized into coherent highlights.
- [x] Rebalance the dashboard so Usage/Library support the input area and Imports/YouTube capture fill the lower grid without a lopsided empty floor.
- [x] Add a clear-history action for completed/failed import jobs and remove "needs review" wording where there is no review workflow.
- [x] Add a better human navigation layer for the library: videos, topics, and recent searches.
- [x] Redesign Settings into a wider modal with compact sections and collapsed agent setup.
- [x] Remove visible local-dev/backend status, localhost endpoints, and public agent-doc links from customer-facing UI.
- [x] Reframe landing copy around curated saved-video memory, video breakdowns, and agents avoiding repeated pasted-link ingestion or blind web search.
- [x] Compact Settings modal layout, remove hosted/model-access filler, and keep agent connection expanded.
- [x] Verify the UI with focused tests, typecheck, and fresh screenshots before claiming the changes are visible.

# Library Source Graph Inspector

- [x] Map current ingestion, source-context, MCP, search, and frontend library surfaces with subagent support.
- [x] Add user-scoped backend graph/search helpers that expose videos, channels, labels, concepts, edges, artifacts, notes, and review flags without embeddings or LLM calls.
- [x] Add authenticated REST endpoints for the library graph snapshot and component keyword search.
- [x] Expose the graph snapshot and component keyword search over MCP for agent-side review.
- [x] Upgrade the Library Video Breakdown surface into a video-centered review view with generated guides, key ideas, timestamped moments, saved thumbnails/media, and clip links.
- [x] Surface edge-case QA for missing transcripts, missing source knowledge, weak evidence refs, duplicate grants, stale metadata, and potential cross-video conflicts.
- [x] Remove source-health/QA diagnostics, raw graph rows, labels, edges, and code-like node identifiers from the customer Library UI.
- [x] Rework the Library Video Breakdown mobile UI into readable sections for the selected video, video search, guides, key ideas, and timestamped moments.
- [x] Replace raw timestamp labels like `videoId @ 5:02` with human links like `Open at 5:02`.
- [x] Verify the Library Video Breakdown mobile view at 390px for no horizontal overflow.
- [x] Add focused backend/frontend tests and run verification commands before completion.

# Library Context Maintenance

- [x] Reframe video card deletion as user-scoped "remove from library" instead of deleting shared canonical video/chunk/source-knowledge rows.
- [x] Make direct single-video imports create precise `user_videos` grants so individual videos can be removed without broad channel access side effects.
- [ ] Backfill existing historical single-video ingestion jobs into precise `user_videos` grants so older saved videos can be removed individually too.
- [ ] Add a per-user hidden/excluded-video table so users can remove or hide individual videos that came from playlist/channel grants without deleting shared embeddings.
- [ ] Add bulk library actions: select videos, remove selected, clear failed imports, clear search history, and optionally disconnect/remove a capture source.
- [ ] Add context maintenance views for large libraries: stale videos, low-quality/no-transcript sources, duplicate topics, weak source-graph evidence, and videos never retrieved by agents.
- [ ] Add retention/archival controls so users can keep source records but exclude old or low-value videos from default MCP/search context.
- [ ] Add orphaned canonical-source garbage collection that deletes shared video/chunk/source-knowledge rows only after no user grants, channel grants, overlays, or sync references remain.

# Library Guide Quality and UX Correction

- [x] Trace ingestion, source-knowledge extraction, REST graph, and MCP context flow for generated guides and key ideas.
- [x] Preserve full guide artifact content in the Library graph/UI instead of replacing readable guides with 220-character node summaries.
- [x] Strengthen the source-knowledge extraction prompt and depth budgets so standard/deep guides contain sections, themes, quotes, questions, and action items instead of two-sentence summaries.
- [x] Redesign Library navigation for scale: searchable saved videos, topic cards, full guides, and recent searches as distinct views.
- [x] Turn key ideas into clickable timestamp topic cards with source snippets and exact YouTube links.
- [x] Add focused backend/frontend tests and run verification for Library context quality, UI behavior, and MCP access.

# GBrain-Aligned Video Context

- [x] Inspect the private gbrain repo structure enough to calibrate against company/person/project pages without exposing private contents.
- [x] Reframe video study guides as gbrain-style entity pages with Compiled Truth, Agent Quick Index, people/orgs/tools, claims, decisions, timeline, and evidence sections.
- [x] Preserve timestamp source anchors inside generated guide content so agents can retrieve structured objects before transcript evidence.
- [x] Increase generated-artifact MCP detail budgets so deep mode can return the contextual breakdown instead of forcing raw transcript scanning.
- [x] Add tests proving the richer guide fields survive extraction, formatting, source refs, and compact source-knowledge retrieval.
- [x] Replace sparse guide/example expectations with explicit word-count, paragraph-level, no-placeholder, timestamp-backed requirements.
- [x] Add an offline report-lift eval comparing Memexai source reports against raw transcript scanning for agent navigation efficiency.
- [x] Make guide/report length adaptive to video duration while preserving one uniform analysis contract for every indexed video.
- [x] Clarify MCP OAuth onboarding so agents can initiate account/login/approval without forcing dashboard-created tokens.

# Library Report Presentation Correction

- [x] Replace customer-facing "study guide"/"guide" language with TLDR and source report language.
- [x] Render generated report markdown structure as headings, bullets, paragraphs, and source timestamp links instead of raw `#`, `##`, and `-` text.
- [x] Make topic cards timestamp-first and hide non-source-backed static topics from the Key Ideas/Topics surfaces.
- [x] Update backend generated artifact titles and extraction prompt language to call the artifact a source report, while preserving existing artifact-type compatibility.
- [x] Add regression tests for rendered report structure, source timestamp links, and timestamped topic cards.
- [x] Verify locally, then redeploy the updated frontend/API surfaces.

# Stripe Paid-Tier Subscription Plan

- [x] Decide paid tier packaging: Free, Plus at $12 monthly/$120 annual, Pro at $29 monthly/$288 annual, transcript-hour quotas over raw video counts, no Stripe trial, no BYOK quota bypass, and no Team plan in v1.
- [x] Create the approved pricing and Stripe handoff spec at `docs/PAID_PRICING_AND_STRIPE_HANDOFF.md`.
- [x] Create Stripe sandbox products/prices for Memexai paid subscription and optional annual price; keep stable Price IDs or lookup keys for backend config.
- [x] Add hosted billing schema fields/tables for Stripe customer IDs, subscription IDs, price IDs, subscription status, current period end, cancel-at-period-end, and resolved entitlement/plan state.
- [x] Add backend config/secrets for `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, Stripe Plus/Pro lookup keys, `STRIPE_SUCCESS_URL`, `STRIPE_CANCEL_URL`, and `STRIPE_PORTAL_RETURN_URL`.
- [x] Add FastAPI billing endpoints: create Checkout session for the authenticated user, create Customer Portal session, return current billing status, and expose paid-tier limits through `/api/usage`.
- [x] Add a raw-body Stripe webhook endpoint that verifies `Stripe-Signature`, stores processed event IDs idempotently, and updates hosted entitlement state from Checkout, subscription, invoice, and entitlement events.
- [x] Refactor quota helpers so `check_search_quota`, `check_index_quota`, import caps, result caps, and active-job caps resolve limits from the user's hosted plan instead of free-only env vars.
- [x] Update dashboard/settings UI with a paid plan status, upgrade action, manage billing action, failed-payment/past-due messaging, and no local-tier customer copy.
- [x] Add tests for checkout creation, portal creation, webhook signature failure, duplicate webhook idempotency, paid quota resolution, and free fallback.
- [ ] Add explicit subscription cancelation/downgrade tests after Stripe sandbox fixtures are available.
- [x] Apply billing migration `022_stripe_billing.sql` to the linked Supabase project and smoke-test Checkout session creation against Stripe sandbox.
- [x] Create the Stripe sandbox webhook endpoint, deploy API runtime Stripe secrets to Cloudflare, and verify the production webhook with a signed smoke event.
- [x] Switch Stripe runtime to live keys, create the live webhook endpoint, deploy live secrets to Cloudflare, and verify the production webhook with a signed live-mode smoke event.
- [x] Fix live-mode checkout after sandbox testing by replacing stale Stripe test customer IDs on first live checkout, surfacing backend billing errors, and adding a plan-detail selector before redirecting to Stripe.
- [x] Replace the inline Settings upgrade expansion with a dedicated plan-selection view/modal and visually verify it on desktop and mobile before redeploying.
- [ ] Verify with Stripe CLI sandbox: checkout success, monthly renewal/invoice paid, payment failed, portal cancelation, subscription deleted, and entitlements update all produce correct Supabase state.

# Project-Scoped Video Context

- [x] Add user-owned project and project-video membership schema with RLS.
- [x] Add project-aware search/library RPC filtering without changing existing access grants.
- [x] Add backend project CRUD, video assignment, and project-scoped library/search endpoints.
- [x] Attach capture playlists to one default project and sync successful videos into that project.
- [x] Add MCP project listing, project context maps, scoped retrieval inputs, and updated agent guidance.
- [x] Add dashboard/library UI for creating projects, assigning videos, linking playlists, and switching project scopes.
- [x] Add backend, MCP, and frontend regression tests for project scope behavior.
- [x] Run verification before shipping.

# Project-Scoped Context Cloudflare Deploy And Production MCP Eval

- [x] Confirm Wrangler is authenticated to the intended Cloudflare account.
- [x] Apply the project-scoped Supabase migration to production.
- [x] Re-run deploy-quality checks before shipping.
- [x] Deploy the API container worker to Cloudflare.
- [x] Deploy the frontend to Cloudflare Pages.
- [x] Smoke-test production API, app, and MCP discovery.
- [x] Run production MCP retrieval evals against `cadecr@gmail.com`.
- [x] Compare MCP answers against local BashGym/Ghostwork project context for relevance, speed, and response size.

# Project UX Follow-Up

- [x] Add user-scoped playlist disconnect for capture sources without disconnecting YouTube OAuth.
- [x] Fix mobile project/capture settings layouts so long playlist URLs and project controls wrap cleanly.
- [x] Make projects easier to browse/search and open as a selected Library scope from Dashboard and Library.
- [x] Create a production project for `cadecr@gmail.com` from the existing linked playlist/videos if safe.
- [x] Run frontend/backend tests and deploy the project UX fixes.

# First-Class Projects Navigation

- [x] Add a top-level Projects navigation item on desktop and mobile.
- [x] Add a Projects section inside the Library menu.
- [x] Render a dedicated project management view that works even before a user has indexed videos.
- [x] Update dashboard project actions to send users to Projects management when appropriate.
- [x] Add/adjust regression tests, verify, and deploy.

# Claude MCP Connector Setup

- [x] Audit current website and public docs for Claude connector setup instructions.
- [x] Add Claude custom connector setup instructions to the user-facing Settings agent connection surface.
- [x] Update public/MCP setup metadata so agents and users see OAuth-first Claude guidance before token fallback.
- [x] Document the Anthropic Connector Directory submission path and readiness checklist.
- [x] Add/update regression tests and run focused verification.
