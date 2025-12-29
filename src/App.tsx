import React, { useState, useEffect } from 'react';
import { SearchState, VideoClip, AppMode } from './types';
import { searchVideoClips, checkBackendHealth } from './services/api';
import { VideoPlayer } from './components/VideoPlayer';
import { IngestionView } from './components/IngestionView';
import { LibraryView } from './components/LibraryView';
import { SettingsModal, getStoredApiKey } from './components/SettingsModal';

const App: React.FC = () => {
  const [mode, setMode] = useState<AppMode>('ingest');
  const [isBackendConnected, setIsBackendConnected] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [hasApiKey, setHasApiKey] = useState(!!getStoredApiKey());
  const [hasServerKey, setHasServerKey] = useState(false);  // Server has .env key

  // Search State
  const [query, setQuery] = useState('');
  const [searchState, setSearchState] = useState<SearchState>({
    status: 'idle',
    query: '',
    answer: '',
    relevantClips: []
  });
  const [activeClip, setActiveClip] = useState<VideoClip | null>(null);
  const [resultLimit, setResultLimit] = useState(5);  // User-configurable result count

  // Check backend connection once on mount (no polling)
  useEffect(() => {
    checkBackendHealth().then(({ connected, hasServerKey }) => {
      setIsBackendConnected(connected);
      setHasServerKey(hasServerKey);
    });
  }, []);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setSearchState(prev => ({ ...prev, status: 'searching', query, error: undefined }));
    setActiveClip(null);

    try {
      const { answer, relevantClips } = await searchVideoClips(query, resultLimit);

      setSearchState(prev => ({
        ...prev,
        status: 'complete',
        answer,
        relevantClips
      }));

      if (relevantClips.length > 0) setActiveClip(relevantClips[0]);

    } catch (err) {
      setSearchState(prev => ({
        ...prev,
        status: 'error',
        error: "Could not connect to Python backend. Is 'server.py' running?"
      }));
    }
  };

  const handleCitationClick = (clip: VideoClip) => {
    setActiveClip(clip);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="min-h-screen bg-[#f8f9fa] text-[#202124] flex flex-col font-['Google_Sans',system-ui,sans-serif]">
      {/* Header - Google Style */}
      <header className="bg-white border-b border-[#dadce0] sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
          <div
            className="flex items-center gap-3 cursor-pointer"
            onClick={() => setMode('ingest')}
          >
            {/* Google-style logo */}
            <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none">
              <circle cx="11" cy="11" r="7" stroke="#ea4335" strokeWidth="2.5" />
              <path d="M16 16l5 5" stroke="#4285f4" strokeWidth="2.5" strokeLinecap="round" />
            </svg>
            <span className="font-medium text-lg text-[#5f6368]">Clip Finder</span>
          </div>

          <div className="flex items-center gap-4">
            {/* Navigation Tabs */}
            <div className="flex gap-1">
              <button
                onClick={() => setMode('search')}
                className={`text-sm px-3 py-2 rounded-md transition-colors font-medium ${mode === 'search' ? 'bg-[#e8f0fe] text-[#1a73e8]' : 'text-[#5f6368] hover:bg-[#f1f3f4]'
                  }`}
              >
                Search
              </button>
              <button
                onClick={() => setMode('library')}
                className={`text-sm px-3 py-2 rounded-md transition-colors font-medium ${mode === 'library' ? 'bg-[#e8f0fe] text-[#1a73e8]' : 'text-[#5f6368] hover:bg-[#f1f3f4]'
                  }`}
              >
                Library
              </button>
              <button
                onClick={() => setMode('ingest')}
                className={`text-sm px-3 py-2 rounded-md transition-colors font-medium ${mode === 'ingest' ? 'bg-[#e8f0fe] text-[#1a73e8]' : 'text-[#5f6368] hover:bg-[#f1f3f4]'
                  }`}
              >
                + Add
              </button>
            </div>

            <div className={`text-xs px-3 py-1 rounded-full ${isBackendConnected
              ? 'bg-[#e6f4ea] text-[#137333]'
              : 'bg-[#fce8e6] text-[#c5221f]'
              }`}>
              {isBackendConnected ? 'Connected' : 'Offline'}
            </div>

            {/* API Key Status */}
            <div className={`text-xs px-3 py-1 rounded-full ${hasApiKey
              ? 'bg-[#e8f0fe] text-[#1a73e8]'
              : 'bg-[#fef7e0] text-[#b06000]'
              }`}>
              {hasApiKey ? '🔑 Key Set' : '⚠️ No API Key'}
            </div>

            {/* Settings Button */}
            <button
              onClick={() => setSettingsOpen(true)}
              className="p-2 text-[#5f6368] hover:bg-[#f1f3f4] rounded-full transition-colors"
              title="Settings"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </button>
          </div>
        </div>
      </header>

      {/* Settings Modal */}
      <SettingsModal
        isOpen={settingsOpen}
        onClose={() => { setSettingsOpen(false); setHasApiKey(!!getStoredApiKey()); }}
      />

      {/* Main Content */}
      <main className="flex-1 w-full max-w-6xl mx-auto px-4 py-8">

        {mode === 'ingest' ? (
          <div className="py-8">
            <IngestionView onComplete={() => {
              // Clear old search state when transitioning to search
              setSearchState({ status: 'idle', query: '', answer: '', relevantClips: [] });
              setActiveClip(null);
              setQuery('');
              setMode('search');
            }} isBackendConnected={isBackendConnected} />
          </div>
        ) : mode === 'library' ? (
          <div className="py-8">
            <LibraryView onIndexMore={() => setMode('ingest')} />
          </div>
        ) : (
          /* Search View */
          <div>
            {/* API Key Warning - only show if neither client nor server has a key */}
            {!hasApiKey && !hasServerKey && (
              <div className="max-w-2xl mx-auto mb-6 bg-[#fef7e0] border border-[#fdd663] text-[#5f4000] p-4 rounded-lg flex items-center gap-3">
                <svg className="w-6 h-6 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" />
                </svg>
                <div className="flex-1">
                  <p className="font-medium">API Key Required for Search</p>
                  <p className="text-sm">To search your indexed videos, you need a free Gemini API key.</p>
                </div>
                <button
                  onClick={() => setSettingsOpen(true)}
                  className="bg-[#5f4000] hover:bg-[#3f2a00] text-white px-4 py-2 rounded-md text-sm font-medium whitespace-nowrap"
                >
                  Add API Key
                </button>
              </div>
            )}

            {/* Search Input - Google Style */}
            <div className="max-w-2xl mx-auto mb-10">
              <form onSubmit={handleSearch} className="relative">
                <div className="flex items-center bg-white border border-[#dfe1e5] rounded-full hover:shadow-md focus-within:shadow-md transition-shadow">
                  <svg className="w-5 h-5 text-[#9aa0a6] ml-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  <input
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder={isBackendConnected ? "Ask about your videos..." : "Backend offline..."}
                    disabled={!isBackendConnected}
                    className="flex-1 px-4 py-3 bg-transparent border-none focus:outline-none text-base disabled:opacity-50"
                  />
                  {query && (
                    <button
                      type="button"
                      onClick={() => setQuery('')}
                      className="p-2 text-[#70757a] hover:text-[#202124]"
                    >
                      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
                      </svg>
                    </button>
                  )}
                </div>
                <div className="flex justify-center items-center gap-3 mt-6">
                  <button
                    type="submit"
                    disabled={searchState.status === 'searching' || !isBackendConnected}
                    className="bg-[#f8f9fa] hover:bg-[#f1f3f4] border border-[#f8f9fa] hover:border-[#dadce0] text-[#3c4043] px-4 py-2 rounded text-sm font-medium disabled:opacity-50 transition-all"
                  >
                    {searchState.status === 'searching' ? 'Searching...' : 'Clip Finder Search'}
                  </button>
                  <div className="flex items-center gap-2 bg-[#f8f9fa] border border-[#f8f9fa] hover:border-[#dadce0] rounded px-3 py-2">
                    <label className="text-xs text-[#5f6368]">Results:</label>
                    <select
                      value={resultLimit}
                      onChange={(e) => setResultLimit(Number(e.target.value))}
                      className="text-sm bg-transparent text-[#3c4043] focus:outline-none cursor-pointer"
                    >
                      <option value={1}>1</option>
                      <option value={3}>3</option>
                      <option value={5}>5</option>
                      <option value={10}>10</option>
                    </select>
                  </div>
                  <button
                    type="button"
                    className="bg-[#f8f9fa] hover:bg-[#f1f3f4] border border-[#f8f9fa] hover:border-[#dadce0] text-[#3c4043] px-4 py-2 rounded text-sm font-medium"
                    onClick={() => setMode('ingest')}
                  >
                    Index Channel
                  </button>
                </div>
              </form>
              {!isBackendConnected && (
                <p className="text-center text-[#d93025] mt-4 text-sm bg-[#fce8e6] p-3 rounded-lg">
                  Python server not detected. Run <code className="bg-[#f1f3f4] px-1 rounded">python server.py</code>
                </p>
              )}
            </div>

            {/* Error Message */}
            {searchState.error && (
              <div className="max-w-2xl mx-auto mb-8 bg-[#fce8e6] border border-[#f5c6cb] text-[#c5221f] p-4 rounded-lg text-center text-sm">
                {searchState.error}
              </div>
            )}

            {/* Results Area - YouTube-style layout */}
            {searchState.status !== 'idle' && !searchState.error && (
              <div className="flex gap-4 -mx-4 px-4">
                {/* Left Sidebar: Sources */}
                {searchState.relevantClips.length > 0 && (
                  <div className="w-48 flex-shrink-0">
                    <div className="sticky top-20">
                      <h3 className="text-xs font-medium text-[#5f6368] uppercase tracking-wide mb-3">
                        Clips
                      </h3>
                      <div className="space-y-3">
                        {searchState.relevantClips.map((clip) => (
                          <div
                            key={clip.id}
                            onClick={() => handleCitationClick(clip)}
                            className={`cursor-pointer transition-colors rounded-lg p-1.5 ${activeClip?.id === clip.id
                              ? 'bg-[#e8f0fe]'
                              : 'hover:bg-[#f1f3f4]'
                              }`}
                          >
                            {clip.thumbnailUrl && (
                              <img src={clip.thumbnailUrl} className="w-full h-auto rounded" alt="" />
                            )}
                            <p className="text-xs text-[#202124] font-medium line-clamp-2 mt-1">{clip.title}</p>
                            <p className="text-xs text-[#1a73e8]">{formatTime(clip.startSeconds)}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* Main Content: Video + Transcript */}
                <div className="flex-1 max-w-4xl">
                  {/* Video Player */}
                  <div>
                    {activeClip ? (
                      <div className="bg-white rounded-lg shadow-sm border border-[#dadce0] overflow-hidden">
                        <VideoPlayer
                          key={activeClip.id}
                          videoId={activeClip.videoId}
                          startSeconds={activeClip.startSeconds}
                          autoplay={true}
                        />
                        <div className="p-4">
                          <h3 className="font-medium text-[#202124] text-lg">{activeClip.title}</h3>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-[#606368] text-sm">{activeClip.channelName}</span>
                            <span className="text-[#9aa0a6]">•</span>
                            <span className="text-[#1a73e8] text-sm font-medium">{formatTime(activeClip.startSeconds)}</span>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="aspect-video bg-white rounded-lg border border-[#dadce0] flex items-center justify-center text-[#5f6368]">
                        <div className="text-center">
                          <svg className="w-12 h-12 mx-auto mb-2 text-[#dadce0]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          <p className="text-sm">Select a source to play</p>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Transcript below video */}
                  {activeClip && (
                    <div className="bg-white rounded-lg border border-[#dadce0] p-5 mt-4">
                      <div className="flex items-center gap-2 mb-3">
                        <svg className="w-5 h-5 text-[#1a73e8]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        <h2 className="text-sm font-medium text-[#202124]">Transcript</h2>
                        <span className="text-xs text-[#5f6368]">
                          {formatTime(activeClip.startSeconds)} - {formatTime(activeClip.endSeconds)}
                        </span>
                      </div>
                      <p className="text-[#3c4043] text-sm leading-relaxed whitespace-pre-wrap">
                        {activeClip.content}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </main>

      <footer className="py-4 text-center text-[#70757a] text-xs border-t border-[#dadce0] bg-[#f8f9fa]">
        <p>Powered by Ghost Peony</p>
      </footer>
    </div>
  );
};

const formatTime = (seconds: number): string => {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
};

export default App;
