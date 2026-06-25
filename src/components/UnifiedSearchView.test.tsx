import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { searchVideoClips } from '../services/api';
import { UnifiedSearchView } from './UnifiedSearchView';

vi.mock('../services/api', () => ({
  ingestChannel: vi.fn(),
  saveSearchToHistory: vi.fn(),
  searchVideoClips: vi.fn(),
}));

const viewProps = {
  onSearchComplete: () => undefined,
  onIndexComplete: () => undefined,
};

describe('UnifiedSearchView', () => {
  it('removes result options above the free max', () => {
    render(<UnifiedSearchView {...viewProps} maxSearchResults={5} />);

    expect(screen.getByRole('option', { name: '5' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: '10' })).not.toBeInTheDocument();
  });

  it('surfaces quota errors from search', async () => {
    vi.mocked(searchVideoClips).mockRejectedValueOnce(
      new Error('Monthly hosted search limit reached.'),
    );

    render(<UnifiedSearchView {...viewProps} maxSearchResults={5} />);

    fireEvent.click(screen.getAllByText('Search library')[0]);
    fireEvent.change(screen.getByLabelText('Search query'), {
      target: { value: 'pricing objections' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Search library' }));

    await waitFor(() => {
      expect(screen.getByText('Monthly hosted search limit reached.')).toBeInTheDocument();
    });
  });
});
