import React from 'react';
import { formatTimestamp } from '../lib/time';
import { VideoClip } from '../types';

interface AnswerSectionProps {
  answer: string;
  clips: VideoClip[];
  onCitationClick: (clip: VideoClip) => void;
  /** `card` is the dashboard search-results treatment; `inline` nests inside another panel. */
  variant?: 'card' | 'inline';
}

export const AnswerSection: React.FC<AnswerSectionProps> = ({
  answer,
  clips,
  onCitationClick,
  variant = 'card',
}) => {
  // Regex to find [[clip_id]] citations
  const parts = answer.split(/(\[\[clip_\d+\]\])/g);

  const citedAnswer = parts.map((part, index) => {
    const match = part.match(/\[\[(clip_\d+)\]\]/);
    if (match) {
      const clipId = match[1];
      const clip = clips.find((c) => c.id === clipId);

      if (clip) {
        return (
          <button
            key={index}
            onClick={() => onCitationClick(clip)}
            className="mx-0.5 inline-flex cursor-pointer items-center gap-1 rounded-full bg-sun/40 px-2.5 py-0.5 align-middle font-mono text-xs font-medium text-ink transition hover:-translate-y-px hover:bg-sun/70"
          >
            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z" />
            </svg>
            {formatTimestamp(clip.startSeconds)}
          </button>
        );
      }
    }
    return <span key={index}>{part}</span>;
  });

  if (variant === 'inline') {
    return (
      <div className="rounded-xl bg-cream p-4">
        <h3 className="text-sm font-semibold text-ink">Answer</h3>
        <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-bark">{citedAnswer}</p>
      </div>
    );
  }

  return (
    <div className="card p-6">
      <div className="flex items-center gap-2 mb-3">
        <svg className="h-5 w-5 text-violet-deep" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2L9.19 8.63L2 9.24L7.46 13.97L5.82 21L12 17.27L18.18 21L16.54 13.97L22 9.24L14.81 8.63L12 2Z" />
        </svg>
        <h2 className="font-serif text-2xl font-medium text-ink">Answer with receipts</h2>
      </div>

      <p className="text-sm leading-7 text-bark">{citedAnswer}</p>
    </div>
  );
};
