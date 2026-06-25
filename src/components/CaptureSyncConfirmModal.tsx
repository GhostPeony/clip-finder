import React from 'react';

interface CaptureSyncConfirmModalProps {
  sourceTitle: string;
  pendingCount: number;
  isSubmitting?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export const CaptureSyncConfirmModal: React.FC<CaptureSyncConfirmModalProps> = ({
  sourceTitle,
  pendingCount,
  isSubmitting = false,
  onCancel,
  onConfirm,
}) => {
  const videoLabel = `${pendingCount} video${pendingCount === 1 ? '' : 's'}`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/35 px-4 py-8 backdrop-blur-sm">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="capture-sync-title"
        className="card w-full max-w-lg bg-surface p-5 shadow-lift"
      >
        <p className="eyebrow mb-2">Playlist sync</p>
        <h2 id="capture-sync-title" className="font-serif text-3xl font-medium text-ink">
          Import {videoLabel}?
        </h2>
        <p className="mt-3 text-sm leading-6 text-bark">
          Memexai found {videoLabel} waiting in {sourceTitle}. Queueing them starts import jobs and
          the Imports panel will show progress as each video becomes searchable.
        </p>

        <div className="mt-5 rounded-xl bg-cream p-4">
          <div className="flex items-center justify-between gap-4">
            <span className="text-sm font-semibold text-ink">Ready to queue</span>
            <span className="font-mono text-sm font-semibold text-teal-deep">{videoLabel}</span>
          </div>
        </div>

        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onCancel}
            disabled={isSubmitting}
            className="btn btn-secondary min-h-0 px-4 py-2 text-sm"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isSubmitting}
            className="btn btn-primary min-h-0 px-4 py-2 text-sm"
          >
            {isSubmitting ? 'Queueing...' : `Queue ${videoLabel}`}
          </button>
        </div>
      </section>
    </div>
  );
};
