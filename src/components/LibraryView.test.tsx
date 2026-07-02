import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { LibraryView } from './LibraryView';
import {
  addProjectVideos,
  clearSearchHistory,
  createCaptureSource,
  createProject,
  fetchIngestionJobs,
  fetchLibrary,
  fetchProjects,
  getCachedIngestionJobs,
  getCachedLibrary,
  getSearchHistory,
} from '../services/api';

vi.mock('./LibraryKnowledgeGraph', () => ({
  LibraryKnowledgeGraph: ({
    activeView,
    projectId,
  }: {
    activeView: string;
    projectId?: string;
  }) => (
    <div data-testid="library-graph">
      {activeView}
      {projectId ? `:${projectId}` : ''}
    </div>
  ),
}));

vi.mock('../services/api', () => ({
  addProjectVideos: vi.fn(),
  clearSearchHistory: vi.fn(),
  createCaptureSource: vi.fn(),
  createProject: vi.fn(),
  deleteSearchHistoryEntry: vi.fn(),
  deleteVideo: vi.fn(),
  downloadTranscript: vi.fn(),
  fetchIngestionJobs: vi.fn(),
  fetchLibrary: vi.fn(),
  fetchProjects: vi.fn(),
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
    vi.mocked(fetchProjects).mockResolvedValue([]);
    vi.mocked(createProject).mockResolvedValue(null);
    vi.mocked(createCaptureSource).mockResolvedValue(null);
    vi.mocked(addProjectVideos).mockResolvedValue(null);
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

  it('renders the projects management view even when no videos are indexed', async () => {
    vi.mocked(fetchProjects).mockResolvedValue([
      {
        id: 'project-1',
        name: 'Agent harness research',
        slug: 'agent-harness-research',
        description: 'Reliability and eval videos',
        videoCount: 0,
      },
    ]);

    render(<LibraryView initialSurface="projects" onIndexMore={() => undefined} />);

    expect(await screen.findByRole('heading', { name: 'Projects' })).toBeInTheDocument();
    expect(screen.queryByText('No videos indexed yet')).not.toBeInTheDocument();
    expect(screen.getByText('Manage projects')).toBeInTheDocument();
    expect(screen.getByText('Project view')).toBeInTheDocument();
    expect(
      screen.getAllByRole('button', { name: /Agent harness research/i }).length,
    ).toBeGreaterThan(0);
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

  it('opens with an initial project scope and lets users search project cards', async () => {
    vi.mocked(fetchProjects).mockResolvedValue([
      {
        id: 'project-1',
        name: 'Agent harness research',
        slug: 'agent-harness-research',
        description: 'Reliability and eval videos',
        videoCount: 2,
      },
      {
        id: 'project-2',
        name: 'Synthetic data',
        slug: 'synthetic-data',
        description: 'Post-training data videos',
        videoCount: 1,
      },
    ]);
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

    const { unmount } = render(
      <LibraryView initialProjectId="project-1" onIndexMore={() => undefined} />,
    );

    await waitFor(() => {
      expect(screen.getByTestId('library-graph')).toHaveTextContent('videos:project-1');
    });
    expect(screen.getByLabelText('Project scope')).toHaveValue('project-1');

    unmount();
    render(
      <LibraryView
        initialSurface="projects"
        initialProjectId="project-1"
        onIndexMore={() => undefined}
      />,
    );

    fireEvent.change(await screen.findByPlaceholderText('Search projects'), {
      target: { value: 'synthetic' },
    });
    expect(screen.getByRole('button', { name: /Synthetic data/i })).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /Agent harness research/i }),
    ).not.toBeInTheDocument();
  });

  it('clears search history through an app dialog instead of window.confirm', async () => {
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
    vi.mocked(getSearchHistory)
      .mockReturnValueOnce([
        {
          id: 'history-1',
          query: 'agent harness reliability',
          timestamp: Date.now(),
          clips: [],
        },
      ])
      .mockReturnValue([]);
    const confirmSpy = vi.spyOn(window, 'confirm');

    render(<LibraryView onIndexMore={() => undefined} />);

    fireEvent.click(await screen.findByRole('button', { name: /Recent searches/i }));
    expect(screen.getByText('agent harness reliability')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /^clear all$/i }));
    const dialog = await screen.findByRole('dialog', { name: /clear all search history/i });
    fireEvent.click(within(dialog).getByRole('button', { name: /^clear all$/i }));

    await waitFor(() => {
      expect(clearSearchHistory).toHaveBeenCalledTimes(1);
    });
    expect(confirmSpy).not.toHaveBeenCalled();
    expect(screen.getByText('No recent searches')).toBeInTheDocument();
  });
});
