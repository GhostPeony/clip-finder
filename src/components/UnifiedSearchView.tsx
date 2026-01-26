import React, { useState, useRef } from 'react';
import { VideoClip } from '../types';
import { ingestChannel, searchVideoClips, saveSearchToHistory } from '../services/api';

interface UnifiedSearchViewProps {
  onSearchComplete: (clips: VideoClip[], answer: string, activeClip: VideoClip | null) => void;
  onIndexComplete: () => void;  // Called when indexing completes without a search
  isBackendConnected: boolean;
  hasApiKey: boolean;
  hasServerKey: boolean;
  onOpenSettings: () => void;
}

type WorkflowStatus = 'idle' | 'ingesting' | 'searching' | 'complete' | 'error';

export const UnifiedSearchView: React.FC<UnifiedSearchViewProps> = ({
  onSearchComplete,
  onIndexComplete,
  isBackendConnected,
  hasApiKey,
  hasServerKey,
  onOpenSettings,
}) => {
  const [message, setMessage] = useState('');
  const [searchLibrary, setSearchLibrary] = useState(false);
  const [resultLimit, setResultLimit] = useState(5);

  // Workflow state
  const [status, setStatus] = useState<WorkflowStatus>('idle');
  const [currentStep, setCurrentStep] = useState('');
  const [ingestLogs, setIngestLogs] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

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

    // Need either URLs to ingest or searchLibrary checked
    if (!hasUrls && !searchLibrary) {
      setError('Add YouTube links or check "Search Library" to search existing videos');
      return;
    }

    // If searching library without URLs, need a query
    if (!hasUrls && searchLibrary && !hasQuery) {
      setError('Enter a search query to search your library');
      return;
    }

    if (hasUrls) {
      // Ingest URLs
      pendingUrlsRef.current = urls;
      currentUrlIndexRef.current = 0;
      setStatus('ingesting');

      // If there's a query, search after indexing. Otherwise, just index.
      const shouldSearch = hasQuery || searchLibrary;
      await ingestAllUrls(urls, shouldSearch ? (queryText || message) : null);
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
          (msg) => setIngestLogs(prev => [...prev, msg]),
          () => resolve()
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
      const validClips = relevantClips.filter(clip => clip.videoId);
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
  const canSubmit = isBackendConnected && message.trim() && (urls.length > 0 || searchLibrary);

  // Determine button label
  const getButtonLabel = () => {
    if (urls.length > 0 && (hasQuery || searchLibrary)) {
      return 'Index & Search';
    } else if (urls.length > 0) {
      return 'Index';
    } else {
      return 'Search';
    }
  };

  return (
    <div className="max-w-2xl mx-auto w-full">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="flex justify-center mb-4">
          <svg className="w-20 h-20" viewBox="0 0 48 48" fill="none">
            <circle cx="22" cy="22" r="14" stroke="#ea4335" strokeWidth="4" />
            <path d="M32 32l12 12" stroke="#4285f4" strokeWidth="4" strokeLinecap="round" />
          </svg>
        </div>
        <h1 className="text-3xl font-normal text-[#202124] mb-2">
          Clip Finder
        </h1>
        <p className="text-[#5f6368] text-base">
          Search your videos like Google. Find that perfect clip in seconds, not hours.
        </p>
      </div>

      {/* API Key Warning */}
      {!hasApiKey && !hasServerKey && (
        <div className="mb-6 bg-[#fef7e0] border border-[#fdd663] text-[#5f4000] p-4 rounded-lg flex items-center gap-3">
          <svg className="w-6 h-6 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" />
          </svg>
          <div className="flex-1">
            <p className="font-medium">API Key Required</p>
            <p className="text-sm">Add your Gemini API key to get started.</p>
          </div>
          <button
            onClick={onOpenSettings}
            className="bg-[#5f4000] hover:bg-[#3f2a00] text-white px-4 py-2 rounded-md text-sm font-medium whitespace-nowrap"
          >
            Add API Key
          </button>
        </div>
      )}

      {/* Main Card */}
      <div className="bg-white rounded-lg border border-[#dadce0] shadow-sm">
        {!isWorking ? (
          <form onSubmit={handleSubmit} className="p-6">
            {/* Single Message Input */}
            <div className="mb-5">
              <label htmlFor="message" className="block text-sm font-medium text-[#202124] mb-2">
                What do you want to find?
              </label>
              <textarea
                id="message"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder={"Paste a YouTube link to index, or add a question to search:\n• https://youtube.com/@channel — Index only\n• What is AI? https://youtube.com/watch?v=abc — Index & Search"}
                disabled={!isBackendConnected}
                rows={3}
                className="w-full px-4 py-3 border border-[#dadce0] rounded-lg focus:outline-none focus:border-[#1a73e8] focus:ring-1 focus:ring-[#1a73e8] text-sm disabled:bg-[#f1f3f4] disabled:cursor-not-allowed resize-none"
              />
              {urls.length > 0 && (
                <p className="text-xs text-[#1a73e8] mt-1">
                  {urls.length} YouTube link{urls.length !== 1 ? 's' : ''} detected
                </p>
              )}
            </div>

            {/* Search Library Checkbox */}
            <div className="mb-5">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={searchLibrary}
                  onChange={(e) => setSearchLibrary(e.target.checked)}
                  className="w-4 h-4 text-[#1a73e8] border-[#dadce0] rounded focus:ring-[#1a73e8]"
                />
                <span className="text-sm text-[#3c4043]">Search Library</span>
              </label>
            </div>

            {/* Error Message */}
            {error && (
              <div className="mb-4 bg-[#fce8e6] border border-[#f5c6cb] text-[#c5221f] p-3 rounded-lg text-sm">
                {error}
              </div>
            )}

            {/* Submit Row */}
            <div className="flex items-center gap-3">
              <button
                type="submit"
                disabled={!canSubmit}
                className="bg-[#1a73e8] hover:bg-[#1557b0] text-white px-6 py-2 rounded-md text-sm font-medium disabled:bg-[#dadce0] disabled:cursor-not-allowed transition-colors"
              >
                {getButtonLabel()}
              </button>

              <label className="text-xs text-[#5f6368]">Results:</label>
              <select
                value={resultLimit}
                onChange={(e) => setResultLimit(Number(e.target.value))}
                className="text-sm bg-white text-[#3c4043] border border-[#dadce0] rounded px-3 py-2 focus:outline-none focus:border-[#1a73e8] cursor-pointer"
              >
                <option value={1}>1</option>
                <option value={3}>3</option>
                <option value={5}>5</option>
                <option value={10}>10</option>
              </select>
            </div>

            {/* Backend Unavailable Warning */}
            {!isBackendConnected && (
              <div className="mt-4 bg-[#fce8e6] border border-[#f5c6cb] rounded-lg p-4">
                <div className="flex gap-3">
                  <svg className="w-5 h-5 text-[#c5221f] flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <div className="text-sm text-[#c5221f]">
                    <p className="font-medium">Backend Unavailable</p>
                    <p className="mt-1 text-[#5f6368]">Run the Python server:</p>
                    <code className="block bg-[#f1f3f4] text-[#202124] p-2 mt-2 rounded text-xs">
                      pip install -r requirements.txt && python server.py
                    </code>
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
                <div className="w-16 h-16 border-4 border-[#e8f0fe] rounded-full"></div>
                <div className="absolute top-0 left-0 w-16 h-16 border-4 border-transparent border-t-[#1a73e8] rounded-full animate-spin"></div>
              </div>

              {/* Current Step */}
              <p className="mt-6 text-sm text-[#3c4043] text-center min-h-[1.5rem] transition-all max-w-md">
                {currentStep || (status === 'ingesting' ? 'Starting indexing...' : 'Searching...')}
              </p>

              {/* Progress Context */}
              {status === 'ingesting' && (
                <p className="mt-2 text-xs text-[#9aa0a6]">
                  {currentUrlIndexRef.current + 1} of {pendingUrlsRef.current.length} sources
                </p>
              )}

              {/* Latest Log */}
              {ingestLogs.length > 0 && (
                <p className="mt-4 text-xs text-[#5f6368] text-center max-w-sm truncate">
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
