export interface VideoClip {
  id: string;
  videoId: string;
  title: string;
  channelName: string;
  startSeconds: number;
  endSeconds: number;
  content: string; // The transcript text for this chunk
  thumbnailUrl: string;
}

export interface SearchState {
  status: 'idle' | 'searching' | 'analyzing' | 'complete' | 'error';
  query: string;
  answer: string;
  relevantClips: VideoClip[];
  error?: string;
}

export interface IngestionState {
  status: 'idle' | 'scanning' | 'indexing' | 'complete' | 'error';
  logs: string[];
  progress: number;
  totalVideos: number;
  currentVideo?: string;
}

// Library types
export interface LibraryVideo {
  videoId: string;
  title: string;
  thumbnailUrl: string;
  clipCount: number;
  indexedAt?: number;  // Unix timestamp, optional for backward compat
}

export type DensityMode = 'compact' | 'comfortable';
export type SortMode = 'default' | 'dateAdded';
export type ViewMode = 'grouped' | 'flat';

export interface LibraryChannel {
  name: string;
  videoCount: number;
  videos: LibraryVideo[];
}

export interface LibraryData {
  channels: LibraryChannel[];
  totalVideos: number;
  totalClips: number;
}

export type AppMode = 'unified' | 'ingest' | 'search' | 'library' | 'about' | 'contact';

// Search history types
export interface SearchHistoryClip {
  videoId: string;
  title: string;
  thumbnailUrl: string;
  startSeconds: number;
  channelName: string;
}

export interface SearchHistoryEntry {
  id: string;
  query: string;
  timestamp: number;
  clips: SearchHistoryClip[];
}
