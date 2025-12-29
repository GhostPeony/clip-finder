import React from 'react';

interface VideoPlayerProps {
  videoId: string;
  startSeconds: number;
  autoplay?: boolean;
}

export const VideoPlayer: React.FC<VideoPlayerProps> = ({ videoId, startSeconds, autoplay = false }) => {
  const src = `https://www.youtube.com/embed/${videoId}?start=${startSeconds}&autoplay=${autoplay ? 1 : 0}&rel=0`;

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
