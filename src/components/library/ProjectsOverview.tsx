import React, { useState } from 'react';
import { UserProject } from '../../types';
import { addProjectVideos, createCaptureSource } from '../../services/api';
import { VideoWithChannel } from '../../lib/videoKnowledge';
import { NoticeState } from '../ui/Notice';
import { Panel } from '../ui/Panel';

export function ProjectsOverview({
  selectedProject,
  allVideos,
  totalVideoCount,
  onNotice,
  onProjectChanged,
  onViewProjectVideos,
}: {
  selectedProject: UserProject | null;
  allVideos: VideoWithChannel[];
  totalVideoCount: number;
  onNotice: (notice: NoticeState | null) => void;
  onProjectChanged: () => Promise<void>;
  onViewProjectVideos: () => void;
}) {
  const [assignVideoId, setAssignVideoId] = useState('');
  const [linkPlaylistUrl, setLinkPlaylistUrl] = useState('');
  const [working, setWorking] = useState(false);

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
    <Panel
      title="Project view"
      size="section"
      description="Everything about the selected project: its videos, linked playlists, and the actions that grow it."
    >
      {selectedProject ? (
        <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(280px,360px)]">
          <div className="min-w-0 rounded-2xl border border-ink/10 bg-cream p-4">
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
          </div>

          <div className="min-w-0 rounded-2xl border border-ink/10 bg-cream p-4">
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted">
                Grow this project
              </p>
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
                <label className="sr-only" htmlFor="project-link-playlist">
                  Link a YouTube playlist to this project
                </label>
                <input
                  id="project-link-playlist"
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
          </div>
        </div>
      ) : (
        <div className="min-w-0 rounded-2xl border border-ink/10 bg-cream p-4">
          <div className="flex min-h-40 flex-col justify-center">
            <p className="text-sm font-semibold text-ink">No project selected</p>
            <p className="mt-2 max-w-xl text-sm leading-6 text-bark">
              Choose a project from the list or create one above. Your full library currently has{' '}
              <span className="font-semibold text-ink">{totalVideoCount}</span> saved video
              {totalVideoCount === 1 ? '' : 's'} available for assignment.
            </p>
          </div>
        </div>
      )}
    </Panel>
  );
}
