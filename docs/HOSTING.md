# Hosted Deployment

Last checked: 2026-05-31

## Recommended Launch Stack

Use Cloudflare for the production web edge. This fork is hosted-product-first: Supabase auth/storage and a server-side Gemini key are the defaults.

| Layer                     | Provider                                          | First production choice                       |
| ------------------------- | ------------------------------------------------- | --------------------------------------------- |
| Frontend                  | Cloudflare Pages                                  | Vite static build from `dist`                 |
| API                       | Cloudflare Containers or temporary container host | Existing FastAPI app with Python dependencies |
| Async jobs                | Cloudflare Workflows + Queues, later              | Durable orchestration plus ingestion queue    |
| Auth + database + vectors | Supabase                                          | Existing auth, Postgres, and pgvector adapter |
| AI                        | Gemini Developer API                              | Server-side hosted key with app quotas        |

Cloudflare Python Workers can run FastAPI, but Memexai ingestion depends on transcript and scraping libraries that need runtime validation before we replace the container path. Cloudflare Containers are the better Cloudflare-native target for the current backend because they can run the existing Python app and filesystem-oriented dependencies.

## What We Can Do Without Cloudflare Auth

Safe setup before Cloudflare auth:

```bash
python scripts/check_hosted_readiness.py
npm run smoke:hosted
npm run typecheck
npm run build
npm test
python -m compileall backend
python -c "import backend.server"
python -m pytest
```

Prepare hosted env values from [.env.production.example](../.env.production.example). Local development still runs on your machine, but it should point at the hosted Supabase project; the old local Chroma/no-auth storage mode has been removed from this hosted fork.

The readiness script checks required env values without printing secrets. It must pass before a meaningful hosted-mode local smoke test can run.
After readiness passes, run `npm run smoke:hosted` to verify the local FastAPI public surfaces,
linked Supabase schema, and Google OAuth provider state without printing secrets. A failure like
`Unsupported provider: provider is not enabled` means Google OAuth still needs to be enabled in
Supabase Auth before the interactive auth e2e can be called done.

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
Production domain target: https://memexai.xyz
API domain target: https://api.memexai.xyz
Previous preview project: https://searchtube-hosted-preview.pages.dev
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

Install hosted Python dependencies with:

```bash
pip install -r requirements.txt
```

Install only `requirements.txt` in the hosted runtime. ChromaDB/local storage dependencies are no
longer part of this fork.

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
WORKFLOW_INTERNAL_SECRET=...
```

Start with hybrid mode for the hosted beta when BYOK is enabled. User keys cover AI requests,
while hosted indexing and storage caps still apply.

## Queue Consumer Runtime

Hosted ingestion can run from a dedicated queue-consumer image:

```bash
docker build -f Dockerfile.queue-consumer -t memexai-queue-consumer .
docker run --env-file .env.local memexai-queue-consumer
```

For a local/container-hosted smoke path:

```bash
docker compose --profile queue up queue-consumer
```

Healthcheck/config validation:

```bash
python -m backend.queue_consumer --healthcheck
python -m backend.queue_consumer --once --batch-size 1
```

Queue consumer env:

```text
INGESTION_DISPATCH_MODE=cloudflare_queue
CLOUDFLARE_ACCOUNT_ID=...
CLOUDFLARE_INGESTION_QUEUE_ID=...
CLOUDFLARE_QUEUES_API_TOKEN=...
INGESTION_QUEUE_PULL_BATCH_SIZE=1
INGESTION_QUEUE_VISIBILITY_TIMEOUT_MS=3600000
INGESTION_QUEUE_IDLE_SLEEP_SECONDS=5
INGESTION_QUEUE_ERROR_SLEEP_SECONDS=10
INGESTION_QUEUE_MAX_CONSECUTIVE_ERRORS=10
```

Cloudflare HTTP pull must be enabled on the queue before the pull consumer can run:

```bash
npx wrangler queues consumer http add memexai-ingestion
```

Use a Cloudflare API token with Queues read and write permissions. Write permission is required
because acknowledging or retrying pulled messages mutates queue state.

## Supabase

Enable the `vector` extension, then apply the tracked migrations in
[backend/supabase/migrations](../backend/supabase/migrations) or
[supabase/migrations](../supabase/migrations). The linked `embedmoments` Supabase project has
001-013 applied, covering the base schema, ingestion jobs, hosted quotas, search RPCs,
source-knowledge/overlay tables, MCP tokens, source labels, YouTube capture sources, workflow
state, precise `user_videos` access grants, category filters, search access provenance, and
source-context RLS reconciliation.

Auth settings:

```text
Site URL: https://your-cloudflare-domain
Redirect URLs:
  https://your-cloudflare-domain/**
  https://your-project.pages.dev/**
  http://localhost:3000/**
```

Use Google OAuth for the first beta. Base sign-in uses `openid`, `email`, and `profile`; the playlist capture flow should request `https://www.googleapis.com/auth/youtube.readonly` when the user connects YouTube playlist sync. Keep the service-role key backend-only, and provide the anon key to the backend so it can validate bearer tokens through Supabase Auth.

## Cloudflare-Native Migration Path

1. Launch the frontend on Cloudflare Pages.
2. Run the existing FastAPI backend in a normal container runtime while validating hosted usage.
3. Use the durable ingestion job schema and `/api/ingestion-jobs` endpoints for hosted progress tracking.
4. Enable `INGESTION_DISPATCH_MODE=cloudflare_queue` so hosted queued ingestion publishes to Cloudflare Queues through the HTTP Push API.
5. Run `Dockerfile.queue-consumer` or `docker compose --profile queue up queue-consumer` as the first pull-based container worker to process queue messages.
6. Deploy the Cloudflare Workflows prototype from [workers/orchestrator](../workers/orchestrator) once the queue, API URL, and secrets are production-owned:
   ```bash
   npx wrangler secret put ORCHESTRATOR_SHARED_SECRET -c workers/orchestrator/wrangler.toml
   npx wrangler secret put MEMEXAI_WORKFLOW_SECRET -c workers/orchestrator/wrangler.toml
   npx wrangler deploy -c workers/orchestrator/wrangler.toml
   ```
   `MEMEXAI_WORKFLOW_SECRET` must match backend `WORKFLOW_INTERNAL_SECRET`.
7. Evaluate Cloudflare Vectorize only after Supabase pgvector cost or complexity becomes a real problem.

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
npm run smoke:hosted
npm run typecheck
npm run build
npm test
npm audit --audit-level=moderate
python -m compileall backend
python -c "import backend.server"
python -m pytest
```
