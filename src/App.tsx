import React, { useState, useEffect } from 'react';
import { SearchState, VideoClip, AppMode } from './types';
import { fetchAppConfig } from './services/api';
import { LibraryView } from './components/LibraryView';
import { IngestionJobsView } from './components/IngestionJobsView';
import { SettingsModal } from './components/SettingsModal';
import { PromoTrialBanner } from './components/PromoTrialBanner';
import { capturePromoCodeFromUrl } from './lib/promo';
import { Toast, useToast } from './components/Toast';
import { LandingPage } from './components/LandingPage';
import { ProductDashboard } from './components/ProductDashboard';
import { McpAuthorizePage } from './components/McpAuthorizePage';
import { AboutPage } from './components/AboutPage';
import { ContactPage } from './components/ContactPage';
import { SearchResultsView } from './components/SearchResultsView';
import { BrandLogo } from './components/BrandLogo';
import { SocialLinks } from './components/SocialLinks';
import { useAuth } from './contexts/AuthContext';
import { isSupabaseAuth, StorageMode } from './config';
import { GHOST_PEONY_FOOTER_LINE, GHOST_PEONY_URL, PRODUCT_NAME } from './brand';

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

  // Stash ?promo= codes before the auth gate so they survive the OAuth redirect.
  useEffect(() => {
    capturePromoCodeFromUrl();
  }, []);

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
        {isSupabaseAuth && user && <PromoTrialBanner />}
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
              onManageProjects={() => selectMode('projects')}
            />
          </div>
        ) : mode === 'projects' ? (
          <div className="py-8">
            <LibraryView
              initialSurface="projects"
              initialProjectId={initialLibraryProjectId}
              onIndexMore={() => setMode('unified')}
              onOpenLibrary={(projectId) => {
                setInitialLibraryProjectId(projectId);
                setMode('library');
              }}
            />
          </div>
        ) : mode === 'jobs' ? (
          <div className="py-8">
            <IngestionJobsView />
          </div>
        ) : mode === 'about' ? (
          <AboutPage onBack={() => setMode('unified')} />
        ) : mode === 'contact' ? (
          <ContactPage onBack={() => setMode('unified')} />
        ) : (
          <SearchResultsView
            searchState={searchState}
            activeClip={activeClip}
            onCitationClick={handleCitationClick}
            onCopyClipLink={(clip) => void copyClipLink(clip)}
            onNewSearch={() => {
              setSearchState({ status: 'idle', query: '', answer: '', relevantClips: [] });
              setActiveClip(null);
              setMode('unified');
            }}
            onTryAnotherSearch={() => setMode('unified')}
          />
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

export default App;
