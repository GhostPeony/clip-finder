import React from 'react';
import { UserProject } from '../../types';
import { Panel } from '../ui/Panel';
import { SelectableTile } from '../ui/SelectableTile';

export function ProjectsOverview({
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
    <Panel
      title="Project view"
      size="section"
      description="Use projects as retrieval scopes for humans and agents. Select one here, then open its videos, reports, topics, and timestamped evidence."
      action={
        <button onClick={onIndexMore} className="btn btn-secondary">
          Add videos
        </button>
      }
    >
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
                <SelectableTile
                  key={project.id}
                  onClick={() => onSelectProject(project.id)}
                  selected={selectedProjectId === project.id}
                  unselectedClassName="bg-surface/60 text-bark hover:bg-surface hover:text-ink"
                  className="w-full min-w-0 rounded-xl px-3 py-3 text-left transition-colors"
                >
                  <span className="block truncate text-sm font-semibold">{project.name}</span>
                  <span className="mt-1 block text-xs text-muted">
                    {project.videoCount ?? 0} video{(project.videoCount ?? 0) === 1 ? '' : 's'}
                    {project.linkedCaptureSourceCount
                      ? ` · ${project.linkedCaptureSourceCount} playlist`
                      : ''}
                  </span>
                </SelectableTile>
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
    </Panel>
  );
}
