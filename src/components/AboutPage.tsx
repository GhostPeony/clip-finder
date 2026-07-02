import React from 'react';
import { SocialLinks } from './SocialLinks';
import { PRODUCT_NAME } from '../brand';

export function AboutPage({ onBack }: { onBack: () => void }) {
  return (
    <div className="py-8 max-w-2xl mx-auto">
      <button onClick={onBack} className="link-quiet mb-6 flex items-center gap-1 text-sm">
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        Back
      </button>
      <div className="card p-8">
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <h1 className="font-serif text-4xl font-medium text-ink">About {PRODUCT_NAME}</h1>
          <SocialLinks compact />
        </div>
        <div className="space-y-4 text-sm leading-7 text-bark">
          <p>
            {PRODUCT_NAME} turns saved YouTube videos into a searchable library with timestamped
            clips, transcripts, and notes.
          </p>
          <p>
            Built for people who learn from video and want useful moments to be easy to find again:
            researchers, builders, writers, creators, students, and teams.
          </p>
          <h2 className="pt-4 font-serif text-2xl font-medium text-ink">Why {PRODUCT_NAME}?</h2>
          <ul className="list-disc list-inside space-y-2">
            <li>
              <strong>Semantic search</strong> - Find by meaning, not just keywords
            </li>
            <li>
              <strong>Timestamped clips</strong> - Open the exact moment behind an answer
            </li>
            <li>
              <strong>Capture from YouTube</strong> - Save videos to linked playlists and move them
              into your library
            </li>
            <li>
              <strong>Full channel support</strong> - Index entire channels, playlists, or
              individual videos
            </li>
          </ul>
          <h2 className="pt-4 font-serif text-2xl font-medium text-ink">How it works</h2>
          <ol className="list-decimal list-inside space-y-2">
            <li>Paste any YouTube URL (video, playlist, or channel)</li>
            <li>Memexai indexes the available captions and timestamps</li>
            <li>Your searches return relevant clips from your saved sources</li>
            <li>You can open, copy, or revisit the exact YouTube moment</li>
          </ol>
        </div>
      </div>
    </div>
  );
}
