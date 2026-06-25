-- 011_search_category_filters.sql
-- Category-filtered semantic search over user-accessible canonical videos.

DROP FUNCTION IF EXISTS search_chunks(VECTOR(768), UUID, INT, INT);

CREATE OR REPLACE FUNCTION search_chunks(
  query_embedding VECTOR(768),
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
  ORDER BY c.embedding <=> query_embedding
  LIMIT match_limit;
$$;
