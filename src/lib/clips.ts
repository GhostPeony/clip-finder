import type { VideoClip } from '../types';

export interface VideoClipGroup {
  videoId: string;
  title: string;
  channelName: string;
  thumbnailUrl: string;
  clips: VideoClip[];
}

export function groupClipsByVideo(clips: VideoClip[]): VideoClipGroup[] {
  const groups = new Map<string, VideoClipGroup>();
  for (const clip of clips) {
    const existing = groups.get(clip.videoId);
    if (existing) {
      existing.clips.push(clip);
    } else {
      groups.set(clip.videoId, {
        videoId: clip.videoId,
        title: clip.title,
        channelName: clip.channelName,
        thumbnailUrl: clip.thumbnailUrl,
        clips: [clip],
      });
    }
  }
  return [...groups.values()];
}
