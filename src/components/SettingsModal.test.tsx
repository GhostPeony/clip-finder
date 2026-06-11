import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SettingsModal } from './SettingsModal';

vi.mock('../services/api', () => ({
  deleteApiKey: vi.fn(),
  fetchUsage: vi.fn(async () => ({
    plan: 'free',
    searchesUsedToday: 4,
    searchesUsedThisMonth: 4,
    searchLimit: null,
    searchPeriod: 'month',
    indexesUsedThisMonth: 2,
    indexLimit: 15,
    indexedVideosUsed: 2,
    indexedVideoLimit: 15,
    indexedSecondsUsed: 7200,
    indexedSecondsLimit: 18000,
    maxImportVideos: 10,
    maxSearchResults: 5,
    hasOwnKey: true,
    apiKeyMode: 'hybrid',
    hasServerKey: true,
    allowUserKeys: true,
  })),
  getStoredLocalApiKey: vi.fn(() => null),
  saveApiKey: vi.fn(async () => true),
}));

describe('SettingsModal', () => {
  it('shows BYOK as AI-request coverage while keeping hosted storage caps', async () => {
    render(<SettingsModal isOpen onClose={() => undefined} allowUserKeys />);

    await waitFor(() => {
      expect(screen.getByText('Searches this month')).toBeInTheDocument();
    });

    expect(screen.getByText('Own key')).toBeInTheDocument();
    expect(screen.getByText('Videos indexed/accessed')).toBeInTheDocument();
    expect(screen.getByText('Transcript hours')).toBeInTheDocument();
    expect(
      screen.getByText(
        /Use your Gemini key for AI requests\. Hosted indexing and storage caps still apply\./,
      ),
    ).toBeInTheDocument();
  });
});
