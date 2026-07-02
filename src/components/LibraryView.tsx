import React, { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import { IngestionJob, LibraryData, SearchHistoryEntry, UserProject } from '../types';
import {
  clearSearchHistory,
  deleteSearchHistoryEntry,
  fetchIngestionJobs,
  fetchLibrary,
  fetchProjects,
  getCachedIngestionJobs,
  getCachedLibrary,
  getSearchHistory,
} from '../services/api';
import { VideoWithChannel } from '../lib/videoKnowledge';
import { BrandLoader } from './BrandLoader';
import { ConfirmDialog } from './ui/ConfirmDialog';
import { NoticeState } from './ui/Notice';
import { SelectableTile } from './ui/SelectableTile';
import { HistoryView } from './library/HistoryView';
import { LibraryImportRow } from './library/LibraryImportRow';
import { LibrarySearchSection } from './library/LibrarySearchSection';
import { ProjectScopePanel } from './library/ProjectScopePanel';
import { ProjectsOverview } from './library/ProjectsOverview';

const LibraryKnowledgeGraph = lazy(() =>
  import('./LibraryKnowledgeGraph').then((module) => ({ default: module.LibraryKnowledgeGraph })),
);

type LibrarySurface = 'projects' | 'videos' | 'topics' | 'guides' | 'history';

interface LibraryViewProps {
  initialProjectId?: string;
  initialSurface?: LibrarySurface;
  onIndexMore: () => void;
  onManageProjects?: () => void;
  /** Navigate to the Library page scoped to a project (keeps top-nav state truthful). */
  onOpenLibrary?: (projectId: string) => void;
}

// The Projects surface is reached from the top nav, not this menu — listing it
// here too created two competing "you are here" indicators (F-002).
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

export const LibraryView: React.FC<LibraryViewProps> = ({
  initialProjectId = '',
  initialSurface = 'videos',
  onIndexMore,
  onManageProjects,
  onOpenLibrary,
}) => {
  const [library, setLibrary] = useState<LibraryData | null>(null);
  const [allLibrary, setAllLibrary] = useState<LibraryData | null>(null);
  const [projects, setProjects] = useState<UserProject[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [librarySurface, setLibrarySurface] = useState<LibrarySurface>(initialSurface);
  const [searchHistory, setSearchHistory] = useState<SearchHistoryEntry[]>([]);
  const [recentJobs, setRecentJobs] = useState<IngestionJob[]>([]);
  const [loadError, setLoadError] = useState('');
  const [projectNotice, setProjectNotice] = useState<NoticeState | null>(null);
  const [clearHistoryDialogOpen, setClearHistoryDialogOpen] = useState(false);

  const loadLibrary = useCallback(async () => {
    setLoadError('');
    const projectId = selectedProjectId || null;
    const [cachedAllLibrary, cachedScopedLibrary, cachedJobs] = await Promise.all([
      getCachedLibrary(),
      projectId ? getCachedLibrary(projectId) : Promise.resolve(null),
      getCachedIngestionJobs(),
    ]);

    if (cachedAllLibrary) {
      setAllLibrary(cachedAllLibrary);
    }

    if (projectId && cachedScopedLibrary) {
      setLibrary(cachedScopedLibrary);
      setLoading(false);
    } else if (!projectId && cachedAllLibrary) {
      setLibrary(cachedAllLibrary);
      setLoading(false);
    } else {
      setLoading(true);
    }

    if (cachedJobs) {
      setRecentJobs(cachedJobs.slice(0, 3));
    }

    const [allLibraryResult, scopedLibraryResult, jobsResult, projectsResult] =
      await Promise.allSettled([
        fetchLibrary(),
        projectId ? fetchLibrary(projectId) : Promise.resolve(null),
        fetchIngestionJobs(),
        fetchProjects(),
      ]);

    if (jobsResult.status === 'fulfilled') {
      setRecentJobs(jobsResult.value.slice(0, 3));
    }

    if (projectsResult.status === 'fulfilled') {
      setProjects(projectsResult.value);
      if (
        selectedProjectId &&
        !projectsResult.value.some((project) => project.id === selectedProjectId)
      ) {
        setSelectedProjectId('');
      }
    }

    if (allLibraryResult.status === 'fulfilled') {
      setAllLibrary(allLibraryResult.value);
    }

    if (projectId) {
      if (scopedLibraryResult.status === 'fulfilled' && scopedLibraryResult.value) {
        setLibrary(scopedLibraryResult.value);
      } else {
        console.warn('Error loading project library:', scopedLibraryResult);
        setLibrary({ channels: [], totalVideos: 0, totalClips: 0 });
      }
    } else if (allLibraryResult.status === 'fulfilled') {
      setLibrary(allLibraryResult.value);
    } else {
      console.warn('Error loading library:', allLibraryResult.reason);
      if (!cachedAllLibrary) {
        setLibrary(null);
        setLoadError(
          "Memexai couldn't read your saved-video library. Your imports may still be saved; retry in a moment.",
        );
      }
    }

    setLoading(false);
  }, [selectedProjectId]);

  useEffect(() => {
    setSelectedProjectId(initialProjectId);
  }, [initialProjectId]);

  useEffect(() => {
    setLibrarySurface(initialSurface);
  }, [initialSurface]);

  useEffect(() => {
    void loadLibrary();
    setSearchHistory(getSearchHistory());
  }, [loadLibrary]);

  const latestVideos = useMemo<VideoWithChannel[]>(() => {
    const videos =
      library?.channels.flatMap((channel) =>
        channel.videos.map((video) => ({ ...video, channelName: channel.name })),
      ) || [];

    return [...videos].sort((a, b) => (b.indexedAt || 0) - (a.indexedAt || 0));
  }, [library]);

  const allLatestVideos = useMemo<VideoWithChannel[]>(() => {
    const sourceLibrary = allLibrary || library;
    const videos =
      sourceLibrary?.channels.flatMap((channel) =>
        channel.videos.map((video) => ({ ...video, channelName: channel.name })),
      ) || [];

    return [...videos].sort((a, b) => (b.indexedAt || 0) - (a.indexedAt || 0));
  }, [allLibrary, library]);

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === selectedProjectId) || null,
    [projects, selectedProjectId],
  );

  const isProjectsSurface = librarySurface === 'projects';
  const hasAnyIndexedVideos = (allLibrary || library)?.totalVideos ? true : false;

  const handleProjectChanged = async () => {
    await loadLibrary();
  };

  const handleDeleteHistoryEntry = (id: string) => {
    deleteSearchHistoryEntry(id);
    setSearchHistory(getSearchHistory());
  };

  const handleClearHistory = () => {
    setClearHistoryDialogOpen(false);
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

  if ((!library || !hasAnyIndexedVideos) && !isProjectsSurface) {
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

  const displayLibrary = library || { channels: [], totalVideos: 0, totalClips: 0 };
  const totalVideoCount = (allLibrary || displayLibrary).totalVideos || 0;

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="font-serif text-4xl font-medium text-ink md:text-5xl">
            {isProjectsSurface ? 'Projects' : 'Library'}
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-bark">
            {isProjectsSurface
              ? 'Create project scopes, link playlists, and choose which saved videos belong to each workstream.'
              : 'Search saved videos, read TLDRs and reports, and scope context by project.'}
          </p>
        </div>
        <button onClick={onIndexMore} className="btn btn-primary self-start md:self-auto">
          Add videos
        </button>
      </div>

      {isProjectsSurface ? (
        <>
          <ProjectScopePanel
            projects={projects}
            selectedProjectId={selectedProjectId}
            visibleVideoCount={latestVideos.length}
            totalVideoCount={totalVideoCount}
            heading="Manage projects"
            description="Search projects, create new workstreams, assign saved videos, and link YouTube playlists."
            notice={projectNotice}
            onNotice={setProjectNotice}
            onSelectProject={setSelectedProjectId}
            onProjectChanged={handleProjectChanged}
          />
          <ProjectsOverview
            selectedProject={selectedProject}
            allVideos={allLatestVideos}
            totalVideoCount={totalVideoCount}
            onNotice={setProjectNotice}
            onProjectChanged={handleProjectChanged}
            onViewProjectVideos={() =>
              onOpenLibrary ? onOpenLibrary(selectedProjectId) : setLibrarySurface('videos')
            }
          />
        </>
      ) : (
        <>
          <LibrarySearchSection
            projectId={selectedProjectId || undefined}
            projectName={selectedProject?.name}
          />

          <div className="grid gap-5 lg:grid-cols-[240px_minmax(0,1fr)] lg:items-start">
            <aside className="card min-w-0 p-3 lg:sticky lg:top-24">
              <p
                id="library-menu-label"
                className="px-2 pb-2 text-xs font-semibold uppercase tracking-wide text-muted"
              >
                Library menu
              </p>
              <nav
                aria-labelledby="library-menu-label"
                className="grid grid-cols-2 gap-2 lg:grid-cols-1"
              >
                {librarySurfaceOptions.map((option) => (
                  <SelectableTile
                    key={option.id}
                    aria-label={option.label}
                    onClick={() => setLibrarySurface(option.id)}
                    aria-current={librarySurface === option.id ? 'page' : undefined}
                    selected={librarySurface === option.id}
                    className="rounded-xl px-3 py-3 text-left transition-all"
                  >
                    <span className="block text-sm font-semibold">
                      <span className="sm:hidden">{option.mobileLabel}</span>
                      <span className="hidden sm:inline">{option.label}</span>
                    </span>
                    <span className="mt-1 hidden text-xs leading-5 text-muted sm:block">
                      {option.description}
                    </span>
                  </SelectableTile>
                ))}
              </nav>

              <div className="mt-3 border-t border-ink/10 px-2 pb-1 pt-3">
                <label
                  htmlFor="library-project-scope"
                  className="text-xs font-semibold uppercase tracking-wide text-muted"
                >
                  Project scope
                </label>
                <select
                  id="library-project-scope"
                  value={selectedProjectId}
                  onChange={(event) => setSelectedProjectId(event.target.value)}
                  className="input mt-2 w-full px-3 py-2 text-sm"
                >
                  <option value="">All library</option>
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                </select>
                <p className="mt-2 text-xs leading-5 text-muted">
                  {latestVideos.length} shown of {totalVideoCount} saved video
                  {totalVideoCount === 1 ? '' : 's'}
                </p>
                {onManageProjects ? (
                  <button
                    type="button"
                    onClick={onManageProjects}
                    className="link-quiet mt-2 text-xs"
                  >
                    Manage projects
                  </button>
                ) : null}
              </div>
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
                    projectId={selectedProjectId || undefined}
                    totalVideoCount={displayLibrary.totalVideos || 0}
                  />
                </Suspense>
              ) : (
                <HistoryView
                  entries={searchHistory}
                  onClear={() => setClearHistoryDialogOpen(true)}
                  onDeleteEntry={handleDeleteHistoryEntry}
                />
              )}
            </div>
          </div>
        </>
      )}
      {clearHistoryDialogOpen ? (
        <ConfirmDialog
          eyebrow="Recent searches"
          title="Clear all search history?"
          body="Saved local searches and their clips will be removed from this device."
          confirmLabel="Clear all"
          onCancel={() => setClearHistoryDialogOpen(false)}
          onConfirm={handleClearHistory}
        />
      ) : null}
    </div>
  );
};

export default LibraryView;
