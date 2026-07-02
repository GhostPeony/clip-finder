import React from 'react';

interface ConfirmDialogProps {
  /** Small uppercase context line above the title. */
  eyebrow?: string;
  title: string;
  body: React.ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  isSubmitting?: boolean;
  submittingLabel?: string;
  onCancel: () => void;
  onConfirm: () => void;
}

/**
 * App-rendered confirmation modal (never `window.confirm`), generalized from
 * the capture-sync confirmation flow so copy and actions match the product UI.
 */
export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  eyebrow,
  title,
  body,
  confirmLabel,
  cancelLabel = 'Cancel',
  isSubmitting = false,
  submittingLabel,
  onCancel,
  onConfirm,
}) => {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/35 px-4 py-8 backdrop-blur-sm">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        className="card w-full max-w-lg bg-surface p-5 shadow-lift"
      >
        {eyebrow ? <p className="eyebrow mb-2">{eyebrow}</p> : null}
        <h2 id="confirm-dialog-title" className="font-serif text-3xl font-medium text-ink">
          {title}
        </h2>
        <p className="mt-3 text-sm leading-6 text-bark">{body}</p>

        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onCancel}
            disabled={isSubmitting}
            className="btn btn-secondary min-h-0 px-4 py-2 text-sm"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isSubmitting}
            className="btn btn-primary min-h-0 px-4 py-2 text-sm"
          >
            {isSubmitting ? (submittingLabel ?? confirmLabel) : confirmLabel}
          </button>
        </div>
      </section>
    </div>
  );
};
