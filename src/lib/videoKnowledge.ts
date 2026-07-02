import {
  LibraryGraphNode,
  LibraryGraphVideo,
  LibrarySourceGraphData,
  LibrarySourceRef,
  LibraryVideo,
} from '../types';

export type VideoWithChannel = LibraryVideo & { channelName: string };

export interface VideoKnowledge {
  key: string;
  video: LibraryGraphVideo;
  latest?: VideoWithChannel;
  guides: LibraryGraphNode[];
  ideas: LibraryGraphNode[];
}

export interface IdeaWithVideo {
  idea: LibraryGraphNode;
  video: LibraryGraphVideo;
  videoKey: string;
}

export interface GuideWithVideo {
  guide: LibraryGraphNode;
  video: LibraryGraphVideo;
}

export interface TopicSection {
  id: string;
  title: string;
  items: IdeaWithVideo[];
}

export interface GuideVideoSection {
  key: string;
  video: LibraryGraphVideo;
  guides: LibraryGraphNode[];
}

const MIN_BROWSABLE_TOPIC_SECONDS = 10;
const TOPIC_DEDUPE_WINDOW_SECONDS = 15;

export function buildVideoKnowledge(
  graphData: LibrarySourceGraphData | null,
  latestVideos: VideoWithChannel[],
): VideoKnowledge[] {
  const latestByKey = new Map(
    latestVideos.flatMap((video) => {
      const keys = new Set([video.videoId, normalizeVideoKey(video.videoId)]);
      return Array.from(keys).map((key) => [key, video] as const);
    }),
  );

  const maps = new Map<string, VideoKnowledge>();

  const ensureMap = (video: LibraryGraphVideo): VideoKnowledge | null => {
    const key = normalizeVideoKey(video.videoId || video.id || video.youtubeUrl || video.title);
    if (!key) return null;
    const latest =
      latestByKey.get(key) || (video.videoId ? latestByKey.get(video.videoId) : undefined);
    const existing = maps.get(key);
    if (existing) {
      existing.video = mergeVideoData(video, existing.latest || latest);
      return existing;
    }

    const sourceMap: VideoKnowledge = {
      key,
      video: mergeVideoData(video, latest),
      latest,
      guides: [],
      ideas: [],
    };
    maps.set(key, sourceMap);
    return sourceMap;
  };

  latestVideos.forEach((video) => {
    ensureMap({
      videoId: video.videoId,
      title: video.title,
      thumbnailUrl: video.thumbnailUrl,
      transcriptSeconds: video.transcriptSeconds || null,
      channel: { name: video.channelName },
      accessSource: video.accessSource,
      accessReason: video.accessReason,
    });
  });

  graphData?.videos.forEach((video) => {
    ensureMap(video);
  });

  graphData?.graph.nodes.forEach((node) => {
    if (node.type !== 'source_concept' && node.type !== 'knowledge_artifact') return;
    const map = findMapForNode(node, maps);
    if (!map) return;
    if (node.type === 'source_concept' && isBrowsableTopic(node)) {
      map.ideas.push(node);
    }
    if (node.type === 'knowledge_artifact') map.guides.push(node);
  });

  maps.forEach((item) => {
    item.ideas = dedupeTopicsBySourceMoment(item.ideas);
    item.guides = sortGuides(item.guides);
  });

  return Array.from(maps.values()).sort((a, b) => {
    const aIndexed = Date.parse(a.video.indexedAt || '') || a.latest?.indexedAt || 0;
    const bIndexed = Date.parse(b.video.indexedAt || '') || b.latest?.indexedAt || 0;
    return bIndexed - aIndexed;
  });
}

export function flattenIdeas(items: VideoKnowledge[]): IdeaWithVideo[] {
  return items.flatMap((item) =>
    item.ideas.map((idea) => ({
      idea,
      video: item.video,
      videoKey: item.key,
    })),
  );
}

export function flattenGuides(items: VideoKnowledge[]): GuideWithVideo[] {
  return items.flatMap((item) =>
    item.guides.map((guide) => ({
      guide,
      video: item.video,
    })),
  );
}

export function groupIdeasByCategory(ideas: IdeaWithVideo[]): TopicSection[] {
  const sections = new Map<string, TopicSection>();
  ideas.forEach((item) => {
    const category = topicCategory(item.idea);
    const existing = sections.get(category.id);
    if (existing) {
      existing.items.push(item);
    } else {
      sections.set(category.id, { ...category, items: [item] });
    }
  });

  return Array.from(sections.values()).sort((a, b) => {
    const order = topicCategoryOrder(a.id) - topicCategoryOrder(b.id);
    if (order !== 0) return order;
    return a.title.localeCompare(b.title);
  });
}

export function groupGuidesByVideo(guides: GuideWithVideo[]): GuideVideoSection[] {
  const sections = new Map<string, GuideVideoSection>();
  guides.forEach(({ guide, video }) => {
    const key = normalizeVideoKey(video.videoId || video.id || video.youtubeUrl || video.title);
    if (!key) return;
    const existing = sections.get(key);
    if (existing) {
      existing.guides.push(guide);
    } else {
      sections.set(key, { key, video, guides: [guide] });
    }
  });

  return Array.from(sections.values()).map((section) => ({
    ...section,
    guides: sortGuides(section.guides),
  }));
}

function isBrowsableTopic(idea: LibraryGraphNode): boolean {
  const source = firstUsefulSourceRef(idea.sourceRefs || []);
  if (!source || typeof source.start_seconds !== 'number') return false;
  return source.start_seconds >= MIN_BROWSABLE_TOPIC_SECONDS;
}

function dedupeTopicsBySourceMoment(ideas: LibraryGraphNode[]): LibraryGraphNode[] {
  const groups = new Map<string, LibraryGraphNode[]>();
  ideas.forEach((idea) => {
    const source = firstUsefulSourceRef(idea.sourceRefs || []);
    if (!source || typeof source.start_seconds !== 'number') return;
    const videoKey = normalizeVideoKey(
      source.youtube_video_id || source.source_id || idea.video?.videoId || idea.video?.youtubeUrl,
    );
    const bucket = Math.floor(source.start_seconds / TOPIC_DEDUPE_WINDOW_SECONDS);
    const key = `${videoKey || 'video'}:${bucket}`;
    groups.set(key, [...(groups.get(key) || []), idea]);
  });

  return Array.from(groups.values()).flatMap((group) => {
    const [best, ...merged] = group;
    if (!best) return [];
    if (merged.length === 0) return [best];
    return [
      {
        ...best,
        metadata: {
          ...best.metadata,
          mergedTopicCount: group.length,
        },
      },
    ];
  });
}

function sortGuides(guides: LibraryGraphNode[]): LibraryGraphNode[] {
  return [...guides].sort((a, b) => artifactKindOrder(a) - artifactKindOrder(b));
}

function findMapForNode(
  node: LibraryGraphNode,
  maps: Map<string, VideoKnowledge>,
): VideoKnowledge | null {
  const candidates = [
    node.video?.videoId,
    node.video?.id,
    node.video?.youtubeUrl,
    ...(node.sourceRefs || []).flatMap((ref) => [
      ref.youtube_video_id,
      ref.source_id,
      typeof ref.source_id === 'string' ? extractVideoId(ref.source_id) : '',
    ]),
  ]
    .map((value) => normalizeVideoKey(value || ''))
    .filter(Boolean);

  for (const candidate of candidates) {
    const sourceMap = maps.get(candidate);
    if (sourceMap) return sourceMap;
  }

  if (maps.size === 1) return Array.from(maps.values())[0];
  return null;
}

function mergeVideoData(video: LibraryGraphVideo, latest?: VideoWithChannel): LibraryGraphVideo {
  return {
    ...video,
    videoId: video.videoId || latest?.videoId,
    title: video.title || latest?.title || 'Saved video',
    thumbnailUrl: video.thumbnailUrl || latest?.thumbnailUrl || null,
    transcriptSeconds: video.transcriptSeconds || latest?.transcriptSeconds || null,
    indexedAt: video.indexedAt || normalizeIndexedAt(latest?.indexedAt),
    channel: {
      ...video.channel,
      name: video.channel?.name || latest?.channelName || null,
    },
    accessSource: video.accessSource || latest?.accessSource,
    accessReason: video.accessReason || latest?.accessReason,
  };
}

export function getChannelName(video: LibraryGraphVideo, latest?: VideoWithChannel): string {
  return video.channel?.name || latest?.channelName || '';
}

export function formatVideoIndexedDate(
  video: LibraryGraphVideo,
  latest?: VideoWithChannel,
): string {
  const timestamp = videoIndexedTimestamp(video, latest);
  if (!timestamp) return '';
  return `Indexed ${new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date(timestamp))}`;
}

function videoIndexedTimestamp(video: LibraryGraphVideo, latest?: VideoWithChannel): number | null {
  const parsedVideoDate = Date.parse(video.indexedAt || '');
  if (Number.isFinite(parsedVideoDate) && parsedVideoDate > 0) return parsedVideoDate;
  return normalizeIndexedTimestamp(latest?.indexedAt);
}

function normalizeIndexedAt(value?: number): string | null {
  const timestamp = normalizeIndexedTimestamp(value);
  return timestamp ? new Date(timestamp).toISOString() : null;
}

function normalizeIndexedTimestamp(value?: number): number | null {
  if (!value) return null;
  return value < 100000000000 ? value * 1000 : value;
}

export function getVideoUrl(video: LibraryGraphVideo): string {
  if (video.youtubeUrl) return video.youtubeUrl;
  if (video.videoId) return `https://www.youtube.com/watch?v=${extractVideoId(video.videoId)}`;
  return '';
}

export function buildTimestampUrl(video: LibraryGraphVideo | undefined, seconds: number): string {
  const videoId = extractVideoId(video?.videoId || video?.youtubeUrl || '');
  if (!videoId) return getVideoUrl(video || { title: '' });
  return `https://www.youtube.com/watch?v=${videoId}&t=${Math.max(0, Math.floor(seconds))}`;
}

export function firstUsefulSourceRef(refs: LibrarySourceRef[]): LibrarySourceRef | null {
  return (
    refs.find((ref) => typeof ref.start_seconds === 'number' && ref.start_seconds >= 0) || null
  );
}

export function cleanDisplayTitle(title: string): string {
  return title
    .replace(/^study guide:\s*/i, '')
    .replace(/^source report:\s*/i, '')
    .replace(/^implementation brief:\s*/i, '')
    .replace(/^tldr:\s*/i, '')
    .replace(/\s+/g, ' ')
    .trim();
}

export function artifactKind(node: LibraryGraphNode): string {
  const kind = String(node.metadata?.artifactType || '');
  if (kind === 'tldr') return 'TLDR';
  if (kind === 'study_guide' || kind === 'source_report') return 'Source report';
  if (kind) return formatSourceType(kind);
  if (/source report/i.test(node.label)) return 'Source report';
  if (/study guide/i.test(node.label)) return 'Source report';
  if (/tldr/i.test(node.label)) return 'TLDR';
  if (/brief/i.test(node.label)) return 'Implementation brief';
  return 'Generated report';
}

export function artifactActionLabel(node: LibraryGraphNode): string {
  const kind = artifactKind(node);
  if (kind === 'TLDR') return 'Read TLDR';
  if (kind === 'Source report') return 'Read report';
  return 'Read artifact';
}

function artifactKindOrder(node: LibraryGraphNode): number {
  const kind = artifactKind(node);
  if (kind === 'TLDR') return 0;
  if (kind === 'Source report') return 1;
  return 2;
}

function topicCategory(node: LibraryGraphNode): { id: string; title: string } {
  const type = String(node.metadata?.conceptType || 'concept').toLowerCase();
  if (['method', 'algorithm', 'tool'].includes(type)) {
    return { id: 'methods', title: 'Methods, tools, and systems' };
  }
  if (type === 'implementation_note') {
    return { id: 'practical', title: 'Practical notes' };
  }
  if (type === 'claim') {
    return { id: 'claims', title: 'Claims and takeaways' };
  }
  if (type === 'pitfall') {
    return { id: 'warnings', title: 'Warnings and caveats' };
  }
  if (type === 'entity') {
    return { id: 'entities', title: 'People, organizations, and named things' };
  }
  return { id: 'concepts', title: 'Concepts and themes' };
}

function topicCategoryOrder(id: string): number {
  const order = ['methods', 'practical', 'claims', 'warnings', 'entities', 'concepts'];
  const index = order.indexOf(id);
  return index === -1 ? order.length : index;
}

export function mergedTopicCount(node: LibraryGraphNode): number {
  const value = node.metadata?.mergedTopicCount;
  return typeof value === 'number' && Number.isFinite(value) ? value : 1;
}

function normalizeVideoKey(value: string | null | undefined): string {
  if (!value) return '';
  return extractVideoId(value) || value.trim();
}

function extractVideoId(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return '';
  if (/^[a-zA-Z0-9_-]{6,}$/.test(trimmed) && !trimmed.includes('/')) return trimmed;
  try {
    const normalized = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
    const url = new URL(normalized);
    if (url.hostname.includes('youtu.be')) return url.pathname.replace('/', '').split('/')[0] || '';
    return url.searchParams.get('v') || url.pathname.split('/').filter(Boolean).pop() || '';
  } catch {
    return trimmed;
  }
}

export function formatDuration(seconds: number): string {
  if (!seconds || seconds < 60) return `${Math.max(0, Math.round(seconds || 0))}s`;
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

export function formatSourceType(value: string): string {
  return value.replace(/[_-]+/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}
