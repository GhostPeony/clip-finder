import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { LibraryView } from './LibraryView';
import {
  fetchIngestionJobs,
  fetchLibrary,
  getCachedIngestionJobs,
  getCachedLibrary,
  getSearchHistory,
} from '../services/api';

vi.mock('./LibraryKnowledgeGraph', () => ({
  LibraryKnowledgeGraph: ({ activeView }: { activeView: string }) => (
    <div data-testid="library-graph">{activeView}</div>
  ),
}));

vi.mock('../services/api', () => ({
  clearSearchHistory: vi.fn(),
  deleteSearchHistoryEntry: vi.fn(),
  deleteVideo: vi.fn(),
  downloadTranscript: vi.fn(),
  fetchIngestionJobs: vi.fn(),
  fetchLibrary: vi.fn(),
  getCachedIngestionJobs: vi.fn(),
  getCachedLibrary: vi.fn(),
  getSearchHistory: vi.fn(),
}));

describe('LibraryView', () => {
  beforeEach(() => {
    vi.mocked(fetchLibrary).mockResolvedValue({
      channels: [],
      totalVideos: 0,
      totalClips: 0,
    });
    vi.mocked(getCachedLibrary).mockResolvedValue(null);
    vi.mocked(getCachedIngestionJobs).mockResolvedValue(null);
    vi.mocked(fetchIngestionJobs).mockResolvedValue([
      {
        id: 'job-1',
        user_id: 'user-1',
        source_url: 'https://www.youtube.com/watch?v=6nyJ8y8ghsE&list=playlist',
        source_type: 'video',
        status: 'failed',
        requested_video_count: 0,
        indexed_video_count: 0,
        skipped_video_count: 0,
        failed_video_count: 0,
        last_message: "Error: 'NoneType' object has no attribute 'data'",
        error: 'Source channel could not be prepared.',
        cost_estimate: {},
        created_at: '2026-06-24T06:30:55Z',
      },
    ]);
    vi.mocked(getSearchHistory).mockReturnValue([]);
  });

  it('shows recent failed imports when the indexed-video library is empty', async () => {
    render(<LibraryView onIndexMore={() => undefined} />);

    await waitFor(() => {
      expect(screen.getByText('No videos indexed yet')).toBeInTheDocument();
    });

    expect(screen.getByText('Recent imports')).toBeInTheDocument();
    expect(screen.getByText('failed')).toBeInTheDocument();
    expect(screen.getByText('video')).toBeInTheDocument();
    expect(screen.getByText('Source channel could not be prepared.')).toBeInTheDocument();
  });

  it('shows a retry state when the library endpoint fails', async () => {
    vi.mocked(fetchLibrary).mockRejectedValue(new Error('Backend Error: Internal Server Error'));

    render(<LibraryView onIndexMore={() => undefined} />);

    await waitFor(() => {
      expect(screen.getByText('Library could not load')).toBeInTheDocument();
    });

    expect(screen.getByText(/couldn't read your saved-video library/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
    expect(screen.getByText('Recent imports')).toBeInTheDocument();
  });

  it('renders cached library data while refreshing the network copy', async () => {
    vi.mocked(getCachedLibrary).mockResolvedValue({
      channels: [
        {
          name: 'Cached Channel',
          videoCount: 1,
          videos: [
            {
              videoId: 'cached-video',
              title: 'Cached video',
              thumbnailUrl: 'thumb.jpg',
              clipCount: 4,
              indexedAt: 1782300000,
            },
          ],
        },
      ],
      totalVideos: 1,
      totalClips: 4,
    });
    vi.mocked(getCachedIngestionJobs).mockResolvedValue([]);
    vi.mocked(fetchLibrary).mockResolvedValue({
      channels: [
        {
          name: 'Fresh Channel',
          videoCount: 1,
          videos: [
            {
              videoId: 'fresh-video',
              title: 'Fresh video',
              thumbnailUrl: 'thumb.jpg',
              clipCount: 6,
              indexedAt: 1782300001,
            },
          ],
        },
      ],
      totalVideos: 1,
      totalClips: 6,
    });

    render(<LibraryView onIndexMore={() => undefined} />);

    await waitFor(() => {
      expect(screen.queryByText('Loading your video library')).not.toBeInTheDocument();
    });
    expect(screen.getByText('Library')).toBeInTheDocument();
    await waitFor(() => {
      expect(fetchLibrary).toHaveBeenCalled();
    });
  });

  it('uses a persistent library menu to switch major sections', async () => {
    vi.mocked(fetchLibrary).mockResolvedValue({
      channels: [
        {
          name: 'Research Channel',
          videoCount: 1,
          videos: [
            {
              videoId: 'video-1',
              title: 'Saved video',
              thumbnailUrl: 'thumb.jpg',
              clipCount: 4,
              indexedAt: 1782300000,
            },
          ],
        },
      ],
      totalVideos: 1,
      totalClips: 4,
    });
    vi.mocked(fetchIngestionJobs).mockResolvedValue([]);

    render(<LibraryView onIndexMore={() => undefined} />);

    expect(await screen.findByText('Library menu')).toBeInTheDocument();
    expect(screen.getByTestId('library-graph')).toHaveTextContent('videos');

    fireEvent.click(screen.getByRole('button', { name: /Topics/i }));
    expect(screen.getByTestId('library-graph')).toHaveTextContent('topics');

    fireEvent.click(screen.getByRole('button', { name: /Reports/i }));
    expect(screen.getByTestId('library-graph')).toHaveTextContent('guides');

    fireEvent.click(screen.getByRole('button', { name: /Recent searches/i }));
    expect(screen.getByText('No recent searches')).toBeInTheDocument();
  });
});
