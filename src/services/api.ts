import { VideoClip, LibraryData, SearchHistoryEntry, IngestionJob } from '../types';
import { supabase } from '../lib/supabase';
import { AppConfig, isSupabaseAuth } from '../config';

// Use environment variable for production, fallback to localhost for dev
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8080';
const API_URL = `${API_BASE}/api`;

// Get auth headers from Supabase session
async function getAuthHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if (isSupabaseAuth) {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session?.access_token) return headers;
    headers['Authorization'] = `Bearer ${session.access_token}`;
  }

  const apiKey = isSupabaseAuth ? null : getStoredLocalApiKey();
  if (apiKey) {
    headers['X-API-Key'] = apiKey;
  }

  return headers;
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

export const fetchLibrary = async (): Promise<LibraryData> => {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/library`, { headers });
    if (!response.ok) {
      throw new Error(`Backend Error: ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.warn('Error fetching library:', error);
    return { channels: [], totalVideos: 0, totalClips: 0 };
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
    return await response.json();
  } catch (error) {
    console.warn('Error deleting video:', error);
    return { success: false, deletedClips: 0, error: String(error) };
  }
};

export const ingestChannel = async (
  url: string,
  onLog: (msg: string) => void,
  onComplete: () => void,
) => {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/ingest`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ url }),
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
): Promise<{ answer: string; relevantClips: VideoClip[] }> => {
  const headers = await getAuthHeaders();

  try {
    const response = await fetch(`${API_URL}/search`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ query, limit }),
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
  plan: 'free' | 'local';
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
  maxImportVideos: number | null;
  maxSearchResults: number | null;
  hasOwnKey: boolean;
  hasServerKey?: boolean;
  apiKeyMode?: 'server' | 'byok' | 'hybrid';
  allowUserKeys?: boolean;
}

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

export const fetchIngestionJobs = async (): Promise<IngestionJob[]> => {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_URL}/ingestion-jobs`, { headers });
    if (!response.ok) throw new Error(`Backend Error: ${response.statusText}`);
    const data = await response.json();
    return data.jobs || [];
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
