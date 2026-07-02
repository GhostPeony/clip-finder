import React, { useMemo, useState } from 'react';
import { UserProject } from '../../types';
import { createCaptureSource, createProject } from '../../services/api';
import { Notice, NoticeState } from '../ui/Notice';
import { SelectableTile } from '../ui/SelectableTile';

export function ProjectScopePanel({
  projects,
  selectedProjectId,
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

      <form
        onSubmit={(event) => void handleCreateProject(event)}
        className="min-w-0 rounded-xl bg-cream p-4"
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

      {notice ? <Notice tone={notice.tone}>{notice.message}</Notice> : null}
    </section>
  );
}
