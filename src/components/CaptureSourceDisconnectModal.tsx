import React from 'react';

interface CaptureSourceDisconnectModalProps {
  sourceTitle: string;
  isSubmitting?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export const CaptureSourceDisconnectModal: React.FC<CaptureSourceDisconnectModalProps> = ({
  sourceTitle,
  isSubmitting = false,
  onCancel,
  onConfirm,
}) => {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/35 px-4 py-8 backdrop-blur-sm">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="capture-disconnect-title"
        className="card w-full max-w-lg bg-surface p-5 shadow-lift"
      >
        <p className="eyebrow mb-2">Playlist source</p>
        <h2 id="capture-disconnect-title" className="font-serif text-3xl font-medium text-ink">
          Disconnect this playlist?
        </h2>
        <p className="mt-3 text-sm leading-6 text-bark">
          This removes {sourceTitle} from future syncs. Videos already saved or indexed stay in your
          library and can still be assigned to projects.
        </p>

        <div className="mt-5 rounded-xl bg-cream p-4">
          <p className="break-words text-sm font-semibold text-ink">{sourceTitle}</p>
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
            {isSubmitting ? 'Disconnecting...' : 'Disconnect playlist'}
          </button>
        </div>
      </section>
    </div>
  );
};
