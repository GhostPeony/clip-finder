import React from 'react';
import { SearchHistoryEntry } from '../../types';
import { formatRelativeTime, formatTimestamp } from '../../lib/time';
import { Panel } from '../ui/Panel';

export function HistoryView({
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
    <Panel
      title="Recent searches"
      size="section"
      description={`${entries.length} saved local query runs`}
      action={
        <button onClick={onClear} className="link-quiet text-sm">
          Clear all
        </button>
      }
    >
      <div className="grid gap-3 lg:grid-cols-2">
        {entries.map((entry) => (
          <SearchHistoryCard
            key={entry.id}
            entry={entry}
            onDelete={() => onDeleteEntry(entry.id)}
          />
        ))}
      </div>
    </Panel>
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
          className="relative rounded-full p-1 text-muted opacity-0 transition-opacity after:absolute after:-inset-2.5 after:content-[''] hover:text-rose-deep group-hover:opacity-100 focus-visible:opacity-100"
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
