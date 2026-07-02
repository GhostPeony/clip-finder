import React, { useEffect, useMemo, useState } from 'react';
import { LibraryGraphNode, LibraryGraphVideo } from '../../types';
import {
  VideoKnowledge,
  artifactActionLabel,
  artifactKind,
  cleanDisplayTitle,
  formatDuration,
  formatVideoIndexedDate,
  getChannelName,
  getVideoUrl,
} from '../../lib/videoKnowledge';
import { SelectableTile } from '../ui/SelectableTile';
import { TopicCard } from './TopicCard';
import {
  EmptySection,
  INITIAL_VISIBLE_TOPICS,
  INITIAL_VISIBLE_VIDEOS,
  LoadMoreRow,
  VISIBLE_BATCH_SIZE,
} from './shared';

export function VideoLibraryPanel({
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
    <SelectableTile
      onClick={() => onSelect(item.key)}
      selected={selected}
      className="min-w-0 rounded-xl p-3 text-left transition-colors"
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
    </SelectableTile>
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
