# Production Hosted Setup

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
- [ ] Verify Supabase hosted mode end-to-end locally. Supabase URL, anon key, and service role key are now available in `.env.local`; remaining blocker is hosted auth provider configuration / sign-in verification.
- [x] Link the repo to the `embedmoments` Supabase project (`favppxodzkmnjvhlrpbq`) and apply initial hosted schema migrations.
- [x] Add root Supabase CLI project scaffolding, standard migrations, and generated database types.
- [x] Authenticate Cloudflare with the production owner account using a temporary API token.
- [x] Create Cloudflare Pages project and deploy frontend test.
- [ ] Rotate the Cloudflare API token pasted into chat.
- [ ] Add real Cloudflare Pages frontend env vars for Supabase and API URL.
- [ ] Add custom domain after production name is chosen.
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
- [x] Sweep remaining UI pages, modals, and components for Embed Moments design consistency.
- [x] Replace grid-style textures with richer paper, ink, and botanical color depth.
- [x] Restyle library, indexing jobs, settings, result detail, answer, toast, and legacy ingestion surfaces.
- [x] Verify the refreshed UI locally across homepage, dashboard, library, jobs, and settings.
- [x] Rework landing hero away from faux UI illustration toward minimal brutalist architectural art.
- [x] Remove decorative landing-page badges, simplify hero CTAs, and add restrained reveal motion.
- [x] Slow the landing reveal and add scroll-triggered section/card reveals.
- [x] Replace the timestamp detail block with a video-to-timestamp-chunks scroll animation.
- [x] Simplify the chunking visual into a cleaner anime-inspired source-to-timestamps panel.
- [x] Remove stale graph/fake-video CSS so the simplified chunking visual is actually what renders.
- [ ] Keep Supabase as the near-term hosted database decision; revisit Cloudflare-native DB only if Cloudflare adds relational vector storage or if Vectorize plus D1 becomes worth the integration tradeoff.

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

- [ ] Apply migrations 003 (quotas) and 004 (search_chunks RPC) to the linked Supabase project: `npx supabase db push`. Remote currently has only 001-002; search_chunks exists remotely only as an untracked ad-hoc function - reconcile with 004 when pushing.
