import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { LibraryGraphNode, LibrarySourceGraphData, LibraryVideo } from '../types';
import { fetchLibraryArtifact, fetchLibraryGraph, getCachedLibraryGraph } from '../services/api';
import { buildVideoKnowledge, flattenGuides, flattenIdeas } from '../lib/videoKnowledge';
import { BrandLoader } from './BrandLoader';
import { Notice } from './ui/Notice';
import { GuideModal } from './library/GuideModal';
import { GuidesLibraryPanel } from './library/GuidesLibraryPanel';
import { TopicsPanel } from './library/TopicsPanel';
import { VideoLibraryPanel } from './library/VideoLibraryPanel';

interface LibraryKnowledgeGraphProps {
  activeView: 'videos' | 'topics' | 'guides';
  latestVideos: Array<LibraryVideo & { channelName: string }>;
  onIndexMore: () => void;
  projectId?: string | null;
  /** Total saved videos in the current scope; defaults to the visible list length. */
  totalVideoCount?: number;
}

export const LibraryKnowledgeGraph: React.FC<LibraryKnowledgeGraphProps> = ({
  activeView,
  latestVideos,
  onIndexMore,
  projectId,
  totalVideoCount = latestVideos.length,
}) => {
  const [graphData, setGraphData] = useState<LibrarySourceGraphData | null>(null);
  const [loadingGraph, setLoadingGraph] = useState(true);
  const [graphReloadToken, setGraphReloadToken] = useState(0);
  const [selectedVideoKey, setSelectedVideoKey] = useState<string | null>(null);
  const [selectedGuide, setSelectedGuide] = useState<LibraryGraphNode | null>(null);
  const [selectedGuideLoading, setSelectedGuideLoading] = useState(false);
  const [selectedGuideError, setSelectedGuideError] = useState('');
  const [videoFilter, setVideoFilter] = useState('');

  useEffect(() => {
    let active = true;

    const load = async () => {
      const cached = projectId
        ? await getCachedLibraryGraph(50, projectId)
        : await getCachedLibraryGraph(50);
      if (!active) return;
      if (cached) {
        setGraphData(cached);
        setLoadingGraph(false);
      } else {
        setLoadingGraph(true);
      }
      const data = projectId ? await fetchLibraryGraph(50, projectId) : await fetchLibraryGraph(50);
      if (!active) return;
      setGraphData(data);
      setLoadingGraph(false);
    };

    void load();

    return () => {
      active = false;
    };
  }, [projectId, graphReloadToken]);

  useEffect(() => {
    setSelectedVideoKey(null);
    setSelectedGuide(null);
  }, [projectId]);

  const videoKnowledge = useMemo(
    () => buildVideoKnowledge(graphData, latestVideos),
    [graphData, latestVideos],
  );

  useEffect(() => {
    if (videoKnowledge.length === 0) {
      setSelectedVideoKey(null);
      return;
    }
    if (!selectedVideoKey || !videoKnowledge.some((item) => item.key === selectedVideoKey)) {
      setSelectedVideoKey(videoKnowledge[0].key);
    }
  }, [selectedVideoKey, videoKnowledge]);

  const selectedVideo =
    videoKnowledge.find((item) => item.key === selectedVideoKey) || videoKnowledge[0] || null;
  const allIdeas = useMemo(() => flattenIdeas(videoKnowledge), [videoKnowledge]);
  const allGuides = useMemo(() => flattenGuides(videoKnowledge), [videoKnowledge]);

  const handleOpenGuide = async (guide: LibraryGraphNode) => {
    setSelectedGuide(guide);
    setSelectedGuideError('');
    if (guide.content || guide.type !== 'knowledge_artifact') {
      setSelectedGuideLoading(false);
      return;
    }

    setSelectedGuideLoading(true);
    const artifact = await fetchLibraryArtifact(guide.id);
    if (!artifact?.content) {
      setSelectedGuideError('The full report could not be loaded. Try again in a moment.');
      setSelectedGuideLoading(false);
      return;
    }
    setSelectedGuide((current) =>
      current?.id === guide.id
        ? {
            ...current,
            ...artifact,
            id: current.id,
            video: artifact.video || current.video,
          }
        : current,
    );
    setSelectedGuideLoading(false);
  };

  // Stable identity so GuideModal's keyboard/focus effects do not re-subscribe every render.
  const handleCloseGuide = useCallback(() => setSelectedGuide(null), []);

  if (loadingGraph) {
    return (
      <div className="card p-8">
        <BrandLoader
          label="Preparing saved videos"
          detail="Loading generated reports, timestamped topics, and source links."
        />
      </div>
    );
  }

  if (videoKnowledge.length === 0) {
    if (totalVideoCount > 0) {
      return (
        <section className="card p-8 text-center">
          <h2 className="font-serif text-3xl font-medium text-ink">Your library is catching up</h2>
          <p className="mx-auto mt-2 max-w-md text-base leading-7 text-bark">
            {totalVideoCount} saved video{totalVideoCount === 1 ? ' is' : 's are'} indexed and
            searchable, but reports and topics are still being prepared. Retry in a moment.
          </p>
          <button
            onClick={() => setGraphReloadToken((token) => token + 1)}
            className="btn btn-primary mt-6"
          >
            Retry
          </button>
        </section>
      );
    }

    return (
      <section className="card p-8 text-center">
        <h2 className="font-serif text-3xl font-medium text-ink">No saved videos ready</h2>
        <p className="mx-auto mt-2 max-w-md text-base leading-7 text-bark">
          Index a captioned video to create a searchable library for you and your agent.
        </p>
        <button onClick={onIndexMore} className="btn btn-primary mt-6">
          Add videos
        </button>
      </section>
    );
  }

  const graphVideoLimit = graphData?.limit || 50;

  return (
    <div className="space-y-4 md:space-y-5">
      {totalVideoCount > graphVideoLimit ? (
        <Notice tone="info">
          Reports and topics cover your {graphVideoLimit} most recent videos. All {totalVideoCount}{' '}
          saved videos stay searchable.
        </Notice>
      ) : null}

      {activeView === 'videos' ? (
        <VideoLibraryPanel
          videos={videoKnowledge}
          selectedVideo={selectedVideo}
          selectedVideoKey={selectedVideo?.key || ''}
          filter={videoFilter}
          onFilterChange={setVideoFilter}
          onSelect={setSelectedVideoKey}
          onOpenGuide={(guide) => void handleOpenGuide(guide)}
        />
      ) : null}

      {activeView === 'topics' ? (
        <TopicsPanel ideas={allIdeas} onSelectVideo={setSelectedVideoKey} />
      ) : null}

      {activeView === 'guides' ? (
        <GuidesLibraryPanel
          guides={allGuides}
          onOpenGuide={(guide) => void handleOpenGuide(guide)}
        />
      ) : null}

      {selectedGuide ? (
        <GuideModal
          guide={selectedGuide}
          video={selectedVideo?.video}
          loading={selectedGuideLoading}
          error={selectedGuideError}
          onClose={handleCloseGuide}
        />
      ) : null}
    </div>
  );
};

export default LibraryKnowledgeGraph;
