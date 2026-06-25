import { render, screen, waitFor } from '@testing-library/react';
import { fireEvent } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ProductDashboard } from './ProductDashboard';
import { fetchCaptureSources, syncCaptureSource } from '../services/api';
import { CaptureSource } from '../types';

vi.mock('./UnifiedSearchView', () => ({
  UnifiedSearchView: () => <div data-testid="workbench" />,
}));

const apiMocks = vi.hoisted(() => ({
  clearIngestionJobHistory: vi.fn(async () => 0),
  fetchCaptureSources: vi.fn(async () => []),
  fetchIngestionJobs: vi.fn(async () => []),
  fetchLibrary: vi.fn(async () => ({ channels: [], totalVideos: 0, totalClips: 0 })),
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
  fetchCaptureSources: apiMocks.fetchCaptureSources,
  fetchIngestionJobs: apiMocks.fetchIngestionJobs,
  fetchLibrary: apiMocks.fetchLibrary,
  fetchUsage: apiMocks.fetchUsage,
  fetchYoutubeOAuthStatus: apiMocks.fetchYoutubeOAuthStatus,
  syncCaptureSource: apiMocks.syncCaptureSource,
}));

const dashboardProps = {
  onOpenSettings: () => undefined,
  onOpenLibrary: () => undefined,
  onOpenJobs: () => undefined,
  onSearchComplete: () => undefined,
  onIndexComplete: () => undefined,
};

describe('ProductDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the free-tier usage labels', async () => {
    render(<ProductDashboard {...dashboardProps} />);

    await waitFor(() => {
      expect(screen.getByText('Searches this month')).toBeInTheDocument();
    });

    expect(screen.getByText('Videos indexed/accessed')).toBeInTheDocument();
    expect(screen.getByText('Transcript hours')).toBeInTheDocument();
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
});
