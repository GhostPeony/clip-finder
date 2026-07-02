import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  fetchLibraryArtifact,
  fetchLibraryGraph,
  getCachedLibraryGraph,
  saveSearchToHistory,
  searchVideoClips,
} from '../services/api';
import { LibrarySourceGraphData } from '../types';
import { LibraryKnowledgeGraph } from './LibraryKnowledgeGraph';

vi.mock('../services/api', () => ({
  fetchLibraryArtifact: vi.fn(),
  fetchLibraryGraph: vi.fn(),
  getCachedLibraryGraph: vi.fn(),
  saveSearchToHistory: vi.fn(),
  searchVideoClips: vi.fn(),
}));

const graphPayload: LibrarySourceGraphData = {
  version: 'memexai-library-source-graph-v1',
  limit: 50,
  accessModel: {
    scope: 'current_user_grants',
    visibilityGrants: ['user_videos', 'user_channels'],
    sourceTruth: 'read_only',
    provenanceFields: ['accessScope', 'accessSource', 'accessReason'],
  },
  videos: [
    {
      id: 'video-db',
      videoId: 'yt-harness',
      title: 'Harness lesson',
      youtubeUrl: 'https://www.youtube.com/watch?v=yt-harness',
      thumbnailUrl: 'https://img.youtube.com/vi/yt-harness/mqdefault.jpg',
      transcriptSeconds: 600,
      indexedAt: '2026-06-20T12:00:00Z',
      channel: { id: 'channel-db', name: 'Research Channel' },
      accessScope: 'video',
      accessSource: 'playlist',
      accessReason: 'Visible through an explicit saved-video grant.',
    },
  ],
  componentCounts: {
    videos: 1,
    channels: 1,
    sourceLabels: 2,
    sourceConcepts: 5,
    sourceEdges: 1,
    knowledgeArtifacts: 2,
    transcriptChunksSampled: 4,
    agentNotes: 1,
    personalConcepts: 1,
    reviewFlags: 2,
  },
  graph: {
    nodes: [
      {
        id: 'video:yt-harness',
        type: 'video',
        label: 'Harness lesson',
        summary: 'Research Channel',
        video: {
          videoId: 'yt-harness',
          title: 'Harness lesson',
          thumbnailUrl: 'https://img.youtube.com/vi/yt-harness/mqdefault.jpg',
        },
      },
      {
        id: 'concept:1',
        type: 'source_concept',
        label: 'Harness loop',
        summary: 'Use harness loops to check agent quality.',
        video: { videoId: 'yt-harness', title: 'Harness lesson' },
        metadata: { conceptType: 'method' },
        sourceRefs: [
          {
            source_type: 'transcript',
            youtube_video_id: 'yt-harness',
            start_seconds: 30,
            end_seconds: 75,
            quote: 'Use harness loops to check agent quality at each release gate.',
          },
        ],
      },
      {
        id: 'concept:duplicate-moment',
        type: 'source_concept',
        label: 'Release gate checks',
        summary: 'A duplicate same-moment idea that should not create another topic card.',
        video: { videoId: 'yt-harness', title: 'Harness lesson' },
        metadata: { conceptType: 'method' },
        sourceRefs: [
          {
            source_type: 'transcript',
            youtube_video_id: 'yt-harness',
            start_seconds: 34,
            end_seconds: 75,
            quote: 'Use harness loops to check agent quality at each release gate.',
          },
        ],
      },
      {
        id: 'concept:intro-moment',
        type: 'source_concept',
        label: 'Opening intro',
        summary: 'An intro-second topic that should not become primary browse structure.',
        video: { videoId: 'yt-harness', title: 'Harness lesson' },
        metadata: { conceptType: 'concept' },
        sourceRefs: [
          {
            source_type: 'transcript',
            youtube_video_id: 'yt-harness',
            start_seconds: 1,
            end_seconds: 8,
            quote: 'Welcome to the lesson.',
          },
        ],
      },
      {
        id: 'artifact:1',
        type: 'knowledge_artifact',
        label: 'Study Guide: Reliable Agent Harnesses',
        summary: 'This report explains how to turn ad hoc prompting into testable systems.',
        content:
          '# Reliable Agent Harnesses\n\n## Compiled Truth\n\n- Harnesses create release gates. (source: 2:00)\n\nThis is the full generated report body with multiple sections and enough detail to avoid truncation.',
        video: { videoId: 'yt-harness', title: 'Harness lesson' },
        sourceRefs: [
          {
            source_type: 'transcript',
            youtube_video_id: 'yt-harness',
            start_seconds: 120,
            end_seconds: 180,
          },
        ],
        metadata: { artifactType: 'study_guide' },
      },
      {
        id: 'artifact:tldr',
        type: 'knowledge_artifact',
        label: 'TLDR: Reliable Agent Harnesses',
        summary: 'Harness loops make agent quality visible before release.',
        content: 'Harness loops make agent quality visible before release.',
        video: { videoId: 'yt-harness', title: 'Harness lesson' },
        metadata: { artifactType: 'tldr' },
      },
      {
        id: 'concept:without-timestamp',
        type: 'source_concept',
        label: 'Static topic without evidence',
        summary: 'This should not take up topic-card space without a timestamp.',
        video: { videoId: 'yt-harness', title: 'Harness lesson' },
      },
      {
        id: 'chunk:1',
        type: 'transcript_chunk',
        label: '120s transcript',
        summary: 'Harnesses help teams verify that agents complete the intended task.',
        video: { videoId: 'yt-harness', title: 'Harness lesson' },
      },
      {
        id: 'label:method:harness',
        type: 'source_label',
        label: 'Harnesses',
        summary: 'method',
        video: { videoId: 'yt-harness', title: 'Harness lesson' },
        metadata: { labelType: 'method' },
      },
    ],
    edges: [
      {
        id: 'video:yt-harness->concept:1',
        source: 'video:yt-harness',
        target: 'concept:1',
        relation: 'extracts',
      },
      {
        id: 'video:yt-harness->artifact:1',
        source: 'video:yt-harness',
        target: 'artifact:1',
        relation: 'generates',
      },
    ],
    selectedNodeId: 'concept:1',
  },
  reviewFlags: [
    {
      id: 'potential-conflict:harness_loop',
      type: 'potential_conflict',
      severity: 'review',
      title: 'Review cross-video claim: Harness loop',
      message: 'Multiple videos contain this claim/concept with different summaries.',
      videoIds: ['yt-harness'],
    },
    {
      id: 'weak-evidence-refs',
      type: 'weak_evidence_refs',
      severity: 'warning',
      title: 'Some source components lack timestamp refs',
      message: '1 label needs source-ref review.',
      count: 1,
    },
  ],
  edgeCaseHandling: [
    {
      edgeCase: 'Conflicting information between videos',
      handling: 'Preserve source-specific claims and citations.',
    },
  ],
  guidance: '',
};

const latestVideos = [
  {
    videoId: 'yt-harness',
    title: 'Harness lesson',
    thumbnailUrl: 'https://img.youtube.com/vi/yt-harness/mqdefault.jpg',
    clipCount: 8,
    indexedAt: Date.now(),
    channelName: 'Research Channel',
  },
];

describe('LibraryKnowledgeGraph', () => {
  beforeEach(() => {
    // jsdom does not implement scrollIntoView.
    Element.prototype.scrollIntoView = vi.fn();
    vi.mocked(getCachedLibraryGraph).mockResolvedValue(null);
    vi.mocked(fetchLibraryArtifact).mockResolvedValue(
      graphPayload.graph.nodes.find((node) => node.id === 'artifact:1') || null,
    );
    vi.mocked(fetchLibraryGraph).mockResolvedValue(graphPayload);
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
    vi.mocked(saveSearchToHistory).mockClear();
  });

  it('renders a compact saved-video knowledge view without exposing raw graph internals', async () => {
    render(
      <LibraryKnowledgeGraph
        activeView="videos"
        latestVideos={latestVideos}
        onIndexMore={() => undefined}
      />,
    );

    expect((await screen.findAllByText('Search saved videos')).length).toBeGreaterThan(0);
    expect(screen.getByText('TLDR and source reports')).toBeInTheDocument();
    expect(screen.getByText('Timestamped topics')).toBeInTheDocument();
    expect(screen.getAllByText(/Indexed Jun 20, 2026/).length).toBeGreaterThan(0);
    expect(screen.getAllByText('Harness loop').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Reliable Agent Harnesses').length).toBeGreaterThan(0);
    expect(screen.queryByText('Static topic without evidence')).not.toBeInTheDocument();
    expect(screen.queryByText('Review cross-video claim: Harness loop')).not.toBeInTheDocument();
    expect(screen.queryByText('Advanced graph data')).not.toBeInTheDocument();
    expect(screen.queryByText('Labels')).not.toBeInTheDocument();
    expect(screen.queryByText('Edges')).not.toBeInTheDocument();
    expect(screen.queryByText('Timestamped moments')).not.toBeInTheDocument();
    expect(screen.queryByText('Guides and summaries')).not.toBeInTheDocument();
    expect(screen.queryByText(/NO EMBEDDINGS/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/NO LLM/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/source map/i)).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Open at 0:30/ })).toHaveAttribute(
      'href',
      expect.stringContaining('&t=30'),
    );
    expect(screen.queryByText(/yt-harness @/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Read report' }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getAllByText('Reliable Agent Harnesses').length).toBeGreaterThan(0);
    expect(screen.getByText(/full generated report body/i)).toBeInTheDocument();
    expect(screen.getByText(/Harnesses create release gates/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'source 2:00' })).toHaveAttribute(
      'href',
      expect.stringContaining('&t=120'),
    );
    expect(screen.queryByText('# Reliable Agent Harnesses')).not.toBeInTheDocument();
    expect(screen.queryByText('## Compiled Truth')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Close report' }));
    fireEvent.click(screen.getByRole('button', { name: 'Exact' }));
    fireEvent.change(screen.getByLabelText('Search saved videos'), {
      target: { value: 'harness loop' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    await waitFor(() => {
      expect(searchVideoClips).toHaveBeenCalledWith('harness loop', 5, undefined, 'keyword');
    });
    expect(saveSearchToHistory).toHaveBeenCalled();
  });

  it('locks scroll and manages focus while a report modal is open', async () => {
    render(
      <LibraryKnowledgeGraph
        activeView="videos"
        latestVideos={latestVideos}
        onIndexMore={() => undefined}
      />,
    );

    await screen.findAllByText('Search saved videos');
    fireEvent.click(screen.getByRole('button', { name: 'Read report' }));

    const closeButton = screen.getByRole('button', { name: 'Close report' });
    expect(document.activeElement).toBe(closeButton);
    expect(document.body.style.overflow).toBe('hidden');

    fireEvent.keyDown(window, { key: 'Escape' });
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
    expect(document.body.style.overflow).toBe('');
  });

  it('renders a cited answer for library search and scrolls to the matching result card', async () => {
    render(
      <LibraryKnowledgeGraph
        activeView="videos"
        latestVideos={latestVideos}
        onIndexMore={() => undefined}
      />,
    );

    await screen.findAllByText('Search saved videos');
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

  it('keeps smart library search within the free result cap', async () => {
    render(
      <LibraryKnowledgeGraph
        activeView="videos"
        latestVideos={latestVideos}
        onIndexMore={() => undefined}
      />,
    );

    await screen.findAllByText('Search saved videos');
    fireEvent.change(screen.getByLabelText('Search saved videos'), {
      target: { value: 'Why use synthetic data?' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    await waitFor(() => {
      expect(searchVideoClips).toHaveBeenCalledWith(
        'Why use synthetic data?',
        5,
        undefined,
        'hybrid',
      );
    });
  });

  it('does not show an empty-library message when indexed videos exist but graph is unavailable', async () => {
    vi.mocked(fetchLibraryGraph).mockResolvedValue({
      ...graphPayload,
      videos: [],
      componentCounts: {
        ...graphPayload.componentCounts,
        videos: 0,
        channels: 0,
        sourceLabels: 0,
        sourceConcepts: 0,
        sourceEdges: 0,
        knowledgeArtifacts: 0,
        transcriptChunksSampled: 0,
        agentNotes: 0,
        personalConcepts: 0,
        reviewFlags: 0,
      },
      graph: { nodes: [], edges: [], selectedNodeId: null },
      reviewFlags: [],
      edgeCaseHandling: [],
    });

    render(
      <LibraryKnowledgeGraph
        activeView="videos"
        latestVideos={latestVideos}
        onIndexMore={() => undefined}
      />,
    );

    expect((await screen.findAllByText('Search saved videos')).length).toBeGreaterThan(0);
    expect(screen.getByText('0 reports · 0 timestamped topics')).toBeInTheDocument();
    expect(screen.queryByText('No saved videos ready')).not.toBeInTheDocument();
  });

  it('shows a catching-up state with retry when videos exist but the graph is empty', async () => {
    const emptyGraph: LibrarySourceGraphData = {
      ...graphPayload,
      videos: [],
      graph: { nodes: [], edges: [], selectedNodeId: null },
      reviewFlags: [],
      edgeCaseHandling: [],
    };
    vi.mocked(fetchLibraryGraph).mockResolvedValue(emptyGraph);

    render(
      <LibraryKnowledgeGraph
        activeView="videos"
        latestVideos={[]}
        totalVideoCount={3}
        onIndexMore={() => undefined}
      />,
    );

    expect(await screen.findByText('Your library is catching up')).toBeInTheDocument();
    expect(screen.getByText(/3 saved videos are indexed and searchable/)).toBeInTheDocument();
    expect(screen.queryByText('No saved videos ready')).not.toBeInTheDocument();

    const callsBeforeRetry = vi.mocked(fetchLibraryGraph).mock.calls.length;
    fireEvent.click(screen.getByRole('button', { name: /^retry$/i }));

    await waitFor(() => {
      expect(vi.mocked(fetchLibraryGraph).mock.calls.length).toBe(callsBeforeRetry + 1);
    });
  });

  it('notes the report/topic coverage cap when the library exceeds the graph limit', async () => {
    render(
      <LibraryKnowledgeGraph
        activeView="videos"
        latestVideos={latestVideos}
        totalVideoCount={120}
        onIndexMore={() => undefined}
      />,
    );

    expect(
      await screen.findByText(/Reports and topics cover your 50 most recent videos/),
    ).toBeInTheDocument();
  });

  it('renders topic cards with timestamp snippets', async () => {
    render(
      <LibraryKnowledgeGraph
        activeView="topics"
        latestVideos={latestVideos}
        onIndexMore={() => undefined}
      />,
    );

    expect(await screen.findByText('Timestamped topics by category')).toBeInTheDocument();
    expect(screen.getByText('Methods, tools, and systems')).toBeInTheDocument();
    expect(screen.getAllByText('Harness loop').length).toBeGreaterThan(0);
    expect(screen.getByText('From Harness lesson')).toBeInTheDocument();
    expect(
      screen.getByText('Use harness loops to check agent quality at each release gate.'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('Merged 2 extracted ideas from this same source moment.'),
    ).toBeInTheDocument();
    expect(screen.queryByText('Release gate checks')).not.toBeInTheDocument();
    expect(screen.queryByText('Opening intro')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Open at 0:30/ })).toHaveAttribute(
      'href',
      expect.stringContaining('&t=30'),
    );
  });

  it('renders a dedicated guide library view', async () => {
    render(
      <LibraryKnowledgeGraph
        activeView="guides"
        latestVideos={latestVideos}
        onIndexMore={() => undefined}
      />,
    );

    expect(await screen.findByText('Reports by video')).toBeInTheDocument();
    expect(screen.getByText('2 generated artifacts')).toBeInTheDocument();
    expect(screen.getAllByText('Reliable Agent Harnesses').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: 'Read report' }));
    expect(screen.getByText(/full generated report body/i)).toBeInTheDocument();
  });

  it('fetches full report content on demand when the graph payload is compact', async () => {
    const compactGraph: LibrarySourceGraphData = {
      ...graphPayload,
      graph: {
        ...graphPayload.graph,
        nodes: graphPayload.graph.nodes.map((node) =>
          node.id === 'artifact:1' ? { ...node, content: undefined } : node,
        ),
      },
    };
    vi.mocked(fetchLibraryGraph).mockResolvedValue(compactGraph);

    render(
      <LibraryKnowledgeGraph
        activeView="guides"
        latestVideos={latestVideos}
        onIndexMore={() => undefined}
      />,
    );

    await screen.findByText('Reports by video');
    fireEvent.click(screen.getByRole('button', { name: 'Read report' }));

    await waitFor(() => {
      expect(fetchLibraryArtifact).toHaveBeenCalledWith('artifact:1');
    });
    expect(await screen.findByText(/full generated report body/i)).toBeInTheDocument();
  });

  it('uses cached graph data immediately and still refreshes the graph endpoint', async () => {
    vi.mocked(getCachedLibraryGraph).mockResolvedValue(graphPayload);

    render(
      <LibraryKnowledgeGraph
        activeView="videos"
        latestVideos={latestVideos}
        onIndexMore={() => undefined}
      />,
    );

    await waitFor(() => {
      expect(screen.queryByText('Preparing saved videos')).not.toBeInTheDocument();
    });
    expect(screen.getAllByText('Harness loop').length).toBeGreaterThan(0);
    await waitFor(() => {
      expect(fetchLibraryGraph).toHaveBeenCalledWith(50);
    });
  });

  it('batches large saved-video libraries instead of rendering every card at once', async () => {
    vi.mocked(fetchLibraryGraph).mockResolvedValue({
      ...graphPayload,
      videos: [],
      componentCounts: {
        ...graphPayload.componentCounts,
        videos: 0,
        sourceConcepts: 0,
        knowledgeArtifacts: 0,
      },
      graph: { nodes: [], edges: [], selectedNodeId: null },
    });
    const manyVideos = Array.from({ length: 60 }, (_, index) => ({
      videoId: `saved-${index}`,
      title: `Saved video ${index}`,
      thumbnailUrl: `https://img.youtube.com/vi/saved-${index}/mqdefault.jpg`,
      clipCount: 3,
      indexedAt: 1782300000 - index,
      channelName: 'Large Library Channel',
    }));

    render(
      <LibraryKnowledgeGraph
        activeView="videos"
        latestVideos={manyVideos}
        onIndexMore={() => undefined}
      />,
    );

    expect(await screen.findByText('Saved videos')).toBeInTheDocument();
    expect(screen.getByText('Showing 36 of 60 saved videos')).toBeInTheDocument();
    expect(screen.getByText('Saved video 35')).toBeInTheDocument();
    expect(screen.queryByText('Saved video 59')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Load more' }));

    expect(screen.getByText('Saved video 59')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Load more' })).not.toBeInTheDocument();
  });
});
