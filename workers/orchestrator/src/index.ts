import { WorkflowEntrypoint } from 'cloudflare:workers';

type WorkflowCreateResult = {
  id: string;
  status?: string;
};

type WorkflowBinding<T> = {
  create(options: { id?: string; params: T }): Promise<WorkflowCreateResult>;
};

type QueueBinding<T> = {
  send(message: T): Promise<void>;
};

export interface Env {
  CAPTURE_SYNC_WORKFLOW: WorkflowBinding<CaptureSyncParams>;
  VIDEO_INGESTION_WORKFLOW: WorkflowBinding<VideoIngestionParams>;
  INGESTION_QUEUE: QueueBinding<IngestionQueueMessage>;
  MEMEXAI_API_URL: string;
  MEMEXAI_WORKFLOW_SECRET: string;
  ORCHESTRATOR_SHARED_SECRET: string;
}

type WorkflowEvent<T> = {
  payload: T;
};

type WorkflowStep = {
  do<T>(name: string, callback: () => T | Promise<T>): Promise<T>;
  do<T>(
    name: string,
    options: { retries?: { limit: number; delay: string; backoff?: 'constant' | 'exponential' } },
    callback: () => T | Promise<T>,
  ): Promise<T>;
};

type CaptureSyncParams = {
  user_id: string;
  capture_source_id: string;
  max_jobs: number;
  created_by_client?: string;
};

type VideoIngestionParams = {
  source?: string;
  job: {
    id: string;
    user_id: string;
    source_url: string;
    source_type?: string;
    status?: string;
  };
};

type IngestionQueueMessage = {
  type: 'ingestion_job.process';
  version: 1;
  source: string;
  job: {
    id: string;
    user_id: string;
    source_url: string;
    source_type: string;
    status: string;
  };
};

const JSON_HEADERS = {
  'content-type': 'application/json; charset=utf-8',
};

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (request.method === 'GET' && url.pathname === '/health') {
      return jsonResponse({
        status: 'ok',
        service: 'memexai-orchestrator',
        workflows: ['capture.playlist.sync', 'video.ingestion'],
      });
    }

    if (request.method === 'POST' && url.pathname === '/workflows/capture-sync') {
      const authError = requireOrchestratorSecret(request, env);
      if (authError) return authError;

      const params = validateCaptureSyncParams(await readJson(request));
      const instance = await env.CAPTURE_SYNC_WORKFLOW.create({
        id: captureSyncWorkflowId(params),
        params,
      });
      return jsonResponse(
        {
          workflow: 'capture.playlist.sync',
          id: instance.id,
          status: instance.status ?? 'started',
        },
        202,
      );
    }

    if (request.method === 'POST' && url.pathname === '/workflows/video-ingestion') {
      const authError = requireOrchestratorSecret(request, env);
      if (authError) return authError;

      const params = validateVideoIngestionParams(await readJson(request));
      const instance = await env.VIDEO_INGESTION_WORKFLOW.create({
        id: videoIngestionWorkflowId(params),
        params,
      });
      return jsonResponse(
        {
          workflow: 'video.ingestion',
          id: instance.id,
          status: instance.status ?? 'started',
        },
        202,
      );
    }

    return jsonResponse({ error: 'Not found' }, 404);
  },
};

export class CapturePlaylistSyncWorkflow extends WorkflowEntrypoint<Env, CaptureSyncParams> {
  async run(event: WorkflowEvent<CaptureSyncParams>, step: WorkflowStep): Promise<unknown> {
    const params = await step.do('validate capture sync payload', () =>
      validateCaptureSyncParams(event.payload),
    );

    const hostedResult = await step.do(
      'run hosted capture sync',
      { retries: { limit: 3, delay: '30 seconds', backoff: 'exponential' } },
      () => callHostedCaptureSync(this.env, params),
    );

    return {
      workflow: 'capture.playlist.sync',
      hosted_workflow_instance_id: getString(hostedResult, 'workflow_instance_id'),
      queued_job_count: getNumber(hostedResult, 'queuedJobCount'),
      capture_source_id: params.capture_source_id,
    };
  }
}

export class VideoIngestionWorkflow extends WorkflowEntrypoint<Env, VideoIngestionParams> {
  async run(event: WorkflowEvent<VideoIngestionParams>, step: WorkflowStep): Promise<unknown> {
    const message = await step.do('build ingestion queue message', () =>
      buildIngestionQueueMessage(validateVideoIngestionParams(event.payload)),
    );

    await step.do(
      'send ingestion queue message',
      { retries: { limit: 3, delay: '15 seconds', backoff: 'exponential' } },
      () => this.env.INGESTION_QUEUE.send(message),
    );

    return {
      workflow: 'video.ingestion',
      queued: true,
      ingestion_job_id: message.job.id,
      source: message.source,
    };
  }
}

async function callHostedCaptureSync(
  env: Env,
  params: CaptureSyncParams,
): Promise<Record<string, unknown>> {
  const response = await fetch(apiUrl(env, '/internal/workflows/capture-sync'), {
    method: 'POST',
    headers: {
      ...JSON_HEADERS,
      'X-Memexai-Workflow-Secret': env.MEMEXAI_WORKFLOW_SECRET,
    },
    body: JSON.stringify(params),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Hosted capture sync failed: ${response.status} ${body}`);
  }

  return asRecord(await response.json());
}

function buildIngestionQueueMessage(params: VideoIngestionParams): IngestionQueueMessage {
  return {
    type: 'ingestion_job.process',
    version: 1,
    source: params.source || 'cloudflare-workflow:video-ingestion',
    job: {
      id: params.job.id,
      user_id: params.job.user_id,
      source_url: params.job.source_url,
      source_type: params.job.source_type || 'video',
      status: params.job.status || 'queued',
    },
  };
}

function validateCaptureSyncParams(input: unknown): CaptureSyncParams {
  const payload = asRecord(input);
  return {
    user_id: requiredString(payload, 'user_id'),
    capture_source_id: requiredString(payload, 'capture_source_id'),
    max_jobs: clampInteger(payload.max_jobs, 0, 5, 1),
    created_by_client: optionalString(payload, 'created_by_client'),
  };
}

function validateVideoIngestionParams(input: unknown): VideoIngestionParams {
  const payload = asRecord(input);
  const job = asRecord(payload.job);
  return {
    source: optionalString(payload, 'source'),
    job: {
      id: requiredString(job, 'id'),
      user_id: requiredString(job, 'user_id'),
      source_url: requiredString(job, 'source_url'),
      source_type: optionalString(job, 'source_type'),
      status: optionalString(job, 'status'),
    },
  };
}

async function readJson(request: Request): Promise<unknown> {
  try {
    return await request.json();
  } catch {
    throw new Error('Request body must be valid JSON');
  }
}

function requireOrchestratorSecret(request: Request, env: Env): Response | null {
  const expected = env.ORCHESTRATOR_SHARED_SECRET?.trim();
  if (!expected) {
    return jsonResponse({ error: 'Orchestrator secret is not configured' }, 503);
  }

  const provided = request.headers.get('X-Memexai-Orchestrator-Secret') || '';
  if (provided !== expected) {
    return jsonResponse({ error: 'Invalid orchestrator secret' }, 401);
  }
  return null;
}

function captureSyncWorkflowId(params: CaptureSyncParams): string {
  return `capture-sync:${params.user_id}:${params.capture_source_id}`;
}

function videoIngestionWorkflowId(params: VideoIngestionParams): string {
  return `video-ingestion:${params.job.id}`;
}

function apiUrl(env: Env, path: string): string {
  return `${env.MEMEXAI_API_URL.replace(/\/+$/, '')}${path}`;
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload, null, 2), {
    status,
    headers: JSON_HEADERS,
  });
}

function asRecord(input: unknown): Record<string, unknown> {
  if (!input || typeof input !== 'object' || Array.isArray(input)) {
    throw new Error('Expected object payload');
  }
  return input as Record<string, unknown>;
}

function requiredString(payload: Record<string, unknown>, key: string): string {
  const value = payload[key];
  if (typeof value !== 'string' || !value.trim()) {
    throw new Error(`${key} is required`);
  }
  return value.trim();
}

function optionalString(payload: Record<string, unknown>, key: string): string | undefined {
  const value = payload[key];
  if (value === undefined || value === null || value === '') {
    return undefined;
  }
  if (typeof value !== 'string') {
    throw new Error(`${key} must be a string`);
  }
  return value.trim() || undefined;
}

function clampInteger(input: unknown, min: number, max: number, fallback: number): number {
  const value = typeof input === 'number' ? input : Number(input ?? fallback);
  if (!Number.isFinite(value)) {
    return fallback;
  }
  return Math.max(min, Math.min(Math.floor(value), max));
}

function getString(payload: Record<string, unknown>, key: string): string | null {
  const value = payload[key];
  return typeof value === 'string' ? value : null;
}

function getNumber(payload: Record<string, unknown>, key: string): number {
  const value = payload[key];
  return typeof value === 'number' ? value : 0;
}
