export interface VideoClip {
  id: string;
  videoId: string;
  title: string;
  channelName: string;
  startSeconds: number;
  endSeconds: number;
  content: string; // The transcript text for this chunk
  thumbnailUrl: string;
  similarity?: number;
  keywordRank?: number;
  hybridScore?: number;
  matchType?: string;
  matchSnippet?: string;
  relevanceReason?: string;
  accessScope?: 'channel' | 'video' | 'channel_and_video' | 'user_library';
  accessSource?: string;
  accessReason?: string;
}

export interface SearchState {
  status: 'idle' | 'searching' | 'analyzing' | 'complete' | 'error';
  query: string;
  answer: string;
  relevantClips: VideoClip[];
  error?: string;
}

export interface IngestionState {
  status: 'idle' | 'scanning' | 'indexing' | 'complete' | 'error';
  logs: string[];
  progress: number;
  totalVideos: number;
  currentVideo?: string;
}

// Library types
export interface LibraryVideo {
  videoId: string;
  title: string;
  thumbnailUrl: string;
  clipCount: number;
  indexedAt?: number; // Unix timestamp, optional for backward compat
  transcriptSeconds?: number;
  accessScope?: 'channel' | 'video' | 'channel_and_video' | 'user_library';
  accessSource?: string;
  accessReason?: string;
}

export type DensityMode = 'compact' | 'comfortable';
export type SortMode = 'default' | 'dateAdded';
export type ViewMode = 'grouped' | 'flat';

export interface LibraryChannel {
  name: string;
  videoCount: number;
  videos: LibraryVideo[];
}

export interface LibraryData {
  channels: LibraryChannel[];
  totalVideos: number;
  totalClips: number;
  projectScope?: ProjectScope | null;
}

export interface ProjectScope {
  id: string;
  name: string;
  slug: string;
  description?: string;
  status?: 'active' | 'archived' | string;
  videoIds?: string[];
  videoCount?: number;
  captureSources?: CaptureSource[];
  linkedCaptureSourceCount?: number;
}

export interface UserProject extends ProjectScope {
  user_id?: string;
  metadata?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
}

export interface ProjectsData {
  projects: UserProject[];
  archivedProjects?: UserProject[];
  totalProjects: number;
}

export interface ProjectContextMap {
  version: string;
  found: boolean;
  project?: ProjectScope;
  videos: Array<{
    videoId: string;
    title: string;
    channelName?: string | null;
    thumbnailUrl?: string | null;
    transcriptSeconds?: number | null;
    indexedAt?: string | null;
    next_mcp_call?: Record<string, unknown>;
  }>;
  componentCounts?: Record<string, number>;
  facets?: Array<Record<string, unknown>>;
  suggestedFollowUpQueries?: string[];
  guidance?: string;
}

export type LibraryComponentType =
  | 'video'
  | 'source_label'
  | 'source_concept'
  | 'source_edge'
  | 'knowledge_artifact'
  | 'transcript_chunk'
  | 'agent_note'
  | 'personal_concept';

export interface LibraryGraphVideo {
  id?: string | null;
  videoId?: string | null;
  title: string;
  youtubeUrl?: string | null;
  thumbnailUrl?: string | null;
  transcriptSeconds?: number | null;
  indexedAt?: string | null;
  channel?: {
    id?: string | null;
    name?: string | null;
    youtubeHandle?: string | null;
  };
  accessScope?: 'channel' | 'video' | 'channel_and_video' | 'user_library';
  accessSource?: string;
  accessReason?: string;
}

export interface LibrarySourceRef {
  source_type?: string;
  youtube_video_id?: string;
  source_id?: string;
  start_seconds?: number | null;
  end_seconds?: number | null;
  quote?: string;
  [key: string]: unknown;
}

export interface LibraryGraphNode {
  id: string;
  type: LibraryComponentType | 'channel';
  label: string;
  summary?: string;
  content?: string;
  thumbnailUrl?: string | null;
  video?: LibraryGraphVideo;
  sourceRefs?: LibrarySourceRef[];
  metadata?: Record<string, unknown>;
  weight?: number;
}

export interface LibraryGraphEdge {
  id: string;
  source: string;
  target: string;
  relation: string;
  sourceRefs?: LibrarySourceRef[];
}

export interface LibraryReviewFlag {
  id: string;
  type:
    | 'missing_thumbnail'
    | 'stale_metadata'
    | 'missing_transcript'
    | 'missing_source_knowledge'
    | 'duplicate_access_grant'
    | 'weak_evidence_refs'
    | 'potential_conflict'
    | string;
  severity: 'info' | 'review' | 'warning' | 'blocking' | string;
  title: string;
  message: string;
  count?: number;
  videoIds?: string[];
  video?: LibraryGraphVideo;
  sourceRefs?: LibrarySourceRef[];
}

export interface LibraryEdgeCaseHandling {
  edgeCase: string;
  handling: string;
}

export interface LibrarySourceGraphData {
  version: string;
  limit: number;
  projectScope?: ProjectScope | null;
  accessModel: {
    scope: string;
    visibilityGrants: string[];
    sourceTruth: string;
    provenanceFields: string[];
  };
  videos: LibraryGraphVideo[];
  componentCounts: {
    videos: number;
    channels: number;
    sourceLabels: number;
    sourceConcepts: number;
    sourceEdges: number;
    knowledgeArtifacts: number;
    transcriptChunksSampled: number;
    agentNotes: number;
    personalConcepts: number;
    reviewFlags: number;
  };
  graph: {
    nodes: LibraryGraphNode[];
    edges: LibraryGraphEdge[];
    selectedNodeId?: string | null;
  };
  reviewFlags: LibraryReviewFlag[];
  edgeCaseHandling: LibraryEdgeCaseHandling[];
  guidance: string;
}

export interface LibraryComponentSearchResult {
  id?: string | null;
  resultType: LibraryComponentType;
  matchType: string;
  title: string;
  summary?: string;
  matchSnippet?: string;
  video?: LibraryGraphVideo;
  sourceRefs?: LibrarySourceRef[];
  score?: number;
  metadata?: Record<string, unknown>;
}

export interface LibraryComponentSearchData {
  query: string;
  retrievalMode: 'component_keyword';
  projectScope?: ProjectScope | null;
  results: LibraryComponentSearchResult[];
  componentTypes: LibraryComponentType[];
  accessModel: {
    scope: string;
    embeddingUsed: boolean;
    llmAnswerUsed: boolean;
  };
  retrievalBudget: {
    embeddingCalls: number;
    llmCalls: number;
    maxResults: number;
    searchedVideos: number;
    returnedResults: number;
  };
  guidance: string;
}

export interface IngestionJobEvent {
  id: string;
  job_id: string;
  level: 'info' | 'warning' | 'error';
  message: string;
  youtube_video_id?: string;
  reason?: string;
  created_at: string;
}

export interface IngestionCostEstimate {
  version: string;
  sourceType: 'channel' | 'playlist' | 'video' | 'unknown';
  sourceUrl: string;
  userId: string;
  discoveredVideos: number;
  discoveredVideosEstimated: boolean;
  alreadyIndexedVideos: number;
  alreadyIndexedVideoIds: string[];
  videosToEmbed: number;
  maxVideosThisRun: number;
  digestDepth: 'none' | 'basic' | 'standard' | 'deep';
  digestDepthDescription: string;
  estimatedTranscriptSeconds: number;
  estimatedEmbeddingChars: number;
  estimatedEmbeddingTokens: number;
  estimatedEmbeddingBatches: number;
  estimatedDigestLlmCalls: number;
  estimatedDigestInputTokens?: number;
  estimatedDigestOutputTokenBudget?: number;
  estimatedModelCostUsd?: {
    embeddingStandardUsd?: number;
    embeddingBatchUsd?: number;
    digestInputUsd?: number;
    digestOutputBudgetUsd?: number;
    totalStandardUpperBoundUsd?: number;
    notes?: string[];
  };
  generationPolicy?: {
    ingestionGenerated?: string[];
    mcpAgentShouldGenerateOnDemand?: string[];
    recommendedDefault?: string;
    rationale?: string;
  };
  assumptions: Record<string, unknown>;
  riskLevel: 'low' | 'medium' | 'high';
  guidance: string;
}

export interface IngestionJob {
  id: string;
  user_id: string;
  source_url: string;
  source_type: 'channel' | 'playlist' | 'video' | 'unknown';
  status: 'queued' | 'running' | 'completed' | 'failed' | 'partial' | 'cancelled';
  requested_video_count: number;
  indexed_video_count: number;
  skipped_video_count: number;
  failed_video_count: number;
  last_message?: string;
  error?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  cost_estimate?: IngestionCostEstimate | Record<string, unknown>;
  ingestion_job_events?: IngestionJobEvent[];
}

export interface McpTokenRecord {
  id: string;
  name: string;
  tokenPrefix: string;
  scopes: string[];
  lastUsedAt?: string | null;
  expiresAt?: string | null;
  createdAt?: string | null;
  oauthClientId?: string | null;
}

export interface McpSetupCall {
  tool: string;
  purpose: string;
}

export interface McpClaudeConnectorSetup {
  name: string;
  url: string;
  setupSteps: string[];
  initialPrompt: string;
  authMode: string;
  fallback: string;
}

export interface McpSetupBundle {
  serverName: string;
  mcpEndpoint: string;
  manifestUrl: string;
  agentGuideUrl: string;
  fullAgentGuideUrl: string;
  claudeCustomConnector?: McpClaudeConnectorSetup;
  tokenEnvironmentVariable: string;
  hermesConfig: string;
  codexConfig?: string;
  codexSetupNote?: string;
  firstSteps: string[];
  firstCalls: McpSetupCall[];
  accessModel: {
    searchScope: string;
    globalSearch: string;
    visibilityGrants: string[];
    canonicalStorage: string;
    dedupeBehavior: string;
    agentInstruction: string;
  };
  oneTimeCredential?: {
    bearerToken: string;
    envLine: string;
    codexEnvLine?: string;
    hermesConfig: string;
  };
}

export interface CreatedMcpToken {
  token: string;
  tokenRecord: McpTokenRecord;
  setup?: McpSetupBundle;
}

export interface WorkflowInstance {
  id: string;
  user_id?: string;
  workflow_key?: string;
  workflow_version?: number;
  trigger?: string;
  status: 'queued' | 'running' | 'waiting' | 'completed' | 'failed' | 'cancelled';
  input?: Record<string, unknown>;
  current_step?: string | null;
  result?: Record<string, unknown>;
  error?: string | null;
  metadata?: Record<string, unknown>;
  created_by?: 'system' | 'user' | 'agent';
  created_by_client?: string | null;
  created_at?: string;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface CaptureSourceItem {
  id: string;
  youtube_video_id: string;
  status: 'discovered' | 'queued' | 'indexed' | 'skipped' | 'failed';
  ingestion_job_id?: string | null;
  skip_reason?: string | null;
  metadata?: {
    title?: string;
    [key: string]: unknown;
  };
  discovered_at?: string;
  updated_at?: string;
}

export interface CaptureSource {
  id: string;
  user_id?: string;
  project_id?: string | null;
  source_type: 'playlist' | 'liked_videos';
  source_url: string;
  external_id: string;
  title: string;
  status: 'active' | 'paused' | 'error' | 'archived';
  visibility?: 'public' | 'private' | 'unlisted' | 'unknown';
  last_synced_at?: string | null;
  last_error?: string | null;
  recentItems?: CaptureSourceItem[];
  created_by?: 'user' | 'agent';
  created_by_client?: string | null;
  created_at?: string;
}

export interface CaptureSourceSyncResult {
  captureSource: CaptureSource;
  workflowInstance?: WorkflowInstance;
  workflow_instance_id?: string;
  discoveredCount: number;
  newItemCount: number;
  queueCandidateCount?: number;
  queuedJobCount: number;
  requestedJobCount?: number;
  remainingQueueCount?: number;
  skippedExistingCount: number;
  activeJobLimitReached: boolean;
  costEstimate?: IngestionCostEstimate | Record<string, unknown>;
  newItems?: CaptureSourceItem[];
  queuedItems?: CaptureSourceItem[];
  queuedJobs?: IngestionJob[];
  guidance?: string;
}

export interface YoutubeOAuthStatus {
  connected: boolean;
  needsReconnect: boolean;
  youtubeReadonlyGranted: boolean;
  hasRefreshToken: boolean;
  scopes: string[];
  expiresAt?: string | null;
  connectedAt?: string | null;
  updatedAt?: string | null;
  lastError?: string | null;
}

export interface OnboardingSignalState {
  youtubeConnected: boolean;
  hasCaptureSource: boolean;
  hasGrantedVideo: boolean;
  hasQueuedOrIndexedJob: boolean;
  hasMcpToken: boolean;
  hasSearchUsage: boolean;
  activationComplete: boolean;
}

export interface OnboardingNextStep {
  id: string;
  label: string;
  reason: string;
}

export interface OnboardingStatus {
  step: 'intro' | 'youtube' | 'playlist' | 'first_import' | 'agent' | 'done' | 'skipped';
  state: Record<string, unknown>;
  completedAt?: string | null;
  skippedAt?: string | null;
  explicitCompleted: boolean;
  explicitSkipped: boolean;
  derived: OnboardingSignalState;
  nextSteps: OnboardingNextStep[];
}

export interface SaveYoutubeOAuthConnectionRequest {
  access_token?: string | null;
  refresh_token?: string | null;
  expires_in?: number | null;
  expires_at?: string | null;
  scopes: string[];
}

export type AppMode =
  | 'home'
  | 'unified'
  | 'ingest'
  | 'search'
  | 'library'
  | 'projects'
  | 'jobs'
  | 'about'
  | 'contact';

// Search history types
export interface SearchHistoryClip {
  videoId: string;
  title: string;
  thumbnailUrl: string;
  startSeconds: number;
  channelName: string;
}

export interface SearchHistoryEntry {
  id: string;
  query: string;
  timestamp: number;
  clips: SearchHistoryClip[];
}
