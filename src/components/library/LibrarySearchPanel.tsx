import React, { useEffect, useRef, useState } from 'react';
import { VideoClip } from '../../types';
import { formatTimestampLabel } from '../../lib/time';
import { buildTimestampUrl } from '../../lib/videoKnowledge';
import { AnswerSection } from '../AnswerSection';
import { BrandLoader } from '../BrandLoader';
import { Notice } from '../ui/Notice';
import { SelectableTile } from '../ui/SelectableTile';

export type LibrarySearchMode = 'hybrid' | 'semantic' | 'keyword';

const searchModeOptions: Array<{
  id: LibrarySearchMode;
  label: string;
  helper: string;
}> = [
  {
    id: 'hybrid',
    label: 'Smart',
    helper: 'Best first search across meaning, titles, and exact terms.',
  },
  {
    id: 'semantic',
    label: 'Meaning',
    helper: 'Use when you remember the idea but not the wording.',
  },
  { id: 'keyword', label: 'Exact', helper: 'Use for names, quotes, acronyms, and product terms.' },
];

export function LibrarySearchPanel({
  mode,
  query,
  searching,
  answer,
  results,
  error,
  onModeChange,
  onQueryChange,
  onSubmit,
  projectName,
}: {
  mode: LibrarySearchMode;
  query: string;
  searching: boolean;
  answer: string;
  results: VideoClip[];
  error: string;
  onModeChange: (mode: LibrarySearchMode) => void;
  onQueryChange: (query: string) => void;
  onSubmit: (event: React.FormEvent) => void;
  projectName?: string;
}) {
  const selectedMode = searchModeOptions.find((option) => option.id === mode);

  return (
    <section className="card p-4 sm:p-5">
      <form onSubmit={onSubmit} className="space-y-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 className="font-serif text-2xl font-medium text-ink">Search saved videos</h2>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-bark">
              {projectName
                ? `Searching project: ${projectName}.`
                : 'Find the video, idea, or moment you saved without pasting the link into an agent again.'}
            </p>
          </div>
          <div className="inline-flex rounded-2xl border border-ink/10 bg-cream p-1">
            {searchModeOptions.map((option) => (
              <SelectableTile
                key={option.id}
                onClick={() => onModeChange(option.id)}
                aria-pressed={mode === option.id}
                selected={mode === option.id}
                unselectedClassName="text-bark hover:text-ink"
                className="rounded-xl px-3 py-2 text-sm font-semibold transition-all"
              >
                {option.label}
              </SelectableTile>
            ))}
          </div>
        </div>

        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
          <label className="sr-only" htmlFor="library-search">
            Search saved videos
          </label>
          <input
            id="library-search"
            type="search"
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder={
              mode === 'keyword'
                ? 'Try an exact phrase, person, tool, acronym...'
                : 'Try a question or idea from your saved videos...'
            }
            className="input w-full px-4 py-3 text-base"
          />
          <button type="submit" disabled={searching || !query.trim()} className="btn btn-primary">
            {searching ? 'Searching...' : 'Search'}
          </button>
        </div>

        {selectedMode ? (
          <p className="text-xs font-medium text-muted">{selectedMode.helper}</p>
        ) : null}
      </form>

      <LibrarySearchResults answer={answer} results={results} error={error} searching={searching} />
    </section>
  );
}

function LibrarySearchResults({
  answer,
  results,
  error,
  searching,
}: {
  answer: string;
  results: VideoClip[];
  error: string;
  searching: boolean;
}) {
  const [highlightedClipId, setHighlightedClipId] = useState<string | null>(null);
  const highlightTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (highlightTimeoutRef.current) window.clearTimeout(highlightTimeoutRef.current);
    };
  }, []);

  const handleCitationClick = (clip: VideoClip) => {
    const card = document.getElementById(`library-clip-${clip.id}`);
    if (card) {
      card.scrollIntoView({ behavior: 'smooth', block: 'center' });
      setHighlightedClipId(clip.id);
      if (highlightTimeoutRef.current) window.clearTimeout(highlightTimeoutRef.current);
      highlightTimeoutRef.current = window.setTimeout(() => setHighlightedClipId(null), 2000);
    } else {
      window.open(
        buildTimestampUrl({ videoId: clip.videoId, title: clip.title }, clip.startSeconds),
        '_blank',
        'noopener,noreferrer',
      );
    }
  };

  if (searching) {
    return (
      <div className="mt-4 rounded-xl bg-cream p-4">
        <BrandLoader compact label="Searching saved videos" />
      </div>
    );
  }

  if (error) {
    return (
      <Notice tone="error" className="mt-4 rounded-xl p-4 text-sm">
        {error}
      </Notice>
    );
  }

  if (!answer && results.length === 0) return null;

  return (
    <div className="mt-4 space-y-3">
      {answer ? (
        <AnswerSection
          variant="inline"
          answer={answer}
          clips={results}
          onCitationClick={handleCitationClick}
        />
      ) : null}

      {results.length > 0 ? (
        <div className="grid gap-3 md:grid-cols-2">
          {results.map((clip, index) => (
            <a
              key={`${clip.videoId}-${clip.startSeconds}-${index}`}
              id={`library-clip-${clip.id}`}
              href={buildTimestampUrl(
                { videoId: clip.videoId, title: clip.title },
                clip.startSeconds,
              )}
              target="_blank"
              rel="noopener noreferrer"
              className={`rounded-xl bg-cream p-3 transition-colors hover:bg-petal/60 ${
                highlightedClipId === clip.id ? 'ring-2 ring-rose/40' : ''
              }`}
            >
              <div className="flex gap-3">
                <img
                  src={clip.thumbnailUrl}
                  alt=""
                  className="aspect-video w-24 shrink-0 rounded-lg object-cover shadow-soft"
                />
                <div className="min-w-0">
                  <p className="line-clamp-2 text-sm font-semibold text-ink">{clip.title}</p>
                  <p className="mt-1 truncate text-xs text-muted">
                    {clip.channelName} · {formatTimestampLabel(clip.startSeconds)}
                  </p>
                  <p className="mt-2 line-clamp-2 text-xs leading-5 text-bark">
                    {clip.matchSnippet || clip.content}
                  </p>
                </div>
              </div>
            </a>
          ))}
        </div>
      ) : null}
    </div>
  );
}
