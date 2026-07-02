import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { saveSearchToHistory, searchVideoClips } from '../../services/api';
import { LibrarySearchSection } from './LibrarySearchSection';

vi.mock('../../services/api', () => ({
  saveSearchToHistory: vi.fn(),
  searchVideoClips: vi.fn(),
}));

describe('LibrarySearchSection', () => {
  beforeEach(() => {
    // jsdom does not implement scrollIntoView.
    Element.prototype.scrollIntoView = vi.fn();
    vi.mocked(saveSearchToHistory).mockClear();
    vi.mocked(searchVideoClips).mockReset();
    vi.mocked(searchVideoClips).mockResolvedValue({
      answer:
        'Harness loops help teams evaluate whether agent systems complete work reliably. [[clip_0]]',
      relevantClips: [
        {
          id: 'clip_0',
          videoId: 'yt-harness',
          title: 'Harness loop',
          channelName: 'Research Channel',
          startSeconds: 30,
          endSeconds: 75,
          content: 'Use harness loops to check agent quality.',
          thumbnailUrl: 'https://img.youtube.com/vi/yt-harness/mqdefault.jpg',
          matchSnippet: 'Use harness loops to check agent quality.',
        },
      ],
    });
  });

  it('searches in auto mode by default and stays within the free result cap', async () => {
    render(<LibrarySearchSection />);

    fireEvent.change(screen.getByLabelText('Search saved videos'), {
      target: { value: 'Why use synthetic data?' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    await waitFor(() => {
      expect(searchVideoClips).toHaveBeenCalledWith(
        'Why use synthetic data?',
        5,
        undefined,
        'auto',
      );
    });
    expect(saveSearchToHistory).toHaveBeenCalled();
  });

  it('keeps mode selection behind a search-options disclosure', async () => {
    render(<LibrarySearchSection />);

    expect(screen.queryByRole('radio', { name: /Exact words/ })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Search options' }));
    fireEvent.click(screen.getByRole('radio', { name: /Exact words/ }));
    expect(
      screen.getByRole('button', { name: /Search options · Exact words/ }),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Search saved videos'), {
      target: { value: 'harness loop' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    await waitFor(() => {
      expect(searchVideoClips).toHaveBeenCalledWith('harness loop', 5, undefined, 'keyword');
    });
  });

  it('scopes searches to the active project', async () => {
    render(<LibrarySearchSection projectId="project-1" projectName="Agent harness research" />);

    expect(screen.getByText('Searching project: Agent harness research.')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Search saved videos'), {
      target: { value: 'reward hacking' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    await waitFor(() => {
      expect(searchVideoClips).toHaveBeenCalledWith(
        'reward hacking',
        5,
        undefined,
        'auto',
        'project-1',
      );
    });
  });

  it('renders a cited answer and scrolls to the matching result card', async () => {
    render(<LibrarySearchSection />);

    fireEvent.change(screen.getByLabelText('Search saved videos'), {
      target: { value: 'harness loop' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    expect(await screen.findByText('Answer')).toBeInTheDocument();
    expect(
      screen.getByText(/Harness loops help teams evaluate whether agent systems/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/\[\[clip_0\]\]/)).not.toBeInTheDocument();

    const resultCard = document.getElementById('library-clip-clip_0');
    expect(resultCard).not.toBeNull();

    fireEvent.click(screen.getByRole('button', { name: /0:30/ }));
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
    expect(resultCard?.className).toContain('ring-2');
  });

  it('announces search failures as alerts', async () => {
    vi.mocked(searchVideoClips).mockRejectedValue(new Error('Search failed upstream'));
    render(<LibrarySearchSection />);

    fireEvent.change(screen.getByLabelText('Search saved videos'), {
      target: { value: 'harness loop' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Search failed upstream');
  });
});
