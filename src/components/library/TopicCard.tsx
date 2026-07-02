import React from 'react';
import { LibraryGraphNode, LibraryGraphVideo } from '../../types';
import { formatTimestampLabel } from '../../lib/time';
import {
  buildTimestampUrl,
  cleanDisplayTitle,
  firstUsefulSourceRef,
  formatSourceType,
  mergedTopicCount,
} from '../../lib/videoKnowledge';

export function TopicCard({
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
      <h3 className="mt-3 text-base font-semibold leading-6 text-ink">
        {cleanDisplayTitle(idea.label)}
      </h3>
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
