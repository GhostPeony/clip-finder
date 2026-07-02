import { describe, expect, it } from 'vitest';
import { IngestionJob } from '../types';
import {
  CLEARABLE_JOB_STATUSES,
  isActiveJob,
  isClearableJob,
  jobOutcomeText,
  jobStatusChipClass,
} from './jobs';

const baseJob: IngestionJob = {
  id: 'job-1',
  user_id: 'user-1',
  source_url: 'https://www.youtube.com/watch?v=abc123',
  source_type: 'video',
  status: 'queued',
  requested_video_count: 1,
  indexed_video_count: 0,
  skipped_video_count: 0,
  failed_video_count: 0,
  created_at: '2026-06-24T06:30:55Z',
};

describe('jobStatusChipClass', () => {
  it('maps every job status to a chip class', () => {
    expect(jobStatusChipClass).toEqual({
      queued: 'chip chip-violet',
      running: 'chip chip-teal',
      completed: 'chip chip-leaf',
      partial: 'chip chip-sun',
      failed: 'chip',
      cancelled: 'chip chip-violet',
    });
  });
});

describe('isActiveJob / isClearableJob', () => {
  it('treats queued and running jobs as active', () => {
    expect(isActiveJob({ ...baseJob, status: 'queued' })).toBe(true);
    expect(isActiveJob({ ...baseJob, status: 'running' })).toBe(true);
    expect(isActiveJob({ ...baseJob, status: 'completed' })).toBe(false);
    expect(isActiveJob({ ...baseJob, status: 'failed' })).toBe(false);
  });

  it('marks settled statuses as clearable and active ones as not', () => {
    for (const status of CLEARABLE_JOB_STATUSES) {
      expect(isClearableJob({ ...baseJob, status })).toBe(true);
    }
    expect(isClearableJob({ ...baseJob, status: 'queued' })).toBe(false);
    expect(isClearableJob({ ...baseJob, status: 'running' })).toBe(false);
  });
});

describe('jobOutcomeText', () => {
  it('summarizes partial imports with counts', () => {
    expect(
      jobOutcomeText({
        ...baseJob,
        status: 'partial',
        indexed_video_count: 3,
        skipped_video_count: 1,
        failed_video_count: 2,
      }),
    ).toBe('Partial import: 3 indexed, 1 skipped, 2 failed');
  });

  it('prefers the error text for failed imports', () => {
    expect(
      jobOutcomeText({
        ...baseJob,
        status: 'failed',
        error: 'Source channel could not be prepared.',
        last_message: 'Some internal message',
      }),
    ).toBe('Source channel could not be prepared.');
    expect(jobOutcomeText({ ...baseJob, status: 'failed' })).toBe('Import failed');
  });

  it('pluralizes completed video counts', () => {
    expect(jobOutcomeText({ ...baseJob, status: 'completed', indexed_video_count: 1 })).toBe(
      '1 video indexed',
    );
    expect(jobOutcomeText({ ...baseJob, status: 'completed', indexed_video_count: 4 })).toBe(
      '4 videos indexed',
    );
  });

  it('distinguishes running from queued jobs', () => {
    expect(jobOutcomeText({ ...baseJob, status: 'running' })).toBe('Import running');
    expect(jobOutcomeText({ ...baseJob, status: 'queued' })).toBe('Waiting to start');
    expect(jobOutcomeText({ ...baseJob, status: 'running', last_message: 'Indexing 2 of 5' })).toBe(
      'Indexing 2 of 5',
    );
  });
});
