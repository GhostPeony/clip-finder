# Workflow Orchestration Architecture

Status: architecture proposal for Memexai platform workflows.

Implemented foundation:

- `workflow_definitions`, `workflow_instances`, `workflow_steps`, and `workflow_artifacts` migrations.
- Backend workflow helpers for creating instances, listing definitions/runs, recording steps/artifacts, and patching status.
- Read-only REST workflow status endpoints.
- Read-only MCP `context://workflows`, `context://workflow/{workflowInstanceId}`, `list_workflow_runs`, and `get_workflow_run`.
- Hosted ingestion dispatch abstraction with local background execution and Cloudflare Queue HTTP publishing modes.
- Cloudflare Queue pull-consumer module that processes `ingestion_job.process` messages with the same Python hosted-ingestion runner.
- Manual playlist capture sync now runs through a durable hosted workflow runner:
  `capture.playlist.sync` creates a workflow instance, records sync and dispatch steps,
  publishes a `capture_sync_result` artifact, and returns a workflow handle agents can poll.
- Cloudflare Workflows prototype scaffold in `workers/orchestrator`:
  `CapturePlaylistSyncWorkflow` triggers the hosted capture-sync bridge, while
  `VideoIngestionWorkflow` publishes existing ingestion job envelopes to Cloudflare Queues.
- Internal FastAPI bridge `POST /internal/workflows/capture-sync` for Cloudflare Workflows.
  It requires `X-Memexai-Workflow-Secret` and reuses the same hosted Python workflow runner.

## Recommendation

Use Cloudflare as the orchestration edge, not as the only database or vector store.

- Cloudflare Workflows: durable coordinators for multi-step ingestion, capture sync, eval, and release flows.
- Cloudflare Queues: fanout, batching, retries, delays, and dead-letter handling for item-level work.
- Cloudflare Containers: Python-heavy execution for transcript fetching, chunking, embeddings, and knowledge extraction.
- Supabase/Postgres/pgvector: canonical state, RLS, user data, workflow records, artifacts, vectors, and MCP-readable context.
- MCP: the agent-facing interface for read-only source context, job status, context bundles, briefs, and approved overlay or ingestion writes.

The core rule: workflows orchestrate state transitions; source knowledge remains provenance-backed and read-only over MCP.

## Why This Fits Memexai

Cloudflare Workflows are a good match for long-running, inspectable platform flows because they persist step state, retry steps, wait for external events, and support approval-style pauses. That maps directly to transcript ingestion, human review, and release gates.

Cloudflare Queues are a good match for high-volume item work. A playlist sync may discover 200 videos, but the platform should fan those into bounded item messages, batch where possible, retry safely, and route terminal failures to a dead-letter queue.

Cloudflare Containers are the right bridge for the existing Python backend. The current ingestion stack depends on Python libraries and model/storage helpers that are better validated in a normal Linux-like runtime than in an isolate-only worker.

Supabase should stay the system of record because it already gives us auth, RLS, relational joins, pgvector, durable jobs, usage limits, and user-scoped MCP data. Moving vectors to Cloudflare Vectorize should remain a later scaling decision, not the first orchestration move.

## Sierra-Inspired Product Loop

The Sierra podcast maps well to a three-part Memexai loop:

- Analyze: monitors, evals, category drift, transcript quality, retrieval quality, and user/agent questions.
- Build: workflow definitions, prompts, extraction schemas, repo-context briefs, and agent instructions.
- Release: approved versions of knowledge artifacts, prompts, MCP resources, and workflow behavior.

The useful lesson is not to copy Sierra's customer-support product. It is to make every workflow inspectable, versioned, evaluatable, and easy for the person or agent with the most context to improve.

## Platform Primitives

### Workflow Definitions

Store versioned workflow definitions in Postgres, optionally mirrored to Git later.

Suggested shape:

```json
{
  "key": "video.ingest.v1",
  "version": 3,
  "trigger": "youtube.video.submitted",
  "inputs": ["user_id", "source_url", "youtube_video_id"],
  "steps": [
    "validate_source",
    "fetch_metadata",
    "fetch_transcript",
    "chunk_transcript",
    "embed_chunks",
    "extract_source_knowledge",
    "categorize_video",
    "run_quality_evals",
    "publish_context"
  ],
  "policies": {
    "max_transcript_seconds": "plan_limit",
    "requires_approval_above_cost_estimate_cents": 50,
    "source_context_write_mode": "system_only"
  },
  "outputs": ["video", "chunks", "source_labels", "source_concepts", "source_artifacts"]
}
```

This is the Memexai equivalent of Sierra's "journeys": declarative enough to inspect and edit, but deterministic enough to compile into known execution paths.

### Workflow Instances

Every submitted URL, playlist sync, eval run, and generated brief should have an instance record.

Minimum fields:

- `id`
- `user_id`
- `workflow_key`
- `workflow_version`
- `status`
- `input`
- `current_step`
- `cost_estimate`
- `created_by`
- `created_by_client`
- `started_at`
- `completed_at`
- `error`

### Workflow Steps

Every step should emit durable events and artifacts.

Minimum fields:

- `workflow_instance_id`
- `step_key`
- `status`
- `attempt`
- `started_at`
- `completed_at`
- `input_ref`
- `output_ref`
- `error`
- `metrics`

Step outputs larger than small metadata should live in Postgres rows or R2, with references stored on the workflow step.

## Core Workflows

### 1. Capture Source Sync

Trigger:

- User clicks sync.
- Scheduled polling runs.
- Future YouTube OAuth webhook or cron-like schedule fires.

Flow:

1. Load capture source.
2. Fetch playlist items.
3. Diff against `youtube_capture_items`.
4. Insert discovered items.
5. Estimate ingest cost.
6. Queue bounded video ingestion messages.
7. Update source status and recent item state.

Best primitives:

- Workflow for the sync coordinator.
- Queue for each video ingestion candidate.
- Supabase for dedupe and status.

### 2. Video Ingestion

Trigger:

- MCP `queue_youtube_ingestion`.
- Capture sync discovered video.
- User submits a direct URL.

Flow:

1. Validate URL and ownership.
2. Fetch metadata.
3. Fetch transcript.
4. Chunk transcript.
5. Write transcript lines and chunks.
6. Embed chunks.
7. Extract knowledge graph artifacts.
8. Categorize and label.
9. Run quality checks.
10. Publish to MCP-readable context.

Best primitives:

- Workflow for step-level orchestration and retry.
- Container for Python transcript/model work.
- Queue for video-level and batch embedding fanout.
- Supabase for durable source context.

Current dispatch foundation:

- `capture.playlist.sync` currently runs in the hosted Python/FastAPI runtime as the first
  durable coordinator. It is shaped to move behind Cloudflare Workflows later without changing the
  MCP/REST status surface.
- `workers/orchestrator` is the first deployable Cloudflare Workflows prototype. It keeps
  orchestration in Cloudflare, but canonical playlist diffing, Supabase writes, source-context
  publication, and quota logic remain in the hosted backend.
- `POST /workflows/capture-sync` on the Worker creates a `CapturePlaylistSyncWorkflow` instance.
  That workflow calls the backend internal bridge with `MEMEXAI_WORKFLOW_SECRET`, which must
  match backend `WORKFLOW_INTERNAL_SECRET`.
- `POST /workflows/video-ingestion` on the Worker creates a `VideoIngestionWorkflow` instance for
  a pre-created ingestion job and sends a versioned `ingestion_job.process` queue message.
- `ORCHESTRATOR_SHARED_SECRET` protects the Worker trigger routes from unauthenticated callers.
- `INGESTION_DISPATCH_MODE=background`: schedule the existing Python runner with FastAPI `BackgroundTasks`.
- `INGESTION_DISPATCH_MODE=cloudflare_queue`: publish a versioned `ingestion_job.process` message directly to the Cloudflare Queues HTTP Push API.
- `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_INGESTION_QUEUE_ID`, and `CLOUDFLARE_QUEUES_API_TOKEN` configure direct queue publishing.
- `CLOUDFLARE_INGESTION_QUEUE_API_URL` can override the generated API URL when needed.
- `python -m backend.queue_consumer` runs the first pull-based container consumer.
- `INGESTION_QUEUE_PULL_BATCH_SIZE`, `INGESTION_QUEUE_VISIBILITY_TIMEOUT_MS`, and `INGESTION_QUEUE_IDLE_SLEEP_SECONDS` tune consumption.
- `Dockerfile.queue-consumer` packages the pull consumer as a dedicated worker image with
  `python -m backend.queue_consumer --healthcheck`.
- `docker compose --profile queue up queue-consumer` runs the supervised pull-consumer path
  locally or on a plain container host before moving it behind Cloudflare Containers.

### 3. Knowledge Release

Trigger:

- Ingestion completed.
- Extraction schema changes.
- User or agent asks to reprocess a video.

Flow:

1. Create draft knowledge artifacts.
2. Run extraction quality checks.
3. Compare with previous artifact version.
4. Auto-publish if low risk, otherwise request approval.
5. Expose approved version through MCP.

Best primitives:

- Workflow with `waitForEvent` for approval.
- Supabase for draft/published artifact versions.
- MCP resources return published source context by default.

### 4. Agent Brief / Spec Generation

Trigger:

- MCP `build_agent_brief`.
- User generates a study guide or project brief.

Flow:

1. Resolve query and optional repo context.
2. Retrieve candidate clips/concepts.
3. Rerank and assemble evidence.
4. Generate brief.
5. Store optional artifact if user or agent requests persistence.

Best primitives:

- Synchronous path for small briefs.
- Workflow for durable, expensive, or multi-repo briefs.
- Supabase for stored artifacts and citations.

### 5. Monitors And Evals

Trigger:

- New ingestion.
- Scheduled library quality run.
- Schema/prompt/model version changes.
- User thumbs up/down or agent feedback.

Flow:

1. Sample videos/chunks.
2. Run retrieval evals.
3. Detect transcript/extraction/category issues.
4. Suggest fixes or reprocessing.
5. Require approval unless confidence and blast radius are low.

Best primitives:

- Workflow for monitor runs.
- Queue for batch eval items.
- Supabase for eval results and recommendations.

## MCP Interaction Model

MCP should stay mostly read-only and fast:

- Read source context.
- Read categories.
- Read capture source status.
- Search moments.
- Build briefs.
- Write personal overlay notes/concepts.
- Queue ingestion only with explicit `ingest:write`.

Long-running workflows should return handles:

- `workflow_instance_id`
- `ingestion_job_id`
- `status_resource_uri`
- `recommended_next_poll_at`

Agents should not block on transcript ingestion. They should submit, poll, and use the source only after the workflow publishes it.

## Efficiency Rules

- Keep user-facing HTTP and MCP calls short.
- Use Workflows for cross-step state and human approval.
- Use Queues when a step fans out across videos, chunks, eval cases, or embeddings.
- Use Containers only for workloads that need Python libraries, filesystem behavior, or heavier runtime support.
- Make every step idempotent with stable keys such as `user_id + video_id + workflow_version`.
- Batch embeddings and writes when the platform can tolerate latency.
- Store large intermediate output by reference, not inside workflow step return values.
- Use dead-letter queues for terminal failures.
- Keep Supabase unique constraints as the final dedupe guard.
- Emit enough events for users and agents to explain what happened.

## What Not To Do Yet

- Do not move all source/vector state to Cloudflare Vectorize before pgvector becomes a proven bottleneck.
- Do not run Python transcript ingestion in Python Workers until dependency/runtime behavior is validated.
- Do not make every small transformation its own queue message; queue fanout should match useful retry and cost boundaries.
- Do not let agents mutate source transcript or source knowledge graph records directly.
- Do not auto-apply generated improvements until eval confidence and user trust are much higher.

## Implementation Slices

1. Add workflow tables for definitions, instances, steps, and artifacts. Done.
2. Wrap the existing ingestion job runner in a local workflow runner interface.
3. Add Cloudflare Queue producer config for hosted ingestion messages. Done.
4. Add a queue consumer that calls the existing Python runner in a Container or pull-based container worker. Done.
5. Convert direct background task scheduling to queue dispatch in production mode.
6. Add capture sync as the first durable hosted workflow runner. Done.
   6b. Move the capture sync coordinator behind Cloudflare Workflows. Prototype scaffold done; deployment and production trigger wiring remain.
7. Add video ingestion as the second Cloudflare Workflow. Prototype queue coordinator done; full ingestion-step orchestration remains.
8. Add monitor/eval workflow that proposes, but does not auto-apply, changes.
9. Surface workflow instance status through REST and MCP. Done.
10. Add an internal workflow editor/viewer so prompts, extraction schemas, gates, and policies are easy to iterate.
