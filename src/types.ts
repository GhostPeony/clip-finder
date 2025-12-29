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
}

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

export type AppMode = 'ingest' | 'search' | 'library';
