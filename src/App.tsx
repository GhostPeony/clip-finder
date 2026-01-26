import React, { useState, useEffect } from 'react';
import { SearchState, VideoClip, AppMode } from './types';
import { searchVideoClips, checkBackendHealth } from './services/api';
import { VideoPlayer } from './components/VideoPlayer';
import { UnifiedSearchView } from './components/UnifiedSearchView';
import { LibraryView } from './components/LibraryView';
import { SettingsModal, getStoredApiKey } from './components/SettingsModal';
import { Toast, useToast } from './components/Toast';

const App: React.FC = () => {
  const [mode, setMode] = useState<AppMode>('unified');
  const [isBackendConnected, setIsBackendConnected] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [hasApiKey, setHasApiKey] = useState(!!getStoredApiKey());
  const [hasServerKey, setHasServerKey] = useState(false);  // Server has .env key
  const { toast, showToast, hideToast } = useToast();

  // Copy shareable link to clipboard
  const copyClipLink = async (clip: VideoClip) => {
    const url = `https://youtu.be/${clip.videoId}?t=${Math.floor(clip.startSeconds)}`;
    try {
      await navigator.clipboard.writeText(url);
      showToast('Link copied!');
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

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
            onClick={() => setMode('unified')}
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
                onClick={() => setMode('unified')}
                className={`text-sm px-3 py-2 rounded-md transition-colors font-medium ${mode === 'unified' || mode === 'search' ? 'bg-[#e8f0fe] text-[#1a73e8]' : 'text-[#5f6368] hover:bg-[#f1f3f4]'
                  }`}
              >
                Home
              </button>
              <button
                onClick={() => setMode('library')}
                className={`text-sm px-3 py-2 rounded-md transition-colors font-medium ${mode === 'library' ? 'bg-[#e8f0fe] text-[#1a73e8]' : 'text-[#5f6368] hover:bg-[#f1f3f4]'
                  }`}
              >
                Library
              </button>
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

        {mode === 'unified' ? (
          <div className="py-8">
            <UnifiedSearchView
              onSearchComplete={(clips, answer, active) => {
                setSearchState({
                  status: 'complete',
                  query: '',
                  answer,
                  relevantClips: clips
                });
                // Only set activeClip if it has a valid videoId
                setActiveClip(active?.videoId ? active : null);
                setMode('search'); // Switch to show results
              }}
              onIndexComplete={() => {
                // Navigate to library after indexing completes
                setMode('library');
              }}
              isBackendConnected={isBackendConnected}
              hasApiKey={hasApiKey}
              hasServerKey={hasServerKey}
              onOpenSettings={() => setSettingsOpen(true)}
            />
          </div>
        ) : mode === 'library' ? (
          <div className="py-8">
            <LibraryView onIndexMore={() => setMode('unified')} />
          </div>
        ) : mode === 'about' ? (
          <div className="py-8 max-w-2xl mx-auto">
            <button
              onClick={() => setMode('unified')}
              className="text-sm text-[#1a73e8] hover:text-[#1557b0] flex items-center gap-1 mb-6"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              Back
            </button>
            <div className="bg-white rounded-lg border border-[#dadce0] p-8">
              <div className="flex items-center justify-between mb-6">
                <h1 className="text-2xl font-normal text-[#202124]">About Clip Finder</h1>
                <div className="flex items-center gap-4">
                  <a
                    href="https://linkedin.com/in/cadecrussell"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[#5f6368] hover:text-[#0A66C2] transition-colors"
                    title="LinkedIn"
                  >
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
                    </svg>
                  </a>
                  <a
                    href="https://github.com/ghostpeony"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[#5f6368] hover:text-[#24292f] transition-colors"
                    title="GitHub"
                  >
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z"/>
                    </svg>
                  </a>
                  <a
                    href="https://www.ghostpeony.com"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[#5f6368] hover:text-[#1a73e8] transition-colors"
                    title="Ghost Peony"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9"/>
                    </svg>
                  </a>
                </div>
              </div>
              <div className="text-[#5f6368] space-y-4 text-sm leading-relaxed">
                <p>
                  You remember saying something great — but where? Clip Finder indexes your YouTube
                  channels, making every word searchable. Just describe what you're looking for in
                  plain English, and we'll find the exact moment.
                </p>
                <p>
                  Built for creators with hours of talk-heavy content: podcasters finding quotable
                  moments, commentary channels, educational creators, and anyone who needs to mine
                  their videos for clips without scrubbing through endless footage.
                </p>
                <h2 className="text-lg font-medium text-[#202124] pt-4">Why Clip Finder?</h2>
                <ul className="list-disc list-inside space-y-2">
                  <li><strong>Semantic search</strong> — Find by meaning, not just keywords</li>
                  <li><strong>You control the search</strong> — Find what you're looking for, not AI-guessed "viral moments"</li>
                  <li><strong>Works with talk-heavy content</strong> — Podcasts, commentary, reviews, educational videos</li>
                  <li><strong>Full channel support</strong> — Index entire channels, playlists, or individual videos</li>
                </ul>
                <h2 className="text-lg font-medium text-[#202124] pt-4">How It Works</h2>
                <ol className="list-decimal list-inside space-y-2">
                  <li>Paste any YouTube URL (video, playlist, or channel)</li>
                  <li>We extract and chunk the transcript into searchable segments</li>
                  <li>Segments are embedded using Google's text-embedding-004 model</li>
                  <li>Your questions are matched against the embeddings to find relevant clips</li>
                  <li>An AI summarizes the findings with clickable timestamp citations</li>
                </ol>
              </div>
            </div>
          </div>
        ) : mode === 'contact' ? (
          <div className="py-8 max-w-2xl mx-auto">
            <button
              onClick={() => setMode('unified')}
              className="text-sm text-[#1a73e8] hover:text-[#1557b0] flex items-center gap-1 mb-6"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              Back
            </button>
            <div className="bg-white rounded-lg border border-[#dadce0] p-8">
              <h1 className="text-2xl font-normal text-[#202124] mb-4">Contact</h1>
              <div className="text-[#5f6368] space-y-4 text-sm leading-relaxed">
                <p>
                  Have questions, feedback, or found a bug? We'd love to hear from you.
                </p>
                <div className="bg-[#f8f9fa] rounded-lg p-4 space-y-3">
                  <div className="flex items-center gap-3">
                    <svg className="w-5 h-5 text-[#5f6368]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                    <a href="mailto:cade@ghostpeony.com" className="text-[#1a73e8] hover:underline">
                      cade@ghostpeony.com
                    </a>
                  </div>
                  <div className="flex items-center gap-3">
                    <svg className="w-5 h-5 text-[#5f6368]" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                    </svg>
                    <a href="https://github.com/ghostpeony" target="_blank" rel="noopener noreferrer" className="text-[#1a73e8] hover:underline">
                      github.com/ghostpeony
                    </a>
                  </div>
                </div>
                <p className="pt-2">
                  Clip Finder is an open-source project. Contributions, issues, and feature requests
                  are welcome on GitHub.
                </p>
              </div>
            </div>
          </div>
        ) : (
          /* Search Results View */
          <div>
            {/* Back to search button */}
            <div className="mb-6">
              <button
                onClick={() => {
                  setSearchState({ status: 'idle', query: '', answer: '', relevantClips: [] });
                  setActiveClip(null);
                  setMode('unified');
                }}
                className="text-sm text-[#1a73e8] hover:text-[#1557b0] flex items-center gap-1"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
                New Search
              </button>
            </div>

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
                            className={`group/clip relative cursor-pointer transition-colors rounded-lg p-1.5 ${activeClip?.id === clip.id
                              ? 'bg-[#e8f0fe]'
                              : 'hover:bg-[#f1f3f4]'
                              }`}
                          >
                            <div onClick={() => handleCitationClick(clip)}>
                              {clip.thumbnailUrl && (
                                <img src={clip.thumbnailUrl} className="w-full h-auto rounded" alt="" />
                              )}
                              <p className="text-xs text-[#202124] font-medium line-clamp-2 mt-1">{clip.title}</p>
                              <p className="text-xs text-[#1a73e8]">{formatTime(clip.startSeconds)}</p>
                            </div>
                            {/* Copy button */}
                            <button
                              onClick={(e) => { e.stopPropagation(); copyClipLink(clip); }}
                              className="absolute top-2 right-2 p-1 bg-black/60 hover:bg-black/80 text-white rounded opacity-0 group-hover/clip:opacity-100 transition-opacity"
                              title="Copy link"
                            >
                              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                              </svg>
                            </button>
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
                            <span className="text-[#9aa0a6]">•</span>
                            <a
                              href={`https://youtube.com/watch?v=${activeClip.videoId}&t=${activeClip.startSeconds}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-[#5f6368] text-sm hover:text-[#1a73e8]"
                            >
                              Watch on YouTube ↗
                            </a>
                            <span className="text-[#9aa0a6]">•</span>
                            <button
                              onClick={() => copyClipLink(activeClip)}
                              className="text-[#5f6368] text-sm hover:text-[#1a73e8] flex items-center gap-1"
                              title="Copy shareable link"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                              </svg>
                              Copy Link
                            </button>
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
        <div className="flex items-center justify-center gap-4">
          <span>Powered by Ghost Peony</span>
          <span className="text-[#dadce0]">|</span>
          <button
            onClick={() => setMode('about')}
            className="hover:text-[#1a73e8] transition-colors"
          >
            About
          </button>
          <button
            onClick={() => setMode('contact')}
            className="hover:text-[#1a73e8] transition-colors"
          >
            Contact
          </button>
        </div>
      </footer>

      {/* Toast notification */}
      <Toast message={toast.message} isVisible={toast.isVisible} onClose={hideToast} />
    </div>
  );
};

const formatTime = (seconds: number): string => {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
};

export default App;
