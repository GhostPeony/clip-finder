import React, { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import { IngestionJob, LibraryData, LibraryVideo, SearchHistoryEntry, UserProject } from '../types';
import {
  addProjectVideos,
  clearSearchHistory,
  createCaptureSource,
  createProject,
  deleteSearchHistoryEntry,
  fetchIngestionJobs,
  fetchLibrary,
  fetchProjects,
  getCachedIngestionJobs,
  getCachedLibrary,
  getSearchHistory,
} from '../services/api';
import { BrandLoader } from './BrandLoader';

const LibraryKnowledgeGraph = lazy(() =>
  import('./LibraryKnowledgeGraph').then((module) => ({ default: module.LibraryKnowledgeGraph })),
);

type LibrarySurface = 'projects' | 'videos' | 'topics' | 'guides' | 'history';

interface LibraryViewProps {
  initialProjectId?: string;
  initialSurface?: LibrarySurface;
  onIndexMore: () => void;
}
type VideoWithChannel = LibraryVideo & { channelName: string };

const librarySurfaceOptions: Array<{
  id: LibrarySurface;
  label: string;
  mobileLabel: string;
  description: string;
}> = [
  {
    id: 'projects',
    label: 'Projects',
    mobileLabel: 'Projects',
    description: 'Create, search, assign videos, and link playlists to project scopes.',
  },
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
  const [projectNotice, setProjectNotice] = useState('');

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
    if (!confirm('Clear all search history?')) return;
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

      <ProjectScopePanel
        projects={projects}
        selectedProjectId={selectedProjectId}
        selectedProject={selectedProject}
        allVideos={allLatestVideos}
        visibleVideoCount={latestVideos.length}
        totalVideoCount={totalVideoCount}
        heading={isProjectsSurface ? 'Manage projects' : 'Projects'}
        description={
          isProjectsSurface
            ? 'Search projects, create new workstreams, assign saved videos, and link YouTube playlists.'
            : 'Scope browsing and agent retrieval to a specific use case without duplicating videos.'
        }
        notice={projectNotice}
        onNotice={setProjectNotice}
        onSelectProject={setSelectedProjectId}
        onProjectChanged={handleProjectChanged}
      />

      <div className="grid gap-5 lg:grid-cols-[240px_minmax(0,1fr)] lg:items-start">
        <aside className="card min-w-0 p-3 lg:sticky lg:top-24">
          <p className="px-2 pb-2 text-xs font-semibold uppercase tracking-wide text-muted">
            Library menu
          </p>
          <nav aria-label="Library sections" className="grid grid-cols-2 gap-2 lg:grid-cols-1">
            {librarySurfaceOptions.map((option) => (
              <button
                key={option.id}
                type="button"
                aria-label={option.label}
                onClick={() => setLibrarySurface(option.id)}
                aria-current={librarySurface === option.id ? 'page' : undefined}
                className={`rounded-xl px-3 py-3 text-left transition-all ${
                  librarySurface === option.id
                    ? 'bg-surface text-ink shadow-soft'
                    : 'bg-cream text-bark hover:bg-petal/50 hover:text-ink'
                }`}
              >
                <span className="block text-sm font-semibold">
                  <span className="sm:hidden">{option.mobileLabel}</span>
                  <span className="hidden sm:inline">{option.label}</span>
                </span>
                <span className="mt-1 hidden text-xs leading-5 text-muted sm:block">
                  {option.description}
                </span>
              </button>
            ))}
          </nav>
        </aside>

        <div className="min-w-0">
          {librarySurface !== 'history' && librarySurface !== 'projects' ? (
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
                projectName={selectedProject?.name}
              />
            </Suspense>
          ) : null}

          {librarySurface === 'projects' ? (
            <ProjectsOverview
              projects={projects}
              selectedProject={selectedProject}
              selectedProjectId={selectedProjectId}
              totalVideoCount={totalVideoCount}
              onSelectProject={setSelectedProjectId}
              onViewProjectVideos={() => setLibrarySurface('videos')}
              onIndexMore={onIndexMore}
            />
          ) : null}

          {librarySurface === 'history' ? (
            <HistoryView
              entries={searchHistory}
              onClear={handleClearHistory}
              onDeleteEntry={handleDeleteHistoryEntry}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
};

function ProjectScopePanel({
  projects,
  selectedProjectId,
  selectedProject,
  allVideos,
  visibleVideoCount,
  totalVideoCount,
  heading,
  description,
  notice,
  onNotice,
  onSelectProject,
  onProjectChanged,
}: {
  projects: UserProject[];
  selectedProjectId: string;
  selectedProject: UserProject | null;
  allVideos: VideoWithChannel[];
  visibleVideoCount: number;
  totalVideoCount: number;
  heading: string;
  description: string;
  notice: string;
  onNotice: (notice: string) => void;
  onSelectProject: (projectId: string) => void;
  onProjectChanged: () => Promise<void>;
}) {
  const [projectName, setProjectName] = useState('');
  const [projectDescription, setProjectDescription] = useState('');
  const [projectPlaylistUrl, setProjectPlaylistUrl] = useState('');
  const [assignVideoId, setAssignVideoId] = useState('');
  const [linkPlaylistUrl, setLinkPlaylistUrl] = useState('');
  const [projectQuery, setProjectQuery] = useState('');
  const [working, setWorking] = useState(false);
  const filteredProjects = useMemo(() => {
    const query = projectQuery.trim().toLowerCase();
    if (!query) return projects;
    return projects.filter((project) =>
      [project.name, project.description, project.slug]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(query)),
    );
  }, [projectQuery, projects]);

  const handleCreateProject = async (event: React.FormEvent) => {
    event.preventDefault();
    const trimmedName = projectName.trim();
    if (!trimmedName) return;
    setWorking(true);
    onNotice('');
    try {
      const project = await createProject(trimmedName, projectDescription.trim());
      if (!project) {
        onNotice('Project could not be created. Try again.');
        return;
      }
      if (projectPlaylistUrl.trim()) {
        await createCaptureSource(
          projectPlaylistUrl.trim(),
          `${project.name} playlist`,
          project.id,
        );
      }
      setProjectName('');
      setProjectDescription('');
      setProjectPlaylistUrl('');
      onSelectProject(project.id);
      onNotice(
        projectPlaylistUrl.trim() ? 'Project created and playlist linked.' : 'Project created.',
      );
      await onProjectChanged();
    } finally {
      setWorking(false);
    }
  };

  const handleAssignVideo = async () => {
    if (!selectedProject || !assignVideoId) return;
    setWorking(true);
    onNotice('');
    try {
      const result = await addProjectVideos(selectedProject.id, [assignVideoId]);
      if (!result) {
        onNotice('Video could not be assigned to this project.');
        return;
      }
      setAssignVideoId('');
      onNotice('Video assigned to project.');
      await onProjectChanged();
    } finally {
      setWorking(false);
    }
  };

  const handleLinkPlaylist = async () => {
    if (!selectedProject || !linkPlaylistUrl.trim()) return;
    setWorking(true);
    onNotice('');
    try {
      const source = await createCaptureSource(
        linkPlaylistUrl.trim(),
        `${selectedProject.name} playlist`,
        selectedProject.id,
      );
      if (!source) {
        onNotice('Playlist could not be linked to this project.');
        return;
      }
      setLinkPlaylistUrl('');
      onNotice('Playlist linked. Sync it from capture settings when you are ready.');
      await onProjectChanged();
    } finally {
      setWorking(false);
    }
  };

  return (
    <section className="card min-w-0 space-y-4 overflow-hidden p-4 sm:p-5">
      <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <h2 className="font-serif text-3xl font-medium text-ink">{heading}</h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-bark">{description}</p>
        </div>
        <div className="shrink-0 rounded-xl border border-ink/10 bg-cream px-3 py-2 text-sm text-bark">
          <span className="font-semibold text-ink">{visibleVideoCount}</span>
          <span> shown of </span>
          <span className="font-semibold text-ink">{totalVideoCount}</span>
          <span> saved videos</span>
        </div>
      </div>

      <div className="grid min-w-0 gap-3 lg:grid-cols-[minmax(220px,320px)_minmax(0,1fr)] lg:items-start">
        <label className="block min-w-0">
          <span className="sr-only">Search projects</span>
          <input
            value={projectQuery}
            onChange={(event) => setProjectQuery(event.target.value)}
            className="input w-full"
            placeholder="Search projects"
          />
        </label>
        <div className="flex min-w-0 gap-2 overflow-x-auto pb-1">
          <button
            type="button"
            onClick={() => onSelectProject('')}
            className={`shrink-0 rounded-xl border px-4 py-3 text-left text-sm font-semibold transition-colors ${
              selectedProjectId
                ? 'border-ink/10 bg-cream text-bark hover:text-ink'
                : 'border-rose/30 bg-surface text-ink shadow-soft'
            }`}
          >
            <span className="block">All library</span>
            <span className="mt-1 block text-xs font-medium text-muted">
              {totalVideoCount} video{totalVideoCount === 1 ? '' : 's'}
            </span>
          </button>
          {filteredProjects.map((project) => (
            <button
              key={project.id}
              type="button"
              onClick={() => onSelectProject(project.id)}
              className={`min-w-[180px] max-w-[240px] shrink-0 rounded-xl border px-4 py-3 text-left text-sm font-semibold transition-colors ${
                selectedProjectId === project.id
                  ? 'border-rose/30 bg-surface text-ink shadow-soft'
                  : 'border-ink/10 bg-cream text-bark hover:text-ink'
              }`}
            >
              <span className="block truncate">{project.name}</span>
              <span className="mt-1 block text-xs font-medium text-muted">
                {project.videoCount ?? 0} video{(project.videoCount ?? 0) === 1 ? '' : 's'}
                {project.linkedCaptureSourceCount
                  ? ` · ${project.linkedCaptureSourceCount} source`
                  : ''}
              </span>
            </button>
          ))}
          {filteredProjects.length === 0 ? (
            <p className="rounded-xl bg-cream px-4 py-3 text-sm text-bark">No matching projects.</p>
          ) : null}
        </div>
      </div>

      <div className="grid min-w-0 gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(280px,380px)]">
        <form
          onSubmit={(event) => void handleCreateProject(event)}
          className="min-w-0 rounded-2xl border border-ink/10 bg-cream p-3"
        >
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <label className="block">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted">
                New project
              </span>
              <input
                value={projectName}
                onChange={(event) => setProjectName(event.target.value)}
                className="input mt-1 w-full"
                placeholder="Agent harness research"
              />
            </label>
            <label className="block">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted">
                Optional playlist
              </span>
              <input
                value={projectPlaylistUrl}
                onChange={(event) => setProjectPlaylistUrl(event.target.value)}
                className="input mt-1 w-full"
                placeholder="https://youtube.com/playlist?list=..."
              />
            </label>
          </div>
          <label className="mt-3 block">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted">
              Description
            </span>
            <input
              value={projectDescription}
              onChange={(event) => setProjectDescription(event.target.value)}
              className="input mt-1 w-full"
              placeholder="What this project is trying to learn or build"
            />
          </label>
          <button
            type="submit"
            disabled={working || !projectName.trim()}
            className="btn btn-primary mt-3 w-full sm:w-auto"
          >
            Create project
          </button>
        </form>

        <div className="min-w-0 rounded-2xl border border-ink/10 bg-cream p-3">
          {selectedProject ? (
            <div className="space-y-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted">
                  Selected project
                </p>
                <p className="mt-1 break-words text-sm font-semibold text-ink">
                  {selectedProject.name}
                </p>
              </div>
              <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
                <select
                  value={assignVideoId}
                  onChange={(event) => setAssignVideoId(event.target.value)}
                  className="input w-full"
                >
                  <option value="">Assign a saved video</option>
                  {allVideos.map((video) => (
                    <option key={video.videoId} value={video.videoId}>
                      {video.title}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => void handleAssignVideo()}
                  disabled={working || !assignVideoId}
                  className="btn btn-secondary w-full sm:w-auto"
                >
                  Assign
                </button>
              </div>
              <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
                <input
                  value={linkPlaylistUrl}
                  onChange={(event) => setLinkPlaylistUrl(event.target.value)}
                  className="input w-full"
                  placeholder="Link playlist to this project"
                />
                <button
                  type="button"
                  onClick={() => void handleLinkPlaylist()}
                  disabled={working || !linkPlaylistUrl.trim()}
                  className="btn btn-secondary w-full sm:w-auto"
                >
                  Link
                </button>
              </div>
            </div>
          ) : (
            <div className="flex h-full min-h-40 flex-col justify-center">
              <p className="text-sm font-semibold text-ink">Full library scope</p>
              <p className="mt-1 text-sm leading-6 text-bark">
                Select a project to narrow videos, reports, topics, and agent-facing search.
              </p>
            </div>
          )}
        </div>
      </div>

      {notice ? <p className="text-sm font-medium text-bark">{notice}</p> : null}
    </section>
  );
}

function ProjectsOverview({
  projects,
  selectedProject,
  selectedProjectId,
  totalVideoCount,
  onSelectProject,
  onViewProjectVideos,
  onIndexMore,
}: {
  projects: UserProject[];
  selectedProject: UserProject | null;
  selectedProjectId: string;
  totalVideoCount: number;
  onSelectProject: (projectId: string) => void;
  onViewProjectVideos: () => void;
  onIndexMore: () => void;
}) {
  return (
    <section className="card min-w-0 space-y-5 overflow-hidden p-5">
      <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h2 className="font-serif text-3xl font-medium text-ink">Project view</h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-bark">
            Use projects as retrieval scopes for humans and agents. Select one here, then open its
            videos, reports, topics, and timestamped evidence.
          </p>
        </div>
        <button onClick={onIndexMore} className="btn btn-secondary w-full sm:w-auto">
          Add videos
        </button>
      </div>

      <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(280px,360px)]">
        <div className="min-w-0 rounded-2xl border border-ink/10 bg-cream p-4">
          {selectedProject ? (
            <div className="space-y-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted">
                  Selected project
                </p>
                <h3 className="mt-1 break-words font-serif text-3xl font-medium text-ink">
                  {selectedProject.name}
                </h3>
                {selectedProject.description ? (
                  <p className="mt-2 text-sm leading-6 text-bark">{selectedProject.description}</p>
                ) : null}
              </div>
              <dl className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl bg-surface px-3 py-2">
                  <dt className="text-xs font-semibold uppercase tracking-wide text-muted">
                    Videos
                  </dt>
                  <dd className="mt-1 text-2xl font-semibold text-ink">
                    {selectedProject.videoCount ?? 0}
                  </dd>
                </div>
                <div className="rounded-xl bg-surface px-3 py-2">
                  <dt className="text-xs font-semibold uppercase tracking-wide text-muted">
                    Playlists
                  </dt>
                  <dd className="mt-1 text-2xl font-semibold text-ink">
                    {selectedProject.linkedCaptureSourceCount ?? 0}
                  </dd>
                </div>
              </dl>
              <button onClick={onViewProjectVideos} className="btn btn-primary w-full sm:w-auto">
                View project videos
              </button>
            </div>
          ) : (
            <div className="flex min-h-56 flex-col justify-center">
              <p className="text-sm font-semibold text-ink">No project selected</p>
              <p className="mt-2 text-sm leading-6 text-bark">
                Choose a project from the list or create one above. Your full library currently has{' '}
                <span className="font-semibold text-ink">{totalVideoCount}</span> saved video
                {totalVideoCount === 1 ? '' : 's'} available for assignment.
              </p>
            </div>
          )}
        </div>

        <div className="min-w-0 rounded-2xl border border-ink/10 bg-cream p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">
              All projects
            </h3>
            <span className="text-sm font-semibold text-ink">{projects.length}</span>
          </div>
          {projects.length > 0 ? (
            <div className="max-h-[420px] space-y-2 overflow-y-auto pr-1">
              {projects.map((project) => (
                <button
                  key={project.id}
                  type="button"
                  onClick={() => onSelectProject(project.id)}
                  className={`w-full min-w-0 rounded-xl px-3 py-3 text-left transition-colors ${
                    selectedProjectId === project.id
                      ? 'bg-surface text-ink shadow-soft'
                      : 'bg-surface/60 text-bark hover:bg-surface hover:text-ink'
                  }`}
                >
                  <span className="block truncate text-sm font-semibold">{project.name}</span>
                  <span className="mt-1 block text-xs text-muted">
                    {project.videoCount ?? 0} video{(project.videoCount ?? 0) === 1 ? '' : 's'}
                    {project.linkedCaptureSourceCount
                      ? ` · ${project.linkedCaptureSourceCount} playlist`
                      : ''}
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <p className="text-sm leading-6 text-bark">
              Create a project above to group saved videos around a client, research area, build,
              course, or agent task.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

function LibraryImportRow({ job }: { job: IngestionJob }) {
  return (
    <div className="rounded-xl bg-cream px-3 py-2 text-left">
      <div className="flex flex-wrap items-center gap-2">
        <span className={libraryJobStatusClass[job.status]}>{job.status}</span>
        <span className="text-xs font-semibold uppercase tracking-wide text-muted">
          {job.source_type}
        </span>
      </div>
      <p className="mt-1 truncate text-sm font-semibold text-ink">{job.source_url}</p>
      <p
        className={`mt-1 truncate text-xs ${
          job.status === 'failed' ? 'font-medium text-rose-deep' : 'text-muted'
        }`}
      >
        {libraryJobOutcomeText(job)}
      </p>
    </div>
  );
}

const libraryJobStatusClass: Record<IngestionJob['status'], string> = {
  queued: 'chip chip-violet',
  running: 'chip chip-teal',
  completed: 'chip chip-leaf',
  partial: 'chip chip-sun',
  failed: 'chip',
  cancelled: 'chip chip-violet',
};

function libraryJobOutcomeText(job: IngestionJob): string {
  if (job.status === 'failed') {
    return job.error || job.last_message || 'Import failed';
  }
  if (job.status === 'partial') {
    return `Partial import: ${job.indexed_video_count} indexed, ${job.skipped_video_count} skipped, ${job.failed_video_count} failed`;
  }
  if (job.status === 'completed') {
    return `${job.indexed_video_count} video${job.indexed_video_count === 1 ? '' : 's'} indexed`;
  }
  return job.last_message || 'Import in progress';
}

function HistoryView({
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
    <section className="card p-5">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="font-serif text-3xl font-medium text-ink">Recent searches</h2>
          <p className="mt-1 text-sm text-bark">{entries.length} saved local query runs</p>
        </div>
        <button
          onClick={onClear}
          className="self-start text-xs font-semibold uppercase tracking-wide text-muted hover:text-rose-deep sm:self-auto"
        >
          Clear all
        </button>
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        {entries.map((entry) => (
          <SearchHistoryCard
            key={entry.id}
            entry={entry}
            onDelete={() => onDeleteEntry(entry.id)}
          />
        ))}
      </div>
    </section>
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
          className="rounded-full p-1 text-muted opacity-0 transition-opacity hover:text-rose-deep group-hover:opacity-100 focus-visible:opacity-100"
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

function formatRelativeTime(timestamp: number): string {
  const diff = Date.now() - timestamp;
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;
  return new Date(timestamp).toLocaleDateString();
}

function formatTimestamp(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
}

export default LibraryView;
