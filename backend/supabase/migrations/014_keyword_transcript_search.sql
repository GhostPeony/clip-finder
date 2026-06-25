-- 014_keyword_transcript_search.sql
-- Add an exact/entity keyword transcript search lane for agents. This avoids
-- embedding spend for phrase-heavy queries while preserving the same
-- user_channels/user_videos access gate as semantic search.

CREATE INDEX IF NOT EXISTS chunks_content_fts_idx
  ON chunks USING GIN (to_tsvector('english', COALESCE(content, '')));

CREATE INDEX IF NOT EXISTS videos_title_fts_idx
  ON videos USING GIN (to_tsvector('english', COALESCE(title, '')));

DROP FUNCTION IF EXISTS search_chunks_keyword(TEXT, UUID, INT, INT, JSONB);

CREATE OR REPLACE FUNCTION search_chunks_keyword(
  search_query TEXT,
  match_user_id UUID,
  match_limit INT DEFAULT 20,
  min_start_seconds INT DEFAULT 0,
  category_filters JSONB DEFAULT '{}'::jsonb
)
RETURNS TABLE (
  youtube_video_id TEXT,
  title TEXT,
  channel_name TEXT,
  start_seconds INT,
  end_seconds INT,
  content TEXT,
  thumbnail_url TEXT,
  keyword_rank FLOAT,
  headline TEXT,
  match_type TEXT,
  access_scope TEXT,
  access_source TEXT,
  access_reason TEXT
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  WITH query AS (
    SELECT websearch_to_tsquery('english', COALESCE(search_query, '')) AS tsq
  )
  SELECT
    v.youtube_video_id,
    v.title,
    ch.name AS channel_name,
    c.start_seconds,
    c.end_seconds,
    c.content,
    v.thumbnail_url,
    ts_rank_cd(
      setweight(to_tsvector('english', COALESCE(v.title, '')), 'A') ||
      setweight(to_tsvector('english', COALESCE(c.content, '')), 'B'),
      query.tsq
    )::float AS keyword_rank,
    ts_headline(
      'english',
      c.content,
      query.tsq,
      'StartSel=<mark>, StopSel=</mark>, MaxWords=36, MinWords=12'
    ) AS headline,
    CASE
      WHEN to_tsvector('english', COALESCE(v.title, '')) @@ query.tsq
        THEN 'title_keyword'
      ELSE 'transcript_keyword'
    END AS match_type,
    CASE
      WHEN COALESCE(channel_access.has_access, FALSE)
        AND video_access.access_source IS NOT NULL
        THEN 'channel_and_video'
      WHEN COALESCE(channel_access.has_access, FALSE)
        THEN 'channel'
      ELSE 'video'
    END AS access_scope,
    COALESCE(video_access.access_source, 'channel') AS access_source,
    CASE
      WHEN COALESCE(channel_access.has_access, FALSE)
        AND video_access.access_source IS NOT NULL
        THEN 'Visible through channel access and an explicit video grant.'
      WHEN COALESCE(channel_access.has_access, FALSE)
        THEN 'Visible through a channel access grant.'
      ELSE 'Visible through an explicit saved-video grant.'
    END AS access_reason
  FROM chunks c
  JOIN videos v ON v.id = c.video_id
  JOIN channels ch ON ch.id = v.channel_id
  CROSS JOIN query
  LEFT JOIN LATERAL (
    SELECT TRUE AS has_access
    FROM user_channels uc
    WHERE uc.user_id = match_user_id
      AND uc.channel_id = v.channel_id
    LIMIT 1
  ) channel_access ON TRUE
  LEFT JOIN LATERAL (
    SELECT uv.access_source
    FROM user_videos uv
    WHERE uv.user_id = match_user_id
      AND uv.video_id = v.id
    ORDER BY uv.added_at DESC
    LIMIT 1
  ) video_access ON TRUE
  WHERE c.start_seconds >= min_start_seconds
    AND numnode(query.tsq) > 0
    AND (
      COALESCE(channel_access.has_access, FALSE)
      OR video_access.access_source IS NOT NULL
    )
    AND (
      setweight(to_tsvector('english', COALESCE(v.title, '')), 'A') ||
      setweight(to_tsvector('english', COALESCE(c.content, '')), 'B')
    ) @@ query.tsq
    AND (
      COALESCE(category_filters, '{}'::jsonb) = '{}'::jsonb
      OR NOT EXISTS (
        SELECT 1
        FROM jsonb_each(COALESCE(category_filters, '{}'::jsonb)) AS filter(label_type, labels)
        WHERE NOT EXISTS (
          SELECT 1
          FROM source_labels sl
          JOIN jsonb_array_elements_text(filter.labels) AS expected(label)
            ON LOWER(sl.label) = LOWER(expected.label)
          WHERE sl.video_id = v.id
            AND sl.label_type = filter.label_type
        )
      )
    )
  ORDER BY keyword_rank DESC, c.start_seconds ASC
  LIMIT match_limit;
$$;
