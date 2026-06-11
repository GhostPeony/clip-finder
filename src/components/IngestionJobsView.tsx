import React, { useEffect, useState } from 'react';
import { IngestionJob } from '../types';
import { fetchIngestionJobs } from '../services/api';

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

  useEffect(() => {
    let active = true;

    const loadJobs = async () => {
      const nextJobs = await fetchIngestionJobs();
      if (!active) return;
      setJobs(nextJobs);
      setLoading(false);
    };

    loadJobs();
    const interval = window.setInterval(loadJobs, 10000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  return (
    <div className="max-w-4xl mx-auto">
      <div className="card mb-6 p-6">
        <p className="eyebrow mb-2">Jobs</p>
        <h1 className="font-serif text-4xl font-medium text-ink">Indexing jobs</h1>
        <p className="mt-2 text-sm text-bark">Recent hosted indexing activity and import health.</p>
      </div>

      <div className="card overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-sm font-medium text-bark">Loading jobs...</div>
        ) : jobs.length === 0 ? (
          <div className="p-8 text-center">
            <h2 className="font-serif text-2xl font-medium text-ink">No indexing jobs yet</h2>
            <p className="mt-2 text-sm text-bark">
              Jobs will appear here when you index a video, playlist, or channel.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-ink/10">
            {jobs.map((job) => (
              <div key={job.id} className="bg-surface p-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 mb-1.5">
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

                  <div className="grid grid-cols-3 gap-3 text-right flex-shrink-0">
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
