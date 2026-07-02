import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { clearIngestionJobHistory, fetchIngestionJobs } from '../services/api';
import { isActiveJob, isClearableJob, jobOutcomeText, jobStatusChipClass } from '../lib/jobs';
import { formatDateTimeLabel } from '../lib/time';
import { usePolling } from '../lib/usePolling';
import { IngestionJob } from '../types';
import { BrandLoader } from './BrandLoader';
import { ConfirmDialog } from './ui/ConfirmDialog';
import { Notice, NoticeState } from './ui/Notice';

export const IngestionJobsView: React.FC = () => {
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [clearDialogOpen, setClearDialogOpen] = useState(false);
  const [notice, setNotice] = useState<NoticeState | null>(null);

  const clearableJobs = useMemo(() => jobs.filter(isClearableJob), [jobs]);
  const hasActiveJobs = useMemo(() => jobs.some(isActiveJob), [jobs]);

  const loadJobs = useCallback(async () => {
    try {
      const nextJobs = await fetchIngestionJobs();
      setJobs(nextJobs);
      setLoadFailed(false);
    } catch {
      setLoadFailed(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadJobs();
  }, [loadJobs]);

  // Refresh only while imports are actually running and the tab is visible.
  usePolling(loadJobs, 10000, { enabled: hasActiveJobs });

  const handleClearHistory = async () => {
    if (clearableJobs.length === 0) return;
    setClearDialogOpen(false);
    setClearing(true);
    setNotice(null);
    const deletedCount = await clearIngestionJobHistory();
    await loadJobs();
    setNotice(
      deletedCount > 0
        ? {
            message: `Cleared ${deletedCount} import${deletedCount === 1 ? '' : 's'}.`,
            tone: 'success',
          }
        : { message: 'No settled imports were cleared.', tone: 'info' },
    );
    setClearing(false);
  };

  return (
    <div className="mx-auto max-w-4xl min-w-0">
      <div className="card mb-6 p-5 sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="font-serif text-4xl font-medium text-ink">Imports</h1>
            <p className="mt-2 text-sm text-bark">Recent URL imports and playlist syncs.</p>
          </div>
          {clearableJobs.length > 0 ? (
            <button
              type="button"
              onClick={() => setClearDialogOpen(true)}
              disabled={clearing}
              className="btn btn-secondary self-start sm:self-auto disabled:opacity-50"
            >
              {clearing ? 'Clearing...' : 'Clear history'}
            </button>
          ) : null}
        </div>
        {notice ? (
          <Notice tone={notice.tone} className="mt-4">
            {notice.message}
          </Notice>
        ) : null}
      </div>

      <div className="card min-w-0 overflow-hidden">
        {loading ? (
          <BrandLoader
            label="Loading recent imports"
            detail="Checking playlist syncs and video indexing runs."
          />
        ) : loadFailed ? (
          <div className="p-8 text-center">
            <h2 className="font-serif text-2xl font-medium text-ink">Imports could not load</h2>
            <p className="mt-2 text-sm text-bark">
              Your imports may still be running; retry in a moment.
            </p>
            <button type="button" onClick={() => void loadJobs()} className="btn btn-primary mt-5">
              Retry
            </button>
          </div>
        ) : jobs.length === 0 ? (
          <div className="p-8 text-center">
            <h2 className="font-serif text-2xl font-medium text-ink">No indexing jobs yet</h2>
            <p className="mt-2 text-sm text-bark">
              Imports will appear here when you add a video, playlist, channel, or capture source.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-ink/10">
            {jobs.map((job) => (
              <div key={job.id} className="bg-surface p-4 sm:p-5">
                <div className="flex min-w-0 flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="mb-1.5 flex min-w-0 flex-wrap items-center gap-2">
                      <span className={jobStatusChipClass[job.status]}>{job.status}</span>
                      <span className="text-xs font-medium uppercase tracking-wide text-muted">
                        {job.source_type}
                      </span>
                      <span className="text-xs text-muted">
                        {formatDateTimeLabel(job.created_at)}
                      </span>
                    </div>
                    <p className="truncate text-sm font-semibold text-ink">{job.source_url}</p>
                    <p
                      className={`mt-1 truncate text-xs font-medium ${
                        job.status === 'failed'
                          ? 'text-rose-deep'
                          : job.status === 'partial'
                            ? 'text-bark'
                            : 'text-muted'
                      }`}
                    >
                      {jobOutcomeText(job)}
                    </p>
                    {job.last_message && (
                      <p className="mt-1 truncate text-xs text-muted">{job.last_message}</p>
                    )}
                    {job.error && (
                      <p className="mt-1 truncate text-xs font-medium text-rose-deep">
                        {job.error}
                      </p>
                    )}
                  </div>

                  <div className="grid w-full flex-shrink-0 grid-cols-3 gap-2 rounded-xl bg-cream p-3 text-left sm:w-auto sm:gap-3 sm:bg-transparent sm:p-0 sm:text-right">
                    <div>
                      <p className="font-mono text-sm font-medium text-ink">
                        {job.indexed_video_count}
                      </p>
                      <p className="text-xs text-muted">indexed</p>
                    </div>
                    <div>
                      <p className="font-mono text-sm font-medium text-ink">
                        {job.skipped_video_count}
                      </p>
                      <p className="text-xs text-muted">skipped</p>
                    </div>
                    <div>
                      <p className="font-mono text-sm font-medium text-ink">
                        {job.failed_video_count}
                      </p>
                      <p className="text-xs text-muted">failed</p>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      {clearDialogOpen ? (
        <ConfirmDialog
          eyebrow="Imports"
          title="Clear import history?"
          body="Completed and failed imports will be removed from this list. Active imports stay visible."
          confirmLabel="Clear history"
          isSubmitting={clearing}
          submittingLabel="Clearing..."
          onCancel={() => setClearDialogOpen(false)}
          onConfirm={() => void handleClearHistory()}
        />
      ) : null}
    </div>
  );
};
