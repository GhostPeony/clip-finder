import React, { useEffect, useMemo, useState } from 'react';
import {
  LibraryGraphNode,
  LibraryGraphVideo,
  LibrarySourceGraphData,
  LibrarySourceRef,
  LibraryVideo,
  VideoClip,
} from '../types';
import {
  fetchLibraryArtifact,
  fetchLibraryGraph,
  getCachedLibraryGraph,
  saveSearchToHistory,
  searchVideoClips,
} from '../services/api';
import { BrandLoader } from './BrandLoader';

interface LibraryKnowledgeGraphProps {
  activeView: 'videos' | 'topics' | 'guides';
  latestVideos: Array<LibraryVideo & { channelName: string }>;
  onIndexMore: () => void;
}

interface VideoKnowledge {
  key: string;
  video: LibraryGraphVideo;
  latest?: LibraryVideo & { channelName: string };
  guides: LibraryGraphNode[];
  ideas: LibraryGraphNode[];
}

type LibrarySearchMode = 'hybrid' | 'semantic' | 'keyword';
const LIBRARY_SEARCH_RESULT_LIMIT = 5;
const INITIAL_VISIBLE_VIDEOS = 36;
const INITIAL_VISIBLE_TOPICS = 48;
const INITIAL_VISIBLE_GUIDES = 24;
const VISIBLE_BATCH_SIZE = 24;
const MIN_BROWSABLE_TOPIC_SECONDS = 10;
const TOPIC_DEDUPE_WINDOW_SECONDS = 15;

const searchModeOptions: Array<{
  id: LibrarySearchMode;
  label: string;
  helper: string;
}> = [
  {
    id: 'hybrid',
    label: 'Smart',
    helper: 'Best first search across meaning, titles, and exact terms.',
  },
  {
    id: 'semantic',
    label: 'Meaning',
    helper: 'Use when you remember the idea but not the wording.',
  },
  { id: 'keyword', label: 'Exact', helper: 'Use for names, quotes, acronyms, and product terms.' },
];

export const LibraryKnowledgeGraph: React.FC<LibraryKnowledgeGraphProps> = ({
  activeView,
  latestVideos,
  onIndexMore,
}) => {
  const [graphData, setGraphData] = useState<LibrarySourceGraphData | null>(null);
  const [loadingGraph, setLoadingGraph] = useState(true);
  const [selectedVideoKey, setSelectedVideoKey] = useState<string | null>(null);
  const [selectedGuide, setSelectedGuide] = useState<LibraryGraphNode | null>(null);
  const [selectedGuideLoading, setSelectedGuideLoading] = useState(false);
  const [selectedGuideError, setSelectedGuideError] = useState('');
  const [videoFilter, setVideoFilter] = useState('');
  const [searchMode, setSearchMode] = useState<LibrarySearchMode>('hybrid');
  const [searchQuery, setSearchQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchAnswer, setSearchAnswer] = useState('');
  const [searchResults, setSearchResults] = useState<VideoClip[]>([]);
  const [searchError, setSearchError] = useState('');

  useEffect(() => {
    let active = true;

    const load = async () => {
      const cached = await getCachedLibraryGraph(50);
      if (!active) return;
      if (cached) {
        setGraphData(cached);
        setLoadingGraph(false);
      } else {
        setLoadingGraph(true);
      }
      const data = await fetchLibraryGraph(50);
      if (!active) return;
      setGraphData(data);
      setLoadingGraph(false);
    };

    void load();

    return () => {
      active = false;
    };
  }, []);

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

  const handleSearch = async (event: React.FormEvent) => {
    event.preventDefault();
    const trimmedQuery = searchQuery.trim();
    if (!trimmedQuery) return;

    setSearching(true);
    setSearchError('');
    setSearchAnswer('');
    setSearchResults([]);
    try {
      const { answer, relevantClips } = await searchVideoClips(
        trimmedQuery,
        LIBRARY_SEARCH_RESULT_LIMIT,
        undefined,
        searchMode,
      );
      const clips = relevantClips.filter((clip) => clip.videoId);
      setSearchAnswer(answer || '');
      setSearchResults(clips);
      if (clips.length > 0) {
        saveSearchToHistory(trimmedQuery, clips);
      }
    } catch (error) {
      setSearchError(error instanceof Error ? error.message : 'Search failed');
    } finally {
      setSearching(false);
    }
  };

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

  return (
    <div className="space-y-4 md:space-y-5">
      <LibrarySearchPanel
        mode={searchMode}
        query={searchQuery}
        searching={searching}
        answer={searchAnswer}
        results={searchResults}
        error={searchError}
        onModeChange={setSearchMode}
        onQueryChange={setSearchQuery}
        onSubmit={handleSearch}
      />

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
          onClose={() => setSelectedGuide(null)}
        />
      ) : null}
    </div>
  );
};

function LibrarySearchPanel({
  mode,
  query,
  searching,
  answer,
  results,
  error,
  onModeChange,
  onQueryChange,
  onSubmit,
}: {
  mode: LibrarySearchMode;
  query: string;
  searching: boolean;
  answer: string;
  results: VideoClip[];
  error: string;
  onModeChange: (mode: LibrarySearchMode) => void;
  onQueryChange: (query: string) => void;
  onSubmit: (event: React.FormEvent) => void;
}) {
  const selectedMode = searchModeOptions.find((option) => option.id === mode);

  return (
    <section className="card p-4 sm:p-5">
      <form onSubmit={onSubmit} className="space-y-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 className="font-serif text-3xl font-medium text-ink">Search saved videos</h2>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-bark">
              Find the video, idea, or moment you saved without pasting the link into an agent
              again.
            </p>
          </div>
          <div className="inline-flex rounded-2xl border border-ink/10 bg-cream p-1">
            {searchModeOptions.map((option) => (
              <button
                key={option.id}
                type="button"
                onClick={() => onModeChange(option.id)}
                aria-pressed={mode === option.id}
                className={`rounded-xl px-3 py-2 text-sm font-semibold transition-all ${
                  mode === option.id
                    ? 'bg-surface text-ink shadow-soft'
                    : 'text-bark hover:text-ink'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
          <label className="sr-only" htmlFor="library-search">
            Search saved videos
          </label>
          <input
            id="library-search"
            type="search"
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder={
              mode === 'keyword'
                ? 'Try an exact phrase, person, tool, acronym...'
                : 'Try a question or idea from your saved videos...'
            }
            className="input w-full px-4 py-3 text-base"
          />
          <button type="submit" disabled={searching || !query.trim()} className="btn btn-primary">
            {searching ? 'Searching...' : 'Search'}
          </button>
        </div>

        {selectedMode ? (
          <p className="text-xs font-medium text-muted">{selectedMode.helper}</p>
        ) : null}
      </form>

      <LibrarySearchResults answer={answer} results={results} error={error} searching={searching} />
    </section>
  );
}

function LibrarySearchResults({
  answer,
  results,
  error,
  searching,
}: {
  answer: string;
  results: VideoClip[];
  error: string;
  searching: boolean;
}) {
  if (searching) {
    return (
      <div className="mt-4 rounded-xl bg-cream p-4">
        <BrandLoader compact label="Searching saved videos" />
      </div>
    );
  }

  if (error) {
    return (
      <p className="mt-4 rounded-xl bg-rose/10 p-4 text-sm font-medium text-rose-deep">{error}</p>
    );
  }

  if (!answer && results.length === 0) return null;

  return (
    <div className="mt-4 space-y-3">
      {answer ? (
        <div className="rounded-xl bg-cream p-4">
          <h3 className="text-sm font-semibold text-ink">Answer</h3>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-bark">{answer}</p>
        </div>
      ) : null}

      {results.length > 0 ? (
        <div className="grid gap-3 md:grid-cols-2">
          {results.map((clip, index) => (
            <a
              key={`${clip.videoId}-${clip.startSeconds}-${index}`}
              href={buildTimestampUrl(
                { videoId: clip.videoId, title: clip.title },
                clip.startSeconds,
              )}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-xl bg-cream p-3 transition-colors hover:bg-petal/60"
            >
              <div className="flex gap-3">
                <img
                  src={clip.thumbnailUrl}
                  alt=""
                  className="aspect-video w-24 shrink-0 rounded-lg object-cover shadow-soft"
                />
                <div className="min-w-0">
                  <p className="line-clamp-2 text-sm font-semibold text-ink">{clip.title}</p>
                  <p className="mt-1 truncate text-xs text-muted">
                    {clip.channelName} · {formatTimestampLabel(clip.startSeconds)}
                  </p>
                  <p className="mt-2 line-clamp-2 text-xs leading-5 text-bark">
                    {clip.matchSnippet || clip.content}
                  </p>
                </div>
              </div>
            </a>
          ))}
        </div>
      ) : null}
    </div>
  );
}

interface IdeaWithVideo {
  idea: LibraryGraphNode;
  video: LibraryGraphVideo;
  videoKey: string;
}

interface GuideWithVideo {
  guide: LibraryGraphNode;
  video: LibraryGraphVideo;
}

interface TopicSection {
  id: string;
  title: string;
  items: IdeaWithVideo[];
}

interface GuideVideoSection {
  key: string;
  video: LibraryGraphVideo;
  guides: LibraryGraphNode[];
}

function VideoLibraryPanel({
  videos,
  selectedVideo,
  selectedVideoKey,
  filter,
  onFilterChange,
  onSelect,
  onOpenGuide,
}: {
  videos: VideoKnowledge[];
  selectedVideo: VideoKnowledge | null;
  selectedVideoKey: string;
  filter: string;
  onFilterChange: (value: string) => void;
  onSelect: (key: string) => void;
  onOpenGuide: (guide: LibraryGraphNode) => void;
}) {
  const [visibleCount, setVisibleCount] = useState(INITIAL_VISIBLE_VIDEOS);
  const filteredVideos = useMemo(() => {
    const query = filter.trim().toLowerCase();
    if (!query) return videos;
    return videos.filter((item) =>
      [item.video.title, getChannelName(item.video, item.latest)]
        .join(' ')
        .toLowerCase()
        .includes(query),
    );
  }, [filter, videos]);
  const visibleVideos = filteredVideos.slice(0, visibleCount);

  useEffect(() => {
    setVisibleCount(INITIAL_VISIBLE_VIDEOS);
  }, [filter, videos.length]);

  return (
    <div className="space-y-4">
      <section className="card p-4 sm:p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h3 className="font-serif text-2xl font-medium text-ink">Saved videos</h3>
            <p className="mt-1 text-sm leading-6 text-bark">
              Browse your indexed videos without crowding the page as the library grows.
            </p>
          </div>
          <label className="sr-only" htmlFor="saved-video-filter">
            Filter saved videos
          </label>
          <input
            id="saved-video-filter"
            type="search"
            value={filter}
            onChange={(event) => onFilterChange(event.target.value)}
            placeholder="Filter by title or channel..."
            className="input w-full px-3 py-2 text-sm sm:w-72"
          />
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {visibleVideos.map((item) => (
            <VideoSelectCard
              key={item.key}
              item={item}
              selected={item.key === selectedVideoKey}
              onSelect={onSelect}
            />
          ))}
        </div>

        <LoadMoreRow
          total={filteredVideos.length}
          visible={visibleVideos.length}
          label="saved videos"
          onLoadMore={() =>
            setVisibleCount((current) =>
              Math.min(current + VISIBLE_BATCH_SIZE, filteredVideos.length),
            )
          }
        />

        {filteredVideos.length === 0 ? (
          <p className="mt-4 rounded-xl bg-cream p-4 text-sm leading-6 text-bark">
            No saved videos match that filter.
          </p>
        ) : null}
      </section>

      {selectedVideo ? (
        <>
          <SelectedVideoPanel item={selectedVideo} />
          <GuidesPanel guides={selectedVideo.guides} onOpenGuide={onOpenGuide} />
          <IdeasPanel ideas={selectedVideo.ideas} video={selectedVideo.video} />
        </>
      ) : null}
    </div>
  );
}

function VideoSelectCard({
  item,
  selected,
  onSelect,
}: {
  item: VideoKnowledge;
  selected: boolean;
  onSelect: (key: string) => void;
}) {
  const channelName = getChannelName(item.video, item.latest);
  const topicCount = item.ideas.length;
  const reportCount = item.guides.length;
  const indexedDate = formatVideoIndexedDate(item.video, item.latest);

  return (
    <button
      type="button"
      onClick={() => onSelect(item.key)}
      className={`min-w-0 rounded-xl p-3 text-left transition-colors ${
        selected ? 'bg-surface shadow-soft' : 'bg-cream hover:bg-petal/50'
      }`}
    >
      <div className="flex gap-3">
        {item.video.thumbnailUrl ? (
          <img
            src={item.video.thumbnailUrl}
            alt=""
            className="aspect-video w-24 shrink-0 rounded-lg object-cover shadow-soft"
          />
        ) : (
          <div className="flex aspect-video w-24 shrink-0 items-center justify-center rounded-lg bg-petal text-xs text-muted">
            Video
          </div>
        )}
        <div className="min-w-0">
          <p className="line-clamp-2 text-sm font-semibold text-ink">{item.video.title}</p>
          <p className="mt-1 truncate text-xs text-muted">
            {[channelName, indexedDate].filter(Boolean).join(' · ')}
          </p>
          <p className="mt-2 text-xs text-bark">
            {reportCount} report{reportCount === 1 ? '' : 's'} · {topicCount} timestamped topic
            {topicCount === 1 ? '' : 's'}
          </p>
        </div>
      </div>
    </button>
  );
}

function SelectedVideoPanel({ item }: { item: VideoKnowledge }) {
  const { video, latest } = item;
  const channelName = getChannelName(video, latest);
  const youtubeUrl = getVideoUrl(video);
  const indexedDate = formatVideoIndexedDate(video, latest);

  return (
    <section className="card overflow-hidden p-4 sm:p-5">
      <div className="grid gap-4 md:grid-cols-[220px_minmax(0,1fr)]">
        {video.thumbnailUrl ? (
          <img
            src={video.thumbnailUrl}
            alt=""
            className="aspect-video w-full rounded-xl object-cover shadow-soft"
          />
        ) : (
          <div className="flex aspect-video w-full items-center justify-center rounded-xl bg-petal text-sm text-muted">
            Video preview
          </div>
        )}
        <div className="min-w-0">
          <h3 className="font-serif text-3xl font-medium leading-tight text-ink">{video.title}</h3>
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-sm text-bark">
            {channelName ? <span>{channelName}</span> : null}
            {indexedDate ? <span>{indexedDate}</span> : null}
            {video.transcriptSeconds ? (
              <span>{formatDuration(video.transcriptSeconds)} transcript</span>
            ) : null}
          </div>
          {youtubeUrl ? (
            <a
              href={youtubeUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="link-quiet mt-4 inline-flex text-sm"
            >
              Open on YouTube
            </a>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function GuidesPanel({
  guides,
  onOpenGuide,
}: {
  guides: LibraryGraphNode[];
  onOpenGuide: (guide: LibraryGraphNode) => void;
}) {
  return (
    <section className="card p-4 sm:p-5">
      <h3 className="font-serif text-2xl font-medium text-ink">TLDR and source reports</h3>
      <p className="mt-1 text-sm leading-6 text-bark">
        Read the short summary or the full source-backed report Memexai created from this video.
      </p>

      {guides.length === 0 ? (
        <EmptySection text="No report is available yet. The video is still searchable while generated knowledge is prepared." />
      ) : (
        <div className="mt-4 grid gap-3">
          {guides.map((guide) => (
            <article key={guide.id} className="rounded-xl bg-cream p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted">
                {artifactKind(guide)}
              </p>
              <h4 className="mt-1 text-lg font-semibold leading-6 text-ink">
                {cleanDisplayTitle(guide.label)}
              </h4>
              {guide.summary ? (
                <p className="mt-3 line-clamp-3 text-sm leading-7 text-bark">{guide.summary}</p>
              ) : null}
              <button
                type="button"
                onClick={() => onOpenGuide(guide)}
                className="link-quiet mt-4 inline-flex text-sm"
              >
                {artifactActionLabel(guide)}
              </button>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function IdeasPanel({ ideas, video }: { ideas: LibraryGraphNode[]; video: LibraryGraphVideo }) {
  const [visibleCount, setVisibleCount] = useState(INITIAL_VISIBLE_TOPICS);
  const visibleIdeas = ideas.slice(0, visibleCount);

  useEffect(() => {
    setVisibleCount(INITIAL_VISIBLE_TOPICS);
  }, [ideas.length, video.videoId]);

  return (
    <section className="card p-4 sm:p-5">
      <h3 className="font-serif text-2xl font-medium text-ink">Timestamped topics</h3>
      <p className="mt-1 text-sm leading-6 text-bark">
        Source-backed topics with a snippet and a direct jump to the supporting moment.
      </p>

      {ideas.length === 0 ? (
        <EmptySection text="No timestamped topics are available for this video yet." />
      ) : (
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {visibleIdeas.map((idea) => (
            <TopicCard key={idea.id} idea={idea} video={video} />
          ))}
        </div>
      )}

      <LoadMoreRow
        total={ideas.length}
        visible={visibleIdeas.length}
        label="topics"
        onLoadMore={() =>
          setVisibleCount((current) => Math.min(current + VISIBLE_BATCH_SIZE, ideas.length))
        }
      />
    </section>
  );
}

function TopicsPanel({
  ideas,
  onSelectVideo,
}: {
  ideas: IdeaWithVideo[];
  onSelectVideo: (key: string) => void;
}) {
  const [visibleCount, setVisibleCount] = useState(INITIAL_VISIBLE_TOPICS);
  const visibleIdeas = useMemo(() => ideas.slice(0, visibleCount), [ideas, visibleCount]);
  const sections = useMemo(() => groupIdeasByCategory(visibleIdeas), [visibleIdeas]);

  useEffect(() => {
    setVisibleCount(INITIAL_VISIBLE_TOPICS);
  }, [ideas.length]);

  if (ideas.length === 0) {
    return (
      <section className="card p-8 text-center">
        <h3 className="font-serif text-3xl font-medium text-ink">
          No timestamped topics ready yet
        </h3>
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-bark">
          Topic cards appear after Memexai extracts source-backed moments from indexed videos.
        </p>
      </section>
    );
  }

  return (
    <section className="card p-4 sm:p-5">
      <h3 className="font-serif text-2xl font-medium text-ink">Timestamped topics by category</h3>
      <p className="mt-1 text-sm leading-6 text-bark">
        Deduped source moments grouped by what they are, with the source video on every card.
      </p>

      <div className="mt-5 space-y-6">
        {sections.map((section) => (
          <section
            key={section.id}
            className="border-t border-ink/10 pt-4 first:border-t-0 first:pt-0"
          >
            <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
              <h4 className="text-lg font-semibold text-ink">{section.title}</h4>
              <p className="text-xs font-medium text-muted">
                {section.items.length} moment{section.items.length === 1 ? '' : 's'}
              </p>
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              {section.items.map(({ idea, video, videoKey }) => (
                <TopicCard
                  key={`${videoKey}-${idea.id}`}
                  idea={idea}
                  video={video}
                  showVideoTitle
                  footer={
                    <button
                      type="button"
                      onClick={() => onSelectVideo(videoKey)}
                      className="link-quiet mt-3 inline-flex text-xs"
                    >
                      View video breakdown
                    </button>
                  }
                />
              ))}
            </div>
          </section>
        ))}
      </div>
      <LoadMoreRow
        total={ideas.length}
        visible={visibleIdeas.length}
        label="topics"
        onLoadMore={() =>
          setVisibleCount((current) => Math.min(current + VISIBLE_BATCH_SIZE, ideas.length))
        }
      />
    </section>
  );
}

function TopicCard({
  idea,
  video,
  footer,
  showVideoTitle = false,
}: {
  idea: LibraryGraphNode;
  video: LibraryGraphVideo;
  footer?: React.ReactNode;
  showVideoTitle?: boolean;
}) {
  const source = firstUsefulSourceRef(idea.sourceRefs || []);
  const seconds = source?.start_seconds ?? null;
  const href =
    source && typeof seconds === 'number'
      ? buildTimestampUrl(
          {
            ...video,
            videoId: source.youtube_video_id || source.source_id || video.videoId,
          },
          seconds,
        )
      : '';
  const topicType = String(idea.metadata?.conceptType || 'topic');
  if (!href || typeof seconds !== 'number') return null;

  return (
    <article className="rounded-xl bg-cream p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">
          {formatSourceType(topicType)}
        </p>
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center rounded-lg bg-surface px-2 py-1 font-mono text-xs font-semibold text-rose-deep shadow-soft transition-colors hover:bg-petal"
        >
          Open at {formatTimestampLabel(seconds)}
        </a>
      </div>
      <h4 className="mt-3 text-base font-semibold leading-6 text-ink">
        {cleanDisplayTitle(idea.label)}
      </h4>
      {showVideoTitle ? (
        <p className="mt-1 line-clamp-2 text-xs font-medium text-muted">From {video.title}</p>
      ) : null}
      {idea.summary ? <p className="mt-2 text-sm leading-6 text-bark">{idea.summary}</p> : null}
      {mergedTopicCount(idea) > 1 ? (
        <p className="mt-3 text-xs leading-5 text-muted">
          Merged {mergedTopicCount(idea)} extracted ideas from this same source moment.
        </p>
      ) : null}
      {source?.quote ? (
        <p className="mt-3 border-l-2 border-rose/40 pl-3 text-sm leading-6 text-muted">
          {source.quote}
        </p>
      ) : null}
      {footer}
    </article>
  );
}

function GuidesLibraryPanel({
  guides,
  onOpenGuide,
}: {
  guides: GuideWithVideo[];
  onOpenGuide: (guide: LibraryGraphNode) => void;
}) {
  const [visibleCount, setVisibleCount] = useState(INITIAL_VISIBLE_GUIDES);
  const visibleGuides = useMemo(() => guides.slice(0, visibleCount), [guides, visibleCount]);
  const videoSections = useMemo(() => groupGuidesByVideo(visibleGuides), [visibleGuides]);

  useEffect(() => {
    setVisibleCount(INITIAL_VISIBLE_GUIDES);
  }, [guides.length]);

  if (guides.length === 0) {
    return (
      <section className="card p-8 text-center">
        <h3 className="font-serif text-3xl font-medium text-ink">No reports ready yet</h3>
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-bark">
          TLDRs and full source reports appear here after standard or deep digestion completes.
        </p>
      </section>
    );
  }

  return (
    <section className="card p-4 sm:p-5">
      <h3 className="font-serif text-2xl font-medium text-ink">Reports by video</h3>
      <p className="mt-1 text-sm leading-6 text-bark">
        Each saved video gets one report shelf with its TLDR and source report together.
      </p>

      <div className="mt-4 space-y-4">
        {videoSections.map((section) => (
          <article key={section.key} className="rounded-xl bg-cream p-4">
            <div className="grid gap-4 md:grid-cols-[150px_minmax(0,1fr)]">
              {section.video.thumbnailUrl ? (
                <img
                  src={section.video.thumbnailUrl}
                  alt=""
                  className="aspect-video w-full rounded-lg object-cover shadow-soft"
                />
              ) : (
                <div className="flex aspect-video w-full items-center justify-center rounded-lg bg-petal text-xs text-muted">
                  Video
                </div>
              )}
              <div className="min-w-0">
                <h4 className="line-clamp-2 text-lg font-semibold leading-6 text-ink">
                  {section.video.title}
                </h4>
                <p className="mt-1 text-xs text-muted">
                  {section.guides.length} generated artifact
                  {section.guides.length === 1 ? '' : 's'}
                </p>
                <div className="mt-3 grid gap-2">
                  {section.guides.map((guide) => (
                    <div
                      key={guide.id}
                      className="flex flex-col gap-2 rounded-lg bg-surface px-3 py-3 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="min-w-0">
                        <p className="text-xs font-semibold uppercase tracking-wide text-muted">
                          {artifactKind(guide)}
                        </p>
                        <p className="mt-1 line-clamp-2 text-sm font-semibold text-ink">
                          {cleanDisplayTitle(guide.label)}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => onOpenGuide(guide)}
                        className="link-quiet self-start text-sm sm:self-auto"
                      >
                        {artifactActionLabel(guide)}
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </article>
        ))}
      </div>
      <LoadMoreRow
        total={guides.length}
        visible={visibleGuides.length}
        label="reports"
        onLoadMore={() =>
          setVisibleCount((current) => Math.min(current + VISIBLE_BATCH_SIZE, guides.length))
        }
      />
    </section>
  );
}

function LoadMoreRow({
  total,
  visible,
  label,
  onLoadMore,
}: {
  total: number;
  visible: number;
  label: string;
  onLoadMore: () => void;
}) {
  if (visible >= total) return null;

  return (
    <div className="mt-4 flex flex-col gap-3 border-t border-ink/10 pt-4 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-sm text-muted">
        Showing {visible} of {total} {label}
      </p>
      <button type="button" onClick={onLoadMore} className="btn btn-secondary self-start">
        Load more
      </button>
    </div>
  );
}

function GuideModal({
  guide,
  video,
  loading,
  error,
  onClose,
}: {
  guide: LibraryGraphNode;
  video?: LibraryGraphVideo;
  loading: boolean;
  error: string;
  onClose: () => void;
}) {
  const youtubeUrl = getVideoUrl(guide.video || video || { title: '' });

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-end bg-ink/40 p-3 backdrop-blur-sm sm:items-center sm:justify-center sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="guide-modal-title"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section className="card max-h-[88vh] w-full max-w-3xl overflow-y-auto bg-surface p-5 sm:p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted">
              {artifactKind(guide)}
            </p>
            <h2 id="guide-modal-title" className="mt-1 font-serif text-3xl font-medium text-ink">
              {cleanDisplayTitle(guide.label)}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-2 text-muted hover:bg-cream hover:text-ink"
            aria-label="Close report"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {loading ? (
          <div className="mt-5 rounded-xl bg-cream p-4">
            <BrandLoader compact label="Loading full report" />
          </div>
        ) : error ? (
          <p className="mt-5 rounded-xl bg-rose/10 p-4 text-sm font-medium text-rose-deep">
            {error}
          </p>
        ) : guide.content || guide.summary ? (
          <ReportContent
            content={guide.content || guide.summary || ''}
            video={guide.video || video}
          />
        ) : (
          <p className="mt-5 rounded-xl bg-cream p-4 text-sm leading-6 text-bark">
            This report does not have readable text yet.
          </p>
        )}

        {youtubeUrl ? (
          <a
            href={youtubeUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-secondary mt-6 inline-flex"
          >
            Open source video
          </a>
        ) : null}
      </section>
    </div>
  );
}

function EmptySection({ text }: { text: string }) {
  return <p className="mt-4 rounded-xl bg-cream p-4 text-sm leading-6 text-bark">{text}</p>;
}

function buildVideoKnowledge(
  graphData: LibrarySourceGraphData | null,
  latestVideos: Array<LibraryVideo & { channelName: string }>,
): VideoKnowledge[] {
  const latestByKey = new Map(
    latestVideos.flatMap((video) => {
      const keys = new Set([video.videoId, normalizeVideoKey(video.videoId)]);
      return Array.from(keys).map((key) => [key, video] as const);
    }),
  );

  const maps = new Map<string, VideoKnowledge>();

  const ensureMap = (video: LibraryGraphVideo): VideoKnowledge | null => {
    const key = normalizeVideoKey(video.videoId || video.id || video.youtubeUrl || video.title);
    if (!key) return null;
    const latest =
      latestByKey.get(key) || (video.videoId ? latestByKey.get(video.videoId) : undefined);
    const existing = maps.get(key);
    if (existing) {
      existing.video = mergeVideoData(video, existing.latest || latest);
      return existing;
    }

    const sourceMap: VideoKnowledge = {
      key,
      video: mergeVideoData(video, latest),
      latest,
      guides: [],
      ideas: [],
    };
    maps.set(key, sourceMap);
    return sourceMap;
  };

  latestVideos.forEach((video) => {
    ensureMap({
      videoId: video.videoId,
      title: video.title,
      thumbnailUrl: video.thumbnailUrl,
      transcriptSeconds: video.transcriptSeconds || null,
      channel: { name: video.channelName },
      accessSource: video.accessSource,
      accessReason: video.accessReason,
    });
  });

  graphData?.videos.forEach((video) => {
    ensureMap(video);
  });

  graphData?.graph.nodes.forEach((node) => {
    if (node.type !== 'source_concept' && node.type !== 'knowledge_artifact') return;
    const map = findMapForNode(node, maps);
    if (!map) return;
    if (node.type === 'source_concept' && isBrowsableTopic(node)) {
      map.ideas.push(node);
    }
    if (node.type === 'knowledge_artifact') map.guides.push(node);
  });

  maps.forEach((item) => {
    item.ideas = dedupeTopicsBySourceMoment(item.ideas);
    item.guides = sortGuides(item.guides);
  });

  return Array.from(maps.values()).sort((a, b) => {
    const aIndexed = Date.parse(a.video.indexedAt || '') || a.latest?.indexedAt || 0;
    const bIndexed = Date.parse(b.video.indexedAt || '') || b.latest?.indexedAt || 0;
    return bIndexed - aIndexed;
  });
}

function flattenIdeas(items: VideoKnowledge[]): IdeaWithVideo[] {
  return items.flatMap((item) =>
    item.ideas.map((idea) => ({
      idea,
      video: item.video,
      videoKey: item.key,
    })),
  );
}

function flattenGuides(items: VideoKnowledge[]): GuideWithVideo[] {
  return items.flatMap((item) =>
    item.guides.map((guide) => ({
      guide,
      video: item.video,
    })),
  );
}

function groupIdeasByCategory(ideas: IdeaWithVideo[]): TopicSection[] {
  const sections = new Map<string, TopicSection>();
  ideas.forEach((item) => {
    const category = topicCategory(item.idea);
    const existing = sections.get(category.id);
    if (existing) {
      existing.items.push(item);
    } else {
      sections.set(category.id, { ...category, items: [item] });
    }
  });

  return Array.from(sections.values()).sort((a, b) => {
    const order = topicCategoryOrder(a.id) - topicCategoryOrder(b.id);
    if (order !== 0) return order;
    return a.title.localeCompare(b.title);
  });
}

function groupGuidesByVideo(guides: GuideWithVideo[]): GuideVideoSection[] {
  const sections = new Map<string, GuideVideoSection>();
  guides.forEach(({ guide, video }) => {
    const key = normalizeVideoKey(video.videoId || video.id || video.youtubeUrl || video.title);
    if (!key) return;
    const existing = sections.get(key);
    if (existing) {
      existing.guides.push(guide);
    } else {
      sections.set(key, { key, video, guides: [guide] });
    }
  });

  return Array.from(sections.values()).map((section) => ({
    ...section,
    guides: sortGuides(section.guides),
  }));
}

function isBrowsableTopic(idea: LibraryGraphNode): boolean {
  const source = firstUsefulSourceRef(idea.sourceRefs || []);
  if (!source || typeof source.start_seconds !== 'number') return false;
  return source.start_seconds >= MIN_BROWSABLE_TOPIC_SECONDS;
}

function dedupeTopicsBySourceMoment(ideas: LibraryGraphNode[]): LibraryGraphNode[] {
  const groups = new Map<string, LibraryGraphNode[]>();
  ideas.forEach((idea) => {
    const source = firstUsefulSourceRef(idea.sourceRefs || []);
    if (!source || typeof source.start_seconds !== 'number') return;
    const videoKey = normalizeVideoKey(
      source.youtube_video_id || source.source_id || idea.video?.videoId || idea.video?.youtubeUrl,
    );
    const bucket = Math.floor(source.start_seconds / TOPIC_DEDUPE_WINDOW_SECONDS);
    const key = `${videoKey || 'video'}:${bucket}`;
    groups.set(key, [...(groups.get(key) || []), idea]);
  });

  return Array.from(groups.values()).flatMap((group) => {
    const [best, ...merged] = group;
    if (!best) return [];
    if (merged.length === 0) return [best];
    return [
      {
        ...best,
        metadata: {
          ...best.metadata,
          mergedTopicCount: group.length,
        },
      },
    ];
  });
}

function sortGuides(guides: LibraryGraphNode[]): LibraryGraphNode[] {
  return [...guides].sort((a, b) => artifactKindOrder(a) - artifactKindOrder(b));
}

function findMapForNode(
  node: LibraryGraphNode,
  maps: Map<string, VideoKnowledge>,
): VideoKnowledge | null {
  const candidates = [
    node.video?.videoId,
    node.video?.id,
    node.video?.youtubeUrl,
    ...(node.sourceRefs || []).flatMap((ref) => [
      ref.youtube_video_id,
      ref.source_id,
      typeof ref.source_id === 'string' ? extractVideoId(ref.source_id) : '',
    ]),
  ]
    .map((value) => normalizeVideoKey(value || ''))
    .filter(Boolean);

  for (const candidate of candidates) {
    const sourceMap = maps.get(candidate);
    if (sourceMap) return sourceMap;
  }

  if (maps.size === 1) return Array.from(maps.values())[0];
  return null;
}

function mergeVideoData(
  video: LibraryGraphVideo,
  latest?: LibraryVideo & { channelName: string },
): LibraryGraphVideo {
  return {
    ...video,
    videoId: video.videoId || latest?.videoId,
    title: video.title || latest?.title || 'Saved video',
    thumbnailUrl: video.thumbnailUrl || latest?.thumbnailUrl || null,
    transcriptSeconds: video.transcriptSeconds || latest?.transcriptSeconds || null,
    indexedAt: video.indexedAt || normalizeIndexedAt(latest?.indexedAt),
    channel: {
      ...video.channel,
      name: video.channel?.name || latest?.channelName || null,
    },
    accessSource: video.accessSource || latest?.accessSource,
    accessReason: video.accessReason || latest?.accessReason,
  };
}

function getChannelName(
  video: LibraryGraphVideo,
  latest?: LibraryVideo & { channelName: string },
): string {
  return video.channel?.name || latest?.channelName || '';
}

function formatVideoIndexedDate(
  video: LibraryGraphVideo,
  latest?: LibraryVideo & { channelName: string },
): string {
  const timestamp = videoIndexedTimestamp(video, latest);
  if (!timestamp) return '';
  return `Indexed ${new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date(timestamp))}`;
}

function videoIndexedTimestamp(
  video: LibraryGraphVideo,
  latest?: LibraryVideo & { channelName: string },
): number | null {
  const parsedVideoDate = Date.parse(video.indexedAt || '');
  if (Number.isFinite(parsedVideoDate) && parsedVideoDate > 0) return parsedVideoDate;
  return normalizeIndexedTimestamp(latest?.indexedAt);
}

function normalizeIndexedAt(value?: number): string | null {
  const timestamp = normalizeIndexedTimestamp(value);
  return timestamp ? new Date(timestamp).toISOString() : null;
}

function normalizeIndexedTimestamp(value?: number): number | null {
  if (!value) return null;
  return value < 100000000000 ? value * 1000 : value;
}

function getVideoUrl(video: LibraryGraphVideo): string {
  if (video.youtubeUrl) return video.youtubeUrl;
  if (video.videoId) return `https://www.youtube.com/watch?v=${extractVideoId(video.videoId)}`;
  return '';
}

function buildTimestampUrl(video: LibraryGraphVideo | undefined, seconds: number): string {
  const videoId = extractVideoId(video?.videoId || video?.youtubeUrl || '');
  if (!videoId) return getVideoUrl(video || { title: '' });
  return `https://www.youtube.com/watch?v=${videoId}&t=${Math.max(0, Math.floor(seconds))}`;
}

function firstUsefulSourceRef(refs: LibrarySourceRef[]): LibrarySourceRef | null {
  return (
    refs.find((ref) => typeof ref.start_seconds === 'number' && ref.start_seconds >= 0) || null
  );
}

function cleanDisplayTitle(title: string): string {
  return title
    .replace(/^study guide:\s*/i, '')
    .replace(/^source report:\s*/i, '')
    .replace(/^implementation brief:\s*/i, '')
    .replace(/^tldr:\s*/i, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function artifactKind(node: LibraryGraphNode): string {
  const kind = String(node.metadata?.artifactType || '');
  if (kind === 'tldr') return 'TLDR';
  if (kind === 'study_guide' || kind === 'source_report') return 'Source report';
  if (kind) return formatSourceType(kind);
  if (/source report/i.test(node.label)) return 'Source report';
  if (/study guide/i.test(node.label)) return 'Source report';
  if (/tldr/i.test(node.label)) return 'TLDR';
  if (/brief/i.test(node.label)) return 'Implementation brief';
  return 'Generated report';
}

function artifactActionLabel(node: LibraryGraphNode): string {
  const kind = artifactKind(node);
  if (kind === 'TLDR') return 'Read TLDR';
  if (kind === 'Source report') return 'Read report';
  return 'Read artifact';
}

function artifactKindOrder(node: LibraryGraphNode): number {
  const kind = artifactKind(node);
  if (kind === 'TLDR') return 0;
  if (kind === 'Source report') return 1;
  return 2;
}

function topicCategory(node: LibraryGraphNode): { id: string; title: string } {
  const type = String(node.metadata?.conceptType || 'concept').toLowerCase();
  if (['method', 'algorithm', 'tool'].includes(type)) {
    return { id: 'methods', title: 'Methods, tools, and systems' };
  }
  if (type === 'implementation_note') {
    return { id: 'practical', title: 'Practical notes' };
  }
  if (type === 'claim') {
    return { id: 'claims', title: 'Claims and takeaways' };
  }
  if (type === 'pitfall') {
    return { id: 'warnings', title: 'Warnings and caveats' };
  }
  if (type === 'entity') {
    return { id: 'entities', title: 'People, organizations, and named things' };
  }
  return { id: 'concepts', title: 'Concepts and themes' };
}

function topicCategoryOrder(id: string): number {
  const order = ['methods', 'practical', 'claims', 'warnings', 'entities', 'concepts'];
  const index = order.indexOf(id);
  return index === -1 ? order.length : index;
}

function mergedTopicCount(node: LibraryGraphNode): number {
  const value = node.metadata?.mergedTopicCount;
  return typeof value === 'number' && Number.isFinite(value) ? value : 1;
}

function normalizeVideoKey(value: string | null | undefined): string {
  if (!value) return '';
  return extractVideoId(value) || value.trim();
}

function extractVideoId(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return '';
  if (/^[a-zA-Z0-9_-]{6,}$/.test(trimmed) && !trimmed.includes('/')) return trimmed;
  try {
    const normalized = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
    const url = new URL(normalized);
    if (url.hostname.includes('youtu.be')) return url.pathname.replace('/', '').split('/')[0] || '';
    return url.searchParams.get('v') || url.pathname.split('/').filter(Boolean).pop() || '';
  } catch {
    return trimmed;
  }
}

function formatDuration(seconds: number): string {
  if (!seconds || seconds < 60) return `${Math.max(0, Math.round(seconds || 0))}s`;
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

function formatTimestampLabel(seconds: number): string {
  const safeSeconds = Math.max(0, Math.floor(seconds || 0));
  if (safeSeconds === 0) return 'Start of video';
  const hours = Math.floor(safeSeconds / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);
  const remainingSeconds = safeSeconds % 60;
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${remainingSeconds
      .toString()
      .padStart(2, '0')}`;
  }
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
}

function formatSourceType(value: string): string {
  return value.replace(/[_-]+/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

interface ReportBlock {
  type: 'heading' | 'paragraph' | 'list';
  level?: number;
  text?: string;
  items?: string[];
}

function ReportContent({ content, video }: { content: string; video?: LibraryGraphVideo }) {
  const blocks = parseReportMarkdown(content);

  return (
    <div className="mt-5 space-y-5 text-bark">
      {blocks.map((block, index) => {
        if (block.type === 'heading') {
          const HeadingTag = block.level === 1 ? 'h3' : 'h4';
          return (
            <HeadingTag
              key={`heading-${index}`}
              className={
                block.level === 1
                  ? 'font-serif text-2xl font-medium leading-tight text-ink'
                  : 'pt-2 text-sm font-semibold uppercase tracking-wide text-muted'
              }
            >
              {block.text}
            </HeadingTag>
          );
        }

        if (block.type === 'list') {
          return (
            <ul key={`list-${index}`} className="space-y-3">
              {(block.items || []).map((item, itemIndex) => (
                <li
                  key={`${index}-${itemIndex}`}
                  className="border-l-2 border-rose/30 pl-4 text-base leading-8 text-bark"
                >
                  {renderReportInlineText(item, video)}
                </li>
              ))}
            </ul>
          );
        }

        return (
          <p key={`paragraph-${index}`} className="text-base leading-8 text-bark">
            {renderReportInlineText(block.text || '', video)}
          </p>
        );
      })}
    </div>
  );
}

function parseReportMarkdown(content: string): ReportBlock[] {
  const blocks: ReportBlock[] = [];
  const lines = content.split(/\r?\n/);
  let paragraph: string[] = [];
  let listItems: string[] = [];

  const flushParagraph = () => {
    if (paragraph.length === 0) return;
    blocks.push({ type: 'paragraph', text: paragraph.join(' ').trim() });
    paragraph = [];
  };

  const flushList = () => {
    if (listItems.length === 0) return;
    blocks.push({ type: 'list', items: listItems });
    listItems = [];
  };

  lines.forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed) {
      flushParagraph();
      flushList();
      return;
    }

    const heading = /^(#{1,3})\s+(.+)$/.exec(trimmed);
    if (heading) {
      flushParagraph();
      flushList();
      blocks.push({
        type: 'heading',
        level: heading[1].length,
        text: heading[2].trim(),
      });
      return;
    }

    const bullet = /^[-*]\s+(.+)$/.exec(trimmed);
    if (bullet) {
      flushParagraph();
      listItems.push(bullet[1].trim());
      return;
    }

    flushList();
    paragraph.push(trimmed);
  });

  flushParagraph();
  flushList();
  return blocks;
}

function renderReportInlineText(text: string, video?: LibraryGraphVideo): React.ReactNode {
  const pieces: React.ReactNode[] = [];
  const sourcePattern = /\(source:\s*([^)]+)\)/gi;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = sourcePattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      pieces.push(text.slice(lastIndex, match.index));
    }

    const timestampLinks = match[1]
      .split(',')
      .map((label) => label.trim())
      .map((label) => ({ label, seconds: parseTimestampToSeconds(label) }))
      .filter((item): item is { label: string; seconds: number } => item.seconds !== null);

    if (timestampLinks.length > 0) {
      pieces.push(
        <span key={`source-${match.index}`} className="inline-flex flex-wrap gap-1 align-baseline">
          {timestampLinks.map(({ label, seconds }) => (
            <a
              key={`${match.index}-${label}`}
              href={buildTimestampUrl(video, seconds)}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex rounded-lg bg-petal px-2 py-0.5 font-mono text-xs font-semibold text-rose-deep transition-colors hover:bg-rose/15"
            >
              source {formatTimestampLabel(seconds)}
            </a>
          ))}
        </span>,
      );
    } else {
      pieces.push(match[0]);
    }
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    pieces.push(text.slice(lastIndex));
  }

  return pieces.length > 0 ? pieces : text;
}

function parseTimestampToSeconds(label: string): number | null {
  const cleaned = label
    .trim()
    .replace(/^source\s*/i, '')
    .replace(/[^\d:]/g, '');
  if (!cleaned) return null;
  const parts = cleaned.split(':').map((part) => Number(part));
  if (parts.some((part) => Number.isNaN(part))) return null;
  if (parts.length === 1) return parts[0];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  return null;
}

export default LibraryKnowledgeGraph;
