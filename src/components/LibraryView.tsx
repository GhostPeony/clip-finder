import React, { useState, useEffect } from 'react';
import { LibraryData, LibraryChannel, LibraryVideo, DensityMode, SortMode, ViewMode, SearchHistoryEntry } from '../types';
import { fetchLibrary, deleteVideo, getSearchHistory, deleteSearchHistoryEntry, clearSearchHistory, downloadTranscript } from '../services/api';

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
    setExpandedChannels(prev => {
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

  const filteredChannels = library?.channels.filter(channel => {
    if (!filter) return true;
    const lowerFilter = filter.toLowerCase();
    if (channel.name.toLowerCase().includes(lowerFilter)) return true;
    return channel.videos.some(v => v.title.toLowerCase().includes(lowerFilter));
  }) || [];

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#1a73e8]"></div>
      </div>
    );
  }

  if (!library || library.totalVideos === 0) {
    return (
      <div className="max-w-xl mx-auto text-center py-16">
        <div className="text-6xl mb-4">📚</div>
        <h2 className="text-2xl font-normal text-[#202124] mb-2">Your Library is Empty</h2>
        <p className="text-[#5f6368] mb-6">Index some YouTube videos to get started</p>
        <button
          onClick={onIndexMore}
          className="bg-[#1a73e8] hover:bg-[#1557b0] text-white px-6 py-2 rounded-md text-sm font-medium transition-colors"
        >
          Index Videos
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-normal text-[#202124] flex items-center gap-2">
            📚 Your Library
          </h1>
          <p className="text-sm text-[#5f6368] mt-1">
            {library.totalVideos} videos • {library.totalClips} clips • {library.channels.length} channels
          </p>
        </div>
        <button
          onClick={onIndexMore}
          className="bg-[#1a73e8] hover:bg-[#1557b0] text-white px-4 py-2 rounded-md text-sm font-medium transition-colors"
        >
          + Add Videos
        </button>
      </div>

      {/* Filter */}
      <div className="mb-4">
        <div className="relative max-w-md">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#5f6368]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter videos..."
            className="w-full pl-10 pr-4 py-2 border border-[#dadce0] rounded-md focus:outline-none focus:border-[#1a73e8] text-sm"
          />
        </div>
      </div>

      {/* View Controls */}
      <div className="flex items-center gap-4 mb-6 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-sm text-[#5f6368]">Layout:</span>
          <div className="flex border border-[#dadce0] rounded-md overflow-hidden">
            <button
              onClick={() => setViewMode('flat')}
              className={`px-3 py-1.5 text-sm ${viewMode === 'flat' ? 'bg-[#e8f0fe] text-[#1a73e8]' : 'text-[#5f6368] hover:bg-[#f1f3f4]'}`}
            >
              Grid
            </button>
            <button
              onClick={() => setViewMode('grouped')}
              className={`px-3 py-1.5 text-sm ${viewMode === 'grouped' ? 'bg-[#e8f0fe] text-[#1a73e8]' : 'text-[#5f6368] hover:bg-[#f1f3f4]'}`}
            >
              By Channel
            </button>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-[#5f6368]">Size:</span>
          <div className="flex border border-[#dadce0] rounded-md overflow-hidden">
            <button
              onClick={() => setDensity('compact')}
              className={`px-3 py-1.5 text-sm ${density === 'compact' ? 'bg-[#e8f0fe] text-[#1a73e8]' : 'text-[#5f6368] hover:bg-[#f1f3f4]'}`}
            >
              Small
            </button>
            <button
              onClick={() => setDensity('comfortable')}
              className={`px-3 py-1.5 text-sm ${density === 'comfortable' ? 'bg-[#e8f0fe] text-[#1a73e8]' : 'text-[#5f6368] hover:bg-[#f1f3f4]'}`}
            >
              Large
            </button>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-[#5f6368]">Sort:</span>
          <select
            value={sortMode}
            onChange={(e) => setSortMode(e.target.value as SortMode)}
            className="px-3 py-1.5 text-sm border border-[#dadce0] rounded-md bg-white focus:outline-none focus:border-[#1a73e8]"
          >
            <option value="default">Default</option>
            <option value="dateAdded">Recently added</option>
          </select>
        </div>
      </div>

      {/* Recent Searches */}
      {searchHistory.length > 0 && (
        <div className="mb-6">
          <div className="bg-white rounded-lg border border-[#dadce0] overflow-hidden">
            <button
              onClick={() => setHistoryExpanded(!historyExpanded)}
              className="w-full px-4 py-3 flex items-center justify-between hover:bg-[#f8f9fa] transition-colors"
            >
              <div className="flex items-center gap-3">
                <svg
                  className={`w-4 h-4 text-[#5f6368] transition-transform ${historyExpanded ? 'rotate-90' : ''}`}
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6-1.41-1.41z" />
                </svg>
                <span className="font-medium text-[#202124]">Recent Searches</span>
                <span className="text-sm text-[#5f6368]">({searchHistory.length})</span>
              </div>
              {historyExpanded && (
                <span
                  onClick={(e) => { e.stopPropagation(); handleClearHistory(); }}
                  className="text-xs text-[#5f6368] hover:text-[#c5221f] cursor-pointer"
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
                  <p className="text-xs text-[#5f6368] text-center pt-2">
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
        <div className="text-center py-12 text-[#5f6368]">
          No videos matching "{filter}"
        </div>
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

const FlatVideoGrid: React.FC<FlatVideoGridProps> = ({ channels, density, sortMode, filter, onDeleteVideo, onDownloadTranscript, deletingVideo, downloadingVideo }) => {
  // Flatten all videos from all channels
  const allVideos = channels.flatMap(channel =>
    channel.videos
      .filter(v => !filter || v.title.toLowerCase().includes(filter.toLowerCase()))
      .map(video => ({ ...video, channelName: channel.name }))
  );

  // Sort videos
  const sortedVideos = [...allVideos].sort((a, b) => {
    if (sortMode === 'dateAdded') {
      return (b.indexedAt || 0) - (a.indexedAt || 0);
    }
    return 0;
  });

  const gridClass = density === 'compact'
    ? 'grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 lg:grid-cols-8 gap-2'
    : 'grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4';

  if (sortedVideos.length === 0) {
    return (
      <div className="text-center py-12 text-[#5f6368]">
        No videos found
      </div>
    );
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

const FlatVideoCard: React.FC<FlatVideoCardProps> = ({ video, channelName, onDelete, onDownload, isDeleting, isDownloading, density }) => {
  const isCompact = density === 'compact';

  return (
    <div className="group relative">
      <a
        href={`https://www.youtube.com/watch?v=${video.videoId}`}
        target="_blank"
        rel="noopener noreferrer"
      >
        <div className={`aspect-video bg-[#f1f3f4] overflow-hidden relative ${isCompact ? 'rounded' : 'rounded-lg'}`}>
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
          <h4 className={`text-[#202124] group-hover:text-[#1a73e8] ${isCompact ? 'text-[11px] line-clamp-1' : 'text-sm line-clamp-2'}`}>
            {video.title}
          </h4>
          <p className={`text-[#5f6368] ${isCompact ? 'text-[10px]' : 'text-xs mt-0.5'}`}>
            {channelName}
          </p>
        </div>
      </a>

      {/* Action buttons */}
      <div className={`absolute flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity ${isCompact ? 'top-1 right-1' : 'top-2 right-2'}`}>
        {/* Download button */}
        <button
          onClick={(e) => { e.preventDefault(); e.stopPropagation(); onDownload(); }}
          disabled={isDownloading}
          className={`bg-black/70 hover:bg-[#1a73e8] text-white rounded disabled:opacity-50 ${isCompact ? 'p-0.5' : 'p-1'}`}
          title="Download transcript (SRT)"
        >
          {isDownloading ? (
            <div className={`animate-spin border-2 border-white border-t-transparent rounded-full ${isCompact ? 'w-3 h-3' : 'w-4 h-4'}`} />
          ) : (
            <svg className={isCompact ? 'w-3 h-3' : 'w-4 h-4'} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          )}
        </button>
        {/* Delete button */}
        <button
          onClick={(e) => { e.preventDefault(); e.stopPropagation(); onDelete(); }}
          disabled={isDeleting}
          className={`bg-black/70 hover:bg-red-600 text-white rounded disabled:opacity-50 ${isCompact ? 'p-0.5' : 'p-1'}`}
          title="Delete from library"
        >
          {isDeleting ? (
            <div className={`animate-spin border-2 border-white border-t-transparent rounded-full ${isCompact ? 'w-3 h-3' : 'w-4 h-4'}`} />
          ) : (
            <svg className={isCompact ? 'w-3 h-3' : 'w-4 h-4'} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
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

const ChannelSection: React.FC<ChannelSectionProps> = ({ channel, isExpanded, onToggle, filter, onDeleteVideo, onDownloadTranscript, deletingVideo, downloadingVideo, density, sortMode }) => {
  const filteredVideos = filter
    ? channel.videos.filter(v => v.title.toLowerCase().includes(filter.toLowerCase()))
    : channel.videos;

  // Sort videos based on sortMode
  const sortedVideos = [...filteredVideos].sort((a, b) => {
    if (sortMode === 'dateAdded') {
      // Sort by indexed date, newest first. Videos without indexedAt go to the end
      return (b.indexedAt || 0) - (a.indexedAt || 0);
    }
    return 0; // default: maintain original order
  });

  const gridClass = density === 'compact'
    ? 'grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-1.5'
    : 'grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3';

  return (
    <div className="bg-white rounded-lg border border-[#dadce0] overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-[#f8f9fa] transition-colors"
      >
        <div className="flex items-center gap-3">
          <svg
            className={`w-4 h-4 text-[#5f6368] transition-transform ${isExpanded ? 'rotate-90' : ''}`}
            fill="currentColor"
            viewBox="0 0 24 24"
          >
            <path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6-1.41-1.41z" />
          </svg>
          <span className="font-medium text-[#202124]">{channel.name}</span>
          <span className="text-sm text-[#5f6368]">({channel.videoCount} videos)</span>
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

const VideoCard: React.FC<VideoCardProps> = ({ video, onDelete, onDownload, isDeleting, isDownloading, density }) => {
  const isCompact = density === 'compact';

  return (
    <div className="group relative">
      <a
        href={`https://www.youtube.com/watch?v=${video.videoId}`}
        target="_blank"
        rel="noopener noreferrer"
      >
        <div className={`aspect-video bg-[#f1f3f4] overflow-hidden relative ${isCompact ? 'rounded' : 'rounded-lg mb-2'}`}>
          <img
            src={video.thumbnailUrl}
            alt={video.title}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform"
          />
        </div>
        <h4 className={`text-[#202124] group-hover:text-[#1a73e8] ${isCompact ? 'text-xs line-clamp-1 mt-1' : 'text-sm line-clamp-2'}`}>
          {video.title}
        </h4>
        {!isCompact && (
          <p className="text-xs text-[#5f6368] mt-1">
            {video.clipCount} clips
          </p>
        )}
      </a>

      {/* Action buttons */}
      <div className={`absolute flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity ${isCompact ? 'top-1 right-1' : 'top-2 right-2'}`}>
        {/* Download button */}
        <button
          onClick={(e) => { e.preventDefault(); e.stopPropagation(); onDownload(); }}
          disabled={isDownloading}
          className={`bg-black/70 hover:bg-[#1a73e8] text-white rounded disabled:opacity-50 ${isCompact ? 'p-1' : 'p-1.5'}`}
          title="Download transcript (SRT)"
        >
          {isDownloading ? (
            <div className={`animate-spin border-2 border-white border-t-transparent rounded-full ${isCompact ? 'w-3 h-3' : 'w-4 h-4'}`} />
          ) : (
            <svg className={isCompact ? 'w-3 h-3' : 'w-4 h-4'} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          )}
        </button>
        {/* Delete button */}
        <button
          onClick={(e) => { e.preventDefault(); e.stopPropagation(); onDelete(); }}
          disabled={isDeleting}
          className={`bg-black/70 hover:bg-red-600 text-white rounded disabled:opacity-50 ${isCompact ? 'p-1' : 'p-1.5'}`}
          title="Delete from library"
        >
          {isDeleting ? (
            <div className={`animate-spin border-2 border-white border-t-transparent rounded-full ${isCompact ? 'w-3 h-3' : 'w-4 h-4'}`} />
          ) : (
            <svg className={isCompact ? 'w-3 h-3' : 'w-4 h-4'} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
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
    <div className="group border border-[#e8eaed] rounded-lg p-3 hover:border-[#dadce0] transition-colors">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-[#202124] truncate">{entry.query}</p>
          <p className="text-xs text-[#5f6368]">
            {formatRelativeTime(entry.timestamp)} • {entry.clips.length} clip{entry.clips.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          onClick={(e) => { e.stopPropagation(); onDelete(); }}
          className="text-[#5f6368] hover:text-[#c5221f] p-1 opacity-0 group-hover:opacity-100 transition-opacity"
          title="Remove from history"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
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
            <div className="relative w-24 aspect-video bg-[#f1f3f4] rounded overflow-hidden">
              <img
                src={clip.thumbnailUrl}
                alt={clip.title}
                className="w-full h-full object-cover group-hover/clip:scale-105 transition-transform"
              />
              <span className="absolute bottom-1 right-1 bg-black/80 text-white text-[10px] px-1 rounded">
                {formatTime(clip.startSeconds)}
              </span>
            </div>
            <p className="text-[10px] text-[#5f6368] mt-1 w-24 truncate group-hover/clip:text-[#1a73e8]">
              {clip.title}
            </p>
          </a>
        ))}
        {entry.clips.length > 4 && (
          <div className="flex-shrink-0 w-24 aspect-video bg-[#f1f3f4] rounded flex items-center justify-center">
            <span className="text-xs text-[#5f6368]">+{entry.clips.length - 4} more</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default LibraryView;
