import React, { useEffect, useMemo, useState } from 'react';
import { IngestionJob } from '../types';
import { clearIngestionJobHistory, fetchIngestionJobs } from '../services/api';
import { BrandLoader } from './BrandLoader';

const statusClass: Record<IngestionJob['status'], string> = {
  queued: 'chip chip-violet',
  running: 'chip chip-teal',
  completed: 'chip chip-leaf',
  partial: 'chip chip-sun',
  failed: 'chip',
  cancelled: 'chip chip-violet',
};

const formatDate = (value?: string) => {
  if (!value) return '';
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(value));
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

export const IngestionJobsView: React.FC = () => {
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [clearing, setClearing] = useState(false);
  const [notice, setNotice] = useState('');

  const clearableJobs = useMemo(
    () =>
      jobs.filter((job) => ['completed', 'failed', 'partial', 'cancelled'].includes(job.status)),
    [jobs],
  );

  const loadJobs = async () => {
    const nextJobs = await fetchIngestionJobs();
    setJobs(nextJobs);
    setLoading(false);
  };

  useEffect(() => {
    let active = true;

    const loadActiveJobs = async () => {
      const nextJobs = await fetchIngestionJobs();
      if (!active) return;
      setJobs(nextJobs);
      setLoading(false);
    };

    loadActiveJobs();
    const interval = window.setInterval(loadActiveJobs, 10000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  const handleClearHistory = async () => {
    if (clearableJobs.length === 0) return;
    if (!confirm('Clear completed and failed import history? Active imports will stay visible.')) {
      return;
    }

    setClearing(true);
    setNotice('');
    const deletedCount = await clearIngestionJobHistory();
    await loadJobs();
    setNotice(
      deletedCount > 0
        ? `Cleared ${deletedCount} import${deletedCount === 1 ? '' : 's'}.`
        : 'No settled imports were cleared.',
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
              onClick={() => void handleClearHistory()}
              disabled={clearing}
              className="btn btn-secondary self-start sm:self-auto disabled:opacity-50"
            >
              {clearing ? 'Clearing...' : 'Clear history'}
            </button>
          ) : null}
        </div>
        {notice ? (
          <p className="mt-4 rounded-lg bg-mint/40 px-3 py-2 text-xs font-medium text-leaf-deep">
            {notice}
          </p>
        ) : null}
      </div>

      <div className="card min-w-0 overflow-hidden">
        {loading ? (
          <BrandLoader
            label="Loading recent imports"
            detail="Checking playlist syncs and video indexing runs."
          />
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
                      <span className={statusClass[job.status]}>{job.status}</span>
                      <span className="text-xs font-medium uppercase tracking-wide text-muted">
                        {job.source_type}
                      </span>
                      <span className="text-xs text-muted">{formatDate(job.created_at)}</span>
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
                      {getOutcomeText(job)}
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
    </div>
  );
};
