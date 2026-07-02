import { IngestionJob } from '../types';

/** Shared status-chip classes for ingestion job rows across dashboard, imports, and library. */
export const jobStatusChipClass: Record<IngestionJob['status'], string> = {
  queued: 'chip chip-violet',
  running: 'chip chip-teal',
  completed: 'chip chip-leaf',
  partial: 'chip chip-sun',
  failed: 'chip',
  cancelled: 'chip chip-violet',
};

/** Statuses that can be removed by "clear history" actions. Active jobs stay visible. */
export const CLEARABLE_JOB_STATUSES: ReadonlyArray<IngestionJob['status']> = [
  'completed',
  'failed',
  'partial',
  'cancelled',
];

export const isActiveJob = (job: IngestionJob): boolean =>
  job.status === 'queued' || job.status === 'running';

export const isClearableJob = (job: IngestionJob): boolean =>
  CLEARABLE_JOB_STATUSES.includes(job.status);

/** One-line human outcome for an ingestion job (distinguishes running vs queued). */
export const jobOutcomeText = (job: IngestionJob): string => {
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
