import React, { useEffect, useRef } from 'react';
import { LibraryGraphNode, LibraryGraphVideo } from '../../types';
import { ReportContent } from '../../lib/reportMarkdown';
import { artifactKind, cleanDisplayTitle, getVideoUrl } from '../../lib/videoKnowledge';
import { BrandLoader } from '../BrandLoader';

export function GuideModal({
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
  const modalRef = useRef<HTMLElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);

  // Initial focus, focus restore, and body scroll lock for the modal's lifetime.
  useEffect(() => {
    const previouslyFocused =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeButtonRef.current?.focus();
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
        onClose();
        return;
      }
      if (event.key !== 'Tab') return;
      const modal = modalRef.current;
      if (!modal) return;
      const focusable = modal.querySelectorAll<HTMLElement>(
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
      <section
        ref={modalRef}
        className="card max-h-[88vh] w-full max-w-3xl overflow-y-auto bg-surface p-5 sm:p-6"
      >
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
            ref={closeButtonRef}
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
