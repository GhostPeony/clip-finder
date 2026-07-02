import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  approveMcpOAuthAuthorization,
  checkBackendHealth,
  clearIngestionJobHistory,
  addProjectVideos,
  createBillingCheckout,
  createBillingPortal,
  createCaptureSource,
  createMcpToken,
  createProject,
  deleteApiKey,
  deleteCaptureSource,
  disconnectYoutubeOAuth,
  fetchAppConfig,
  fetchBillingPromo,
  fetchBillingStatus,
  fetchCaptureSources,
  fetchLibraryArtifact,
  fetchLibrary,
  fetchLibraryGraph,
  fetchProjects,
  fetchProjectContextMap,
  fetchIngestionJobs,
  getCachedLibrary,
  getCachedLibraryGraph,
  fetchMcpTokens,
  fetchUsage,
  fetchYoutubeOAuthStatus,
  getAgentFullGuideUrl,
  getAgentGuideUrl,
  getMcpManifestUrl,
  getMcpServerUrl,
  getStoredLocalApiKey,
  revokeMcpToken,
  saveApiKey,
  saveYoutubeOAuthConnection,
  searchLibraryComponents,
  searchVideoClips,
  setCaptureSourceProject,
  syncCaptureSource,
} from './api';
import { supabase } from '../lib/supabase';

const API_BASE = import.meta.env.VITE_API_URL || 'https://api.memexai.xyz';

describe('api client', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it('fetches public app config', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          storage: 'supabase',
          authMode: 'supabase',
          hasServerKey: true,
          apiKeyMode: 'server',
          allowUserKeys: false,
        }),
      })),
    );

    await expect(fetchAppConfig()).resolves.toEqual({
      storage: 'supabase',
      authMode: 'supabase',
      hasServerKey: true,
      apiKeyMode: 'server',
      allowUserKeys: false,
    });
  });

  it('saves hosted BYOK values through the backend settings endpoint', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({}),
    }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(saveApiKey('AIza-hosted')).resolves.toBe(true);
    expect(getStoredLocalApiKey()).toBeNull();
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/api/settings/key`,
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ api_key: 'AIza-hosted' }),
      }),
    );

    await expect(deleteApiKey()).resolves.toBe(true);
  });

  it('surfaces backend search errors', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: false,
        statusText: 'Unauthorized',
        json: async () => ({ detail: 'No API key provided' }),
      })),
    );

    await expect(searchVideoClips('query', 5)).rejects.toThrow('No API key provided');
  });

  it('sends category filters with semantic search requests', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({ answer: '', relevantClips: [] }),
    }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      searchVideoClips('agent harness', 6, {
        task_fit: ['product spec'],
        tool: 'MCP',
      }),
    ).resolves.toEqual({ answer: '', relevantClips: [] });

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/api/search`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          query: 'agent harness',
          limit: 6,
          category_filters: {
            task_fit: ['product spec'],
            tool: 'MCP',
          },
          retrieval_mode: 'hybrid',
        }),
      }),
    );
  });

  it('can request keyword retrieval mode for search requests', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({ answer: '', relevantClips: [] }),
    }));
    vi.stubGlobal('fetch', fetchMock);

    await searchVideoClips('exact acronym', 4, undefined, 'keyword');

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/api/search`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          query: 'exact acronym',
          limit: 4,
          category_filters: undefined,
          retrieval_mode: 'keyword',
        }),
      }),
    );
  });

  it('can scope search requests to a project', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({ answer: '', relevantClips: [] }),
    }));
    vi.stubGlobal('fetch', fetchMock);

    await searchVideoClips('agent memory', 5, undefined, 'hybrid', 'project-1');

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/api/search`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          query: 'agent memory',
          limit: 5,
          category_filters: undefined,
          retrieval_mode: 'hybrid',
          project_id: 'project-1',
        }),
      }),
    );
  });

  it('checks backend health', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        json: async () => ({ hasApiKey: false }),
      })),
    );

    await expect(checkBackendHealth()).resolves.toEqual({
      connected: true,
      hasServerKey: false,
    });
  });

  it('fetches hosted ingestion jobs', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          jobs: [
            {
              id: 'job-1',
              user_id: 'user-1',
              source_url: 'https://youtube.com/@x',
              source_type: 'channel',
              status: 'completed',
              requested_video_count: 1,
              indexed_video_count: 1,
              skipped_video_count: 0,
              failed_video_count: 0,
              created_at: '2026-05-31T00:00:00Z',
            },
          ],
        }),
      })),
    );

    await expect(fetchIngestionJobs()).resolves.toHaveLength(1);
  });

  it('clears settled ingestion job history', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({ deletedCount: 2 }),
    }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(clearIngestionJobHistory()).resolves.toBe(2);

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/api/ingestion-jobs/history`,
      expect.objectContaining({ method: 'DELETE' }),
    );
  });

  it('fetches the library source graph', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        version: 'memexai-library-source-graph-v1',
        limit: 25,
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
        graph: { nodes: [], edges: [], selectedNodeId: null },
        reviewFlags: [],
        edgeCaseHandling: [],
        guidance: '',
      }),
    }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(fetchLibraryGraph(25)).resolves.toMatchObject({
      version: 'memexai-library-source-graph-v1',
      limit: 25,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/api/library/graph?limit=25`,
      expect.objectContaining({ headers: expect.any(Object) }),
    );
  });

  it('scopes library and graph fetches by project id', async () => {
    const fetchMock = vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url.includes('/library/graph')
          ? {
              version: 'memexai-library-source-graph-v1',
              limit: 25,
              accessModel: {
                scope: 'project',
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
              graph: { nodes: [], edges: [], selectedNodeId: null },
              reviewFlags: [],
              edgeCaseHandling: [],
              guidance: '',
            }
          : { channels: [], totalVideos: 0, totalClips: 0 },
    }));
    vi.stubGlobal('fetch', fetchMock);

    await fetchLibrary('project-1');
    await fetchLibraryGraph(25, 'project-1');

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/api/library?project_id=project-1`,
      expect.objectContaining({ headers: expect.any(Object) }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/api/library/graph?limit=25&project_id=project-1`,
      expect.objectContaining({ headers: expect.any(Object) }),
    );
  });

  it('fetches one full library artifact on demand', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        id: 'artifact:artifact-1',
        type: 'knowledge_artifact',
        label: 'Source report',
        content: 'Full source report body',
      }),
    }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(fetchLibraryArtifact('artifact:artifact-1')).resolves.toMatchObject({
      id: 'artifact:artifact-1',
      content: 'Full source report body',
    });

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/api/library/artifacts/artifact-1`,
      expect.objectContaining({ headers: expect.any(Object) }),
    );
  });

  it('caches library and graph responses within the current auth scope', async () => {
    vi.spyOn(supabase.auth, 'getSession').mockResolvedValue({
      data: {
        session: {
          access_token: 'supabase-access-token',
          user: { id: 'user-1' },
        },
      },
      error: null,
    } as never);
    const fetchMock = vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url.includes('/library/graph')
          ? {
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
              graph: { nodes: [], edges: [], selectedNodeId: null },
              reviewFlags: [],
              edgeCaseHandling: [],
              guidance: '',
            }
          : { channels: [], totalVideos: 0, totalClips: 0 },
    }));
    vi.stubGlobal('fetch', fetchMock);

    await fetchLibrary();
    await fetchLibraryGraph(50);

    await expect(getCachedLibrary()).resolves.toEqual({
      channels: [],
      totalVideos: 0,
      totalClips: 0,
    });
    await expect(getCachedLibraryGraph(50)).resolves.toMatchObject({
      version: 'memexai-library-source-graph-v1',
      limit: 50,
    });
  });

  it('searches library components without retrieval body payload', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        query: 'harness loop',
        retrievalMode: 'component_keyword',
        results: [{ resultType: 'source_concept', title: 'Harness loop' }],
        componentTypes: ['source_concept', 'video'],
        accessModel: {
          scope: 'current_user_grants',
          embeddingUsed: false,
          llmAnswerUsed: false,
        },
        retrievalBudget: {
          embeddingCalls: 0,
          llmCalls: 0,
          maxResults: 20,
          searchedVideos: 1,
          returnedResults: 1,
        },
        guidance: '',
      }),
    }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      searchLibraryComponents('harness loop', 20, ['source_concept', 'video']),
    ).resolves.toMatchObject({
      retrievalMode: 'component_keyword',
      accessModel: { embeddingUsed: false, llmAnswerUsed: false },
    });

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/api/library/components/search?q=harness+loop&limit=20&component_types=source_concept%2Cvideo`,
      expect.objectContaining({ headers: expect.any(Object) }),
    );
  });

  it('manages project scopes through authenticated backend endpoints', async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/api/projects') && init?.method !== 'POST') {
        return {
          ok: true,
          json: async () => ({
            projects: [{ id: 'project-1', name: 'Agent harness', slug: 'agent-harness' }],
            totalProjects: 1,
          }),
        };
      }
      if (url.endsWith('/api/projects') && init?.method === 'POST') {
        return {
          ok: true,
          json: async () => ({
            project: { id: 'project-1', name: 'Agent harness', slug: 'agent-harness' },
          }),
        };
      }
      if (url.endsWith('/api/projects/project-1/videos')) {
        return {
          ok: true,
          json: async () => ({
            project: { id: 'project-1', name: 'Agent harness', slug: 'agent-harness' },
            addedVideos: ['yt-1'],
          }),
        };
      }
      if (url.endsWith('/api/projects/project-1/context-map?limit=25')) {
        return {
          ok: true,
          json: async () => ({ found: true, project: { id: 'project-1' }, videos: [] }),
        };
      }
      if (url.endsWith('/api/capture/sources/capture-1/project')) {
        return {
          ok: true,
          json: async () => ({ captureSource: { id: 'capture-1', project_id: 'project-1' } }),
        };
      }
      return { ok: false, json: async () => ({}) };
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(fetchProjects()).resolves.toHaveLength(1);
    await expect(createProject('Agent harness', 'Research scope')).resolves.toMatchObject({
      id: 'project-1',
    });
    await expect(addProjectVideos('project-1', ['yt-1'])).resolves.toMatchObject({
      addedVideos: ['yt-1'],
    });
    await expect(fetchProjectContextMap('project-1')).resolves.toMatchObject({
      found: true,
    });
    await expect(setCaptureSourceProject('capture-1', 'project-1')).resolves.toMatchObject({
      project_id: 'project-1',
    });

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/api/projects`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ name: 'Agent harness', description: 'Research scope' }),
      }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/api/projects/project-1/videos`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ youtube_video_ids: ['yt-1'], added_source: 'manual' }),
      }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/api/capture/sources/capture-1/project`,
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ project_id: 'project-1' }),
      }),
    );
  });

  it('fetches free-tier usage details', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          plan: 'free',
          searchesUsedToday: 4,
          searchesUsedThisMonth: 4,
          searchLimit: 100,
          searchPeriod: 'month',
          indexesUsedThisMonth: 2,
          indexLimit: 15,
          indexedVideosUsed: 2,
          indexedVideoLimit: 15,
          indexedSecondsUsed: 7200,
          indexedSecondsLimit: 18000,
          maxImportVideos: 10,
          maxSearchResults: 5,
          hasOwnKey: false,
          apiKeyMode: 'hybrid',
          hasServerKey: true,
          allowUserKeys: true,
        }),
      })),
    );

    await expect(fetchUsage()).resolves.toMatchObject({
      plan: 'free',
      searchesUsedThisMonth: 4,
      indexedVideosUsed: 2,
      indexedSecondsLimit: 18000,
      maxSearchResults: 5,
    });
  });

  it('manages hosted billing through authenticated backend endpoints', async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/api/billing/checkout') && init?.method === 'POST') {
        return {
          ok: true,
          json: async () => ({ url: 'https://checkout.stripe.com/test' }),
        };
      }
      if (url.endsWith('/api/billing/portal') && init?.method === 'POST') {
        return {
          ok: true,
          json: async () => ({ url: 'https://billing.stripe.com/test' }),
        };
      }
      if (url.endsWith('/api/billing/status')) {
        return {
          ok: true,
          json: async () => ({
            planKey: 'plus',
            billingStatus: 'active',
            currentPeriodStart: '2026-06-01T00:00:00+00:00',
            currentPeriodEnd: '2026-07-01T00:00:00+00:00',
            cancelAtPeriodEnd: false,
            entitlements: {},
            usage: {},
            hasStripeCustomer: true,
          }),
        };
      }
      throw new Error(`Unexpected URL ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(createBillingCheckout('memexai_plus_monthly_v1')).resolves.toBe(
      'https://checkout.stripe.com/test',
    );
    await expect(createBillingPortal()).resolves.toBe('https://billing.stripe.com/test');
    await expect(fetchBillingStatus()).resolves.toMatchObject({
      planKey: 'plus',
      billingStatus: 'active',
    });

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/api/billing/checkout`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ lookupKey: 'memexai_plus_monthly_v1' }),
      }),
    );
  });

  it('surfaces hosted billing endpoint errors', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: false,
      status: 500,
      json: async () => ({ detail: 'No such customer: cus_old_sandbox' }),
    }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(createBillingCheckout('memexai_plus_monthly_v1')).rejects.toThrow(
      'No such customer: cus_old_sandbox',
    );
  });

  it('sends promo codes to checkout and describes promo offers', async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/api/billing/checkout') && init?.method === 'POST') {
        return {
          ok: true,
          json: async () => ({ url: 'https://checkout.stripe.com/trial' }),
        };
      }
      if (url.endsWith('/api/billing/promo/producthunt')) {
        return {
          ok: true,
          json: async () => ({
            code: 'producthunt',
            planKey: 'plus',
            trialDays: 14,
            lookupKey: 'memexai_plus_monthly_v1',
          }),
        };
      }
      if (url.endsWith('/api/billing/promo/notacode')) {
        return { ok: false, status: 404, json: async () => ({ detail: 'Unknown promo code' }) };
      }
      throw new Error(`Unexpected URL ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(fetchBillingPromo('producthunt')).resolves.toMatchObject({
      code: 'producthunt',
      planKey: 'plus',
      trialDays: 14,
    });
    await expect(fetchBillingPromo('notacode')).resolves.toBeNull();

    await expect(createBillingCheckout('memexai_plus_monthly_v1', 'producthunt')).resolves.toBe(
      'https://checkout.stripe.com/trial',
    );
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/api/billing/checkout`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          lookupKey: 'memexai_plus_monthly_v1',
          promoCode: 'producthunt',
        }),
      }),
    );
  });

  it('manages MCP tokens through authenticated backend endpoints', async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/api/mcp/tokens') && init?.method === 'POST') {
        return {
          ok: true,
          json: async () => ({
            token: 'emt_visible_secret',
            tokenRecord: {
              id: 'token-1',
              name: 'My MCP agent',
              tokenPrefix: 'emt_visible',
              scopes: ['context:read', 'overlay:write'],
            },
            setup: {
              serverName: 'memexai',
              mcpEndpoint: `${API_BASE}/mcp`,
              manifestUrl: `${API_BASE}/mcp.json`,
              agentGuideUrl: `${API_BASE}/llms.txt`,
              fullAgentGuideUrl: `${API_BASE}/llms-full.txt`,
              tokenEnvironmentVariable: 'MEMEXAI_MCP_TOKEN',
              hermesConfig: 'Bearer ${MEMEXAI_MCP_TOKEN}',
              firstSteps: ['Call get_mcp_session.'],
              firstCalls: [{ tool: 'get_mcp_session', purpose: 'Confirm scopes.' }],
              accessModel: {
                searchScope: 'current_user_grants',
                globalSearch: 'not_exposed',
                visibilityGrants: ['user_videos', 'user_channels'],
                canonicalStorage: 'Stored once.',
                dedupeBehavior: 'Grant instead of re-embed.',
                agentInstruction: 'Keep provenance.',
              },
              oneTimeCredential: {
                bearerToken: 'emt_visible_secret',
                envLine: 'MEMEXAI_MCP_TOKEN=emt_visible_secret',
                hermesConfig: 'Bearer emt_visible_secret',
              },
            },
          }),
        };
      }
      if (url.endsWith('/api/mcp/tokens/token-1') && init?.method === 'DELETE') {
        return {
          ok: true,
          json: async () => ({ revoked: true }),
        };
      }
      return {
        ok: true,
        json: async () => ({
          tokens: [
            {
              id: 'token-1',
              name: 'My MCP agent',
              tokenPrefix: 'emt_visible',
              scopes: ['context:read', 'overlay:write'],
            },
          ],
        }),
      };
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(fetchMcpTokens()).resolves.toHaveLength(1);
    await expect(createMcpToken('My MCP agent')).resolves.toMatchObject({
      tokenRecord: { name: 'My MCP agent' },
      setup: {
        accessModel: {
          searchScope: 'current_user_grants',
          visibilityGrants: ['user_videos', 'user_channels'],
        },
      },
    });
    await expect(revokeMcpToken('token-1')).resolves.toBe(true);
    expect(getMcpServerUrl()).toBe(`${API_BASE}/mcp`);
    expect(getMcpManifestUrl()).toBe(`${API_BASE}/mcp.json`);
    expect(getAgentGuideUrl()).toBe(`${API_BASE}/llms.txt`);
    expect(getAgentFullGuideUrl()).toBe(`${API_BASE}/llms-full.txt`);
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/api/mcp/tokens`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          name: 'My MCP agent',
          scopes: ['context:read', 'overlay:write'],
        }),
      }),
    );
  });

  it('manages YouTube capture sources through authenticated backend endpoints', async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/api/capture/sources') && init?.method === 'POST') {
        return {
          ok: true,
          json: async () => ({
            captureSource: {
              id: 'capture-1',
              source_type: 'playlist',
              source_url: 'https://www.youtube.com/playlist?list=PLabcdef123456',
              external_id: 'PLabcdef123456',
              title: 'AI research inbox',
              status: 'active',
            },
          }),
        };
      }
      if (url.endsWith('/api/capture/sources/capture-1/sync') && init?.method === 'POST') {
        return {
          ok: true,
          json: async () => ({
            captureSource: { id: 'capture-1' },
            discoveredCount: 2,
            newItemCount: 1,
            queuedJobCount: 1,
            skippedExistingCount: 1,
            activeJobLimitReached: false,
          }),
        };
      }
      if (url.endsWith('/api/capture/sources/capture-1') && init?.method === 'DELETE') {
        return {
          ok: true,
          json: async () => ({ deleted: true }),
        };
      }
      return {
        ok: true,
        json: async () => ({
          captureSources: [
            {
              id: 'capture-1',
              source_type: 'playlist',
              source_url: 'https://www.youtube.com/playlist?list=PLabcdef123456',
              external_id: 'PLabcdef123456',
              title: 'AI research inbox',
              status: 'active',
            },
          ],
        }),
      };
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(fetchCaptureSources()).resolves.toHaveLength(1);
    await expect(
      createCaptureSource(
        'https://www.youtube.com/playlist?list=PLabcdef123456',
        'AI research inbox',
      ),
    ).resolves.toMatchObject({ title: 'AI research inbox' });
    await expect(syncCaptureSource('capture-1', 2)).resolves.toMatchObject({
      queuedJobCount: 1,
    });
    await expect(deleteCaptureSource('capture-1')).resolves.toBe(true);

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/api/capture/sources`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          playlist_url: 'https://www.youtube.com/playlist?list=PLabcdef123456',
          title: 'AI research inbox',
          created_by: 'user',
        }),
      }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/api/capture/sources/capture-1/sync`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ max_jobs: 2 }),
      }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/api/capture/sources/capture-1`,
      expect.objectContaining({ method: 'DELETE' }),
    );
  });

  it('manages YouTube OAuth connection status through authenticated backend endpoints', async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/api/youtube/oauth/connection') && init?.method === 'POST') {
        return {
          ok: true,
          json: async () => ({
            connected: true,
            needsReconnect: false,
            youtubeReadonlyGranted: true,
            hasRefreshToken: true,
            scopes: ['openid', 'https://www.googleapis.com/auth/youtube.readonly'],
          }),
        };
      }
      if (url.endsWith('/api/youtube/oauth/connection') && init?.method === 'DELETE') {
        return {
          ok: true,
          json: async () => ({
            connected: false,
            needsReconnect: false,
            youtubeReadonlyGranted: false,
            hasRefreshToken: false,
            scopes: [],
          }),
        };
      }
      return {
        ok: true,
        json: async () => ({
          connected: true,
          needsReconnect: false,
          youtubeReadonlyGranted: true,
          hasRefreshToken: true,
          scopes: ['openid', 'https://www.googleapis.com/auth/youtube.readonly'],
        }),
      };
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(fetchYoutubeOAuthStatus()).resolves.toMatchObject({
      connected: true,
      hasRefreshToken: true,
      youtubeReadonlyGranted: true,
    });
    await expect(
      saveYoutubeOAuthConnection({
        access_token: 'provider-access',
        refresh_token: 'provider-refresh',
        scopes: ['openid', 'https://www.googleapis.com/auth/youtube.readonly'],
      }),
    ).resolves.toMatchObject({
      connected: true,
      hasRefreshToken: true,
    });
    await expect(disconnectYoutubeOAuth()).resolves.toMatchObject({
      connected: false,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/api/youtube/oauth/connection`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          access_token: 'provider-access',
          refresh_token: 'provider-refresh',
          scopes: ['openid', 'https://www.googleapis.com/auth/youtube.readonly'],
        }),
      }),
    );
  });

  it('approves MCP OAuth authorization requests through the backend', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        redirectUrl: 'http://localhost:31337/callback?code=abc&state=state-1',
      }),
    }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      approveMcpOAuthAuthorization({
        response_type: 'code',
        client_id: 'memexai_mcp_client',
        redirect_uri: 'http://localhost:31337/callback',
        code_challenge: 'challenge',
        code_challenge_method: 'S256',
        scope: 'context:read overlay:write',
        state: 'state-1',
      }),
    ).resolves.toEqual({
      redirectUrl: 'http://localhost:31337/callback?code=abc&state=state-1',
    });

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/api/mcp/oauth/approve`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          response_type: 'code',
          client_id: 'memexai_mcp_client',
          redirect_uri: 'http://localhost:31337/callback',
          code_challenge: 'challenge',
          code_challenge_method: 'S256',
          scope: 'context:read overlay:write',
          state: 'state-1',
        }),
      }),
    );
  });

  it('sends the Supabase bearer token to authenticated backend endpoints', async () => {
    vi.spyOn(supabase.auth, 'getSession').mockResolvedValue({
      data: {
        session: {
          access_token: 'supabase-access-token',
        },
      },
      error: null,
    } as never);
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({ channels: [], totalVideos: 0, totalClips: 0 }),
    }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(fetchLibrary()).resolves.toEqual({
      channels: [],
      totalVideos: 0,
      totalClips: 0,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/api/library`,
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer supabase-access-token',
        }),
      }),
    );
  });

  it('surfaces library backend failures instead of returning an empty library', async () => {
    vi.spyOn(supabase.auth, 'getSession').mockResolvedValue({
      data: {
        session: {
          access_token: 'supabase-access-token',
        },
      },
      error: null,
    } as never);
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: false,
        statusText: 'Internal Server Error',
      })),
    );

    await expect(fetchLibrary()).rejects.toThrow('Backend Error: Internal Server Error');
  });
});
