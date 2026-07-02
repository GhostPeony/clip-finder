import React from 'react';
import { IngestionJob } from '../../types';
import { jobOutcomeText, jobStatusChipClass } from '../../lib/jobs';

export function LibraryImportRow({ job }: { job: IngestionJob }) {
  return (
    <div className="rounded-xl bg-cream px-3 py-2 text-left">
      <div className="flex flex-wrap items-center gap-2">
        <span className={jobStatusChipClass[job.status]}>{job.status}</span>
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
        {jobOutcomeText(job)}
      </p>
    </div>
  );
}
