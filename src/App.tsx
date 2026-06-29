import React, { useState, useEffect } from 'react';
import { SearchState, VideoClip, AppMode } from './types';
import { fetchAppConfig } from './services/api';
import { groupClipsByVideo } from './lib/clips';
import { AnswerSection } from './components/AnswerSection';
import { VideoPlayer } from './components/VideoPlayer';
import { LibraryView } from './components/LibraryView';
import { IngestionJobsView } from './components/IngestionJobsView';
import { SettingsModal } from './components/SettingsModal';
import { Toast, useToast } from './components/Toast';
import { LandingPage } from './components/LandingPage';
import { ProductDashboard } from './components/ProductDashboard';
import { McpAuthorizePage } from './components/McpAuthorizePage';
import { BrandLogo } from './components/BrandLogo';
import { SocialLinks } from './components/SocialLinks';
import { useAuth } from './contexts/AuthContext';
import { isSupabaseAuth, StorageMode } from './config';
import {
  CONTACT_EMAIL,
  GHOST_PEONY_FOOTER_LINE,
  GHOST_PEONY_GITHUB_URL,
  GHOST_PEONY_NAME,
  GHOST_PEONY_URL,
  PRODUCT_DOMAIN,
  PRODUCT_NAME,
} from './brand';

const App: React.FC = () => {
  const { user, loading: authLoading, signOut, connectYouTube } = useAuth();
  const [mode, setMode] = useState<AppMode>(() =>
    typeof window !== 'undefined' && window.location.pathname === '/home' ? 'home' : 'unified',
  );
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [allowUserKeys, setAllowUserKeys] = useState(false);
  const [storageMode, setStorageMode] = useState<StorageMode>('supabase');
  const [initialLibraryProjectId, setInitialLibraryProjectId] = useState<string>('');
  const { toast, showToast, hideToast } = useToast();
  const [searchState, setSearchState] = useState<SearchState>({
    status: 'idle',
    query: '',
    answer: '',
    relevantClips: [],
  });
  const [activeClip, setActiveClip] = useState<VideoClip | null>(null);

  // Load hosted runtime configuration after the authenticated app is available.
  useEffect(() => {
    if (authLoading) return;
    if (isSupabaseAuth && !user) return;

    fetchAppConfig().then((config) => {
      setAllowUserKeys(config.allowUserKeys);
      setStorageMode(config.storage);
    });
  }, [authLoading, user]);

  // Close the mobile menu on Escape.
  useEffect(() => {
    if (!mobileMenuOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMobileMenuOpen(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [mobileMenuOpen]);

  useEffect(() => {
    const onPopState = () => {
      setMode(window.location.pathname === '/home' ? 'home' : 'unified');
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  // Auth gate
  if (authLoading) {
    return (
      <div className="min-h-screen bg-cream flex items-center justify-center">
        <div className="card animate-pulse px-6 py-4 text-sm font-medium text-bark">
          Loading {PRODUCT_NAME}...
        </div>
      </div>
    );
  }

  if (window.location.pathname === '/mcp/authorize') {
    return <McpAuthorizePage />;
  }

  if (isSupabaseAuth && !user) {
    return <LandingPage />;
  }

  const openDashboard = () => {
    if (window.location.pathname === '/home') {
      window.history.pushState({}, '', '/');
    }
    setMode('unified');
  };

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

  const handleCitationClick = (clip: VideoClip) => {
    setActiveClip(clip);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const showJobs = isSupabaseAuth || storageMode === 'supabase';

  const selectMode = (next: AppMode) => {
    if (next === 'home' && window.location.pathname !== '/home') {
      window.history.pushState({}, '', '/home');
    } else if (next !== 'home' && window.location.pathname === '/home') {
      window.history.pushState({}, '', '/');
    }
    if (next === 'library') setInitialLibraryProjectId('');
    setMode(next);
    setMobileMenuOpen(false);
  };

  const navItems: Array<{ label: string; target: AppMode; isActive: boolean }> = [
    { label: 'Home', target: 'home', isActive: mode === 'home' },
    { label: 'Dashboard', target: 'unified', isActive: mode === 'unified' || mode === 'search' },
    { label: 'Library', target: 'library', isActive: mode === 'library' },
    { label: 'Projects', target: 'projects', isActive: mode === 'projects' },
    ...(showJobs ? [{ label: 'Jobs', target: 'jobs' as AppMode, isActive: mode === 'jobs' }] : []),
  ];

  if (mode === 'home') {
    return <LandingPage onOpenDashboard={openDashboard} />;
  }

  return (
    <div className="min-h-screen bg-cream text-ink flex flex-col font-sans">
      <header className="sticky top-0 z-50 border-b border-ink/10 bg-surface/90 backdrop-blur">
        <div className="max-w-7xl mx-auto px-5 h-16 flex items-center justify-between">
          <button
            className="flex items-center gap-3"
            onClick={() => selectMode('unified')}
            aria-label={`${PRODUCT_NAME} home`}
          >
            <BrandLogo size="sm" />
          </button>

          <div className="flex items-center gap-3">
            <nav
              className="hidden items-center gap-1 rounded-full border border-ink/10 bg-cream p-1 md:flex"
              aria-label="Main navigation"
            >
              {navItems.map((item) => (
                <button
                  key={item.label}
                  onClick={() => selectMode(item.target)}
                  className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
                    item.isActive ? 'bg-surface text-ink shadow-soft' : 'text-bark hover:text-ink'
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </nav>

            <button
              onClick={() => setSettingsOpen(true)}
              className="btn btn-ghost h-10 min-h-0 w-10 rounded-full p-0"
              title="Settings"
              aria-label="Settings"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                />
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                />
              </svg>
            </button>

            {/* User avatar + sign out */}
            {isSupabaseAuth && user && (
              <div className="hidden items-center gap-2 md:flex">
                {user.user_metadata?.avatar_url && (
                  <img
                    src={user.user_metadata.avatar_url}
                    alt=""
                    className="w-8 h-8 rounded-full"
                  />
                )}
                <button
                  onClick={signOut}
                  className="text-xs font-medium text-bark transition-colors hover:text-ink"
                >
                  Sign out
                </button>
              </div>
            )}

            {/* Mobile menu toggle */}
            <button
              onClick={() => setMobileMenuOpen((open) => !open)}
              className="btn btn-ghost h-10 min-h-0 w-10 rounded-full p-0 md:hidden"
              aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
              aria-expanded={mobileMenuOpen}
              aria-controls="mobile-menu"
            >
              {mobileMenuOpen ? (
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              ) : (
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 7h16M4 12h16M4 17h16"
                  />
                </svg>
              )}
            </button>
          </div>
        </div>

        {/* Mobile menu */}
        {mobileMenuOpen && (
          <nav
            id="mobile-menu"
            aria-label="Mobile navigation"
            className="border-t border-ink/10 bg-surface px-5 py-4 shadow-soft md:hidden"
          >
            <div className="flex flex-col gap-1">
              {navItems.map((item) => (
                <button
                  key={item.label}
                  onClick={() => selectMode(item.target)}
                  className={`rounded-xl px-4 py-3 text-left text-sm font-medium transition-colors ${
                    item.isActive ? 'bg-cream text-ink' : 'text-bark hover:bg-cream/60'
                  }`}
                >
                  {item.label}
                </button>
              ))}
              <button
                onClick={() => selectMode('about')}
                className="rounded-xl px-4 py-3 text-left text-sm font-medium text-bark transition-colors hover:bg-cream/60"
              >
                About
              </button>
              <button
                onClick={() => selectMode('contact')}
                className="rounded-xl px-4 py-3 text-left text-sm font-medium text-bark transition-colors hover:bg-cream/60"
              >
                Contact
              </button>
              {isSupabaseAuth && user && (
                <button
                  onClick={signOut}
                  className="mt-1 rounded-xl border-t border-ink/10 px-4 py-3 text-left text-sm font-medium text-bark transition-colors hover:bg-cream/60"
                >
                  Sign out
                </button>
              )}
            </div>
          </nav>
        )}
      </header>

      {/* Settings Modal */}
      <SettingsModal
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        allowUserKeys={allowUserKeys}
        onConnectYouTube={connectYouTube}
      />

      {/* Main Content */}
      <main className="flex-1 w-full max-w-7xl mx-auto px-5 py-8">
        {mode === 'unified' ? (
          <div className="py-4">
            <ProductDashboard
              onSearchComplete={(clips, answer, active) => {
                setSearchState({
                  status: 'complete',
                  query: '',
                  answer,
                  relevantClips: clips,
                });
                // Only set activeClip if it has a valid videoId
                setActiveClip(active?.videoId ? active : null);
                setMode('search'); // Switch to show results
              }}
              onOpenLibrary={(projectId) => {
                setInitialLibraryProjectId(projectId || '');
                setMode('library');
              }}
              onOpenProjects={() => {
                setInitialLibraryProjectId('');
                setMode('projects');
              }}
              onOpenJobs={() => setMode('jobs')}
              onConnectYouTube={connectYouTube}
              onIndexComplete={() => {
                setInitialLibraryProjectId('');
                setMode('library');
              }}
              onOpenSettings={() => setSettingsOpen(true)}
            />
          </div>
        ) : mode === 'library' ? (
          <div className="py-8">
            <LibraryView
              initialProjectId={initialLibraryProjectId}
              onIndexMore={() => setMode('unified')}
            />
          </div>
        ) : mode === 'projects' ? (
          <div className="py-8">
            <LibraryView
              initialSurface="projects"
              initialProjectId={initialLibraryProjectId}
              onIndexMore={() => setMode('unified')}
            />
          </div>
        ) : mode === 'jobs' ? (
          <div className="py-8">
            <IngestionJobsView />
          </div>
        ) : mode === 'about' ? (
          <div className="py-8 max-w-2xl mx-auto">
            <button
              onClick={() => setMode('unified')}
              className="link-quiet mb-6 flex items-center gap-1 text-sm"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15 19l-7-7 7-7"
                />
              </svg>
              Back
            </button>
            <div className="card p-8">
              <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <h1 className="font-serif text-4xl font-medium text-ink">About {PRODUCT_NAME}</h1>
                <SocialLinks compact />
              </div>
              <div className="space-y-4 text-sm leading-7 text-bark">
                <p>
                  {PRODUCT_NAME} turns saved YouTube videos into a searchable library with
                  timestamped clips, transcripts, and notes.
                </p>
                <p>
                  Built for people who learn from video and want useful moments to be easy to find
                  again: researchers, builders, writers, creators, students, and teams.
                </p>
                <h2 className="pt-4 font-serif text-2xl font-medium text-ink">
                  Why {PRODUCT_NAME}?
                </h2>
                <ul className="list-disc list-inside space-y-2">
                  <li>
                    <strong>Semantic search</strong> - Find by meaning, not just keywords
                  </li>
                  <li>
                    <strong>Timestamped clips</strong> - Open the exact moment behind an answer
                  </li>
                  <li>
                    <strong>Capture from YouTube</strong> - Save videos to linked playlists and move
                    them into your library
                  </li>
                  <li>
                    <strong>Full channel support</strong> - Index entire channels, playlists, or
                    individual videos
                  </li>
                </ul>
                <h2 className="pt-4 font-serif text-2xl font-medium text-ink">How it works</h2>
                <ol className="list-decimal list-inside space-y-2">
                  <li>Paste any YouTube URL (video, playlist, or channel)</li>
                  <li>Memexai indexes the available captions and timestamps</li>
                  <li>Your searches return relevant clips from your saved sources</li>
                  <li>You can open, copy, or revisit the exact YouTube moment</li>
                </ol>
              </div>
            </div>
          </div>
        ) : mode === 'contact' ? (
          <div className="py-8 max-w-2xl mx-auto">
            <button
              onClick={() => setMode('unified')}
              className="link-quiet mb-6 flex items-center gap-1 text-sm"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15 19l-7-7 7-7"
                />
              </svg>
              Back
            </button>
            <div className="card p-8">
              <h1 className="mb-4 font-serif text-4xl font-medium text-ink">Contact</h1>
              <div className="space-y-4 text-sm leading-7 text-bark">
                <p>Have questions, feedback, or found a bug? We'd love to hear from you.</p>
                <div className="space-y-3 rounded-xl bg-cream p-5">
                  <a
                    href={`mailto:${CONTACT_EMAIL}`}
                    className="block font-semibold text-violet-deep underline decoration-2 underline-offset-4"
                  >
                    {CONTACT_EMAIL}
                  </a>
                  <a
                    href={GHOST_PEONY_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block font-semibold text-violet-deep underline decoration-2 underline-offset-4"
                  >
                    ghostpeony.com
                  </a>
                  <a
                    href={GHOST_PEONY_GITHUB_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block font-semibold text-violet-deep underline decoration-2 underline-offset-4"
                  >
                    github.com/GhostPeony
                  </a>
                  <SocialLinks className="pt-2" />
                </div>
                <p className="pt-2">
                  {PRODUCT_NAME} is a {GHOST_PEONY_NAME} product for turning YouTube videos into a
                  searchable saved-video library. The production home is {PRODUCT_DOMAIN}.
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
                className="link-quiet flex items-center gap-1 text-sm"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M15 19l-7-7 7-7"
                  />
                </svg>
                New Search
              </button>
            </div>

            {/* Zero-results state */}
            {searchState.status === 'complete' && searchState.relevantClips.length === 0 && (
              <div className="card mx-auto max-w-xl p-8 text-center">
                <h2 className="font-serif text-3xl font-medium text-ink">No moments found</h2>
                <p className="mx-auto mt-3 max-w-sm text-sm leading-6 text-bark">
                  Nothing in your library matched that description. Try different wording, or index
                  more videos to widen the search.
                </p>
                <button onClick={() => setMode('unified')} className="btn btn-primary mt-6">
                  Try another search
                </button>
              </div>
            )}

            {/* Results Area - YouTube-style layout */}
            {searchState.status !== 'idle' &&
              !searchState.error &&
              searchState.relevantClips.length > 0 && (
                <div className="flex flex-col-reverse gap-6 md:flex-row">
                  {/* Sources grouped by video: sidebar on desktop, strip below player on mobile */}
                  <div className="w-full flex-shrink-0 md:w-56">
                    <div className="md:sticky md:top-20">
                      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted">
                        Clips
                      </h3>
                      <div className="flex gap-3 overflow-x-auto pb-2 md:block md:space-y-3 md:overflow-visible md:pb-0">
                        {groupClipsByVideo(searchState.relevantClips).map((group) => (
                          <div
                            key={group.videoId}
                            className="card w-56 flex-shrink-0 overflow-hidden p-2 md:w-auto"
                          >
                            <button
                              onClick={() => handleCitationClick(group.clips[0])}
                              className="block w-full text-left"
                            >
                              {group.thumbnailUrl && (
                                <img
                                  src={group.thumbnailUrl}
                                  className="h-auto w-full rounded-lg"
                                  alt=""
                                />
                              )}
                              <p className="mt-2 line-clamp-2 text-xs font-semibold text-ink">
                                {group.title}
                              </p>
                            </button>
                            <div className="mt-1.5 flex flex-wrap gap-1.5">
                              {group.clips.map((clip) => (
                                <button
                                  key={clip.id}
                                  onClick={() => handleCitationClick(clip)}
                                  className={`rounded-full px-2 py-0.5 font-mono text-xs font-medium transition-colors ${
                                    activeClip?.id === clip.id
                                      ? 'bg-rose-deep text-cream'
                                      : 'bg-petal/60 text-rose-deep hover:bg-petal'
                                  }`}
                                >
                                  {formatTime(clip.startSeconds)}
                                </button>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Main Content: Answer + Video + Transcript */}
                  <div className="flex-1 max-w-4xl">
                    {/* Cited answer */}
                    {searchState.answer && (
                      <div className="mb-5">
                        <AnswerSection
                          answer={searchState.answer}
                          clips={searchState.relevantClips}
                          onCitationClick={handleCitationClick}
                        />
                      </div>
                    )}
                    {/* Video Player */}
                    <div>
                      {activeClip ? (
                        <div className="card overflow-hidden">
                          <VideoPlayer
                            key={activeClip.id}
                            videoId={activeClip.videoId}
                            startSeconds={activeClip.startSeconds}
                            autoplay={true}
                          />
                          <div className="p-5">
                            <h3 className="font-serif text-2xl font-medium text-ink">
                              {activeClip.title}
                            </h3>
                            <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1">
                              <span className="text-sm text-bark">{activeClip.channelName}</span>
                              <span className="text-muted">-</span>
                              <span className="font-mono text-sm font-medium text-rose-deep">
                                {formatTime(activeClip.startSeconds)}
                              </span>
                              <span className="text-muted">-</span>
                              <a
                                href={`https://youtube.com/watch?v=${activeClip.videoId}&t=${activeClip.startSeconds}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-sm font-medium text-muted hover:text-violet-deep"
                              >
                                Watch on YouTube
                              </a>
                              <span className="text-muted">-</span>
                              <button
                                onClick={() => copyClipLink(activeClip)}
                                className="flex items-center gap-1 text-sm font-medium text-muted hover:text-rose-deep"
                                title="Copy shareable link"
                              >
                                <svg
                                  className="w-4 h-4"
                                  fill="none"
                                  stroke="currentColor"
                                  viewBox="0 0 24 24"
                                >
                                  <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"
                                  />
                                </svg>
                                Copy Link
                              </button>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div className="card flex aspect-video items-center justify-center text-bark">
                          <div className="text-center">
                            <svg
                              className="mx-auto mb-2 h-12 w-12 text-muted"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={1.5}
                                d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
                              />
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={1.5}
                                d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                              />
                            </svg>
                            <p className="text-sm">Select a source to play</p>
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Transcript below video */}
                    {activeClip && (
                      <div className="card mt-5 p-6">
                        <div className="flex items-center gap-2 mb-3">
                          <svg
                            className="h-5 w-5 text-violet-deep"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                            />
                          </svg>
                          <h2 className="font-serif text-2xl font-medium text-ink">Transcript</h2>
                          <span className="font-mono text-xs font-medium text-muted">
                            {formatTime(activeClip.startSeconds)} -{' '}
                            {formatTime(activeClip.endSeconds)}
                          </span>
                        </div>
                        <p className="whitespace-pre-wrap text-sm leading-7 text-bark">
                          {activeClip.content}
                        </p>
                        {activeClip.relevanceReason && (
                          <p className="mt-3 border-l-4 border-rose pl-3 text-xs font-medium text-muted">
                            {activeClip.relevanceReason}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}
          </div>
        )}
      </main>

      <footer className="bg-ink px-5 py-6 text-xs text-cream">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 md:flex-row">
          <div className="flex flex-wrap items-center justify-center gap-4">
            <a
              href={GHOST_PEONY_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium underline decoration-rose decoration-2 underline-offset-4 transition-colors hover:text-cream/80"
            >
              {GHOST_PEONY_FOOTER_LINE}
            </a>
            <span className="text-cream/30">|</span>
            <button
              onClick={() => setMode('about')}
              className="transition-colors hover:text-cream/80"
            >
              About
            </button>
            <button
              onClick={() => setMode('contact')}
              className="transition-colors hover:text-cream/80"
            >
              Contact
            </button>
          </div>
          <SocialLinks compact tone="light" />
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
