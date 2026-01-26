import { VideoClip, LibraryData, SearchHistoryEntry, SearchHistoryClip } from '../types';

// Use environment variable for production, fallback to localhost for dev
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8080';
const API_URL = `${API_BASE}/api`;

export const checkBackendHealth = async (): Promise<{ connected: boolean; hasServerKey: boolean }> => {
  try {
    const res = await fetch(`${API_BASE}/`);
    if (res.ok) {
      const data = await res.json();
      return { connected: true, hasServerKey: data.hasApiKey || false };
    }
    return { connected: false, hasServerKey: false };
  } catch (e) {
    return { connected: false, hasServerKey: false };
  }
};

export const fetchLibrary = async (): Promise<LibraryData> => {
  try {
    const response = await fetch(`${API_URL}/library`);
    if (!response.ok) {
      throw new Error(`Backend Error: ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.warn("Error fetching library:", error);
    return { channels: [], totalVideos: 0, totalClips: 0 };
  }
};

export const deleteVideo = async (videoId: string): Promise<{ success: boolean; deletedClips: number; error?: string }> => {
  try {
    const response = await fetch(`${API_URL}/video/${videoId}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error(`Backend Error: ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.warn("Error deleting video:", error);
    return { success: false, deletedClips: 0, error: String(error) };
  }
};

export const ingestChannel = async (url: string, onLog: (msg: string) => void, onComplete: () => void) => {
  try {
    const response = await fetch(`${API_URL}/ingest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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
    console.error("Ingest error:", error);
    onLog(`❌ Connection Error: Ensure server.py is running. (${error})`);
  }
};

export const searchVideoClips = async (query: string, limit: number = 5): Promise<{ answer: string; relevantClips: VideoClip[] }> => {
  // Get API key from localStorage (BYOK)
  const apiKey = localStorage.getItem('clipfinder_api_key');

  const headers: Record<string, string> = {
    'Content-Type': 'application/json'
  };

  // Add API key header if available
  if (apiKey) {
    headers['X-API-Key'] = apiKey;
  }

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
    console.warn("Backend unreachable, returning error:", error);
    throw error;
  }
};

// Search History (localStorage)
const SEARCH_HISTORY_KEY = 'clipfinder_search_history';
const MAX_HISTORY_ENTRIES = 20;

export const saveSearchToHistory = (query: string, clips: VideoClip[]): void => {
  const history = getSearchHistory();

  const entry: SearchHistoryEntry = {
    id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    query: query.trim(),
    timestamp: Date.now(),
    clips: clips.map(clip => ({
      videoId: clip.videoId,
      title: clip.title,
      thumbnailUrl: clip.thumbnailUrl,
      startSeconds: clip.startSeconds,
      channelName: clip.channelName,
    })),
  };

  // Add to beginning, remove duplicates of same query
  const filtered = history.filter(h => h.query.toLowerCase() !== query.toLowerCase().trim());
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
  const updated = history.filter(h => h.id !== id);
  localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(updated));
};

// Download transcript as SRT file
export const downloadTranscript = async (videoId: string): Promise<void> => {
  try {
    const response = await fetch(`${API_URL}/transcript/${videoId}?format=srt`);
    if (!response.ok) {
      throw new Error(`Failed to download transcript: ${response.statusText}`);
    }

    // Get filename from Content-Disposition header or use default
    const contentDisposition = response.headers.get('Content-Disposition');
    let filename = `${videoId}.srt`;
    if (contentDisposition) {
      const match = contentDisposition.match(/filename="(.+)"/);
      if (match) filename = match[1];
    }

    // Create blob and trigger download
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
    console.error("Error downloading transcript:", error);
    throw error;
  }
};
