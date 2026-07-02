import { act, render, screen, waitFor } from '@testing-library/react';
import { fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ProductDashboard } from './ProductDashboard';
import {
  clearIngestionJobHistory,
  createProject,
  deleteCaptureSource,
  fetchCaptureSources,
  fetchIngestionJobs,
  fetchProjects,
  syncCaptureSource,
} from '../services/api';
import { CaptureSource, IngestionJob } from '../types';

vi.mock('./UnifiedSearchView', () => ({
  UnifiedSearchView: () => <div data-testid="workbench" />,
}));

const apiMocks = vi.hoisted(() => ({
  clearIngestionJobHistory: vi.fn(async () => 0),
  createProject: vi.fn(async () => null),
  deleteCaptureSource: vi.fn(async () => false),
  fetchCaptureSources: vi.fn(async () => []),
  fetchIngestionJobs: vi.fn(async () => []),
  fetchLibrary: vi.fn(async () => ({ channels: [], totalVideos: 0, totalClips: 0 })),
  fetchProjects: vi.fn(async () => []),
  fetchUsage: vi.fn(async () => ({
    plan: 'free',
    searchesUsedToday: 4,
    searchesUsedThisMonth: 4,
    searchLimit: 100,
    searchPeriod: 'month',
    indexesUsedThisMonth: 2,
    indexLimit: 15,
    indexedVideosUsed: 2,
    indexedVideoLimit: 15,
    indexedSecondsUsed: 7200,
    indexedSecondsLimit: 18000,
    maxImportVideos: 10,
    maxSearchResults: 5,
    hasOwnKey: false,
    apiKeyMode: 'hybrid',
    hasServerKey: true,
    allowUserKeys: true,
  })),
  fetchYoutubeOAuthStatus: vi.fn(async () => ({
    connected: false,
    needsReconnect: false,
    youtubeReadonlyGranted: false,
    hasRefreshToken: false,
    scopes: [],
    expiresAt: null,
    connectedAt: null,
    updatedAt: null,
    lastError: null,
  })),
  syncCaptureSource: vi.fn(async () => null),
}));

vi.mock('../services/api', () => ({
  clearIngestionJobHistory: apiMocks.clearIngestionJobHistory,
  createProject: apiMocks.createProject,
  deleteCaptureSource: apiMocks.deleteCaptureSource,
  fetchCaptureSources: apiMocks.fetchCaptureSources,
  fetchIngestionJobs: apiMocks.fetchIngestionJobs,
  fetchLibrary: apiMocks.fetchLibrary,
  fetchProjects: apiMocks.fetchProjects,
  fetchUsage: apiMocks.fetchUsage,
  fetchYoutubeOAuthStatus: apiMocks.fetchYoutubeOAuthStatus,
  syncCaptureSource: apiMocks.syncCaptureSource,
}));

const dashboardProps = {
  onOpenSettings: () => undefined,
  onOpenLibrary: () => undefined,
  onOpenProjects: () => undefined,
  onOpenJobs: () => undefined,
  onSearchComplete: () => undefined,
  onIndexComplete: () => undefined,
};

const completedJob: IngestionJob = {
  id: 'job-1',
  user_id: 'user-1',
  source_url: 'https://www.youtube.com/watch?v=abc123',
  source_type: 'video',
  status: 'completed',
  requested_video_count: 1,
  indexed_video_count: 1,
  skipped_video_count: 0,
  failed_video_count: 0,
  created_at: '2026-06-24T06:30:55Z',
};

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

describe('ProductDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
    delete (document as { visibilityState?: DocumentVisibilityState }).visibilityState;
  });

  it('renders the free-tier usage labels', async () => {
    render(<ProductDashboard {...dashboardProps} />);

    await waitFor(() => {
      expect(screen.getByText('Searches this month')).toBeInTheDocument();
    });

    expect(screen.getByText('Videos indexed/accessed')).toBeInTheDocument();
    expect(screen.getByText('Transcript hours')).toBeInTheDocument();
  });

  it('exposes limited usage meters as progressbars with values', async () => {
    render(<ProductDashboard {...dashboardProps} />);

    const searchBar = await screen.findByRole('progressbar', { name: 'Searches this month' });
    expect(searchBar).toHaveAttribute('aria-valuenow', '4');
    expect(searchBar).toHaveAttribute('aria-valuemax', '100');
    expect(screen.getAllByRole('progressbar')).toHaveLength(3);
  });

  it('omits progressbars and fake fills for unlimited plans', async () => {
    apiMocks.fetchUsage.mockResolvedValue({
      plan: 'pro',
      searchesUsedToday: 4,
      searchesUsedThisMonth: 4,
      searchLimit: null,
      searchPeriod: 'month',
      indexesUsedThisMonth: 2,
      indexLimit: null,
      indexedVideosUsed: 2,
      indexedVideoLimit: null,
      indexedSecondsUsed: 7200,
      indexedSecondsLimit: null,
      maxImportVideos: 10,
      maxSearchResults: 5,
      hasOwnKey: false,
      apiKeyMode: 'hybrid',
      hasServerKey: true,
      allowUserKeys: true,
    });

    render(<ProductDashboard {...dashboardProps} />);

    expect(await screen.findByText('4/unlimited')).toBeInTheDocument();
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });

  it('confirms playlist sync with an in-app modal before queueing all videos', async () => {
    const captureSource: CaptureSource = {
      id: 'capture-1',
      source_type: 'playlist',
      source_url: 'https://www.youtube.com/playlist?list=PLabcdef123456',
      external_id: 'PLabcdef123456',
      title: 'Research inbox',
      status: 'active',
      recentItems: [],
    };
    vi.mocked(fetchCaptureSources).mockResolvedValue([captureSource]);
    vi.mocked(syncCaptureSource)
      .mockResolvedValueOnce({
        captureSource,
        discoveredCount: 2,
        newItemCount: 2,
        queueCandidateCount: 2,
        queuedJobCount: 0,
        requestedJobCount: 0,
        remainingQueueCount: 2,
        skippedExistingCount: 0,
        activeJobLimitReached: false,
      })
      .mockResolvedValueOnce({
        captureSource,
        discoveredCount: 2,
        newItemCount: 0,
        queueCandidateCount: 2,
        queuedJobCount: 2,
        requestedJobCount: 2,
        remainingQueueCount: 0,
        skippedExistingCount: 2,
        activeJobLimitReached: false,
      });
    const confirmSpy = vi.spyOn(window, 'confirm');

    render(<ProductDashboard {...dashboardProps} />);

    fireEvent.click(await screen.findByRole('button', { name: /^sync$/i }));
    expect(await screen.findByRole('dialog', { name: /import 2 videos/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /queue 2 videos/i }));

    await waitFor(() => {
      expect(syncCaptureSource).toHaveBeenNthCalledWith(1, 'capture-1', 0);
      expect(syncCaptureSource).toHaveBeenNthCalledWith(2, 'capture-1', 2);
    });
    expect(confirmSpy).not.toHaveBeenCalled();
    expect(await screen.findByText(/Watch Imports for progress/i)).toBeInTheDocument();
  });

  it('creates a project from the dashboard panel', async () => {
    vi.mocked(createProject).mockResolvedValue({
      id: 'project-1',
      name: 'Agent harness research',
      slug: 'agent-harness-research',
      videoCount: 0,
    });
    vi.mocked(fetchProjects).mockResolvedValue([]);

    render(<ProductDashboard {...dashboardProps} />);

    const input = await screen.findByLabelText('Project name');
    fireEvent.change(input, { target: { value: 'Agent harness research' } });
    fireEvent.click(screen.getByRole('button', { name: /create new project/i }));

    await waitFor(() => {
      expect(createProject).toHaveBeenCalledWith('Agent harness research');
    });
    expect(await screen.findByText(/Project created/i)).toBeInTheDocument();
  });

  it('opens the library scoped to a selected project', async () => {
    const onOpenLibrary = vi.fn();
    vi.mocked(fetchProjects).mockResolvedValue([
      {
        id: 'project-1',
        name: 'Agent harness research',
        slug: 'agent-harness-research',
        videoCount: 3,
      },
    ]);

    render(<ProductDashboard {...dashboardProps} onOpenLibrary={onOpenLibrary} />);

    fireEvent.click(await screen.findByRole('button', { name: /Agent harness research/i }));

    expect(onOpenLibrary).toHaveBeenCalledWith('project-1');
  });

  it('opens the dedicated projects view from the dashboard projects panel', async () => {
    const onOpenProjects = vi.fn();
    vi.mocked(fetchProjects).mockResolvedValue([
      {
        id: 'project-1',
        name: 'Agent harness research',
        slug: 'agent-harness-research',
        videoCount: 3,
      },
    ]);

    render(<ProductDashboard {...dashboardProps} onOpenProjects={onOpenProjects} />);

    fireEvent.click(await screen.findByRole('button', { name: /^manage$/i }));

    expect(onOpenProjects).toHaveBeenCalledTimes(1);
  });

  it('disconnects one capture source from the dashboard with an app modal', async () => {
    const captureSource: CaptureSource = {
      id: 'capture-1',
      source_type: 'playlist',
      source_url: 'https://www.youtube.com/playlist?list=PLabcdef123456',
      external_id: 'PLabcdef123456',
      title: 'Research inbox',
      status: 'active',
      recentItems: [],
    };
    vi.mocked(fetchCaptureSources).mockResolvedValue([captureSource]);
    vi.mocked(deleteCaptureSource).mockResolvedValue(true);
    const confirmSpy = vi.spyOn(window, 'confirm');

    render(<ProductDashboard {...dashboardProps} />);

    fireEvent.click(await screen.findByRole('button', { name: /^disconnect$/i }));
    expect(
      await screen.findByRole('dialog', { name: /disconnect this playlist/i }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /^disconnect playlist$/i }));

    await waitFor(() => {
      expect(deleteCaptureSource).toHaveBeenCalledWith('capture-1');
    });
    expect(confirmSpy).not.toHaveBeenCalled();
    expect(await screen.findByText(/Playlist disconnected/i)).toBeInTheDocument();
  });

  it('clears import history through an app dialog instead of window.confirm', async () => {
    vi.mocked(fetchIngestionJobs).mockResolvedValue([completedJob]);
    vi.mocked(clearIngestionJobHistory).mockResolvedValue(1);
    const confirmSpy = vi.spyOn(window, 'confirm');

    render(<ProductDashboard {...dashboardProps} />);

    fireEvent.click(await screen.findByRole('button', { name: /^clear$/i }));
    expect(
      await screen.findByRole('dialog', { name: /clear import history/i }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /^clear history$/i }));

    await waitFor(() => {
      expect(clearIngestionJobHistory).toHaveBeenCalledTimes(1);
    });
    expect(confirmSpy).not.toHaveBeenCalled();
    expect(await screen.findByText(/Cleared 1 import\./i)).toBeInTheDocument();
  });

  it('refetches only jobs and usage on the 15s polling interval', async () => {
    vi.useFakeTimers();
    setDocumentVisibility('visible');

    render(<ProductDashboard {...dashboardProps} />);
    await flushAsync();

    expect(apiMocks.fetchLibrary).toHaveBeenCalledTimes(1);
    expect(apiMocks.fetchIngestionJobs).toHaveBeenCalledTimes(1);
    expect(apiMocks.fetchUsage).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(15000);
    });

    expect(apiMocks.fetchIngestionJobs).toHaveBeenCalledTimes(2);
    expect(apiMocks.fetchUsage).toHaveBeenCalledTimes(2);
    expect(apiMocks.fetchLibrary).toHaveBeenCalledTimes(1);
    expect(apiMocks.fetchProjects).toHaveBeenCalledTimes(1);
    expect(apiMocks.fetchCaptureSources).toHaveBeenCalledTimes(1);
    expect(apiMocks.fetchYoutubeOAuthStatus).toHaveBeenCalledTimes(1);
  });

  it('pauses polling while the tab is hidden and refreshes everything on return', async () => {
    vi.useFakeTimers();
    setDocumentVisibility('hidden');

    render(<ProductDashboard {...dashboardProps} />);
    await flushAsync();
    expect(apiMocks.fetchIngestionJobs).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(45000);
    });
    expect(apiMocks.fetchIngestionJobs).toHaveBeenCalledTimes(1);
    expect(apiMocks.fetchUsage).toHaveBeenCalledTimes(1);

    setDocumentVisibility('visible');
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'));
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(apiMocks.fetchLibrary).toHaveBeenCalledTimes(2);
    expect(apiMocks.fetchIngestionJobs).toHaveBeenCalledTimes(2);
  });

  it('shows a per-panel retry state when a dashboard fetch fails', async () => {
    vi.mocked(fetchProjects)
      .mockRejectedValueOnce(new Error('Backend Error: Internal Server Error'))
      .mockResolvedValue([
        {
          id: 'project-1',
          name: 'Agent harness research',
          slug: 'agent-harness-research',
          videoCount: 3,
        },
      ]);

    render(<ProductDashboard {...dashboardProps} />);

    expect(await screen.findByText('Your projects could not load.')).toBeInTheDocument();
    expect(screen.getByText('Projects unavailable')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /^retry$/i }));

    expect(await screen.findByText('1 project')).toBeInTheDocument();
    expect(screen.queryByText('Your projects could not load.')).not.toBeInTheDocument();
  });
});
