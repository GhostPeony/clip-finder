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
    <div className="bg-white rounded-lg border border-[#dadce0] p-5">
      <div className="flex items-center gap-2 mb-3">
        {/* Gemini-style sparkle icon */}
        <svg className="w-5 h-5 text-[#1a73e8]" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2L9.19 8.63L2 9.24L7.46 13.97L5.82 21L12 17.27L18.18 21L16.54 13.97L22 9.24L14.81 8.63L12 2Z"/>
        </svg>
        <h2 className="text-sm font-medium text-[#202124]">AI Overview</h2>
      </div>

      <p className="text-[#3c4043] text-sm leading-relaxed">
        {parts.map((part, index) => {
          const match = part.match(/\[\[(clip_\d+)\]\]/);
          if (match) {
            const clipId = match[1];
            const clip = clips.find(c => c.id === clipId);

            if (clip) {
              return (
                <button
                  key={index}
                  onClick={() => onCitationClick(clip)}
                  className="inline-flex items-center gap-1 mx-0.5 px-2 py-0.5 text-xs font-medium text-[#1a73e8] bg-[#e8f0fe] hover:bg-[#d2e3fc] rounded-full transition-colors cursor-pointer align-middle"
                >
                  <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7z"/>
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
