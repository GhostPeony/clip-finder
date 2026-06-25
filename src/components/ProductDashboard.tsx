import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { CaptureSource, IngestionJob, LibraryData, VideoClip, YoutubeOAuthStatus } from '../types';
import {
  clearIngestionJobHistory,
  fetchCaptureSources,
  fetchIngestionJobs,
  fetchLibrary,
  fetchUsage,
  fetchYoutubeOAuthStatus,
  syncCaptureSource,
  UsageInfo,
} from '../services/api';
import { YOUTUBE_CONNECTION_SAVED_EVENT } from '../contexts/AuthContext';
import { BrandLoader } from './BrandLoader';
import { CaptureSyncConfirmModal } from './CaptureSyncConfirmModal';
import { UnifiedSearchView } from './UnifiedSearchView';

interface ProductDashboardProps {
  onOpenSettings: () => void;
  onOpenLibrary: () => void;
  onOpenJobs: () => void;
  onConnectYouTube?: () => void | Promise<unknown>;
  onSearchComplete: (clips: VideoClip[], answer: string, activeClip: VideoClip | null) => void;
  onIndexComplete: () => void;
}

interface DashboardBundle {
  library: LibraryData;
  libraryLoadFailed: boolean;
  usage: UsageInfo | null;
  jobs: IngestionJob[];
  captureSources: CaptureSource[];
  youtubeStatus: YoutubeOAuthStatus;
}

interface PendingCaptureSync {
  source: CaptureSource;
  pendingCount: number;
}

const loadDashboardBundle = async (): Promise<DashboardBundle> => {
  const [libraryResult, usage, jobs, captureSources, youtubeStatus] = await Promise.all([
    fetchLibrary().then(
      (library) => ({ library, failed: false }),
      () => ({
        library: { channels: [], totalVideos: 0, totalClips: 0 },
        failed: true,
      }),
    ),
    fetchUsage(),
    fetchIngestionJobs(),
    fetchCaptureSources(),
    fetchYoutubeOAuthStatus(),
  ]);

  return {
    library: libraryResult.library,
    libraryLoadFailed: libraryResult.failed,
    usage,
    jobs,
    captureSources,
    youtubeStatus,
  };
};

export const ProductDashboard: React.FC<ProductDashboardProps> = ({
  onOpenSettings,
  onOpenLibrary,
  onOpenJobs,
  onConnectYouTube,
  onSearchComplete,
  onIndexComplete,
}) => {
  const [library, setLibrary] = useState<LibraryData | null>(null);
  const [usage, setUsage] = useState<UsageInfo | null>(null);
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [captureSources, setCaptureSources] = useState<CaptureSource[]>([]);
  const [youtubeStatus, setYoutubeStatus] = useState<YoutubeOAuthStatus | null>(null);
  const [syncingSourceId, setSyncingSourceId] = useState<string | null>(null);
  const [pendingCaptureSync, setPendingCaptureSync] = useState<PendingCaptureSync | null>(null);
  const [confirmingCaptureSync, setConfirmingCaptureSync] = useState(false);
  const [captureNotice, setCaptureNotice] = useState('');
  const [importNotice, setImportNotice] = useState('');
  const [clearingImports, setClearingImports] = useState(false);
  const [libraryLoadFailed, setLibraryLoadFailed] = useState(false);
  const [dashboardLoading, setDashboardLoading] = useState(true);

  const applyDashboardBundle = useCallback((bundle: DashboardBundle) => {
    setLibrary(bundle.library);
    setLibraryLoadFailed(bundle.libraryLoadFailed);
    setUsage(bundle.usage);
    setJobs(bundle.jobs.slice(0, 6));
    setCaptureSources(bundle.captureSources);
    setYoutubeStatus(bundle.youtubeStatus);
  }, []);

  const refreshDashboardData = useCallback(async () => {
    const bundle = await loadDashboardBundle();
    applyDashboardBundle(bundle);
  }, [applyDashboardBundle]);

  useEffect(() => {
    let active = true;

    const load = async () => {
      const bundle = await loadDashboardBundle();
      if (!active) return;
      applyDashboardBundle(bundle);
      setDashboardLoading(false);
    };

    load();
    const interval = window.setInterval(load, 15000);
    const onYoutubeConnected = () => {
      void load();
    };
    window.addEventListener(YOUTUBE_CONNECTION_SAVED_EVENT, onYoutubeConnected);

    return () => {
      active = false;
      window.clearInterval(interval);
      window.removeEventListener(YOUTUBE_CONNECTION_SAVED_EVENT, onYoutubeConnected);
    };
  }, [applyDashboardBundle]);

  const activeJobs = useMemo(
    () => jobs.filter((job) => job.status === 'queued' || job.status === 'running'),
    [jobs],
  );

  const failedJobs = useMemo(() => jobs.filter((job) => job.status === 'failed'), [jobs]);
  const clearableJobs = useMemo(
    () =>
      jobs.filter((job) => ['completed', 'failed', 'partial', 'cancelled'].includes(job.status)),
    [jobs],
  );

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
    setCaptureNotice('');
    try {
      const preview = await syncCaptureSource(source.id, 0);
      if (!preview) {
        setCaptureNotice('Sync did not start. Check the capture source and try again.');
        return;
      }

      const pendingCount = preview.queueCandidateCount ?? preview.newItemCount;
      if (pendingCount <= 0) {
        setCaptureNotice('Sync is up to date. No new videos are waiting to import.');
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
    setCaptureNotice('');
    try {
      const result = await syncCaptureSource(source.id, pendingCount);
      if (!result) {
        setCaptureNotice(
          'Sync failed before all imports could be queued. Check Imports for any queued job and retry.',
        );
        return;
      }

      const queuedCount = result.queuedJobCount;
      const remainingCount = result.remainingQueueCount ?? Math.max(0, pendingCount - queuedCount);
      setCaptureNotice(
        remainingCount > 0
          ? `Queued ${queuedCount} of ${pendingCount} video${pendingCount === 1 ? '' : 's'}. ${remainingCount} still waiting to queue.`
          : `Queued ${queuedCount} video${queuedCount === 1 ? '' : 's'}. Watch Imports for progress.`,
      );
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
      setCaptureNotice(
        `Sync found ${pendingCount} video${pendingCount === 1 ? '' : 's'}. No imports queued.`,
      );
    }
    setPendingCaptureSync(null);
    await refreshDashboardData();
  };

  const handleClearImportHistory = async () => {
    if (clearableJobs.length === 0) return;
    if (!confirm('Clear completed and failed import history? Active imports will stay visible.')) {
      return;
    }

    setClearingImports(true);
    setImportNotice('');
    const deletedCount = await clearIngestionJobHistory();
    await refreshDashboardData();
    setImportNotice(
      deletedCount > 0
        ? `Cleared ${deletedCount} import${deletedCount === 1 ? '' : 's'}.`
        : 'No settled imports were cleared.',
    );
    setClearingImports(false);
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
          <DashboardPanel
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
          </DashboardPanel>

          <DashboardPanel
            title="Library"
            className="h-full"
            description={
              dashboardLoading && !library
                ? 'Loading saved videos'
                : libraryLoadFailed
                  ? 'Library unavailable'
                  : library && library.totalVideos > 0
                    ? `${library.totalVideos} saved video${library.totalVideos === 1 ? '' : 's'}`
                    : 'No indexed videos yet'
            }
            action={
              <button onClick={onOpenLibrary} className="link-quiet text-sm">
                Open
              </button>
            }
          >
            {dashboardLoading && !library ? (
              <BrandLoader compact label="Loading saved videos" />
            ) : libraryLoadFailed ? (
              <p className="text-sm leading-6 text-bark">
                Open Library to retry loading your videos.
              </p>
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
          </DashboardPanel>
        </aside>
      </section>

      <section className="grid min-w-0 gap-5 xl:grid-cols-2">
        <DashboardPanel
          title="Imports"
          className="h-full"
          description={dashboardLoading ? 'Checking recent imports' : recentStatus}
          action={
            <div className="flex items-center gap-3">
              {clearableJobs.length > 0 ? (
                <button
                  onClick={() => void handleClearImportHistory()}
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
          {importNotice && (
            <p className="mt-3 rounded-lg bg-mint/40 px-3 py-2 text-xs font-medium text-leaf-deep">
              {importNotice}
            </p>
          )}
        </DashboardPanel>

        <DashboardPanel
          title="YouTube capture"
          className="h-full"
          description={
            dashboardLoading && !youtubeStatus
              ? 'Checking playlist connection'
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
          ) : (
            <CaptureSourceList
              sources={captureSources}
              syncingSourceId={syncingSourceId}
              onSyncSource={handleSyncSource}
              onOpenSettings={onOpenSettings}
            />
          )}
          {captureNotice && (
            <p className="mt-3 rounded-lg bg-mint/40 px-3 py-2 text-xs font-medium text-leaf-deep">
              {captureNotice}
            </p>
          )}
        </DashboardPanel>
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
    </div>
  );
};

function CaptureSourceList({
  sources,
  syncingSourceId,
  onSyncSource,
  onOpenSettings,
}: {
  sources: CaptureSource[];
  syncingSourceId: string | null;
  onSyncSource: (source: CaptureSource) => void;
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
          <div className="flex min-w-0 items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-ink">{source.title}</p>
              <p className="mt-1 text-xs text-muted">
                {source.status} · {source.recentItems?.length ?? 0} recent
              </p>
            </div>
            <button
              onClick={() => onSyncSource(source)}
              disabled={syncingSourceId === source.id}
              className="shrink-0 text-xs font-semibold uppercase tracking-wide text-teal-deep hover:text-ink disabled:opacity-50"
            >
              {syncingSourceId === source.id ? 'Syncing' : 'Sync'}
            </button>
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
          <span className={statusClass[job.status]}>{job.status}</span>
          <span className="text-xs font-medium uppercase tracking-wide text-muted">
            {job.source_type}
          </span>
        </div>
        <p className="truncate text-sm font-semibold text-ink">{job.source_url}</p>
        <p className="mt-1 truncate text-xs text-muted">
          {job.last_message || getOutcomeText(job)}
        </p>
      </div>
    </div>
  );
}

function DashboardPanel({
  title,
  description,
  action,
  className = '',
  children,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section className={`card min-w-0 overflow-hidden p-4 ${className}`}>
      <div className="mb-3 flex min-w-0 items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-serif text-xl font-medium text-ink">{title}</h2>
          {description && <p className="mt-1 text-xs font-medium text-muted">{description}</p>}
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      {children}
    </section>
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
  const percent = limit && limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 12;

  return (
    <div>
      <div className="mb-2 flex min-w-0 items-center justify-between gap-3 text-xs font-medium text-muted">
        <span className="min-w-0 truncate">{label}</span>
        <span className="shrink-0">
          {displayValue || (limit ? `${used}/${limit}` : `${used}/unlimited`)}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-petal">
        <div className="h-full rounded-full bg-teal" style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

const statusClass: Record<IngestionJob['status'], string> = {
  queued: 'chip chip-violet',
  running: 'chip chip-teal',
  completed: 'chip chip-leaf',
  partial: 'chip chip-sun',
  failed: 'chip',
  cancelled: 'chip chip-violet',
};

const getOutcomeText = (job: IngestionJob) => {
  if (job.status === 'partial') {
    return `Partial import: ${job.indexed_video_count} indexed, ${job.skipped_video_count} skipped, ${job.failed_video_count} failed`;
  }
  if (job.status === 'failed') {
    return job.error || job.last_message || 'Import failed';
  }
  if (job.status === 'completed') {
    return `${job.indexed_video_count} video${job.indexed_video_count === 1 ? '' : 's'} indexed`;
  }
  if (job.status === 'running') {
    return job.last_message || 'Import running';
  }
  return job.last_message || 'Waiting to start';
};

function formatRelativeTime(value: string): string {
  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return value;
  const diff = Date.now() - timestamp;
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;
  return new Date(timestamp).toLocaleDateString();
}

function secondsToHours(seconds: number): number {
  return seconds / 3600;
}
