# Hosted Deployment

Last checked: 2026-05-31

## Recommended Launch Stack

Use Cloudflare for the production web edge. This fork is hosted-product-first: Supabase auth/storage and a server-side Gemini key are the defaults.

| Layer                     | Provider                                          | First production choice                       |
| ------------------------- | ------------------------------------------------- | --------------------------------------------- |
| Frontend                  | Cloudflare Pages                                  | Vite static build from `dist`                 |
| API                       | Cloudflare Containers or temporary container host | Existing FastAPI app with Python dependencies |
| Async jobs                | Cloudflare Queues, later                          | Durable ingestion work queue                  |
| Auth + database + vectors | Supabase                                          | Existing auth, Postgres, and pgvector adapter |
| AI                        | Gemini Developer API                              | Server-side hosted key with app quotas        |

Cloudflare Python Workers can run FastAPI, but SearchTube ingestion depends on transcript and scraping libraries that need runtime validation before we replace the container path. Cloudflare Containers are the better Cloudflare-native target for the current backend because they can run the existing Python app and filesystem-oriented dependencies.

## What We Can Do Without Cloudflare Auth

Safe setup before Cloudflare auth:

```bash
python scripts/check_hosted_readiness.py
npm run typecheck
npm run build
npm test
python -m compileall backend
python -c "import backend.server"
python -m pytest
```

Prepare hosted env values from [.env.production.example](../.env.production.example). Local development still runs on your machine, but it should point at the hosted Supabase project instead of the old local/no-auth mode.

The readiness script checks required env values without printing secrets. It must pass before a meaningful hosted-mode local smoke test can run.

Do not run these until the correct Cloudflare account is active:

```bash
npx wrangler login
npx wrangler whoami
npx wrangler pages deploy dist
npx wrangler deploy
```

## Cloudflare Pages

Current test project:

```text
Project: searchtube-hosted-preview
URL: https://searchtube-hosted-preview.pages.dev
Deployment: https://a4094c35.searchtube-hosted-preview.pages.dev
```

Deploy manually:

```bash
npm run deploy:pages
```

Create the final Pages project from the Cloudflare dashboard after the production name is chosen, or keep this project and attach the final custom domain later.

Settings:

```text
Framework preset: Vite
Build command: npm run build
Build output directory: dist
Node version: 22
```

Frontend environment variables:

```text
VITE_AUTH_MODE=supabase
VITE_API_URL=https://api.your-domain.com
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-supabase-anon-key
```

[public/\_redirects](../public/_redirects) keeps client-side routes working on refresh. [public/\_headers](../public/_headers) adds basic static security headers.

## Backend Runtime

Production backend env:

```text
SEARCHTUBE_STORAGE=supabase
SEARCHTUBE_AUTH_MODE=supabase
SEARCHTUBE_API_KEY_MODE=hybrid
SEARCHTUBE_ALLOWED_ORIGINS=https://your-domain.com,https://your-project.pages.dev
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_ANON_KEY=...
SUPABASE_JWT_SECRET=...
API_KEY_ENCRYPTION_KEY=...
GEMINI_API_KEY=...
EMBEDDING_MODEL=models/gemini-embedding-001
EMBEDDING_DIMENSIONS=768
LLM_MODEL=gemini-3.1-flash-lite
FREE_SEARCHES_PER_MONTH=100
FREE_INDEXED_VIDEOS_TOTAL=15
FREE_INDEXED_TRANSCRIPT_SECONDS_TOTAL=18000
FREE_MAX_IMPORT_VIDEOS=10
FREE_MAX_SEARCH_RESULTS=5
FREE_MAX_ACTIVE_INGESTION_JOBS=1
```

Start with hybrid mode for the hosted beta when BYOK is enabled. User keys cover AI requests,
while hosted indexing and storage caps still apply.

## Supabase

Enable the `vector` extension, then apply:

1. [backend/supabase/migrations/001_initial_schema.sql](../backend/supabase/migrations/001_initial_schema.sql)
2. [backend/supabase/migrations/002_ingestion_jobs.sql](../backend/supabase/migrations/002_ingestion_jobs.sql)
3. [backend/supabase/migrations/003_free_tier_quotas.sql](../backend/supabase/migrations/003_free_tier_quotas.sql)

Auth settings:

```text
Site URL: https://your-cloudflare-domain
Redirect URLs:
  https://your-cloudflare-domain/**
  https://your-project.pages.dev/**
  http://localhost:3000/**
```

Use Google OAuth for the first beta. Google OAuth should request only sign-in scopes (`openid`, email, profile); users paste public YouTube URLs after sign-in, and the app should not request YouTube API scopes until a later owner-channel import feature needs them. Keep the service-role key backend-only, and provide the anon key to the backend so it can validate bearer tokens through Supabase Auth.

## Cloudflare-Native Migration Path

1. Launch the frontend on Cloudflare Pages.
2. Run the existing FastAPI backend in a normal container runtime while validating hosted usage.
3. Use the durable ingestion job schema and `/api/ingestion-jobs` endpoints for hosted progress tracking.
4. Move ingestion to Cloudflare Queues plus either a Container consumer or pull-based worker.
5. Evaluate Cloudflare Vectorize only after Supabase pgvector cost or complexity becomes a real problem.

## Cost Guardrails

Start with:

```text
Free hosted search quota: 100 searches/user/month
Free hosted library quota: 15 indexed/accessed videos total
Free hosted transcript quota: 5 transcript-hours total
Max channel/playlist import: first 10 eligible videos per import
Max search results: 5 clips per search
Max active imports: 1 queued/running ingestion job per user
Gemini billing: low budget alert/cap
Supabase: spend cap enabled
Cloudflare: Workers Paid only when Containers/Queues are actually needed
```

## Preflight

Before publishing the hosted URL:

```bash
python scripts/check_hosted_readiness.py
npm run typecheck
npm run build
npm test
npm audit --audit-level=moderate
python -m compileall backend
python -c "import backend.server"
python -m pytest
```
