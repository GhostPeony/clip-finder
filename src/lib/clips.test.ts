import { describe, expect, it } from 'vitest';
import { groupClipsByVideo } from './clips';
import type { VideoClip } from '../types';

const clip = (id: string, videoId: string, start: number): VideoClip =>
  ({
    id,
    videoId,
    title: `t-${videoId}`,
    channelName: 'c',
    startSeconds: start,
    endSeconds: start + 60,
    content: '',
    thumbnailUrl: `thumb-${videoId}`,
  }) as VideoClip;

describe('groupClipsByVideo', () => {
  it('groups clips under one entry per video, preserving first-seen order', () => {
    const groups = groupClipsByVideo([
      clip('a', 'v1', 10),
      clip('b', 'v2', 20),
      clip('c', 'v1', 99),
    ]);
    expect(groups.map((g) => g.videoId)).toEqual(['v1', 'v2']);
    expect(groups[0].clips.map((c) => c.id)).toEqual(['a', 'c']);
    expect(groups[0].title).toBe('t-v1');
  });

  it('returns empty array for no clips', () => {
    expect(groupClipsByVideo([])).toEqual([]);
  });
});
