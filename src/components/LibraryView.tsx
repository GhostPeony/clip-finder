import React, { useState, useEffect } from 'react';
import { LibraryData, LibraryChannel, LibraryVideo } from '../types';
import { fetchLibrary, deleteVideo } from '../services/api';

interface LibraryViewProps {
  onIndexMore: () => void;
}

export const LibraryView: React.FC<LibraryViewProps> = ({ onIndexMore }) => {
  const [library, setLibrary] = useState<LibraryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [expandedChannels, setExpandedChannels] = useState<Set<string>>(new Set());
  const [deletingVideo, setDeletingVideo] = useState<string | null>(null);

  useEffect(() => {
    loadLibrary();
  }, []);

  const loadLibrary = async () => {
    setLoading(true);
    const data = await fetchLibrary();
    setLibrary(data);
    // Expand all channels by default
    setExpandedChannels(new Set(data.channels.map(c => c.name)));
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
      <div className="mb-6">
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

      {/* Channels */}
      <div className="space-y-4">
        {filteredChannels.map((channel) => (
          <ChannelSection
            key={channel.name}
            channel={channel}
            isExpanded={expandedChannels.has(channel.name)}
            onToggle={() => toggleChannel(channel.name)}
            filter={filter}
            onDeleteVideo={handleDeleteVideo}
            deletingVideo={deletingVideo}
          />
        ))}
      </div>

      {filteredChannels.length === 0 && filter && (
        <div className="text-center py-12 text-[#5f6368]">
          No videos matching "{filter}"
        </div>
      )}
    </div>
  );
};

interface ChannelSectionProps {
  channel: LibraryChannel;
  isExpanded: boolean;
  onToggle: () => void;
  filter: string;
  onDeleteVideo: (videoId: string, title: string) => void;
  deletingVideo: string | null;
}

const ChannelSection: React.FC<ChannelSectionProps> = ({ channel, isExpanded, onToggle, filter, onDeleteVideo, deletingVideo }) => {
  const filteredVideos = filter
    ? channel.videos.filter(v => v.title.toLowerCase().includes(filter.toLowerCase()))
    : channel.videos;

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
        <div className="px-4 pb-4">
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
            {filteredVideos.map((video) => (
              <VideoCard
                key={video.videoId}
                video={video}
                onDelete={() => onDeleteVideo(video.videoId, video.title)}
                isDeleting={deletingVideo === video.videoId}
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
  isDeleting: boolean;
}

const VideoCard: React.FC<VideoCardProps> = ({ video, onDelete, isDeleting }) => {
  return (
    <div className="group relative">
      <a
        href={`https://www.youtube.com/watch?v=${video.videoId}`}
        target="_blank"
        rel="noopener noreferrer"
      >
        <div className="aspect-video bg-[#f1f3f4] rounded-lg overflow-hidden mb-2 relative">
          <img
            src={video.thumbnailUrl}
            alt={video.title}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform"
          />
        </div>
        <h4 className="text-sm text-[#202124] line-clamp-2 group-hover:text-[#1a73e8]">
          {video.title}
        </h4>
        <p className="text-xs text-[#5f6368] mt-1">
          {video.clipCount} clips
        </p>
      </a>

      {/* Delete button */}
      <button
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); onDelete(); }}
        disabled={isDeleting}
        className="absolute top-2 right-2 bg-black/70 hover:bg-red-600 text-white p-1.5 rounded opacity-0 group-hover:opacity-100 transition-opacity disabled:opacity-50"
        title="Delete from library"
      >
        {isDeleting ? (
          <div className="w-4 h-4 animate-spin border-2 border-white border-t-transparent rounded-full" />
        ) : (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        )}
      </button>
    </div>
  );
};

export default LibraryView;
