import React, { useMemo, useState } from 'react';
import { UserProject } from '../../types';
import { addProjectVideos, createCaptureSource, createProject } from '../../services/api';
import { VideoWithChannel } from '../../lib/videoKnowledge';
import { Notice, NoticeState } from '../ui/Notice';
import { SelectableTile } from '../ui/SelectableTile';

export function ProjectScopePanel({
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
  notice: NoticeState | null;
  onNotice: (notice: NoticeState | null) => void;
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
    onNotice(null);
    try {
      const project = await createProject(trimmedName, projectDescription.trim());
      if (!project) {
        onNotice({ message: 'Project could not be created. Try again.', tone: 'error' });
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
      onNotice({
        message: projectPlaylistUrl.trim()
          ? 'Project created and playlist linked.'
          : 'Project created.',
        tone: 'success',
      });
      await onProjectChanged();
    } finally {
      setWorking(false);
    }
  };

  const handleAssignVideo = async () => {
    if (!selectedProject || !assignVideoId) return;
    setWorking(true);
    onNotice(null);
    try {
      const result = await addProjectVideos(selectedProject.id, [assignVideoId]);
      if (!result) {
        onNotice({ message: 'Video could not be assigned to this project.', tone: 'error' });
        return;
      }
      setAssignVideoId('');
      onNotice({ message: 'Video assigned to project.', tone: 'success' });
      await onProjectChanged();
    } finally {
      setWorking(false);
    }
  };

  const handleLinkPlaylist = async () => {
    if (!selectedProject || !linkPlaylistUrl.trim()) return;
    setWorking(true);
    onNotice(null);
    try {
      const source = await createCaptureSource(
        linkPlaylistUrl.trim(),
        `${selectedProject.name} playlist`,
        selectedProject.id,
      );
      if (!source) {
        onNotice({ message: 'Playlist could not be linked to this project.', tone: 'error' });
        return;
      }
      setLinkPlaylistUrl('');
      onNotice({
        message: 'Playlist linked. Sync it from capture settings when you are ready.',
        tone: 'success',
      });
      await onProjectChanged();
    } finally {
      setWorking(false);
    }
  };

  return (
    <section className="card min-w-0 space-y-4 overflow-hidden p-4 sm:p-5">
      <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <h2 className="font-serif text-2xl font-medium text-ink">{heading}</h2>
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
          <SelectableTile
            onClick={() => onSelectProject('')}
            selected={!selectedProjectId}
            variant="bordered"
            className="shrink-0 rounded-xl border px-4 py-3 text-left text-sm font-semibold transition-colors"
          >
            <span className="block">All library</span>
            <span className="mt-1 block text-xs font-medium text-muted">
              {totalVideoCount} video{totalVideoCount === 1 ? '' : 's'}
            </span>
          </SelectableTile>
          {filteredProjects.map((project) => (
            <SelectableTile
              key={project.id}
              onClick={() => onSelectProject(project.id)}
              selected={selectedProjectId === project.id}
              variant="bordered"
              className="min-w-[180px] max-w-[240px] shrink-0 rounded-xl border px-4 py-3 text-left text-sm font-semibold transition-colors"
            >
              <span className="block truncate">{project.name}</span>
              <span className="mt-1 block text-xs font-medium text-muted">
                {project.videoCount ?? 0} video{(project.videoCount ?? 0) === 1 ? '' : 's'}
                {project.linkedCaptureSourceCount
                  ? ` · ${project.linkedCaptureSourceCount} source`
                  : ''}
              </span>
            </SelectableTile>
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
                <label className="sr-only" htmlFor="project-assign-video">
                  Assign a saved video
                </label>
                <select
                  id="project-assign-video"
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

      {notice ? <Notice tone={notice.tone}>{notice.message}</Notice> : null}
    </section>
  );
}
