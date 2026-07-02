import React, { useEffect, useMemo, useState } from 'react';
import { IdeaWithVideo, groupIdeasByCategory } from '../../lib/videoKnowledge';
import { TopicCard } from './TopicCard';
import { INITIAL_VISIBLE_TOPICS, LoadMoreRow, VISIBLE_BATCH_SIZE } from './shared';

export function TopicsPanel({
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
        <h2 className="font-serif text-3xl font-medium text-ink">
          No timestamped topics ready yet
        </h2>
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-bark">
          Topic cards appear after Memexai extracts source-backed moments from indexed videos.
        </p>
      </section>
    );
  }

  return (
    <section className="card p-4 sm:p-5">
      <h2 className="font-serif text-2xl font-medium text-ink">Timestamped topics by category</h2>
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
              <h3 className="text-lg font-semibold text-ink">{section.title}</h3>
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
