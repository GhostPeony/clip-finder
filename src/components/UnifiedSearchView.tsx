import React, { useEffect, useState, useRef } from 'react';
import { VideoClip } from '../types';
import { ingestChannel, searchVideoClips, saveSearchToHistory } from '../services/api';

interface UnifiedSearchViewProps {
  onSearchComplete: (clips: VideoClip[], answer: string, activeClip: VideoClip | null) => void;
  onIndexComplete: () => void; // Called when indexing completes without a search
  maxSearchResults?: number | null;
}

type WorkflowStatus = 'idle' | 'ingesting' | 'searching' | 'complete' | 'error';
type WorkbenchMode = 'index' | 'library';

export const UnifiedSearchView: React.FC<UnifiedSearchViewProps> = ({
  onSearchComplete,
  onIndexComplete,
  maxSearchResults = 5,
}) => {
  const [message, setMessage] = useState('');
  const [workbenchMode, setWorkbenchMode] = useState<WorkbenchMode>('index');
  const [resultLimit, setResultLimit] = useState(5);

  // Workflow state
  const [status, setStatus] = useState<WorkflowStatus>('idle');
  const [currentStep, setCurrentStep] = useState('');
  const [ingestLogs, setIngestLogs] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (maxSearchResults && resultLimit > maxSearchResults) {
      setResultLimit(maxSearchResults);
    }
  }, [maxSearchResults, resultLimit]);

  // Track URLs pending ingestion
  const pendingUrlsRef = useRef<string[]>([]);
  const currentUrlIndexRef = useRef(0);

  // Extract YouTube URLs from natural language message
  const extractUrls = (text: string): string[] => {
    const urlPattern = /(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)[^\s]*/gi;
    const matches = text.match(urlPattern) || [];
    return [...new Set(matches)]; // Remove duplicates
  };

  // Get the query text (message without URLs)
  const getQueryText = (text: string): string => {
    const urlPattern = /(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)[^\s]*/gi;
    return text.replace(urlPattern, '').replace(/\s+/g, ' ').trim();
  };

  // Main submit handler
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim()) return;

    setError(null);
    setIngestLogs([]);

    const urls = extractUrls(message);
    const queryText = getQueryText(message);

    // Determine what action to take
    const hasUrls = urls.length > 0;
    const hasQuery = queryText.length > 0;

    // Need either URLs to ingest or library mode selected.
    if (!hasUrls && workbenchMode === 'index') {
      setError('Paste a YouTube URL, or switch to Search library.');
      return;
    }

    // If searching library without URLs, need a query.
    if (!hasUrls && workbenchMode === 'library' && !hasQuery) {
      setError('Enter a search query to search your library');
      return;
    }

    if (hasUrls) {
      // Ingest URLs
      pendingUrlsRef.current = urls;
      currentUrlIndexRef.current = 0;
      setStatus('ingesting');

      // If there's a query, search after indexing. Otherwise, just index.
      const shouldSearch = hasQuery || workbenchMode === 'library';
      await ingestAllUrls(urls, shouldSearch ? queryText || message : null);
    } else {
      // Direct search (searching existing library)
      await performSearch(queryText);
    }
  };

  // Ingest all URLs sequentially
  const ingestAllUrls = async (urls: string[], queryText: string | null) => {
    for (let i = 0; i < urls.length; i++) {
      currentUrlIndexRef.current = i;
      setCurrentStep(`Indexing ${i + 1} of ${urls.length}...`);

      await new Promise<void>((resolve) => {
        ingestChannel(
          urls[i],
          (msg) => setIngestLogs((prev) => [...prev, msg]),
          () => resolve(),
        );
      });
    }

    // After all ingestion complete
    if (queryText) {
      // Search if there was a query
      setCurrentStep('Searching...');
      await performSearch(queryText);
    } else {
      // Index only - navigate to library
      setStatus('complete');
      setCurrentStep('');
      onIndexComplete();
    }
  };

  // Perform the search
  const performSearch = async (queryText: string) => {
    setStatus('searching');
    setCurrentStep('Searching your videos...');

    try {
      const { answer, relevantClips } = await searchVideoClips(queryText, resultLimit);
      setStatus('complete');
      setCurrentStep('');

      // Filter to clips with valid videoId, find first valid one for active clip
      const validClips = relevantClips.filter((clip) => clip.videoId);
      const firstValidClip = validClips.length > 0 ? validClips[0] : null;

      // Save to search history if we got results
      if (validClips.length > 0) {
        saveSearchToHistory(queryText, validClips);
      }

      // Pass results up to parent with first valid clip as active
      onSearchComplete(relevantClips, answer, firstValidClip);
    } catch (err) {
      setStatus('error');
      setError(err instanceof Error ? err.message : 'Search failed');
    }
  };

  const isWorking = status === 'ingesting' || status === 'searching';
  const urls = extractUrls(message);
  const queryText = getQueryText(message);
  const hasQuery = queryText.length > 0;
  const canSubmit = message.trim() && (urls.length > 0 || workbenchMode === 'library');
  const resultOptions = [1, 3, 5, 10].filter(
    (option) => !maxSearchResults || option <= maxSearchResults,
  );

  // Determine button label
  const getButtonLabel = () => {
    if (urls.length > 0 && (hasQuery || workbenchMode === 'library')) {
      return 'Index and search';
    } else if (urls.length > 0) {
      return 'Add videos';
    } else if (workbenchMode === 'index') {
      return 'Add videos';
    } else {
      return 'Search library';
    }
  };

  return (
    <div className="min-w-0 w-full">
      <div className="min-w-0 overflow-hidden rounded-2xl bg-cream">
        {!isWorking ? (
          <form onSubmit={handleSubmit} className="p-4 sm:p-5 md:p-6">
            <div className="mb-5">
              <h1 className="font-serif text-3xl font-medium text-ink md:text-4xl">
                Add YouTube videos
              </h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-bark">
                Paste a video, playlist, or channel. Add a question if you want results after
                indexing.
              </p>
            </div>

            <div className="mb-4">
              <label
                htmlFor="message"
                className="mb-2 block text-xs font-semibold uppercase tracking-wide text-muted"
              >
                {workbenchMode === 'library'
                  ? 'Search query'
                  : 'Paste YouTube link and optional query'}
              </label>
              <textarea
                id="message"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder={
                  workbenchMode === 'library'
                    ? 'Example: the part where they explain why pricing objections are really uncertainty'
                    : 'Paste a YouTube video, playlist, or channel URL\nOptional: add what you want Memexai to find after indexing'
                }
                rows={7}
                className="input w-full resize-none px-4 py-3 text-sm"
              />
              {urls.length > 0 && (
                <p className="mt-2 text-xs font-medium text-teal-deep">
                  {urls.length} YouTube link{urls.length !== 1 ? 's' : ''} detected
                </p>
              )}
            </div>

            {/* Error Message */}
            {error && (
              <div className="mb-4 rounded-xl bg-rose/10 p-3 text-sm font-medium text-rose-deep">
                {error}
              </div>
            )}

            <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                <div className="inline-flex w-full min-w-0 rounded-xl border border-ink/10 bg-surface p-1 sm:w-auto">
                  <button
                    type="button"
                    onClick={() => setWorkbenchMode('index')}
                    aria-pressed={workbenchMode === 'index'}
                    aria-label="Switch to add videos"
                    className={`min-w-0 flex-1 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-semibold transition-all sm:flex-none ${
                      workbenchMode === 'index'
                        ? 'bg-petal text-ink shadow-soft'
                        : 'text-bark hover:text-ink'
                    }`}
                  >
                    Add videos
                  </button>
                  <button
                    type="button"
                    onClick={() => setWorkbenchMode('library')}
                    aria-pressed={workbenchMode === 'library'}
                    aria-label="Switch to search library"
                    className={`min-w-0 flex-1 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-semibold transition-all sm:flex-none ${
                      workbenchMode === 'library'
                        ? 'bg-petal text-ink shadow-soft'
                        : 'text-bark hover:text-ink'
                    }`}
                  >
                    Search library
                  </button>
                </div>

                <label className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted">
                  Results
                  <select
                    value={resultLimit}
                    onChange={(e) => setResultLimit(Number(e.target.value))}
                    className="input cursor-pointer px-3 py-2 text-sm normal-case tracking-normal"
                  >
                    {resultOptions.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <button
                type="submit"
                disabled={!canSubmit}
                className="btn btn-primary w-full whitespace-nowrap lg:min-w-40 lg:w-auto"
              >
                {getButtonLabel()}
              </button>
            </div>
          </form>
        ) : (
          /* Working State */
          <div className="p-6">
            <div className="flex flex-col items-center justify-center py-12">
              {/* Spinning Circle */}
              <div className="relative">
                <div className="h-16 w-16 rounded-full border-4 border-petal"></div>
                <div className="absolute left-0 top-0 h-16 w-16 animate-spin rounded-full border-4 border-transparent border-t-rose"></div>
              </div>

              {/* Current Step */}
              <p className="mt-6 min-h-[1.5rem] max-w-md text-center text-sm font-medium text-ink transition-all">
                {currentStep || (status === 'ingesting' ? 'Starting indexing...' : 'Searching...')}
              </p>

              {/* Progress Context */}
              {status === 'ingesting' && (
                <p className="mt-2 text-xs font-medium uppercase tracking-wide text-muted">
                  {currentUrlIndexRef.current + 1} of {pendingUrlsRef.current.length} sources
                </p>
              )}

              {/* Latest Log */}
              {ingestLogs.length > 0 && (
                <p className="mt-4 max-w-sm truncate text-center text-xs text-bark">
                  {ingestLogs[ingestLogs.length - 1]}
                </p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default UnifiedSearchView;
