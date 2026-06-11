import React from 'react';
import { VideoClip } from '../types';

interface AnswerSectionProps {
  answer: string;
  clips: VideoClip[];
  onCitationClick: (clip: VideoClip) => void;
}

export const AnswerSection: React.FC<AnswerSectionProps> = ({ answer, clips, onCitationClick }) => {
  // Regex to find [[clip_id]] citations
  const parts = answer.split(/(\[\[clip_\d+\]\])/g);

  return (
    <div className="card p-6">
      <div className="flex items-center gap-2 mb-3">
        <svg className="h-5 w-5 text-violet-deep" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2L9.19 8.63L2 9.24L7.46 13.97L5.82 21L12 17.27L18.18 21L16.54 13.97L22 9.24L14.81 8.63L12 2Z" />
        </svg>
        <h2 className="font-serif text-2xl font-medium text-ink">Answer with receipts</h2>
      </div>

      <p className="text-sm leading-7 text-bark">
        {parts.map((part, index) => {
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
                  {formatTime(clip.startSeconds)}
                </button>
              );
            }
          }
          return <span key={index}>{part}</span>;
        })}
      </p>
    </div>
  );
};

const formatTime = (seconds: number): string => {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
};
