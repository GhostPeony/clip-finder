import React, { useEffect, useRef } from 'react';

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
  const dialogRef = useRef<HTMLElement | null>(null);
  const cancelButtonRef = useRef<HTMLButtonElement | null>(null);

  // Initial focus lands on Cancel (the safe action), focus restores on close,
  // and the page behind stops scrolling for the dialog's lifetime.
  useEffect(() => {
    const previouslyFocused =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    cancelButtonRef.current?.focus();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
      previouslyFocused?.focus();
    };
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onCancel();
        return;
      }
      if (event.key !== 'Tab') return;
      const dialog = dialogRef.current;
      if (!dialog) return;
      const focusable = dialog.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onCancel]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 px-4 py-8 backdrop-blur-sm"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !isSubmitting) onCancel();
      }}
    >
      <section
        ref={dialogRef}
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
            ref={cancelButtonRef}
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
