# Production Cloudflare Setup

Status: Draft  
Last updated: 2026-06-02

## Decision

Use Cloudflare as the production web edge immediately, but do not force the whole backend onto Cloudflare in the first production pass.

This is now a hosted production fork, not an OSS-compatible branch. Supabase auth/storage and server-managed Gemini access are the product defaults.

Recommended staged setup:

1. **Production app branch/repo** from current `main`.
2. **Cloudflare Pages** for the React/Vite frontend.
3. **Supabase** for auth, Postgres, and pgvector.
4. **Existing FastAPI backend** in a container runtime for the first launch validation, with Cloudflare Containers as the preferred Cloudflare-native target once account/auth is ready and we have confirmed runtime fit.
5. Later evaluate **Cloudflare Python Workers/FastAPI**, **Queues**, **Containers**, and **Vectorize** as a full Cloudflare-native rewrite.

Why staged:

- Cloudflare Pages is low-risk for the frontend.
- The current Python ingestion path uses libraries that are safest in a normal Python/container runtime.
- Cloudflare Python Workers now support FastAPI, but production ingestion still needs dependency/runtime validation.
- Cloudflare Containers can run arbitrary runtimes, but they require account setup, Wrangler auth, and a paid Workers plan.

## What We Can Do Before Cloudflare Auth

We can prepare everything locally without logging into Cloudflare:

- Create a production branch.
- Strip or ignore open-source/local mode surfaces.
- Add production env templates.
- Add hosted readiness checks.
- Add Cloudflare Pages static routing/security files.
- Add deployment documentation and manual setup checklist.
- Add background ingestion job schema and API design.
- Add Supabase migrations for production job tracking.
- Keep Cloudflare deploy commands documented but do not run them.

Do not run yet:

- `wrangler login`
- `wrangler deploy`
- `wrangler pages deploy`
- Cloudflare project creation
- Cloudflare secrets write commands
- Any push to a production repo

Before any hosted smoke test, run:

```bash
python scripts/check_hosted_readiness.py
```

The script reports missing or placeholder env values without printing secrets.

## Cloudflare Account Tasks For Later

Current Wrangler token auth has been tested against:

```text
Account: Cade@ghostpeony.com's Account
Account ID: 7d58001c6a1b56b22eb2a763e9481cb2
Pages project: searchtube-hosted-preview
Pages URL: https://searchtube-hosted-preview.pages.dev
```

The API token used for this test was pasted into chat, so rotate it after the deployment test.

When you are ready to authenticate with browser OAuth instead of a token:

1. Create or log into the Cloudflare account you want to own production.
2. Install/authenticate Wrangler:
   ```bash
   npx wrangler login
   npx wrangler whoami
   ```
3. Create a Pages project from the dashboard or CLI.
4. Add production frontend env vars:
   ```text
   VITE_AUTH_MODE=supabase
   VITE_API_URL=https://api.your-domain.com
   VITE_SUPABASE_URL=https://your-project.supabase.co
   VITE_SUPABASE_ANON_KEY=your-supabase-anon-key
   ```
5. Add custom domain after the app name is chosen.

## Track A: Fastest Production Launch On Cloudflare Edge

Use this if the priority is getting a real hosted beta online quickly.

Architecture:

```text
Cloudflare Pages       React/Vite frontend
API container runtime  FastAPI backend
Supabase               Auth + Postgres + pgvector
Gemini                 Embeddings + answer model
```

Hosted setup work:

- Keep `SEARCHTUBE_STORAGE=supabase`.
- Keep `SEARCHTUBE_AUTH_MODE=supabase`.
- Keep `SEARCHTUBE_API_KEY_MODE=hybrid` when BYOK is enabled for beta users.
- Set `SEARCHTUBE_ALLOWED_ORIGINS` to the Cloudflare Pages production and preview domains.
- Set `SUPABASE_ANON_KEY` in the backend runtime so bearer tokens can be validated through Supabase Auth.
- Use Google OAuth for beta auth; Google should request only sign-in scopes, not YouTube scopes.
- Allow BYOK for AI requests, while keeping hosted indexing/storage caps in place.
- Add durable ingestion jobs before public launch.
- Use `GET /api/ingestion-jobs` and `GET /api/ingestion-jobs/{job_id}` for hosted progress/history.
- Add admin usage views before public launch.

Cloudflare setup:

- Pages build command: `npm run build`
- Output directory: `dist`
- Node version: `22`
- SPA fallback: `_redirects`
- Security headers: `_headers`

Backend setup:

- Run the current FastAPI app from `Dockerfile.backend` while validating production traffic.
- Move that image behind Cloudflare Containers after `wrangler whoami` confirms the correct account.
- Add Queues before large public imports so ingestion is not tied to one request/response lifecycle.

## Track B: Cloudflare-Native Backend

Use this after the hosted beta shape is proven.

Options:

### Python Workers/FastAPI

Cloudflare now supports FastAPI in Python Workers. This is attractive for lightweight API routes, but must be validated against SearchTube's dependencies:

- `youtube-transcript-api`
- `scrapetube`
- `langchain-google-genai`
- `supabase`
- network behavior for YouTube transcript fetching

Best fit:

- `/api/config`
- `/api/profile`
- `/api/usage`
- lightweight search endpoints if dependencies work

Risk:

- Ingestion may still be better in Containers because it is long-running and dependency-heavy.

### Cloudflare Containers

Containers are the better Cloudflare-native fit for the existing FastAPI app and ingestion work.

Best fit:

- Existing Dockerfile/Python backend.
- Long-running transcript/indexing jobs.
- Dependency-heavy scraping/transcript libraries.

Risk:

- Requires Workers Paid plan and Wrangler setup.
- Need to design request routing from Worker to Container.
- Need to verify cold start and job duration behavior.

### Cloudflare Queues

Queues are the right primitive for production ingestion jobs.

Best fit:

- User submits index request.
- API inserts `ingestion_jobs` row.
- API enqueues work.
- Consumer processes videos, updates progress, stores chunks.

Risk:

- Requires Cloudflare account setup and queue bindings.
- In local dev, we need a fallback runner.

### Cloudflare Vectorize

Vectorize is worth evaluating later, but not for the first production rewrite.

Best fit:

- If we move away from Supabase pgvector.
- If we want Cloudflare-native vector search at the edge.

Risk:

- We would need to rebuild metadata filtering, user scoping, joins, transcript storage, admin views, and migration tooling.

## Production Refinement Backlog

Before a public hosted beta:

- Add durable ingestion jobs:
  - `queued`
  - `running`
  - `completed`
  - `failed`
  - `partial`
- Add skipped-video reasons:
  - no captions
  - captions disabled/unavailable
  - restricted/private
  - fetch error
  - quota exceeded
- Add background worker/runner.
- Add job progress endpoint.
- Add admin usage view.
- Keep BYOK deliberately enabled only when user-key support is part of the beta policy.
- Restrict CORS to production domains.
- Add Cloudflare Pages `_headers` and `_redirects`.
- Add production env docs.
- Add smoke test checklist.
- Remove stale non-Cloudflare deployment configs from the hosted fork.

## Suggested Immediate Local Sequence

1. Keep this branch local until Cloudflare auth is ready.
2. Rename product/brand only after name is chosen.
3. Add production-only docs/config under a hosted repo or hosted branch.
4. Implement durable ingestion jobs while still running locally.
5. Run `python scripts/check_hosted_readiness.py`, then verify Supabase hosted mode end-to-end locally.
6. Then authenticate Cloudflare and deploy the frontend.
7. Move backend to Cloudflare Containers only after the hosted beta works on the container-hosted backend.

## References

- Cloudflare Pages supports Vite static deployments through the Workers & Pages flow.
- Cloudflare Python Workers support FastAPI through the Workers runtime ASGI server: https://developers.cloudflare.com/workers/languages/python/packages/fastapi/
- Cloudflare Containers can run arbitrary runtime/Docker workloads behind Workers: https://developers.cloudflare.com/containers/
- Cloudflare Queues provide durable producer/consumer message queues for async work: https://developers.cloudflare.com/queues/get-started/
- Cloudflare Pages supports Wrangler config and static build output configuration: https://developers.cloudflare.com/pages/functions/wrangler-configuration/
