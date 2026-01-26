import React from 'react';

interface VideoPlayerProps {
  videoId: string;
  startSeconds: number;
  autoplay?: boolean;
}

export const VideoPlayer: React.FC<VideoPlayerProps> = ({ videoId, startSeconds, autoplay = false }) => {
  // Guard against empty videoId
  if (!videoId) {
    return (
      <div className="relative w-full pt-[56.25%] bg-black rounded-t-lg overflow-hidden flex items-center justify-center">
        <p className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 text-white text-sm">
          Video ID not available
        </p>
      </div>
    );
  }

  const src = `https://www.youtube.com/embed/${videoId}?start=${startSeconds}&autoplay=${autoplay ? 1 : 0}&rel=0&enablejsapi=1`;

  return (
    <div className="relative w-full pt-[56.25%] bg-black rounded-t-lg overflow-hidden">
      <iframe
        className="absolute top-0 left-0 w-full h-full"
        src={src}
        title="YouTube video player"
        frameBorder="0"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowFullScreen
      ></iframe>
    </div>
  );
};
