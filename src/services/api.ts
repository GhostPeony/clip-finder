import {
  VideoClip,
  LibraryData,
  LibraryComponentSearchData,
  LibraryComponentType,
  LibraryGraphNode,
  LibrarySourceGraphData,
  SearchHistoryEntry,
  IngestionJob,
  McpTokenRecord,
  CreatedMcpToken,
  CaptureSource,
  CaptureSourceSyncResult,
  OnboardingStatus,
  ProjectContextMap,
  ProjectsData,
  SaveYoutubeOAuthConnectionRequest,
  UserProject,
  YoutubeOAuthStatus,
} from '../types';
import { supabase } from '../lib/supabase';
import { AppConfig, isSupabaseAuth } from '../config';

// Use the hosted API by default; local dev can override with VITE_API_URL.
const API_BASE = import.meta.env.VITE_API_URL || 'https://api.memexai.xyz';
const API_URL = `${API_BASE}/api`;
const LIBRARY_CACHE_MAX_AGE_MS = 5 * 60 * 1000;
const LIBRARY_GRAPH_CACHE_MAX_AGE_MS = 5 * 60 * 1000;
const INGESTION_JOBS_CACHE_MAX_AGE_MS = 15 * 1000;
const LIBRARY_CACHE_PREFIX = 'memexai:library-cache:v1';

interface AuthContext {
  headers: Record<string, string>;
  cacheScope: string;
}

interface JsonCacheEnvelope<T> {
  scope: string;
  storedAt: number;
  data: T;
}

// Get auth headers from Supabase session
async function getAuthContext(): Promise<AuthContext> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  let cacheScope = 'anonymous';

  if (isSupabaseAuth) {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session?.access_token) return { headers, cacheScope };
    headers['Authorization'] = `Bearer ${session.access_token}`;
    cacheScope = session.user?.id
      ? `supabase:${session.user.id}`
      : `supabase-token:${fingerprintString(session.access_token)}`;
  }

  const apiKey = isSupabaseAuth ? null : getStoredLocalApiKey();
  if (apiKey) {
    headers['X-API-Key'] = apiKey;
    cacheScope = `local-api-key:${fingerprintString(apiKey)}`;
  }

  return { headers, cacheScope };
}

async function getAuthHeaders(): Promise<Record<string, string>> {
  return (await getAuthContext()).headers;
}

const LOCAL_API_KEY = 'searchtube_local_api_key';

export const getStoredLocalApiKey = (): string | null => {
  if (typeof localStorage === 'undefined') return null;
  return localStorage.getItem(LOCAL_API_KEY);
};

export const saveStoredLocalApiKey = (apiKey: string): void => {
  localStorage.setItem(LOCAL_API_KEY, apiKey);
};

export const deleteStoredLocalApiKey = (): void => {
  localStorage.removeItem(LOCAL_API_KEY);
};

function fingerprintString(value: string): string {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = Math.imul(31, hash) + value.charCodeAt(index);
    hash |= 0;
  }
  return Math.abs(hash).toString(36);
}

function getSessionCacheStorage(): Storage | null {
  if (typeof sessionStorage === 'undefined') return null;
  return sessionStorage;
}

function cacheKey(name: string, suffix?: string | number): string {
  return `${LIBRARY_CACHE_PREFIX}:${name}${suffix === undefined ? '' : `:${suffix}`}`;
}

function projectScopeSuffix(projectId?: string | null): string {
  return projectId ? `project:${projectId}` : 'all';
}

function readJsonCache<T>(key: string, scope: string, maxAgeMs: number): T | null {
  try {
    const storage = getSessionCacheStorage();
    if (!storage) return null;
    const raw = storage.getItem(key);
    if (!raw) return null;
    const envelope = JSON.parse(raw) as JsonCacheEnvelope<T>;
    if (envelope.scope !== scope) return null;
    if (!envelope.storedAt || Date.now() - envelope.storedAt > maxAgeMs) return null;
    return envelope.data;
  } catch {
    return null;
  }
}

function writeJsonCache<T>(key: string, scope: string, data: T): void {
  try {
    const storage = getSessionCacheStorage();
    if (!storage) return;
    const envelope: JsonCacheEnvelope<T> = {
      scope,
      storedAt: Date.now(),
      data,
    };
    storage.setItem(key, JSON.stringify(envelope));
  } catch {
    // Storage can be unavailable in privacy modes; the network path remains authoritative.
  }
}

export const invalidateLibraryCaches = (): void => {
  try {
    const storage = getSessionCacheStorage();
    if (!storage) return;
    const keysToRemove: string[] = [];
    for (let index = 0; index < storage.length; index += 1) {
      const key = storage.key(index);
      if (key?.startsWith(LIBRARY_CACHE_PREFIX)) keysToRemove.push(key);
    }
    keysToRemove.forEach((key) => storage.removeItem(key));
  } catch {
    // Cache invalidation is a best-effort UI optimization.
  }
};

export const getCachedLibrary = async (projectId?: string | null): Promise<LibraryData | null> => {
  const { cacheScope } = await getAuthContext();
  return readJsonCache<LibraryData>(
    cacheKey('library', projectScopeSuffix(projectId)),
    cacheScope,
    LIBRARY_CACHE_MAX_AGE_MS,
  );
};

export const getCachedLibraryGraph = async (
  limit: number = 50,
  projectId?: string | null,
): Promise<LibrarySourceGraphData | null> => {
  const { cacheScope } = await getAuthContext();
  return readJsonCache<LibrarySourceGraphData>(
    cacheKey('library-graph', `${limit}:${projectScopeSuffix(projectId)}`),
    cacheScope,
    LIBRARY_GRAPH_CACHE_MAX_AGE_MS,
  );
};

export const getCachedIngestionJobs = async (): Promise<IngestionJob[] | null> => {
  const { cacheScope } = await getAuthContext();
  return readJsonCache<IngestionJob[]>(
    cacheKey('ingestion-jobs'),
    cacheScope,
    INGESTION_JOBS_CACHE_MAX_AGE_MS,
  );
};

export const fetchAppConfig = async (): Promise<AppConfig> => {
  try {
    const res = await fetch(`${API_URL}/config`);
    if (!res.ok) throw new Error(`Config error: ${res.statusText}`);
    return await res.json();
  } catch {
    return {
      storage: 'supabase',
      authMode: isSupabaseAuth ? 'supabase' : 'none',
      hasServerKey: false,
      apiKeyMode: 'server',
      allowUserKeys: false,
    };
  }
};

export const checkBackendHealth = async (): Promise<{
  connected: boolean;
  hasServerKey: boolean;
}> => {
  try {
    const res = await fetch(`${API_BASE}/`);
    if (res.ok) {
      const data = await res.json();
      return { connected: true, hasServerKey: data.hasApiKey || false };
    }
    return { connected: false, hasServerKey: false };
  } catch {
    return { connected: false, hasServerKey: false };
  }
};

export const fetchLibrary = async (projectId?: string | null): Promise<LibraryData> => {
  const { headers, cacheScope } = await getAuthContext();
  const params = new URLSearchParams();
  if (projectId) params.set('project_id', projectId);
  const url = params.toString() ? `${API_URL}/library?${params.toString()}` : `${API_URL}/library`;
  const response = await fetch(url, { headers });
  if (!response.ok) {
    throw new Error(`Backend Error: ${response.statusText}`);
  }
  const data = await response.json();
  writeJsonCache(cacheKey('library', projectScopeSuffix(projectId)), cacheScope, data);
  return data;
};

export const fetchProjects = async (): Promise<UserProject[]> => {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/projects`, { headers });
    if (!response.ok) return [];
    const data = (await response.json()) as ProjectsData;
    return data.projects || [];
  } catch (error) {
    console.warn('Error fetching projects:', error);
    return [];
  }
};

export const createProject = async (
  name: string,
  description: string = '',
): Promise<UserProject | null> => {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/projects`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ name, description }),
    });
    if (!response.ok) return null;
    const data = await response.json();
    invalidateLibraryCaches();
    return data.project || null;
  } catch (error) {
    console.warn('Error creating project:', error);
    return null;
  }
};

export const updateProject = async (
  projectId: string,
  updates: { name?: string; description?: string; status?: 'active' | 'archived' },
): Promise<UserProject | null> => {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/projects/${encodeURIComponent(projectId)}`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify(updates),
    });
    if (!response.ok) return null;
    const data = await response.json();
    invalidateLibraryCaches();
    return data.project || null;
  } catch (error) {
    console.warn('Error updating project:', error);
    return null;
  }
};

export const addProjectVideos = async (
  projectId: string,
  youtubeVideoIds: string[],
): Promise<{ project: UserProject; addedVideos: string[] } | null> => {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/projects/${encodeURIComponent(projectId)}/videos`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ youtube_video_ids: youtubeVideoIds, added_source: 'manual' }),
    });
    if (!response.ok) return null;
    const data = await response.json();
    invalidateLibraryCaches();
    return data;
  } catch (error) {
    console.warn('Error adding project videos:', error);
    return null;
  }
};

export const removeProjectVideo = async (
  projectId: string,
  youtubeVideoId: string,
): Promise<boolean> => {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(
      `${API_URL}/projects/${encodeURIComponent(projectId)}/videos/${encodeURIComponent(
        youtubeVideoId,
      )}`,
      {
        method: 'DELETE',
        headers,
      },
    );
    if (response.ok) invalidateLibraryCaches();
    return response.ok;
  } catch (error) {
    console.warn('Error removing project video:', error);
    return false;
  }
};

export const fetchProjectContextMap = async (
  projectId: string,
  limit: number = 25,
): Promise<ProjectContextMap | null> => {
  try {
    const headers = await getAuthHeaders();
    const params = new URLSearchParams({ limit: String(limit) });
    const response = await fetch(
      `${API_URL}/projects/${encodeURIComponent(projectId)}/context-map?${params.toString()}`,
      { headers },
    );
    if (!response.ok) return null;
    return await response.json();
  } catch (error) {
    console.warn('Error fetching project context map:', error);
    return null;
  }
};

const emptyLibraryGraph = (): LibrarySourceGraphData => ({
  version: 'memexai-library-source-graph-v1',
  limit: 50,
  accessModel: {
    scope: 'current_user_grants',
    visibilityGrants: ['user_videos', 'user_channels'],
    sourceTruth: 'read_only',
    provenanceFields: ['accessScope', 'accessSource', 'accessReason'],
  },
  videos: [],
  componentCounts: {
    videos: 0,
    channels: 0,
    sourceLabels: 0,
    sourceConcepts: 0,
    sourceEdges: 0,
    knowledgeArtifacts: 0,
    transcriptChunksSampled: 0,
    agentNotes: 0,
    personalConcepts: 0,
    reviewFlags: 0,
  },
  graph: {
    nodes: [],
    edges: [],
    selectedNodeId: null,
  },
  reviewFlags: [],
  edgeCaseHandling: [],
  guidance: '',
});

export const fetchLibraryGraph = async (
  limit: number = 50,
  projectId?: string | null,
): Promise<LibrarySourceGraphData> => {
  try {
    const { headers, cacheScope } = await getAuthContext();
    const params = new URLSearchParams({ limit: String(limit) });
    if (projectId) params.set('project_id', projectId);
    const response = await fetch(`${API_URL}/library/graph?${params.toString()}`, { headers });
    if (!response.ok) {
      throw new Error(`Backend Error: ${response.statusText}`);
    }
    const data = await response.json();
    writeJsonCache(
      cacheKey('library-graph', `${limit}:${projectScopeSuffix(projectId)}`),
      cacheScope,
      data,
    );
    return data;
  } catch (error) {
    console.warn('Error fetching library graph:', error);
    return emptyLibraryGraph();
  }
};

export const fetchLibraryArtifact = async (
  artifactId: string,
): Promise<LibraryGraphNode | null> => {
  try {
    const headers = await getAuthHeaders();
    const normalizedId = artifactId.replace(/^artifact:/, '');
    const response = await fetch(
      `${API_URL}/library/artifacts/${encodeURIComponent(normalizedId)}`,
      {
        headers,
      },
    );
    if (!response.ok) return null;
    return await response.json();
  } catch (error) {
    console.warn('Error fetching library artifact:', error);
    return null;
  }
};

export const searchLibraryComponents = async (
  query: string,
  limit: number = 20,
  componentTypes?: LibraryComponentType[],
  projectId?: string | null,
): Promise<LibraryComponentSearchData> => {
  try {
    const headers = await getAuthHeaders();
    const params = new URLSearchParams({
      q: query,
      limit: String(limit),
    });
    if (componentTypes && componentTypes.length > 0) {
      params.set('component_types', componentTypes.join(','));
    }
    if (projectId) params.set('project_id', projectId);
    const response = await fetch(`${API_URL}/library/components/search?${params.toString()}`, {
      headers,
    });
    if (!response.ok) {
      throw new Error(`Backend Error: ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.warn('Error searching library components:', error);
    return {
      query,
      retrievalMode: 'component_keyword',
      results: [],
      componentTypes: componentTypes || [],
      accessModel: {
        scope: 'current_user_grants',
        embeddingUsed: false,
        llmAnswerUsed: false,
      },
      retrievalBudget: {
        embeddingCalls: 0,
        llmCalls: 0,
        maxResults: limit,
        searchedVideos: 0,
        returnedResults: 0,
      },
      guidance: '',
    };
  }
};

export const deleteVideo = async (
  videoId: string,
): Promise<{ success: boolean; deletedClips: number; error?: string }> => {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/video/${videoId}`, {
      method: 'DELETE',
      headers,
    });
    if (!response.ok) {
      throw new Error(`Backend Error: ${response.statusText}`);
    }
    const data = await response.json();
    if (data.success) invalidateLibraryCaches();
    return data;
  } catch (error) {
    console.warn('Error deleting video:', error);
    return { success: false, deletedClips: 0, error: String(error) };
  }
};

export const ingestChannel = async (
  url: string,
  onLog: (msg: string) => void,
  onComplete: () => void,
  digestDepth: 'none' | 'basic' | 'standard' | 'deep' = 'standard',
) => {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/ingest`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ url, digest_depth: digestDepth }),
    });

    if (!response.ok) throw new Error('Failed to start ingestion');
    if (!response.body) throw new Error('No response body');

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const msg = line.replace('data: ', '');
          if (msg === '[DONE]') {
            invalidateLibraryCaches();
            onComplete();
            return;
          }
          onLog(msg);
        }
      }
    }
  } catch (error) {
    console.error('Ingest error:', error);
    onLog(`Connection Error: Ensure server.py is running. (${error})`);
  }
};

export const searchVideoClips = async (
  query: string,
  limit: number = 5,
  categoryFilters?: Record<string, string | string[]>,
  retrievalMode: 'hybrid' | 'semantic' | 'keyword' = 'hybrid',
  projectId?: string | null,
): Promise<{ answer: string; relevantClips: VideoClip[] }> => {
  const headers = await getAuthHeaders();

  try {
    const response = await fetch(`${API_URL}/search`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        query,
        limit,
        category_filters: categoryFilters,
        retrieval_mode: retrievalMode,
        project_id: projectId || undefined,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Backend Error: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.warn('Backend unreachable, returning error:', error);
    throw error;
  }
};

// Usage quota
export interface UsageInfo {
  plan: 'free' | 'plus' | 'pro' | 'local';
  planKey?: 'free' | 'plus' | 'pro' | 'local';
  billingStatus?:
    | 'free'
    | 'trialing'
    | 'active'
    | 'past_due'
    | 'canceled'
    | 'incomplete'
    | 'incomplete_expired'
    | 'unpaid'
    | 'local';
  currentPeriodStart?: string | null;
  currentPeriodEnd?: string | null;
  cancelAtPeriodEnd?: boolean;
  searchesUsedToday: number;
  searchesUsedThisMonth: number;
  searchLimit: number | null;
  searchPeriod: 'month';
  indexesUsedThisMonth: number;
  indexLimit: number | null;
  indexedVideosUsed: number;
  indexedVideoLimit: number | null;
  indexedSecondsUsed: number;
  indexedSecondsLimit: number | null;
  monthlyIndexedSecondsUsed?: number;
  monthlyIndexedSecondsLimit?: number | null;
  deepIndexedSecondsUsed?: number;
  deepIndexedSecondsLimit?: number | null;
  maxImportVideos: number | null;
  maxSearchResults: number | null;
  maxActiveIngestionJobs?: number | null;
  usagePackSecondsBalance?: number;
  priorityQueue?: boolean;
  hasOwnKey: boolean;
  hasServerKey?: boolean;
  apiKeyMode?: 'server' | 'byok' | 'hybrid';
  allowUserKeys?: boolean;
}

export interface BillingStatus {
  planKey: 'free' | 'plus' | 'pro' | 'local';
  billingStatus: NonNullable<UsageInfo['billingStatus']>;
  currentPeriodStart: string | null;
  currentPeriodEnd: string | null;
  cancelAtPeriodEnd: boolean;
  entitlements: Record<string, unknown> | null;
  usage: Record<string, unknown> | null;
  hasStripeCustomer: boolean;
}

const readResponseError = async (response: Response, fallback: string): Promise<string> => {
  try {
    const data = (await response.json()) as { detail?: unknown };
    if (typeof data.detail === 'string' && data.detail.trim()) return data.detail;
  } catch {
    // Some infrastructure errors are plain text or empty; fall back to status context.
  }
  return `${fallback} (${response.status})`;
};

export const fetchUsage = async (): Promise<UsageInfo | null> => {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/usage`, { headers });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
};

export const fetchBillingStatus = async (): Promise<BillingStatus | null> => {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/billing/status`, { headers });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
};

export interface BillingPromo {
  code: string;
  planKey: 'plus' | 'pro';
  trialDays: number;
  lookupKey: string;
}

export const fetchBillingPromo = async (code: string): Promise<BillingPromo | null> => {
  try {
    const response = await fetch(`${API_URL}/billing/promo/${encodeURIComponent(code)}`);
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
};

export const createBillingCheckout = async (
  lookupKey: string,
  promoCode?: string,
): Promise<string> => {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/billing/checkout`, {
    method: 'POST',
    headers,
    body: JSON.stringify(promoCode ? { lookupKey, promoCode } : { lookupKey }),
  });
  if (!response.ok) {
    throw new Error(await readResponseError(response, 'Could not create Stripe Checkout'));
  }
  const data = (await response.json()) as { url?: string };
  if (!data.url) throw new Error('Stripe Checkout did not return a redirect URL.');
  return data.url;
};

export const createBillingPortal = async (): Promise<string> => {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/billing/portal`, {
    method: 'POST',
    headers,
  });
  if (!response.ok) {
    throw new Error(await readResponseError(response, 'Could not open Stripe billing portal'));
  }
  const data = (await response.json()) as { url?: string };
  if (!data.url) throw new Error('Stripe billing portal did not return a redirect URL.');
  return data.url;
};

export const getMcpServerUrl = (): string => {
  return `${API_BASE}/mcp`;
};

export const getMcpManifestUrl = (): string => {
  return `${API_BASE}/mcp.json`;
};

export const getAgentGuideUrl = (): string => {
  return `${API_BASE}/llms.txt`;
};

export const getAgentFullGuideUrl = (): string => {
  return `${API_BASE}/llms-full.txt`;
};

export const fetchMcpTokens = async (): Promise<McpTokenRecord[]> => {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/mcp/tokens`, { headers });
    if (!response.ok) return [];
    const data = await response.json();
    return data.tokens || [];
  } catch (error) {
    console.warn('Error fetching MCP tokens:', error);
    return [];
  }
};

export const createMcpToken = async (
  name: string,
  scopes: string[] = ['context:read', 'overlay:write'],
): Promise<CreatedMcpToken | null> => {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/mcp/tokens`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        name,
        scopes,
      }),
    });
    if (!response.ok) return null;
    return await response.json();
  } catch (error) {
    console.warn('Error creating MCP token:', error);
    return null;
  }
};

export const revokeMcpToken = async (tokenId: string): Promise<boolean> => {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/mcp/tokens/${tokenId}`, {
      method: 'DELETE',
      headers,
    });
    return response.ok;
  } catch (error) {
    console.warn('Error revoking MCP token:', error);
    return false;
  }
};

export const fetchIngestionJobs = async (): Promise<IngestionJob[]> => {
  try {
    const { headers, cacheScope } = await getAuthContext();
    const response = await fetch(`${API_URL}/ingestion-jobs`, { headers });
    if (!response.ok) throw new Error(`Backend Error: ${response.statusText}`);
    const data = await response.json();
    const jobs = data.jobs || [];
    writeJsonCache(cacheKey('ingestion-jobs'), cacheScope, jobs);
    return jobs;
  } catch (error) {
    console.warn('Error fetching ingestion jobs:', error);
    return [];
  }
};

export const fetchIngestionJob = async (jobId: string): Promise<IngestionJob | null> => {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/ingestion-jobs/${jobId}`, { headers });
    if (!response.ok) return null;
    return await response.json();
  } catch (error) {
    console.warn('Error fetching ingestion job:', error);
    return null;
  }
};

export const clearIngestionJobHistory = async (): Promise<number> => {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/ingestion-jobs/history`, {
      method: 'DELETE',
      headers,
    });
    if (!response.ok) return 0;
    const data = await response.json();
    invalidateLibraryCaches();
    return data.deletedCount || 0;
  } catch (error) {
    console.warn('Error clearing ingestion job history:', error);
    return 0;
  }
};

export const fetchCaptureSources = async (): Promise<CaptureSource[]> => {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/capture/sources`, { headers });
    if (!response.ok) return [];
    const data = await response.json();
    return data.captureSources || [];
  } catch (error) {
    console.warn('Error fetching capture sources:', error);
    return [];
  }
};

export const createCaptureSource = async (
  playlistUrl: string,
  title: string = '',
  projectId?: string | null,
): Promise<CaptureSource | null> => {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/capture/sources`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        playlist_url: playlistUrl,
        title,
        project_id: projectId || undefined,
        created_by: 'user',
      }),
    });
    if (!response.ok) return null;
    const data = await response.json();
    invalidateLibraryCaches();
    return data.captureSource || null;
  } catch (error) {
    console.warn('Error creating capture source:', error);
    return null;
  }
};

export const deleteCaptureSource = async (sourceId: string): Promise<boolean> => {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/capture/sources/${encodeURIComponent(sourceId)}`, {
      method: 'DELETE',
      headers,
    });
    if (response.ok) invalidateLibraryCaches();
    return response.ok;
  } catch (error) {
    console.warn('Error deleting capture source:', error);
    return false;
  }
};

export const setCaptureSourceProject = async (
  sourceId: string,
  projectId: string | null,
): Promise<CaptureSource | null> => {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/capture/sources/${sourceId}/project`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ project_id: projectId }),
    });
    if (!response.ok) return null;
    const data = await response.json();
    invalidateLibraryCaches();
    return data.captureSource || null;
  } catch (error) {
    console.warn('Error updating capture source project:', error);
    return null;
  }
};

export const syncCaptureSource = async (
  sourceId: string,
  maxJobs: number = 1,
): Promise<CaptureSourceSyncResult | null> => {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/capture/sources/${sourceId}/sync`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        max_jobs: maxJobs,
      }),
    });
    if (!response.ok) return null;
    const data = await response.json();
    invalidateLibraryCaches();
    return data;
  } catch (error) {
    console.warn('Error syncing capture source:', error);
    return null;
  }
};

const disconnectedYoutubeStatus = (): YoutubeOAuthStatus => ({
  connected: false,
  needsReconnect: false,
  youtubeReadonlyGranted: false,
  hasRefreshToken: false,
  scopes: [],
  expiresAt: null,
  connectedAt: null,
  updatedAt: null,
  lastError: null,
});

export const fetchYoutubeOAuthStatus = async (): Promise<YoutubeOAuthStatus> => {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/youtube/oauth/status`, { headers });
    if (!response.ok) return disconnectedYoutubeStatus();
    return await response.json();
  } catch (error) {
    console.warn('Error fetching YouTube connection status:', error);
    return disconnectedYoutubeStatus();
  }
};

export const saveYoutubeOAuthConnection = async (
  payload: SaveYoutubeOAuthConnectionRequest,
): Promise<YoutubeOAuthStatus | null> => {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/youtube/oauth/connection`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });
    if (!response.ok) return null;
    return await response.json();
  } catch (error) {
    console.warn('Error saving YouTube connection:', error);
    return null;
  }
};

export const disconnectYoutubeOAuth = async (): Promise<YoutubeOAuthStatus> => {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/youtube/oauth/connection`, {
      method: 'DELETE',
      headers,
    });
    if (!response.ok) return disconnectedYoutubeStatus();
    return await response.json();
  } catch (error) {
    console.warn('Error disconnecting YouTube:', error);
    return disconnectedYoutubeStatus();
  }
};

const completedOnboardingStatus = (): OnboardingStatus => ({
  step: 'done',
  state: {},
  completedAt: null,
  skippedAt: null,
  explicitCompleted: true,
  explicitSkipped: false,
  derived: {
    youtubeConnected: false,
    hasCaptureSource: false,
    hasGrantedVideo: false,
    hasQueuedOrIndexedJob: false,
    hasMcpToken: false,
    hasSearchUsage: false,
    activationComplete: true,
  },
  nextSteps: [],
});

export const fetchOnboardingStatus = async (): Promise<OnboardingStatus> => {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/onboarding/status`, { headers });
    if (!response.ok) return completedOnboardingStatus();
    return await response.json();
  } catch (error) {
    console.warn('Error fetching onboarding status:', error);
    return completedOnboardingStatus();
  }
};

export const updateOnboardingStatus = async (
  payload: Partial<{
    onboarding_step: OnboardingStatus['step'];
    onboarding_state: Record<string, unknown>;
    complete: boolean;
    skip: boolean;
  }>,
): Promise<OnboardingStatus | null> => {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/onboarding/status`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify(payload),
    });
    if (!response.ok) return null;
    return await response.json();
  } catch (error) {
    console.warn('Error updating onboarding status:', error);
    return null;
  }
};

export interface ApproveMcpOAuthRequest {
  response_type: string;
  client_id: string;
  redirect_uri: string;
  code_challenge: string;
  code_challenge_method?: string;
  scope?: string;
  state?: string | null;
  resource?: string | null;
}

export const approveMcpOAuthAuthorization = async (
  payload: ApproveMcpOAuthRequest,
): Promise<{ redirectUrl: string } | null> => {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/mcp/oauth/approve`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });
    if (!response.ok) return null;
    return await response.json();
  } catch (error) {
    console.warn('Error approving MCP OAuth request:', error);
    return null;
  }
};

// API key management (server-side)
export const saveApiKey = async (apiKey: string): Promise<boolean> => {
  if (!isSupabaseAuth) {
    saveStoredLocalApiKey(apiKey);
    return true;
  }

  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/settings/key`, {
      method: 'PUT',
      headers,
      body: JSON.stringify({ api_key: apiKey }),
    });
    return response.ok;
  } catch {
    return false;
  }
};

export const deleteApiKey = async (): Promise<boolean> => {
  if (!isSupabaseAuth) {
    deleteStoredLocalApiKey();
    return true;
  }

  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/settings/key`, {
      method: 'DELETE',
      headers,
    });
    return response.ok;
  } catch {
    return false;
  }
};

// Search History (localStorage - kept client-side for now)
const SEARCH_HISTORY_KEY = 'searchtube_search_history';
const MAX_HISTORY_ENTRIES = 20;

export const saveSearchToHistory = (query: string, clips: VideoClip[]): void => {
  const history = getSearchHistory();

  const entry: SearchHistoryEntry = {
    id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    query: query.trim(),
    timestamp: Date.now(),
    clips: clips.map((clip) => ({
      videoId: clip.videoId,
      title: clip.title,
      thumbnailUrl: clip.thumbnailUrl,
      startSeconds: clip.startSeconds,
      channelName: clip.channelName,
    })),
  };

  const filtered = history.filter((h) => h.query.toLowerCase() !== query.toLowerCase().trim());
  const updated = [entry, ...filtered].slice(0, MAX_HISTORY_ENTRIES);

  localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(updated));
};

export const getSearchHistory = (): SearchHistoryEntry[] => {
  try {
    const stored = localStorage.getItem(SEARCH_HISTORY_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
};

export const clearSearchHistory = (): void => {
  localStorage.removeItem(SEARCH_HISTORY_KEY);
};

export const deleteSearchHistoryEntry = (id: string): void => {
  const history = getSearchHistory();
  const updated = history.filter((h) => h.id !== id);
  localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(updated));
};

// Download transcript as SRT file
export const downloadTranscript = async (videoId: string): Promise<void> => {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/transcript/${videoId}?format=srt`, { headers });
    if (!response.ok) {
      throw new Error(`Failed to download transcript: ${response.statusText}`);
    }

    const contentDisposition = response.headers.get('Content-Disposition');
    let filename = `${videoId}.srt`;
    if (contentDisposition) {
      const match = contentDisposition.match(/filename="(.+)"/);
      if (match) filename = match[1];
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Error downloading transcript:', error);
    throw error;
  }
};
