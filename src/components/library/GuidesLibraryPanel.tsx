import React, { useEffect, useMemo, useState } from 'react';
import { LibraryGraphNode } from '../../types';
import {
  GuideWithVideo,
  artifactActionLabel,
  artifactKind,
  cleanDisplayTitle,
  groupGuidesByVideo,
} from '../../lib/videoKnowledge';
import { INITIAL_VISIBLE_GUIDES, LoadMoreRow, VISIBLE_BATCH_SIZE } from './shared';

export function GuidesLibraryPanel({
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
