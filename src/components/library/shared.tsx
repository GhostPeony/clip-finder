import React from 'react';

export const INITIAL_VISIBLE_VIDEOS = 36;
export const INITIAL_VISIBLE_TOPICS = 48;
export const INITIAL_VISIBLE_GUIDES = 24;
export const VISIBLE_BATCH_SIZE = 24;

export function LoadMoreRow({
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

export function EmptySection({ text }: { text: string }) {
  return <p className="mt-4 rounded-xl bg-cream p-4 text-sm leading-6 text-bark">{text}</p>;
}
