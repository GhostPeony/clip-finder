import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  checkBackendHealth,
  deleteApiKey,
  fetchAppConfig,
  fetchUsage,
  fetchLibrary,
  fetchIngestionJobs,
  getStoredLocalApiKey,
  saveApiKey,
  searchVideoClips,
} from './api';
import { supabase } from '../lib/supabase';

describe('api client', () => {
  beforeEach(() => {
    localStorage.clear();
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
      'http://localhost:8080/api/settings/key',
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
      'http://localhost:8080/api/library',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer supabase-access-token',
        }),
      }),
    );
  });
});
