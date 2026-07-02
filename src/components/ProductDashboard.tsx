import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  CaptureSource,
  IngestionJob,
  LibraryData,
  UserProject,
  VideoClip,
  YoutubeOAuthStatus,
} from '../types';
import {
  clearIngestionJobHistory,
  createProject,
  deleteCaptureSource,
  fetchCaptureSources,
  fetchIngestionJobs,
  fetchLibrary,
  fetchProjects,
  fetchUsage,
  fetchYoutubeOAuthStatus,
  syncCaptureSource,
  UsageInfo,
} from '../services/api';
import { YOUTUBE_CONNECTION_SAVED_EVENT } from '../contexts/AuthContext';
import { isActiveJob, isClearableJob, jobOutcomeText, jobStatusChipClass } from '../lib/jobs';
import { formatRelativeTime } from '../lib/time';
import { usePolling } from '../lib/usePolling';
import { BrandLoader } from './BrandLoader';
import { CaptureSourceDisconnectModal } from './CaptureSourceDisconnectModal';
import { CaptureSyncConfirmModal } from './CaptureSyncConfirmModal';
import { ConfirmDialog } from './ui/ConfirmDialog';
import { Notice, NoticeState } from './ui/Notice';
import { Panel } from './ui/Panel';
import { PanelError } from './ui/PanelError';
import { UnifiedSearchView } from './UnifiedSearchView';

interface ProductDashboardProps {
  onOpenSettings: () => void;
  onOpenLibrary: (projectId?: string) => void;
  onOpenProjects: () => void;
  onOpenJobs: () => void;
  onConnectYouTube?: () => void | Promise<unknown>;
  onSearchComplete: (clips: VideoClip[], answer: string, activeClip: VideoClip | null) => void;
  onIndexComplete: () => void;
}

interface DashboardSectionFailures {
  library: boolean;
  usage: boolean;
  jobs: boolean;
  captureSources: boolean;
  projects: boolean;
  youtubeStatus: boolean;
}

interface DashboardBundle {
  library: LibraryData;
  usage: UsageInfo | null;
  jobs: IngestionJob[];
  captureSources: CaptureSource[];
  projects: UserProject[];
  youtubeStatus: YoutubeOAuthStatus | null;
  failures: DashboardSectionFailures;
}

interface PendingCaptureSync {
  source: CaptureSource;
  pendingCount: number;
}

const EMPTY_LIBRARY: LibraryData = { channels: [], totalVideos: 0, totalClips: 0 };

const NO_SECTION_FAILURES: DashboardSectionFailures = {
  library: false,
  usage: false,
  jobs: false,
  captureSources: false,
  projects: false,
  youtubeStatus: false,
};

async function settle<T>(promise: Promise<T>, fallback: T): Promise<{ value: T; failed: boolean }> {
  try {
    return { value: await promise, failed: false };
  } catch {
    return { value: fallback, failed: true };
  }
}

const loadDashboardBundle = async (): Promise<DashboardBundle> => {
  const [library, usage, jobs, captureSources, projects, youtubeStatus] = await Promise.all([
    settle<LibraryData>(fetchLibrary(), EMPTY_LIBRARY),
    settle<UsageInfo | null>(fetchUsage(), null),
    settle<IngestionJob[]>(fetchIngestionJobs(), []),
    settle<CaptureSource[]>(fetchCaptureSources(), []),
    settle<UserProject[]>(fetchProjects(), []),
    settle<YoutubeOAuthStatus | null>(fetchYoutubeOAuthStatus(), null),
  ]);

  return {
    library: library.value,
    usage: usage.value,
    jobs: jobs.value,
    captureSources: captureSources.value,
    projects: projects.value,
    youtubeStatus: youtubeStatus.value,
    failures: {
      library: library.failed,
      usage: usage.failed,
      jobs: jobs.failed,
      captureSources: captureSources.failed,
      projects: projects.failed,
      youtubeStatus: youtubeStatus.failed,
    },
  };
};

export const ProductDashboard: React.FC<ProductDashboardProps> = ({
  onOpenSettings,
  onOpenLibrary,
  onOpenProjects,
  onOpenJobs,
  onConnectYouTube,
  onSearchComplete,
  onIndexComplete,
}) => {
  const [library, setLibrary] = useState<LibraryData | null>(null);
  const [usage, setUsage] = useState<UsageInfo | null>(null);
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [captureSources, setCaptureSources] = useState<CaptureSource[]>([]);
  const [projects, setProjects] = useState<UserProject[]>([]);
  const [youtubeStatus, setYoutubeStatus] = useState<YoutubeOAuthStatus | null>(null);
  const [syncingSourceId, setSyncingSourceId] = useState<string | null>(null);
  const [pendingCaptureSync, setPendingCaptureSync] = useState<PendingCaptureSync | null>(null);
  const [confirmingCaptureSync, setConfirmingCaptureSync] = useState(false);
  const [pendingDisconnectSource, setPendingDisconnectSource] = useState<CaptureSource | null>(
    null,
  );
  const [disconnectingSourceId, setDisconnectingSourceId] = useState<string | null>(null);
  const [captureNotice, setCaptureNotice] = useState<NoticeState | null>(null);
  const [projectNotice, setProjectNotice] = useState<NoticeState | null>(null);
  const [projectName, setProjectName] = useState('');
  const [creatingProject, setCreatingProject] = useState(false);
  const [importNotice, setImportNotice] = useState<NoticeState | null>(null);
  const [clearingImports, setClearingImports] = useState(false);
  const [clearImportsDialogOpen, setClearImportsDialogOpen] = useState(false);
  const [failures, setFailures] = useState<DashboardSectionFailures>(NO_SECTION_FAILURES);
  const [dashboardLoading, setDashboardLoading] = useState(true);

  const applyDashboardBundle = useCallback((bundle: DashboardBundle) => {
    setLibrary(bundle.library);
    setUsage(bundle.usage);
    setJobs(bundle.jobs.slice(0, 6));
    setCaptureSources(bundle.captureSources);
    setProjects(bundle.projects);
    setYoutubeStatus(bundle.youtubeStatus);
    setFailures(bundle.failures);
  }, []);

  const refreshDashboardData = useCallback(async () => {
    const bundle = await loadDashboardBundle();
    applyDashboardBundle(bundle);
  }, [applyDashboardBundle]);

  // Cheap 15s refresh: only the sections that change while you watch (jobs + usage).
  const refreshJobsAndUsage = useCallback(async () => {
    const [usage, jobs] = await Promise.all([
      settle<UsageInfo | null>(fetchUsage(), null),
      settle<IngestionJob[]>(fetchIngestionJobs(), []),
    ]);
    setUsage(usage.value);
    setJobs(jobs.value.slice(0, 6));
    setFailures((current) => ({ ...current, usage: usage.failed, jobs: jobs.failed }));
  }, []);

  useEffect(() => {
    let active = true;

    const load = async () => {
      const bundle = await loadDashboardBundle();
      if (!active) return;
      applyDashboardBundle(bundle);
      setDashboardLoading(false);
    };

    load();
    const onYoutubeConnected = () => {
      void load();
    };
    window.addEventListener(YOUTUBE_CONNECTION_SAVED_EVENT, onYoutubeConnected);

    return () => {
      active = false;
      window.removeEventListener(YOUTUBE_CONNECTION_SAVED_EVENT, onYoutubeConnected);
    };
  }, [applyDashboardBundle]);

  usePolling(refreshJobsAndUsage, 15000, { onVisibilityRefresh: refreshDashboardData });

  const activeJobs = useMemo(() => jobs.filter(isActiveJob), [jobs]);

  const failedJobs = useMemo(() => jobs.filter((job) => job.status === 'failed'), [jobs]);
  const clearableJobs = useMemo(() => jobs.filter(isClearableJob), [jobs]);

  const youtubeConnected = youtubeStatus?.connected || false;

  const recentStatus = useMemo(() => {
    if (activeJobs.length > 0) {
      return `${activeJobs.length} active import${activeJobs.length === 1 ? '' : 's'}`;
    }
    if (failedJobs.length > 0) {
      return `${failedJobs.length} failed import${failedJobs.length === 1 ? '' : 's'}`;
    }
    if (jobs.length > 0) return `${jobs.length} recent import${jobs.length === 1 ? '' : 's'}`;
    return 'No imports yet';
  }, [activeJobs.length, failedJobs.length, jobs.length]);

  const handleSyncSource = async (source: CaptureSource) => {
    setSyncingSourceId(source.id);
    setCaptureNotice(null);
    try {
      const preview = await syncCaptureSource(source.id, 0);
      if (!preview) {
        setCaptureNotice({
          message: 'Sync did not start. Check the capture source and try again.',
          tone: 'error',
        });
        return;
      }

      const pendingCount = preview.queueCandidateCount ?? preview.newItemCount;
      if (pendingCount <= 0) {
        setCaptureNotice({
          message: 'Sync is up to date. No new videos are waiting to import.',
          tone: 'success',
        });
        await refreshDashboardData();
        return;
      }

      setPendingCaptureSync({ source, pendingCount });
      await refreshDashboardData();
    } finally {
      setSyncingSourceId(null);
    }
  };

  const handleConfirmCaptureSync = async () => {
    if (!pendingCaptureSync) return;
    const { source, pendingCount } = pendingCaptureSync;
    setConfirmingCaptureSync(true);
    setSyncingSourceId(source.id);
    setCaptureNotice(null);
    try {
      const result = await syncCaptureSource(source.id, pendingCount);
      if (!result) {
        setCaptureNotice({
          message:
            'Sync failed before all imports could be queued. Check Imports for any queued job and retry.',
          tone: 'error',
        });
        return;
      }

      const queuedCount = result.queuedJobCount;
      const remainingCount = result.remainingQueueCount ?? Math.max(0, pendingCount - queuedCount);
      setCaptureNotice({
        message:
          remainingCount > 0
            ? `Queued ${queuedCount} of ${pendingCount} video${pendingCount === 1 ? '' : 's'}. ${remainingCount} still waiting to queue.`
            : `Queued ${queuedCount} video${queuedCount === 1 ? '' : 's'}. Watch Imports for progress.`,
        tone: 'success',
      });
      setPendingCaptureSync(null);
      await refreshDashboardData();
    } finally {
      setConfirmingCaptureSync(false);
      setSyncingSourceId(null);
    }
  };

  const handleCancelCaptureSync = async () => {
    if (pendingCaptureSync) {
      const pendingCount = pendingCaptureSync.pendingCount;
      setCaptureNotice({
        message: `Sync found ${pendingCount} video${pendingCount === 1 ? '' : 's'}. No imports queued.`,
        tone: 'info',
      });
    }
    setPendingCaptureSync(null);
    await refreshDashboardData();
  };

  const handleConfirmDisconnectSource = async () => {
    if (!pendingDisconnectSource) return;
    const source = pendingDisconnectSource;
    setDisconnectingSourceId(source.id);
    setCaptureNotice(null);
    const deleted = await deleteCaptureSource(source.id);
    setDisconnectingSourceId(null);
    if (!deleted) {
      setCaptureNotice({
        message: 'Could not disconnect that playlist. Refresh and try again.',
        tone: 'error',
      });
      return;
    }
    setPendingDisconnectSource(null);
    setCaptureNotice({
      message: 'Playlist disconnected. Saved videos remain in your library.',
      tone: 'success',
    });
    await refreshDashboardData();
  };

  const handleClearImportHistory = async () => {
    if (clearableJobs.length === 0) return;
    setClearImportsDialogOpen(false);
    setClearingImports(true);
    setImportNotice(null);
    const deletedCount = await clearIngestionJobHistory();
    await refreshDashboardData();
    setImportNotice(
      deletedCount > 0
        ? {
            message: `Cleared ${deletedCount} import${deletedCount === 1 ? '' : 's'}.`,
            tone: 'success',
          }
        : { message: 'No settled imports were cleared.', tone: 'info' },
    );
    setClearingImports(false);
  };

  const handleCreateProject = async (event: React.FormEvent) => {
    event.preventDefault();
    const trimmedName = projectName.trim();
    if (!trimmedName) return;
    setCreatingProject(true);
    setProjectNotice(null);
    try {
      const project = await createProject(trimmedName);
      if (!project) {
        setProjectNotice({ message: 'Project could not be created.', tone: 'error' });
        return;
      }
      setProjectName('');
      setProjectNotice({
        message: 'Project created. Open Library to assign videos or link a playlist.',
        tone: 'success',
      });
      await refreshDashboardData();
    } finally {
      setCreatingProject(false);
    }
  };

  return (
    <div className="min-w-0 space-y-5">
      <section className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_360px] xl:items-stretch">
        <div className="card min-w-0 p-3 sm:p-4 md:p-5 xl:h-full">
          <UnifiedSearchView
            onSearchComplete={onSearchComplete}
            onIndexComplete={onIndexComplete}
            maxSearchResults={usage?.maxSearchResults ?? 5}
          />
        </div>

        <aside className="grid min-w-0 gap-5 xl:h-full xl:grid-rows-2">
          <Panel
            title="Usage"
            className="h-full"
            description={
              dashboardLoading && !usage
                ? 'Checking usage'
                : usage
                  ? `${usage.plan} plan`
                  : 'Usage unavailable'
            }
            action={
              <button onClick={onOpenSettings} className="link-quiet text-sm">
                Limits
              </button>
            }
          >
            {dashboardLoading && !usage ? (
              <BrandLoader compact label="Checking usage" />
            ) : failures.usage ? (
              <PanelError
                label="Usage could not load."
                onRetry={() => void refreshDashboardData()}
              />
            ) : (
              <div className="space-y-2.5">
                <UsageBar
                  label="Searches this month"
                  used={usage?.searchesUsedThisMonth ?? 0}
                  limit={usage?.searchLimit ?? null}
                />
                <UsageBar
                  label="Videos indexed/accessed"
                  used={usage?.indexedVideosUsed ?? 0}
                  limit={usage?.indexedVideoLimit ?? null}
                />
                <UsageBar
                  label="Transcript hours"
                  used={secondsToHours(usage?.indexedSecondsUsed ?? 0)}
                  limit={
                    usage?.indexedSecondsLimit ? secondsToHours(usage.indexedSecondsLimit) : null
                  }
                  displayValue={
                    usage?.indexedSecondsLimit
                      ? `${secondsToHours(usage.indexedSecondsUsed).toFixed(1)}/${secondsToHours(
                          usage.indexedSecondsLimit,
                        ).toFixed(1)}h`
                      : `${secondsToHours(usage?.indexedSecondsUsed ?? 0).toFixed(1)}h/unlimited`
                  }
                />
              </div>
            )}
          </Panel>

          <Panel
            title="Library"
            className="h-full"
            description={
              dashboardLoading && !library
                ? 'Loading saved videos'
                : failures.library
                  ? 'Library unavailable'
                  : library && library.totalVideos > 0
                    ? `${library.totalVideos} saved video${library.totalVideos === 1 ? '' : 's'}`
                    : 'No indexed videos yet'
            }
            action={
              <button onClick={() => onOpenLibrary()} className="link-quiet text-sm">
                Open
              </button>
            }
          >
            {dashboardLoading && !library ? (
              <BrandLoader compact label="Loading saved videos" />
            ) : failures.library ? (
              <PanelError
                label="Your saved videos could not load."
                onRetry={() => void refreshDashboardData()}
              />
            ) : library && library.channels.length > 0 ? (
              <div className="space-y-2">
                {library.channels.slice(0, 3).map((channel) => (
                  <div key={channel.name} className="min-w-0 rounded-xl bg-cream px-3 py-2">
                    <p className="truncate text-sm font-medium text-ink">{channel.name}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm leading-6 text-bark">
                Add a video, playlist, or channel to start your saved-video library.
              </p>
            )}
          </Panel>
        </aside>
      </section>

      <section className="grid min-w-0 gap-5 xl:grid-cols-3">
        <Panel
          title="Projects"
          className="h-full"
          description={
            dashboardLoading
              ? 'Checking scopes'
              : failures.projects
                ? 'Projects unavailable'
                : projects.length > 0
                  ? `${projects.length} project${projects.length === 1 ? '' : 's'}`
                  : 'No projects yet'
          }
          action={
            <button onClick={onOpenProjects} className="link-quiet text-sm">
              Manage
            </button>
          }
        >
          {dashboardLoading ? (
            <BrandLoader compact label="Loading projects" />
          ) : failures.projects ? (
            <PanelError
              label="Your projects could not load."
              onRetry={() => void refreshDashboardData()}
            />
          ) : (
            <div className="space-y-3">
              {projects.length > 0 ? (
                <div className="space-y-2">
                  {projects.slice(0, 3).map((project) => (
                    <button
                      key={project.id}
                      type="button"
                      onClick={() => onOpenLibrary(project.id)}
                      className="min-w-0 rounded-xl bg-cream px-3 py-2 text-left transition-colors hover:bg-petal/50"
                    >
                      <p className="truncate text-sm font-semibold text-ink">{project.name}</p>
                      <p className="mt-1 text-xs text-muted">
                        {project.videoCount ?? 0} video
                        {(project.videoCount ?? 0) === 1 ? '' : 's'}
                      </p>
                    </button>
                  ))}
                </div>
              ) : null}
              <form onSubmit={(event) => void handleCreateProject(event)} className="space-y-2">
                <label className="sr-only" htmlFor="dashboard-project-name">
                  Project name
                </label>
                <input
                  id="dashboard-project-name"
                  value={projectName}
                  onChange={(event) => setProjectName(event.target.value)}
                  className="input w-full"
                  placeholder="New project"
                />
                <button
                  type="submit"
                  disabled={creatingProject || !projectName.trim()}
                  className="btn btn-secondary w-full"
                >
                  {creatingProject ? 'Creating' : 'Create new Project'}
                </button>
              </form>
              {projectNotice ? (
                <Notice tone={projectNotice.tone}>{projectNotice.message}</Notice>
              ) : null}
            </div>
          )}
        </Panel>

        <Panel
          title="Imports"
          className="h-full"
          description={
            dashboardLoading
              ? 'Checking recent imports'
              : failures.jobs
                ? 'Imports unavailable'
                : recentStatus
          }
          action={
            <div className="flex items-center gap-3">
              {clearableJobs.length > 0 ? (
                <button
                  onClick={() => setClearImportsDialogOpen(true)}
                  disabled={clearingImports}
                  className="link-quiet text-sm disabled:opacity-50"
                >
                  {clearingImports ? 'Clearing' : 'Clear'}
                </button>
              ) : null}
              <button onClick={onOpenJobs} className="link-quiet text-sm">
                View
              </button>
            </div>
          }
        >
          {dashboardLoading ? (
            <BrandLoader compact label="Loading recent imports" />
          ) : failures.jobs ? (
            <PanelError
              label="Recent imports could not load."
              onRetry={() => void refreshDashboardData()}
            />
          ) : jobs.length === 0 ? (
            <p className="text-sm leading-6 text-bark">
              URL imports and playlist syncs will appear here.
            </p>
          ) : (
            <div className="space-y-2">
              {jobs.slice(0, 2).map((job) => (
                <JobRow key={job.id} job={job} />
              ))}
            </div>
          )}
          {importNotice ? (
            <Notice tone={importNotice.tone} className="mt-3">
              {importNotice.message}
            </Notice>
          ) : null}
        </Panel>

        <Panel
          title="YouTube capture"
          className="h-full"
          description={
            dashboardLoading && !youtubeStatus
              ? 'Checking playlist connection'
              : failures.youtubeStatus
                ? 'Connection status unavailable'
                : youtubeConnected
                  ? 'Playlist sync is ready'
                  : 'Connect a save playlist'
          }
          action={
            onConnectYouTube ? (
              <button onClick={() => void onConnectYouTube()} className="link-quiet text-sm">
                {youtubeConnected ? 'Reconnect' : 'Connect'}
              </button>
            ) : null
          }
        >
          {dashboardLoading && !youtubeStatus ? (
            <BrandLoader compact label="Checking YouTube capture" />
          ) : failures.captureSources ? (
            <PanelError
              label="Capture sources could not load."
              onRetry={() => void refreshDashboardData()}
            />
          ) : (
            <CaptureSourceList
              sources={captureSources}
              syncingSourceId={syncingSourceId}
              onSyncSource={handleSyncSource}
              onDisconnectSource={setPendingDisconnectSource}
              onOpenSettings={onOpenSettings}
            />
          )}
          {captureNotice ? (
            <Notice tone={captureNotice.tone} className="mt-3">
              {captureNotice.message}
            </Notice>
          ) : null}
        </Panel>
      </section>
      {pendingCaptureSync ? (
        <CaptureSyncConfirmModal
          sourceTitle={pendingCaptureSync.source.title}
          pendingCount={pendingCaptureSync.pendingCount}
          isSubmitting={confirmingCaptureSync}
          onCancel={() => void handleCancelCaptureSync()}
          onConfirm={() => void handleConfirmCaptureSync()}
        />
      ) : null}
      {pendingDisconnectSource ? (
        <CaptureSourceDisconnectModal
          sourceTitle={pendingDisconnectSource.title}
          isSubmitting={disconnectingSourceId === pendingDisconnectSource.id}
          onCancel={() => setPendingDisconnectSource(null)}
          onConfirm={() => void handleConfirmDisconnectSource()}
        />
      ) : null}
      {clearImportsDialogOpen ? (
        <ConfirmDialog
          eyebrow="Imports"
          title="Clear import history?"
          body="Completed and failed imports will be removed from this list. Active imports stay visible."
          confirmLabel="Clear history"
          isSubmitting={clearingImports}
          submittingLabel="Clearing..."
          onCancel={() => setClearImportsDialogOpen(false)}
          onConfirm={() => void handleClearImportHistory()}
        />
      ) : null}
    </div>
  );
};

function CaptureSourceList({
  sources,
  syncingSourceId,
  onSyncSource,
  onDisconnectSource,
  onOpenSettings,
}: {
  sources: CaptureSource[];
  syncingSourceId: string | null;
  onSyncSource: (source: CaptureSource) => void;
  onDisconnectSource: (source: CaptureSource) => void;
  onOpenSettings: () => void;
}) {
  if (sources.length === 0) {
    return (
      <div className="rounded-xl bg-cream p-3">
        <p className="text-sm font-medium text-ink">No capture playlist linked.</p>
        <p className="mt-1 text-xs leading-5 text-bark">
          Add a YouTube playlist so saved videos can import automatically.
        </p>
        <button onClick={onOpenSettings} className="btn btn-secondary mt-4 w-full">
          Add capture source
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {sources.slice(0, 3).map((source) => (
        <div key={source.id} className="min-w-0 overflow-hidden rounded-xl bg-cream p-3">
          <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-ink">{source.title}</p>
              <p className="mt-1 text-xs text-muted">
                {source.status} · {source.recentItems?.length ?? 0} recent
              </p>
            </div>
            <div className="flex shrink-0 flex-wrap gap-3 sm:justify-end">
              <button
                onClick={() => onSyncSource(source)}
                disabled={syncingSourceId === source.id}
                className="text-xs font-semibold uppercase tracking-wide text-teal-deep hover:text-ink disabled:opacity-50"
              >
                {syncingSourceId === source.id ? 'Syncing' : 'Sync'}
              </button>
              <button
                onClick={() => onDisconnectSource(source)}
                className="text-xs font-semibold uppercase tracking-wide text-muted hover:text-ink"
              >
                Disconnect
              </button>
            </div>
          </div>
          {source.last_synced_at && (
            <p className="mt-2 text-xs text-muted">
              Last sync {formatRelativeTime(source.last_synced_at)}
            </p>
          )}
        </div>
      ))}
      {sources.length > 3 && (
        <button onClick={onOpenSettings} className="link-quiet text-sm">
          View all capture sources
        </button>
      )}
    </div>
  );
}

function JobRow({ job }: { job: IngestionJob }) {
  return (
    <div className="min-w-0 overflow-hidden rounded-xl bg-cream p-3">
      <div className="min-w-0">
        <div className="mb-1.5 flex items-center gap-2">
          <span className={jobStatusChipClass[job.status]}>{job.status}</span>
          <span className="text-xs font-medium uppercase tracking-wide text-muted">
            {job.source_type}
          </span>
        </div>
        <p className="truncate text-sm font-semibold text-ink">{job.source_url}</p>
        <p className="mt-1 truncate text-xs text-muted">
          {job.last_message || jobOutcomeText(job)}
        </p>
      </div>
    </div>
  );
}

function UsageBar({
  label,
  used,
  limit,
  displayValue,
}: {
  label: string;
  used: number;
  limit: number | null;
  displayValue?: string;
}) {
  const hasLimit = typeof limit === 'number' && limit > 0;
  const percent = hasLimit ? Math.min(100, Math.round((used / limit) * 100)) : 0;

  return (
    <div>
      <div
        className={`flex min-w-0 items-center justify-between gap-3 text-xs font-medium text-muted ${
          hasLimit ? 'mb-2' : ''
        }`}
      >
        <span className="min-w-0 truncate">{label}</span>
        <span className="shrink-0">
          {displayValue || (hasLimit ? `${used}/${limit}` : `${used}/unlimited`)}
        </span>
      </div>
      {hasLimit ? (
        <div
          role="progressbar"
          aria-label={label}
          aria-valuemin={0}
          aria-valuemax={limit}
          aria-valuenow={Math.min(used, limit)}
          className="h-2 overflow-hidden rounded-full bg-petal"
        >
          <div className="h-full rounded-full bg-teal" style={{ width: `${percent}%` }} />
        </div>
      ) : null}
    </div>
  );
}

function secondsToHours(seconds: number): number {
  return seconds / 3600;
}
