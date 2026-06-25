-- 010_user_video_access.sql
-- Precise per-user access grants for canonical shared videos.

CREATE TABLE IF NOT EXISTS user_videos (
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    access_source TEXT NOT NULL DEFAULT 'ingest'
        CHECK (access_source IN (
            'ingest',
            'channel',
            'playlist',
            'capture_sync',
            'shared_existing',
            'agent'
        )),
    source_url TEXT,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, video_id)
);

CREATE INDEX IF NOT EXISTS user_videos_user_added_idx
    ON user_videos(user_id, added_at DESC);
CREATE INDEX IF NOT EXISTS user_videos_video_idx
    ON user_videos(video_id);

ALTER TABLE user_videos ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_videos_select ON user_videos
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY user_videos_insert ON user_videos
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY user_videos_delete ON user_videos
    FOR DELETE USING (auth.uid() = user_id);

CREATE OR REPLACE FUNCTION search_chunks(
  query_embedding VECTOR(768),
  match_user_id UUID,
  match_limit INT DEFAULT 20,
  min_start_seconds INT DEFAULT 0
)
RETURNS TABLE (
  youtube_video_id TEXT,
  title TEXT,
  channel_name TEXT,
  start_seconds INT,
  end_seconds INT,
  content TEXT,
  thumbnail_url TEXT,
  similarity FLOAT
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT
    v.youtube_video_id,
    v.title,
    ch.name AS channel_name,
    c.start_seconds,
    c.end_seconds,
    c.content,
    v.thumbnail_url,
    1 - (c.embedding <=> query_embedding) AS similarity
  FROM chunks c
  JOIN videos v ON v.id = c.video_id
  JOIN channels ch ON ch.id = v.channel_id
  WHERE c.start_seconds >= min_start_seconds
    AND (
      EXISTS (
        SELECT 1
        FROM user_channels uc
        WHERE uc.user_id = match_user_id
          AND uc.channel_id = v.channel_id
      )
      OR EXISTS (
        SELECT 1
        FROM user_videos uv
        WHERE uv.user_id = match_user_id
          AND uv.video_id = v.id
      )
    )
  ORDER BY c.embedding <=> query_embedding
  LIMIT match_limit;
$$;
