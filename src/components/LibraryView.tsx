import React, { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { IngestionJob, LibraryData, LibraryVideo, SearchHistoryEntry } from '../types';
import {
  clearSearchHistory,
  deleteSearchHistoryEntry,
  fetchIngestionJobs,
  fetchLibrary,
  getCachedIngestionJobs,
  getCachedLibrary,
  getSearchHistory,
} from '../services/api';
import { BrandLoader } from './BrandLoader';

const LibraryKnowledgeGraph = lazy(() =>
  import('./LibraryKnowledgeGraph').then((module) => ({ default: module.LibraryKnowledgeGraph })),
);

interface LibraryViewProps {
  onIndexMore: () => void;
}

type LibrarySurface = 'videos' | 'topics' | 'guides' | 'history';
type VideoWithChannel = LibraryVideo & { channelName: string };

const librarySurfaceOptions: Array<{
  id: LibrarySurface;
  label: string;
  mobileLabel: string;
  description: string;
}> = [
  {
    id: 'videos',
    label: 'Videos',
    mobileLabel: 'Videos',
    description: 'Pick a saved video and inspect its report, topics, and source links.',
  },
  {
    id: 'topics',
    label: 'Topics',
    mobileLabel: 'Topics',
    description: 'Browse deduped source-backed ideas grouped by category.',
  },
  {
    id: 'guides',
    label: 'Reports',
    mobileLabel: 'Reports',
    description: 'Open TLDRs and source reports organized by video.',
  },
  {
    id: 'history',
    label: 'Recent searches',
    mobileLabel: 'Searches',
    description: 'Return to previous saved-video searches and their clips.',
  },
];

export const LibraryView: React.FC<LibraryViewProps> = ({ onIndexMore }) => {
  const [library, setLibrary] = useState<LibraryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [librarySurface, setLibrarySurface] = useState<LibrarySurface>('videos');
  const [searchHistory, setSearchHistory] = useState<SearchHistoryEntry[]>([]);
  const [recentJobs, setRecentJobs] = useState<IngestionJob[]>([]);
  const [loadError, setLoadError] = useState('');

  const loadLibrary = async () => {
    setLoadError('');
    const [cachedLibrary, cachedJobs] = await Promise.all([
      getCachedLibrary(),
      getCachedIngestionJobs(),
    ]);

    if (cachedLibrary) {
      setLibrary(cachedLibrary);
      setLoading(false);
    } else {
      setLoading(true);
    }

    if (cachedJobs) {
      setRecentJobs(cachedJobs.slice(0, 3));
    }

    const [dataResult, jobsResult] = await Promise.allSettled([
      fetchLibrary(),
      fetchIngestionJobs(),
    ]);

    if (jobsResult.status === 'fulfilled') {
      setRecentJobs(jobsResult.value.slice(0, 3));
    }

    if (dataResult.status === 'fulfilled') {
      setLibrary(dataResult.value);
    } else {
      console.warn('Error loading library:', dataResult.reason);
      if (!cachedLibrary) {
        setLibrary(null);
        setLoadError(
          "Memexai couldn't read your saved-video library. Your imports may still be saved; retry in a moment.",
        );
      }
    }

    setLoading(false);
  };

  useEffect(() => {
    void loadLibrary();
    setSearchHistory(getSearchHistory());
  }, []);

  const latestVideos = useMemo<VideoWithChannel[]>(() => {
    const videos =
      library?.channels.flatMap((channel) =>
        channel.videos.map((video) => ({ ...video, channelName: channel.name })),
      ) || [];

    return [...videos].sort((a, b) => (b.indexedAt || 0) - (a.indexedAt || 0));
  }, [library]);

  const handleDeleteHistoryEntry = (id: string) => {
    deleteSearchHistoryEntry(id);
    setSearchHistory(getSearchHistory());
  };

  const handleClearHistory = () => {
    if (!confirm('Clear all search history?')) return;
    clearSearchHistory();
    setSearchHistory([]);
  };

  if (loading) {
    return (
      <div className="card mx-auto max-w-xl p-8">
        <BrandLoader
          label="Loading your video library"
          detail="Checking saved videos, recent imports, and generated reports."
        />
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="card mx-auto max-w-2xl p-8">
        <div className="text-center">
          <h2 className="font-serif text-4xl font-medium text-ink">Library could not load</h2>
          <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-bark">{loadError}</p>
          <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
            <button onClick={() => void loadLibrary()} className="btn btn-primary">
              Retry
            </button>
            <button onClick={onIndexMore} className="btn btn-secondary">
              Add videos
            </button>
          </div>
        </div>

        {recentJobs.length > 0 ? (
          <div className="mt-6 border-t border-ink/10 pt-5">
            <h3 className="text-left text-sm font-semibold uppercase tracking-wide text-muted">
              Recent imports
            </h3>
            <div className="mt-3 space-y-2">
              {recentJobs.map((job) => (
                <LibraryImportRow key={job.id} job={job} />
              ))}
            </div>
          </div>
        ) : null}
      </div>
    );
  }

  if (!library || library.totalVideos === 0) {
    return (
      <div className="card mx-auto max-w-2xl p-8">
        <div className="text-center">
          <h2 className="font-serif text-4xl font-medium text-ink">No videos indexed yet</h2>
          <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-bark">
            Add a YouTube video, playlist, or channel to build your searchable saved-video library.
            Failed imports stay visible here so you can see what happened.
          </p>
          <button onClick={onIndexMore} className="btn btn-primary mt-6">
            Add videos
          </button>
        </div>

        {recentJobs.length > 0 ? (
          <div className="mt-6 border-t border-ink/10 pt-5">
            <h3 className="text-left text-sm font-semibold uppercase tracking-wide text-muted">
              Recent imports
            </h3>
            <div className="mt-3 space-y-2">
              {recentJobs.map((job) => (
                <LibraryImportRow key={job.id} job={job} />
              ))}
            </div>
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="font-serif text-4xl font-medium text-ink md:text-5xl">Library</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-bark">
            Search saved videos, read TLDRs and reports, and jump back to useful moments.
          </p>
        </div>
        <button onClick={onIndexMore} className="btn btn-primary self-start md:self-auto">
          Add videos
        </button>
      </div>

      <div className="grid gap-5 lg:grid-cols-[240px_minmax(0,1fr)] lg:items-start">
        <aside className="card min-w-0 p-3 lg:sticky lg:top-24">
          <p className="px-2 pb-2 text-xs font-semibold uppercase tracking-wide text-muted">
            Library menu
          </p>
          <nav aria-label="Library sections" className="grid grid-cols-2 gap-2 lg:grid-cols-1">
            {librarySurfaceOptions.map((option) => (
              <button
                key={option.id}
                type="button"
                aria-label={option.label}
                onClick={() => setLibrarySurface(option.id)}
                aria-current={librarySurface === option.id ? 'page' : undefined}
                className={`rounded-xl px-3 py-3 text-left transition-all ${
                  librarySurface === option.id
                    ? 'bg-surface text-ink shadow-soft'
                    : 'bg-cream text-bark hover:bg-petal/50 hover:text-ink'
                }`}
              >
                <span className="block text-sm font-semibold">
                  <span className="sm:hidden">{option.mobileLabel}</span>
                  <span className="hidden sm:inline">{option.label}</span>
                </span>
                <span className="mt-1 hidden text-xs leading-5 text-muted sm:block">
                  {option.description}
                </span>
              </button>
            ))}
          </nav>
        </aside>

        <div className="min-w-0">
          {librarySurface !== 'history' ? (
            <Suspense
              fallback={
                <div className="card p-6">
                  <BrandLoader compact label="Opening library browser" />
                </div>
              }
            >
              <LibraryKnowledgeGraph
                activeView={librarySurface}
                latestVideos={latestVideos}
                onIndexMore={onIndexMore}
              />
            </Suspense>
          ) : null}

          {librarySurface === 'history' ? (
            <HistoryView
              entries={searchHistory}
              onClear={handleClearHistory}
              onDeleteEntry={handleDeleteHistoryEntry}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
};

function LibraryImportRow({ job }: { job: IngestionJob }) {
  return (
    <div className="rounded-xl bg-cream px-3 py-2 text-left">
      <div className="flex flex-wrap items-center gap-2">
        <span className={libraryJobStatusClass[job.status]}>{job.status}</span>
        <span className="text-xs font-semibold uppercase tracking-wide text-muted">
          {job.source_type}
        </span>
      </div>
      <p className="mt-1 truncate text-sm font-semibold text-ink">{job.source_url}</p>
      <p
        className={`mt-1 truncate text-xs ${
          job.status === 'failed' ? 'font-medium text-rose-deep' : 'text-muted'
        }`}
      >
        {libraryJobOutcomeText(job)}
      </p>
    </div>
  );
}

const libraryJobStatusClass: Record<IngestionJob['status'], string> = {
  queued: 'chip chip-violet',
  running: 'chip chip-teal',
  completed: 'chip chip-leaf',
  partial: 'chip chip-sun',
  failed: 'chip',
  cancelled: 'chip chip-violet',
};

function libraryJobOutcomeText(job: IngestionJob): string {
  if (job.status === 'failed') {
    return job.error || job.last_message || 'Import failed';
  }
  if (job.status === 'partial') {
    return `Partial import: ${job.indexed_video_count} indexed, ${job.skipped_video_count} skipped, ${job.failed_video_count} failed`;
  }
  if (job.status === 'completed') {
    return `${job.indexed_video_count} video${job.indexed_video_count === 1 ? '' : 's'} indexed`;
  }
  return job.last_message || 'Import in progress';
}

function HistoryView({
  entries,
  onClear,
  onDeleteEntry,
}: {
  entries: SearchHistoryEntry[];
  onClear: () => void;
  onDeleteEntry: (id: string) => void;
}) {
  if (entries.length === 0) {
    return (
      <div className="card p-8 text-center">
        <h2 className="font-serif text-3xl font-medium text-ink">No recent searches</h2>
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-bark">
          Searches you run from the dashboard will appear here with the clips they returned.
        </p>
      </div>
    );
  }

  return (
    <section className="card p-5">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="font-serif text-3xl font-medium text-ink">Recent searches</h2>
          <p className="mt-1 text-sm text-bark">{entries.length} saved local query runs</p>
        </div>
        <button
          onClick={onClear}
          className="self-start text-xs font-semibold uppercase tracking-wide text-muted hover:text-rose-deep sm:self-auto"
        >
          Clear all
        </button>
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        {entries.map((entry) => (
          <SearchHistoryCard
            key={entry.id}
            entry={entry}
            onDelete={() => onDeleteEntry(entry.id)}
          />
        ))}
      </div>
    </section>
  );
}

interface SearchHistoryCardProps {
  entry: SearchHistoryEntry;
  onDelete: () => void;
}

const SearchHistoryCard: React.FC<SearchHistoryCardProps> = ({ entry, onDelete }) => {
  return (
    <div className="group rounded-xl border border-ink/10 bg-cream p-3 transition-colors hover:bg-surface">
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-ink">{entry.query}</p>
          <p className="text-xs text-muted">
            {formatRelativeTime(entry.timestamp)} · {entry.clips.length} clip
            {entry.clips.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          onClick={(event) => {
            event.stopPropagation();
            onDelete();
          }}
          className="rounded-full p-1 text-muted opacity-0 transition-opacity hover:text-rose-deep group-hover:opacity-100 focus-visible:opacity-100"
          title="Remove from history"
          aria-label="Remove from history"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      <div className="flex gap-2 overflow-x-auto pb-1">
        {entry.clips.slice(0, 4).map((clip, index) => (
          <a
            key={`${clip.videoId}-${clip.startSeconds}-${index}`}
            href={`https://www.youtube.com/watch?v=${clip.videoId}&t=${clip.startSeconds}`}
            target="_blank"
            rel="noopener noreferrer"
            className="group/clip shrink-0"
          >
            <div className="relative aspect-video w-24 overflow-hidden rounded-lg bg-petal">
              <img
                src={clip.thumbnailUrl}
                alt={clip.title}
                className="h-full w-full object-cover transition-transform group-hover/clip:scale-105"
              />
              <span className="absolute bottom-1 right-1 rounded bg-sun px-1 font-mono text-[10px] font-medium text-ink">
                {formatTimestamp(clip.startSeconds)}
              </span>
            </div>
            <p className="mt-1 w-24 truncate text-[10px] text-muted group-hover/clip:text-rose-deep">
              {clip.title}
            </p>
          </a>
        ))}
        {entry.clips.length > 4 ? (
          <div className="flex aspect-video w-24 shrink-0 items-center justify-center rounded-lg bg-lavender">
            <span className="text-xs font-semibold text-ink">+{entry.clips.length - 4} more</span>
          </div>
        ) : null}
      </div>
    </div>
  );
};

function formatRelativeTime(timestamp: number): string {
  const diff = Date.now() - timestamp;
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;
  return new Date(timestamp).toLocaleDateString();
}

function formatTimestamp(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
}

export default LibraryView;
