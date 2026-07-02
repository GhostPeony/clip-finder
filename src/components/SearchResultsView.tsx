import React from 'react';
import { SearchState, VideoClip } from '../types';
import { groupClipsByVideo } from '../lib/clips';
import { formatTimestamp } from '../lib/time';
import { AnswerSection } from './AnswerSection';
import { VideoPlayer } from './VideoPlayer';

export function SearchResultsView({
  searchState,
  activeClip,
  onCitationClick,
  onCopyClipLink,
  onNewSearch,
  onTryAnotherSearch,
}: {
  searchState: SearchState;
  activeClip: VideoClip | null;
  onCitationClick: (clip: VideoClip) => void;
  onCopyClipLink: (clip: VideoClip) => void;
  onNewSearch: () => void;
  onTryAnotherSearch: () => void;
}) {
  return (
    <div>
      {/* Back to search button */}
      <div className="mb-6">
        <button onClick={onNewSearch} className="link-quiet flex items-center gap-1 text-sm">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 19l-7-7 7-7"
            />
          </svg>
          New Search
        </button>
      </div>

      {/* Zero-results state */}
      {searchState.status === 'complete' && searchState.relevantClips.length === 0 && (
        <div className="card mx-auto max-w-xl p-8 text-center">
          <h2 className="font-serif text-3xl font-medium text-ink">No moments found</h2>
          <p className="mx-auto mt-3 max-w-sm text-sm leading-6 text-bark">
            Nothing in your library matched that description. Try different wording, or index more
            videos to widen the search.
          </p>
          <button onClick={onTryAnotherSearch} className="btn btn-primary mt-6">
            Try another search
          </button>
        </div>
      )}

      {/* Results Area - YouTube-style layout */}
      {searchState.status !== 'idle' &&
        !searchState.error &&
        searchState.relevantClips.length > 0 && (
          <div className="flex flex-col-reverse gap-6 md:flex-row">
            {/* Sources grouped by video: sidebar on desktop, strip below player on mobile */}
            <div className="w-full flex-shrink-0 md:w-56">
              <div className="md:sticky md:top-20">
                <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted">
                  Clips
                </h3>
                <div className="flex gap-3 overflow-x-auto pb-2 md:block md:space-y-3 md:overflow-visible md:pb-0">
                  {groupClipsByVideo(searchState.relevantClips).map((group) => (
                    <div
                      key={group.videoId}
                      className="card w-56 flex-shrink-0 overflow-hidden p-2 md:w-auto"
                    >
                      <button
                        onClick={() => onCitationClick(group.clips[0])}
                        className="block w-full text-left"
                      >
                        {group.thumbnailUrl && (
                          <img
                            src={group.thumbnailUrl}
                            className="h-auto w-full rounded-lg"
                            alt=""
                          />
                        )}
                        <p className="mt-2 line-clamp-2 text-xs font-semibold text-ink">
                          {group.title}
                        </p>
                      </button>
                      <div className="mt-1.5 flex flex-wrap gap-1.5">
                        {group.clips.map((clip) => (
                          <button
                            key={clip.id}
                            onClick={() => onCitationClick(clip)}
                            className={`rounded-full px-2 py-0.5 font-mono text-xs font-medium transition-colors ${
                              activeClip?.id === clip.id
                                ? 'bg-rose-deep text-cream'
                                : 'bg-petal/60 text-rose-deep hover:bg-petal'
                            }`}
                          >
                            {formatTimestamp(clip.startSeconds)}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Main Content: Answer + Video + Transcript */}
            <div className="flex-1 max-w-4xl">
              {/* Cited answer */}
              {searchState.answer && (
                <div className="mb-5">
                  <AnswerSection
                    answer={searchState.answer}
                    clips={searchState.relevantClips}
                    onCitationClick={onCitationClick}
                  />
                </div>
              )}
              {/* Video Player */}
              <div>
                {activeClip ? (
                  <div className="card overflow-hidden">
                    <VideoPlayer
                      key={activeClip.id}
                      videoId={activeClip.videoId}
                      startSeconds={activeClip.startSeconds}
                      autoplay={true}
                    />
                    <div className="p-5">
                      <h3 className="font-serif text-2xl font-medium text-ink">
                        {activeClip.title}
                      </h3>
                      <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1">
                        <span className="text-sm text-bark">{activeClip.channelName}</span>
                        <span className="text-muted">-</span>
                        <span className="font-mono text-sm font-medium text-rose-deep">
                          {formatTimestamp(activeClip.startSeconds)}
                        </span>
                        <span className="text-muted">-</span>
                        <a
                          href={`https://youtube.com/watch?v=${activeClip.videoId}&t=${activeClip.startSeconds}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm font-medium text-muted hover:text-violet-deep"
                        >
                          Watch on YouTube
                        </a>
                        <span className="text-muted">-</span>
                        <button
                          onClick={() => onCopyClipLink(activeClip)}
                          className="flex items-center gap-1 text-sm font-medium text-muted hover:text-rose-deep"
                          title="Copy shareable link"
                        >
                          <svg
                            className="w-4 h-4"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"
                            />
                          </svg>
                          Copy Link
                        </button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="card flex aspect-video items-center justify-center text-bark">
                    <div className="text-center">
                      <svg
                        className="mx-auto mb-2 h-12 w-12 text-muted"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={1.5}
                          d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
                        />
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={1.5}
                          d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                        />
                      </svg>
                      <p className="text-sm">Select a source to play</p>
                    </div>
                  </div>
                )}
              </div>

              {/* Transcript below video */}
              {activeClip && (
                <div className="card mt-5 p-6">
                  <div className="flex items-center gap-2 mb-3">
                    <svg
                      className="h-5 w-5 text-violet-deep"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                      />
                    </svg>
                    <h2 className="font-serif text-2xl font-medium text-ink">Transcript</h2>
                    <span className="font-mono text-xs font-medium text-muted">
                      {formatTimestamp(activeClip.startSeconds)} -{' '}
                      {formatTimestamp(activeClip.endSeconds)}
                    </span>
                  </div>
                  <p className="whitespace-pre-wrap text-sm leading-7 text-bark">
                    {activeClip.content}
                  </p>
                  {activeClip.relevanceReason && (
                    <p className="mt-3 border-l-4 border-rose pl-3 text-xs font-medium text-muted">
                      {activeClip.relevanceReason}
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
    </div>
  );
}
