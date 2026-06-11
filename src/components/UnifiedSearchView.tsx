import React, { useEffect, useState, useRef } from 'react';
import { VideoClip } from '../types';
import { ingestChannel, searchVideoClips, saveSearchToHistory } from '../services/api';

interface UnifiedSearchViewProps {
  onSearchComplete: (clips: VideoClip[], answer: string, activeClip: VideoClip | null) => void;
  onIndexComplete: () => void; // Called when indexing completes without a search
  isBackendConnected: boolean;
  hasApiKey: boolean;
  hasServerKey: boolean;
  allowUserKeys: boolean;
  showLocalBackendHelp: boolean;
  onOpenSettings: () => void;
  maxSearchResults?: number | null;
}

type WorkflowStatus = 'idle' | 'ingesting' | 'searching' | 'complete' | 'error';
type WorkbenchMode = 'index' | 'library';

export const UnifiedSearchView: React.FC<UnifiedSearchViewProps> = ({
  onSearchComplete,
  onIndexComplete,
  isBackendConnected,
  hasApiKey,
  hasServerKey,
  allowUserKeys,
  showLocalBackendHelp,
  onOpenSettings,
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
      setError('Paste a YouTube URL, or switch to Search library for existing videos.');
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
  const shouldShowApiKeySetup = allowUserKeys && !hasApiKey && !hasServerKey;
  const canSubmit =
    isBackendConnected && message.trim() && (urls.length > 0 || workbenchMode === 'library');
  const resultOptions = [1, 3, 5, 10].filter(
    (option) => !maxSearchResults || option <= maxSearchResults,
  );

  // Determine button label
  const getButtonLabel = () => {
    if (urls.length > 0 && (hasQuery || workbenchMode === 'library')) {
      return 'Index and search';
    } else if (urls.length > 0) {
      return 'Index source';
    } else if (workbenchMode === 'index') {
      return 'Index source';
    } else {
      return 'Search library';
    }
  };

  return (
    <div className="mx-auto w-full max-w-3xl">
      <div className="mb-6">
        <p className="eyebrow mb-2">Workbench</p>
        <h2 className="font-serif text-4xl font-medium text-ink">Find a moment.</h2>
        <p className="mt-2 text-sm leading-6 text-bark">
          Index a new YouTube source, search your existing library, or do both in one request.
        </p>
      </div>

      {/* API Key Warning */}
      {shouldShowApiKeySetup && (
        <div className="mb-6 flex items-center gap-3 rounded-xl bg-sun/25 p-4 text-ink">
          <svg className="w-6 h-6 flex-shrink-0 text-bark" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" />
          </svg>
          <div className="flex-1">
            <p className="font-medium">API key needed for local mode</p>
            <p className="text-sm">Add a Gemini API key to use this self-hosted setup.</p>
          </div>
          <button onClick={onOpenSettings} className="btn btn-secondary whitespace-nowrap">
            Add API Key
          </button>
        </div>
      )}

      {/* Main Card */}
      <div className="rounded-2xl bg-cream">
        {!isWorking ? (
          <form onSubmit={handleSubmit} className="p-6">
            {/* Single Message Input */}
            <div className="mb-5">
              <div className="mb-4 grid gap-2 sm:grid-cols-2">
                <button
                  type="button"
                  onClick={() => setWorkbenchMode('index')}
                  aria-pressed={workbenchMode === 'index'}
                  className={`rounded-xl border p-4 text-left transition-all ${
                    workbenchMode === 'index'
                      ? 'border-rose-deep bg-petal/40 shadow-soft'
                      : 'border-ink/10 bg-surface hover:border-ink/25'
                  }`}
                >
                  <span className="block text-sm font-semibold text-ink">Index source</span>
                  <span className="mt-1 block text-xs text-bark">
                    Add a video, playlist, or channel.
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => setWorkbenchMode('library')}
                  aria-pressed={workbenchMode === 'library'}
                  className={`rounded-xl border p-4 text-left transition-all ${
                    workbenchMode === 'library'
                      ? 'border-rose-deep bg-petal/40 shadow-soft'
                      : 'border-ink/10 bg-surface hover:border-ink/25'
                  }`}
                >
                  <span className="block text-sm font-semibold text-ink">Search library</span>
                  <span className="mt-1 block text-xs text-bark">
                    Search sources you already indexed.
                  </span>
                </button>
              </div>
              <label
                htmlFor="message"
                className="mb-2 block text-xs font-semibold uppercase tracking-wide text-muted"
              >
                {workbenchMode === 'library'
                  ? 'Describe the moment'
                  : 'Paste source and optional query'}
              </label>
              <textarea
                id="message"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder={
                  workbenchMode === 'library'
                    ? 'Example: the part where they explain why pricing objections are really uncertainty'
                    : 'Example: https://youtube.com/@channel\nOptional: find the section about pricing objections'
                }
                disabled={!isBackendConnected}
                rows={3}
                className="input w-full resize-none px-4 py-3 text-sm disabled:cursor-not-allowed disabled:bg-petal/50"
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

            {/* Submit Row */}
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="submit"
                disabled={!canSubmit}
                className="btn btn-primary whitespace-nowrap"
              >
                {getButtonLabel()}
              </button>

              <label className="text-xs font-medium uppercase tracking-wide text-muted">
                Results:
              </label>
              <select
                value={resultLimit}
                onChange={(e) => setResultLimit(Number(e.target.value))}
                className="input cursor-pointer px-3 py-2 text-sm"
              >
                {resultOptions.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </div>

            {/* Backend Unavailable Warning */}
            {!isBackendConnected && (
              <div className="mt-4 rounded-xl border border-ink/10 bg-surface p-4">
                <div className="flex gap-3">
                  <svg
                    className="mt-0.5 h-5 w-5 flex-shrink-0 text-teal-deep"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                    />
                  </svg>
                  <div className="text-sm text-ink">
                    <p className="font-semibold">Service is not connected</p>
                    <p className="mt-1 text-bark">
                      Search and indexing will be available once the backend is online.
                    </p>
                    {showLocalBackendHelp && (
                      <code className="mt-2 block rounded-lg bg-ink p-2.5 font-mono text-xs text-cream">
                        pip install -r requirements.txt && python backend/server.py
                      </code>
                    )}
                  </div>
                </div>
              </div>
            )}
          </form>
        ) : (
          /* Working State - Agent-style Progress */
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
