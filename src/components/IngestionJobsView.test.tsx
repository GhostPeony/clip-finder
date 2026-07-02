import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { IngestionJobsView } from './IngestionJobsView';
import { clearIngestionJobHistory, fetchIngestionJobs } from '../services/api';
import { IngestionJob } from '../types';

vi.mock('../services/api', () => ({
  clearIngestionJobHistory: vi.fn(),
  fetchIngestionJobs: vi.fn(),
}));

const baseJob: IngestionJob = {
  id: 'job-1',
  user_id: 'user-1',
  source_url: 'https://www.youtube.com/watch?v=abc123',
  source_type: 'video',
  status: 'completed',
  requested_video_count: 1,
  indexed_video_count: 2,
  skipped_video_count: 0,
  failed_video_count: 0,
  created_at: '2026-06-24T06:30:55Z',
};

const makeJob = (overrides: Partial<IngestionJob>): IngestionJob => ({
  ...baseJob,
  ...overrides,
});

const setDocumentVisibility = (state: DocumentVisibilityState) => {
  Object.defineProperty(document, 'visibilityState', {
    configurable: true,
    get: () => state,
  });
};

const flushAsync = async () => {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
};

describe('IngestionJobsView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(fetchIngestionJobs).mockResolvedValue([]);
    vi.mocked(clearIngestionJobHistory).mockResolvedValue(0);
  });

  afterEach(() => {
    vi.useRealTimers();
    delete (document as { visibilityState?: DocumentVisibilityState }).visibilityState;
  });

  it('renders job rows with status chips and human outcome text', async () => {
    vi.mocked(fetchIngestionJobs).mockResolvedValue([
      makeJob({ id: 'job-1', status: 'completed', indexed_video_count: 2 }),
      makeJob({
        id: 'job-2',
        status: 'failed',
        source_type: 'playlist',
        indexed_video_count: 0,
        error: 'Transcript unavailable for one video',
      }),
      makeJob({
        id: 'job-3',
        status: 'running',
        indexed_video_count: 0,
        last_message: 'Indexing 2 of 5',
      }),
    ]);

    render(<IngestionJobsView />);

    expect(await screen.findByText('completed')).toBeInTheDocument();
    expect(screen.getAllByText('failed').length).toBeGreaterThan(0);
    expect(screen.getByText('running')).toBeInTheDocument();
    expect(screen.getByText('2 videos indexed')).toBeInTheDocument();
    expect(screen.getAllByText('Transcript unavailable for one video').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Indexing 2 of 5').length).toBeGreaterThan(0);
  });

  it('shows a retry state when the imports fetch fails', async () => {
    vi.mocked(fetchIngestionJobs)
      .mockRejectedValueOnce(new Error('Backend Error: Internal Server Error'))
      .mockResolvedValue([makeJob({ status: 'completed' })]);

    render(<IngestionJobsView />);

    expect(await screen.findByText('Imports could not load')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /^retry$/i }));

    expect(await screen.findByText('completed')).toBeInTheDocument();
    expect(screen.queryByText('Imports could not load')).not.toBeInTheDocument();
  });

  it('polls every 10s while jobs are active and visible', async () => {
    vi.useFakeTimers();
    setDocumentVisibility('visible');
    vi.mocked(fetchIngestionJobs).mockResolvedValue([makeJob({ status: 'running' })]);

    render(<IngestionJobsView />);
    await flushAsync();
    expect(fetchIngestionJobs).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });
    expect(fetchIngestionJobs).toHaveBeenCalledTimes(2);
  });

  it('does not poll when every job has settled', async () => {
    vi.useFakeTimers();
    setDocumentVisibility('visible');
    vi.mocked(fetchIngestionJobs).mockResolvedValue([makeJob({ status: 'completed' })]);

    render(<IngestionJobsView />);
    await flushAsync();
    expect(fetchIngestionJobs).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30000);
    });
    expect(fetchIngestionJobs).toHaveBeenCalledTimes(1);
  });

  it('does not poll while the tab is hidden even with active jobs', async () => {
    vi.useFakeTimers();
    setDocumentVisibility('hidden');
    vi.mocked(fetchIngestionJobs).mockResolvedValue([makeJob({ status: 'queued' })]);

    render(<IngestionJobsView />);
    await flushAsync();
    expect(fetchIngestionJobs).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30000);
    });
    expect(fetchIngestionJobs).toHaveBeenCalledTimes(1);
  });

  it('clears history through an app dialog instead of window.confirm', async () => {
    vi.mocked(fetchIngestionJobs).mockResolvedValue([makeJob({ status: 'completed' })]);
    vi.mocked(clearIngestionJobHistory).mockResolvedValue(2);
    const confirmSpy = vi.spyOn(window, 'confirm');

    render(<IngestionJobsView />);

    fireEvent.click(await screen.findByRole('button', { name: /^clear history$/i }));
    const dialog = await screen.findByRole('dialog', { name: /clear import history/i });
    fireEvent.click(within(dialog).getByRole('button', { name: /^clear history$/i }));

    await waitFor(() => {
      expect(clearIngestionJobHistory).toHaveBeenCalledTimes(1);
    });
    expect(confirmSpy).not.toHaveBeenCalled();
    expect(await screen.findByText(/Cleared 2 imports\./i)).toBeInTheDocument();
  });
});
