import React, { useState, useEffect } from 'react';
import {
  LibraryData,
  LibraryChannel,
  LibraryVideo,
  DensityMode,
  SortMode,
  ViewMode,
  SearchHistoryEntry,
} from '../types';
import {
  fetchLibrary,
  deleteVideo,
  getSearchHistory,
  deleteSearchHistoryEntry,
  clearSearchHistory,
  downloadTranscript,
} from '../services/api';

interface LibraryViewProps {
  onIndexMore: () => void;
}

export const LibraryView: React.FC<LibraryViewProps> = ({ onIndexMore }) => {
  const [library, setLibrary] = useState<LibraryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [expandedChannels, setExpandedChannels] = useState<Set<string>>(new Set());
  const [deletingVideo, setDeletingVideo] = useState<string | null>(null);
  const [downloadingVideo, setDownloadingVideo] = useState<string | null>(null);
  const [density, setDensity] = useState<DensityMode>('compact');
  const [sortMode, setSortMode] = useState<SortMode>('default');
  const [viewMode, setViewMode] = useState<ViewMode>('flat');
  const [searchHistory, setSearchHistory] = useState<SearchHistoryEntry[]>([]);
  const [historyExpanded, setHistoryExpanded] = useState(true);

  useEffect(() => {
    loadLibrary();
    setSearchHistory(getSearchHistory());
  }, []);

  const loadLibrary = async () => {
    setLoading(true);
    const data = await fetchLibrary();
    setLibrary(data);
    // Collapse all channels by default for a condensed view
    setExpandedChannels(new Set());
    setLoading(false);
  };

  const handleDeleteVideo = async (videoId: string, videoTitle: string) => {
    if (!confirm(`Delete "${videoTitle}" and all its indexed clips?`)) return;

    setDeletingVideo(videoId);
    const result = await deleteVideo(videoId);
    setDeletingVideo(null);

    if (result.success) {
      // Refresh library
      loadLibrary();
    } else {
      alert(`Failed to delete: ${result.error}`);
    }
  };

  const toggleChannel = (name: string) => {
    setExpandedChannels((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  };

  const handleDeleteHistoryEntry = (id: string) => {
    deleteSearchHistoryEntry(id);
    setSearchHistory(getSearchHistory());
  };

  const handleClearHistory = () => {
    if (confirm('Clear all search history?')) {
      clearSearchHistory();
      setSearchHistory([]);
    }
  };

  const handleDownloadTranscript = async (videoId: string) => {
    setDownloadingVideo(videoId);
    try {
      await downloadTranscript(videoId);
    } catch (error) {
      alert(`Failed to download transcript: ${error}`);
    }
    setDownloadingVideo(null);
  };

  const filteredChannels =
    library?.channels.filter((channel) => {
      if (!filter) return true;
      const lowerFilter = filter.toLowerCase();
      if (channel.name.toLowerCase().includes(lowerFilter)) return true;
      return channel.videos.some((v) => v.title.toLowerCase().includes(lowerFilter));
    }) || [];

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-petal border-t-rose"></div>
      </div>
    );
  }

  if (!library || library.totalVideos === 0) {
    return (
      <div className="card mx-auto max-w-xl p-8 text-center">
        <p className="eyebrow mx-auto mb-4 w-fit">Library</p>
        <h2 className="font-serif text-4xl font-medium text-ink">Your library is empty</h2>
        <p className="mx-auto mt-3 max-w-sm text-sm leading-6 text-bark">
          Index a YouTube video, playlist, or channel to start building your searchable moment
          archive.
        </p>
        <button onClick={onIndexMore} className="btn btn-primary mt-6">
          Index videos
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="card mb-6 flex flex-col gap-5 p-5 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="eyebrow mb-3 w-fit">Library</p>
          <h1 className="font-serif text-4xl font-medium text-ink">Indexed moments</h1>
          <p className="mt-2 text-sm text-bark">
            {library.totalVideos} videos - {library.totalClips} clips - {library.channels.length}{' '}
            channels
          </p>
        </div>
        <div className="grid grid-cols-3 rounded-2xl border border-ink/10 bg-cream">
          <Metric value={library.totalVideos} label="videos" />
          <Metric value={library.totalClips} label="clips" />
          <Metric value={library.channels.length} label="channels" isLast />
        </div>
        <button onClick={onIndexMore} className="btn btn-primary">
          Add source
        </button>
      </div>

      {/* Filter */}
      <div className="card mb-5 p-4">
        <div className="relative max-w-md">
          <svg
            className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter videos..."
            className="input w-full py-2 pl-10 pr-4 text-sm"
          />
        </div>
      </div>

      {/* View Controls */}
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-muted">Layout</span>
          <div className="inline-flex rounded-full border border-ink/10 bg-cream p-1">
            <button
              onClick={() => setViewMode('flat')}
              className={`rounded-full px-3 py-1 text-xs font-medium ${
                viewMode === 'flat' ? 'bg-surface text-ink shadow-soft' : 'text-bark hover:text-ink'
              }`}
            >
              Grid
            </button>
            <button
              onClick={() => setViewMode('grouped')}
              className={`rounded-full px-3 py-1 text-xs font-medium ${
                viewMode === 'grouped'
                  ? 'bg-surface text-ink shadow-soft'
                  : 'text-bark hover:text-ink'
              }`}
            >
              By Channel
            </button>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-muted">Size</span>
          <div className="inline-flex rounded-full border border-ink/10 bg-cream p-1">
            <button
              onClick={() => setDensity('compact')}
              className={`rounded-full px-3 py-1 text-xs font-medium ${
                density === 'compact'
                  ? 'bg-surface text-ink shadow-soft'
                  : 'text-bark hover:text-ink'
              }`}
            >
              Small
            </button>
            <button
              onClick={() => setDensity('comfortable')}
              className={`rounded-full px-3 py-1 text-xs font-medium ${
                density === 'comfortable'
                  ? 'bg-surface text-ink shadow-soft'
                  : 'text-bark hover:text-ink'
              }`}
            >
              Large
            </button>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-muted">Sort</span>
          <select
            value={sortMode}
            onChange={(e) => setSortMode(e.target.value as SortMode)}
            className="input px-3 py-1.5 text-sm"
          >
            <option value="default">Default</option>
            <option value="dateAdded">Recently added</option>
          </select>
        </div>
      </div>

      {/* Recent Searches */}
      {searchHistory.length > 0 && (
        <div className="mb-6">
          <div className="card overflow-hidden">
            <button
              onClick={() => setHistoryExpanded(!historyExpanded)}
              className="flex w-full items-center justify-between px-4 py-3 transition-colors hover:bg-petal"
            >
              <div className="flex items-center gap-3">
                <svg
                  className={`h-4 w-4 text-muted transition-transform ${historyExpanded ? 'rotate-90' : ''}`}
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6-1.41-1.41z" />
                </svg>
                <span className="font-serif text-xl font-medium text-ink">Recent searches</span>
                <span className="chip chip-leaf">{searchHistory.length}</span>
              </div>
              {historyExpanded && (
                <span
                  onClick={(e) => {
                    e.stopPropagation();
                    handleClearHistory();
                  }}
                  className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-muted hover:text-rose-deep"
                >
                  Clear all
                </span>
              )}
            </button>

            {historyExpanded && (
              <div className="px-4 pb-4 space-y-3">
                {searchHistory.slice(0, 5).map((entry) => (
                  <SearchHistoryCard
                    key={entry.id}
                    entry={entry}
                    onDelete={() => handleDeleteHistoryEntry(entry.id)}
                  />
                ))}
                {searchHistory.length > 5 && (
                  <p className="pt-2 text-center text-xs text-muted">
                    + {searchHistory.length - 5} more searches
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Videos - Flat or Grouped View */}
      {viewMode === 'flat' ? (
        <FlatVideoGrid
          channels={filteredChannels}
          density={density}
          sortMode={sortMode}
          filter={filter}
          onDeleteVideo={handleDeleteVideo}
          onDownloadTranscript={handleDownloadTranscript}
          deletingVideo={deletingVideo}
          downloadingVideo={downloadingVideo}
        />
      ) : (
        <div className="space-y-4">
          {filteredChannels.map((channel) => (
            <ChannelSection
              key={channel.name}
              channel={channel}
              isExpanded={expandedChannels.has(channel.name)}
              onToggle={() => toggleChannel(channel.name)}
              filter={filter}
              onDeleteVideo={handleDeleteVideo}
              onDownloadTranscript={handleDownloadTranscript}
              deletingVideo={deletingVideo}
              downloadingVideo={downloadingVideo}
              density={density}
              sortMode={sortMode}
            />
          ))}
        </div>
      )}

      {filteredChannels.length === 0 && filter && (
        <div className="card py-12 text-center text-bark">No videos matching "{filter}"</div>
      )}
    </div>
  );
};

// Flat Video Grid Component - shows all videos in a single grid
interface FlatVideoGridProps {
  channels: LibraryChannel[];
  density: DensityMode;
  sortMode: SortMode;
  filter: string;
  onDeleteVideo: (videoId: string, title: string) => void;
  onDownloadTranscript: (videoId: string) => void;
  deletingVideo: string | null;
  downloadingVideo: string | null;
}

const FlatVideoGrid: React.FC<FlatVideoGridProps> = ({
  channels,
  density,
  sortMode,
  filter,
  onDeleteVideo,
  onDownloadTranscript,
  deletingVideo,
  downloadingVideo,
}) => {
  // Flatten all videos from all channels
  const allVideos = channels.flatMap((channel) =>
    channel.videos
      .filter((v) => !filter || v.title.toLowerCase().includes(filter.toLowerCase()))
      .map((video) => ({ ...video, channelName: channel.name })),
  );

  // Sort videos
  const sortedVideos = [...allVideos].sort((a, b) => {
    if (sortMode === 'dateAdded') {
      return (b.indexedAt || 0) - (a.indexedAt || 0);
    }
    return 0;
  });

  const gridClass =
    density === 'compact'
      ? 'grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 lg:grid-cols-8 gap-2'
      : 'grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4';

  if (sortedVideos.length === 0) {
    return <div className="card py-12 text-center text-bark">No videos found</div>;
  }

  return (
    <div className={gridClass}>
      {sortedVideos.map((video) => (
        <FlatVideoCard
          key={video.videoId}
          video={video}
          channelName={video.channelName}
          onDelete={() => onDeleteVideo(video.videoId, video.title)}
          onDownload={() => onDownloadTranscript(video.videoId)}
          isDeleting={deletingVideo === video.videoId}
          isDownloading={downloadingVideo === video.videoId}
          density={density}
        />
      ))}
    </div>
  );
};

// Flat Video Card with channel name
interface FlatVideoCardProps {
  video: LibraryVideo;
  channelName: string;
  onDelete: () => void;
  onDownload: () => void;
  isDeleting: boolean;
  isDownloading: boolean;
  density: DensityMode;
}

const FlatVideoCard: React.FC<FlatVideoCardProps> = ({
  video,
  channelName,
  onDelete,
  onDownload,
  isDeleting,
  isDownloading,
  density,
}) => {
  const isCompact = density === 'compact';

  return (
    <div className="group relative">
      <a
        href={`https://www.youtube.com/watch?v=${video.videoId}`}
        target="_blank"
        rel="noopener noreferrer"
      >
        <div className="relative aspect-video overflow-hidden rounded-lg bg-petal shadow-soft">
          <img
            src={video.thumbnailUrl}
            alt={video.title}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform"
          />
          {!isCompact && (
            <span className="absolute bottom-1 right-1 bg-black/80 text-white text-[10px] px-1 rounded">
              {video.clipCount} clips
            </span>
          )}
        </div>
        <div className={isCompact ? 'mt-1' : 'mt-2'}>
          <h4
            className={`text-ink group-hover:text-rose-deep ${isCompact ? 'line-clamp-1 text-[11px]' : 'line-clamp-2 text-sm'}`}
          >
            {video.title}
          </h4>
          <p className={`text-muted ${isCompact ? 'text-[10px]' : 'mt-0.5 text-xs'}`}>
            {channelName}
          </p>
        </div>
      </a>

      {/* Action buttons */}
      <div
        className={`absolute flex gap-1 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity ${isCompact ? 'top-1 right-1' : 'top-2 right-2'}`}
      >
        {/* Download button */}
        <button
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onDownload();
          }}
          disabled={isDownloading}
          className={`rounded-full bg-surface/90 text-teal-deep shadow-soft transition-colors hover:bg-surface disabled:opacity-50 ${isCompact ? 'p-1' : 'p-1.5'}`}
          title="Download transcript (SRT)"
          aria-label="Download transcript (SRT)"
        >
          {isDownloading ? (
            <div
              className={`animate-spin border-2 border-current border-t-transparent rounded-full ${isCompact ? 'w-3 h-3' : 'w-4 h-4'}`}
            />
          ) : (
            <svg
              className={isCompact ? 'w-3 h-3' : 'w-4 h-4'}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
              />
            </svg>
          )}
        </button>
        {/* Delete button */}
        <button
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onDelete();
          }}
          disabled={isDeleting}
          className={`rounded-full bg-surface/90 text-rose-deep shadow-soft transition-colors hover:bg-surface disabled:opacity-50 ${isCompact ? 'p-1' : 'p-1.5'}`}
          title="Delete from library"
          aria-label="Delete from library"
        >
          {isDeleting ? (
            <div
              className={`animate-spin border-2 border-current border-t-transparent rounded-full ${isCompact ? 'w-3 h-3' : 'w-4 h-4'}`}
            />
          ) : (
            <svg
              className={isCompact ? 'w-3 h-3' : 'w-4 h-4'}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
              />
            </svg>
          )}
        </button>
      </div>
    </div>
  );
};

interface ChannelSectionProps {
  channel: LibraryChannel;
  isExpanded: boolean;
  onToggle: () => void;
  filter: string;
  onDeleteVideo: (videoId: string, title: string) => void;
  onDownloadTranscript: (videoId: string) => void;
  deletingVideo: string | null;
  downloadingVideo: string | null;
  density: DensityMode;
  sortMode: SortMode;
}

const ChannelSection: React.FC<ChannelSectionProps> = ({
  channel,
  isExpanded,
  onToggle,
  filter,
  onDeleteVideo,
  onDownloadTranscript,
  deletingVideo,
  downloadingVideo,
  density,
  sortMode,
}) => {
  const filteredVideos = filter
    ? channel.videos.filter((v) => v.title.toLowerCase().includes(filter.toLowerCase()))
    : channel.videos;

  // Sort videos based on sortMode
  const sortedVideos = [...filteredVideos].sort((a, b) => {
    if (sortMode === 'dateAdded') {
      // Sort by indexed date, newest first. Videos without indexedAt go to the end
      return (b.indexedAt || 0) - (a.indexedAt || 0);
    }
    return 0; // default: maintain original order
  });

  const gridClass =
    density === 'compact'
      ? 'grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-1.5'
      : 'grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3';

  return (
    <div className="card overflow-hidden">
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between px-4 py-3 transition-colors hover:bg-petal"
      >
        <div className="flex items-center gap-3">
          <svg
            className={`h-4 w-4 text-muted transition-transform ${isExpanded ? 'rotate-90' : ''}`}
            fill="currentColor"
            viewBox="0 0 24 24"
          >
            <path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6-1.41-1.41z" />
          </svg>
          <span className="font-serif text-xl font-medium text-ink">{channel.name}</span>
          <span className="chip chip-sun">{channel.videoCount} videos</span>
        </div>
      </button>

      {isExpanded && (
        <div className={density === 'compact' ? 'px-3 pb-3' : 'px-4 pb-4'}>
          <div className={gridClass}>
            {sortedVideos.map((video) => (
              <VideoCard
                key={video.videoId}
                video={video}
                onDelete={() => onDeleteVideo(video.videoId, video.title)}
                onDownload={() => onDownloadTranscript(video.videoId)}
                isDeleting={deletingVideo === video.videoId}
                isDownloading={downloadingVideo === video.videoId}
                density={density}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

interface VideoCardProps {
  video: LibraryVideo;
  onDelete: () => void;
  onDownload: () => void;
  isDeleting: boolean;
  isDownloading: boolean;
  density: DensityMode;
}

const VideoCard: React.FC<VideoCardProps> = ({
  video,
  onDelete,
  onDownload,
  isDeleting,
  isDownloading,
  density,
}) => {
  const isCompact = density === 'compact';

  return (
    <div className="group relative">
      <a
        href={`https://www.youtube.com/watch?v=${video.videoId}`}
        target="_blank"
        rel="noopener noreferrer"
      >
        <div
          className={`relative aspect-video overflow-hidden rounded-lg bg-petal shadow-soft ${isCompact ? '' : 'mb-2'}`}
        >
          <img
            src={video.thumbnailUrl}
            alt={video.title}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform"
          />
        </div>
        <h4
          className={`text-ink group-hover:text-rose-deep ${isCompact ? 'mt-1 line-clamp-1 text-xs' : 'line-clamp-2 text-sm'}`}
        >
          {video.title}
        </h4>
        {!isCompact && <p className="mt-1 text-xs text-muted">{video.clipCount} clips</p>}
      </a>

      {/* Action buttons */}
      <div
        className={`absolute flex gap-1 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity ${isCompact ? 'top-1 right-1' : 'top-2 right-2'}`}
      >
        {/* Download button */}
        <button
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onDownload();
          }}
          disabled={isDownloading}
          className={`rounded-full bg-surface/90 text-teal-deep shadow-soft transition-colors hover:bg-surface disabled:opacity-50 ${isCompact ? 'p-1' : 'p-1.5'}`}
          title="Download transcript (SRT)"
          aria-label="Download transcript (SRT)"
        >
          {isDownloading ? (
            <div
              className={`animate-spin border-2 border-current border-t-transparent rounded-full ${isCompact ? 'w-3 h-3' : 'w-4 h-4'}`}
            />
          ) : (
            <svg
              className={isCompact ? 'w-3 h-3' : 'w-4 h-4'}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
              />
            </svg>
          )}
        </button>
        {/* Delete button */}
        <button
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onDelete();
          }}
          disabled={isDeleting}
          className={`rounded-full bg-surface/90 text-rose-deep shadow-soft transition-colors hover:bg-surface disabled:opacity-50 ${isCompact ? 'p-1' : 'p-1.5'}`}
          title="Delete from library"
          aria-label="Delete from library"
        >
          {isDeleting ? (
            <div
              className={`animate-spin border-2 border-current border-t-transparent rounded-full ${isCompact ? 'w-3 h-3' : 'w-4 h-4'}`}
            />
          ) : (
            <svg
              className={isCompact ? 'w-3 h-3' : 'w-4 h-4'}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
              />
            </svg>
          )}
        </button>
      </div>
    </div>
  );
};

// Search History Card Component
interface SearchHistoryCardProps {
  entry: SearchHistoryEntry;
  onDelete: () => void;
}

const SearchHistoryCard: React.FC<SearchHistoryCardProps> = ({ entry, onDelete }) => {
  const formatRelativeTime = (timestamp: number): string => {
    const now = Date.now();
    const diff = now - timestamp;
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    return new Date(timestamp).toLocaleDateString();
  };

  const formatTime = (seconds: number): string => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div className="group rounded-xl border border-ink/10 bg-cream p-3 transition-colors hover:bg-surface">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex-1 min-w-0">
          <p className="truncate text-sm font-semibold text-ink">{entry.query}</p>
          <p className="text-xs text-muted">
            {formatRelativeTime(entry.timestamp)} - {entry.clips.length} clip
            {entry.clips.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          className="rounded-full p-1 text-muted opacity-0 transition-opacity hover:text-rose-deep group-hover:opacity-100 focus-visible:opacity-100"
          title="Remove from history"
          aria-label="Remove from history"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      {/* Clip thumbnails */}
      <div className="flex gap-2 overflow-x-auto pb-1">
        {entry.clips.slice(0, 4).map((clip, idx) => (
          <a
            key={idx}
            href={`https://www.youtube.com/watch?v=${clip.videoId}&t=${clip.startSeconds}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-shrink-0 group/clip"
          >
            <div className="relative aspect-video w-24 overflow-hidden rounded-lg bg-petal">
              <img
                src={clip.thumbnailUrl}
                alt={clip.title}
                className="w-full h-full object-cover group-hover/clip:scale-105 transition-transform"
              />
              <span className="absolute bottom-1 right-1 rounded bg-sun px-1 font-mono text-[10px] font-medium text-ink">
                {formatTime(clip.startSeconds)}
              </span>
            </div>
            <p className="mt-1 w-24 truncate text-[10px] text-muted group-hover/clip:text-rose-deep">
              {clip.title}
            </p>
          </a>
        ))}
        {entry.clips.length > 4 && (
          <div className="flex aspect-video w-24 flex-shrink-0 items-center justify-center rounded-lg bg-lavender">
            <span className="text-xs font-semibold text-ink">+{entry.clips.length - 4} more</span>
          </div>
        )}
      </div>
    </div>
  );
};

function Metric({
  value,
  label,
  isLast = false,
}: {
  value: number;
  label: string;
  isLast?: boolean;
}) {
  return (
    <div className={`min-w-20 px-4 py-3 text-center ${isLast ? '' : 'border-r border-ink/10'}`}>
      <p className="font-mono text-xl font-semibold text-rose-deep">{value}</p>
      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted">{label}</p>
    </div>
  );
}

export default LibraryView;
