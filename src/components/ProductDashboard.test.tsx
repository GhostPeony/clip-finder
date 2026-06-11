import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ProductDashboard } from './ProductDashboard';

vi.mock('./UnifiedSearchView', () => ({
  UnifiedSearchView: () => <div data-testid="workbench" />,
}));

vi.mock('../services/api', () => ({
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
}));

const dashboardProps = {
  isBackendConnected: true,
  hasApiKey: false,
  hasServerKey: true,
  allowUserKeys: true,
  showLocalBackendHelp: false,
  onOpenSettings: () => undefined,
  onOpenLibrary: () => undefined,
  onOpenJobs: () => undefined,
  onSearchComplete: () => undefined,
  onIndexComplete: () => undefined,
};

describe('ProductDashboard', () => {
  it('renders the free-tier usage labels', async () => {
    render(<ProductDashboard {...dashboardProps} />);

    await waitFor(() => {
      expect(screen.getByText('Searches this month')).toBeInTheDocument();
    });

    expect(screen.getByText('Videos indexed/accessed')).toBeInTheDocument();
    expect(screen.getByText('Transcript hours')).toBeInTheDocument();
  });
});
