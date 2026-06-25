# Memexai Cloudflare Orchestrator

This Worker is the deployable Cloudflare Workflows prototype for Memexai.
It coordinates long-running platform flows while the Python/FastAPI backend
remains the system that writes canonical Supabase state.

## Flows

- `CapturePlaylistSyncWorkflow` validates a user capture-source request, then
  calls `POST /internal/workflows/capture-sync` on the hosted API. The hosted
  API performs playlist diffing, records workflow state in Supabase, and
  dispatches bounded ingestion jobs.
- `VideoIngestionWorkflow` validates an existing ingestion job envelope and
  sends a versioned `ingestion_job.process` message to Cloudflare Queues.

## Required Secrets

Set these with Wrangler before exposing the Worker:

```bash
npx wrangler secret put ORCHESTRATOR_SHARED_SECRET -c workers/orchestrator/wrangler.toml
npx wrangler secret put MEMEXAI_WORKFLOW_SECRET -c workers/orchestrator/wrangler.toml
```

The hosted API must use the same value for `WORKFLOW_INTERNAL_SECRET` that the
Worker stores as `MEMEXAI_WORKFLOW_SECRET`.

## Local/Preview Commands

```bash
npx wrangler dev -c workers/orchestrator/wrangler.toml
npx wrangler deploy -c workers/orchestrator/wrangler.toml
```

Do not deploy until the Cloudflare account, queue name, API URL, and secrets
are production-owned.
