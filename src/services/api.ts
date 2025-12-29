import { VideoClip, LibraryData } from '../types';

// Use environment variable for production, fallback to localhost for dev
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
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
