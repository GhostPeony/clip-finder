import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  checkBackendHealth,
  deleteApiKey,
  fetchAppConfig,
  getStoredLocalApiKey,
  saveApiKey,
  searchVideoClips,
} from './api';

describe('api client', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('fetches public app config', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true,
      json: async () => ({
        storage: 'local',
        authMode: 'none',
        hasServerKey: true,
        apiKeyMode: 'server',
        allowUserKeys: false,
      }),
    })));

    await expect(fetchAppConfig()).resolves.toEqual({
      storage: 'local',
      authMode: 'none',
      hasServerKey: true,
      apiKeyMode: 'server',
      allowUserKeys: false,
    });
  });

  it('stores local BYOK values in local mode', async () => {
    await expect(saveApiKey('AIza-local')).resolves.toBe(true);
    expect(getStoredLocalApiKey()).toBe('AIza-local');

    await expect(deleteApiKey()).resolves.toBe(true);
    expect(getStoredLocalApiKey()).toBeNull();
  });

  it('surfaces backend search errors', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: false,
      statusText: 'Unauthorized',
      json: async () => ({ detail: 'No API key provided' }),
    })));

    await expect(searchVideoClips('query', 5)).rejects.toThrow('No API key provided');
  });

  it('checks backend health', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true,
      json: async () => ({ hasApiKey: false }),
    })));

    await expect(checkBackendHealth()).resolves.toEqual({
      connected: true,
      hasServerKey: false,
    });
  });
});
