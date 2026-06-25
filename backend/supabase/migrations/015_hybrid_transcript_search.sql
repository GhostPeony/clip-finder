-- 015_hybrid_transcript_search.sql
-- Fuse semantic vector candidates with keyword/title candidates while preserving
-- the same user_channels/user_videos access gate and category filters.

DROP FUNCTION IF EXISTS search_chunks_hybrid(VECTOR(768), TEXT, UUID, INT, INT, JSONB);

CREATE OR REPLACE FUNCTION search_chunks_hybrid(
  query_embedding VECTOR(768),
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
  similarity FLOAT,
  keyword_rank FLOAT,
  headline TEXT,
  match_type TEXT,
  hybrid_score FLOAT,
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
  ),
  accessible_chunks AS (
    SELECT
      c.id AS chunk_id,
      v.youtube_video_id,
      v.title,
      ch.name AS channel_name,
      c.start_seconds,
      c.end_seconds,
      c.content,
      v.thumbnail_url,
      c.embedding <=> query_embedding AS embedding_distance,
      1 - (c.embedding <=> query_embedding) AS similarity,
      CASE
        WHEN numnode(query.tsq) > 0 THEN ts_rank_cd(
          setweight(to_tsvector('english', COALESCE(v.title, '')), 'A') ||
          setweight(to_tsvector('english', COALESCE(c.content, '')), 'B'),
          query.tsq
        )::float
        ELSE 0::float
      END AS keyword_rank,
      CASE
        WHEN numnode(query.tsq) > 0 THEN ts_headline(
          'english',
          c.content,
          query.tsq,
          'StartSel=<mark>, StopSel=</mark>, MaxWords=36, MinWords=12'
        )
        ELSE NULL
      END AS headline,
      CASE
        WHEN numnode(query.tsq) > 0
          AND to_tsvector('english', COALESCE(v.title, '')) @@ query.tsq
          THEN 'title_keyword'
        WHEN numnode(query.tsq) > 0
          AND to_tsvector('english', COALESCE(c.content, '')) @@ query.tsq
          THEN 'transcript_keyword'
        ELSE 'semantic_transcript'
      END AS keyword_match_type,
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
      AND (
        COALESCE(channel_access.has_access, FALSE)
        OR video_access.access_source IS NOT NULL
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
  ),
  vector_ranked AS (
    SELECT
      chunk_id,
      ROW_NUMBER() OVER (ORDER BY embedding_distance ASC) AS vector_position
    FROM accessible_chunks
    ORDER BY embedding_distance ASC
    LIMIT GREATEST(match_limit * 4, match_limit)
  ),
  keyword_ranked AS (
    SELECT
      chunk_id,
      ROW_NUMBER() OVER (ORDER BY keyword_rank DESC, start_seconds ASC) AS keyword_position
    FROM accessible_chunks
    WHERE keyword_rank > 0
    ORDER BY keyword_rank DESC, start_seconds ASC
    LIMIT GREATEST(match_limit * 4, match_limit)
  )
  SELECT
    a.youtube_video_id,
    a.title,
    a.channel_name,
    a.start_seconds,
    a.end_seconds,
    a.content,
    a.thumbnail_url,
    a.similarity,
    a.keyword_rank,
    a.headline,
    CASE
      WHEN vr.vector_position IS NOT NULL AND kr.keyword_position IS NOT NULL
        THEN 'hybrid'
      WHEN kr.keyword_position IS NOT NULL
        THEN a.keyword_match_type
      ELSE 'semantic_transcript'
    END AS match_type,
    (
      COALESCE(1.0 / (60 + vr.vector_position), 0) +
      COALESCE(1.0 / (60 + kr.keyword_position), 0)
    )::float AS hybrid_score,
    a.access_scope,
    a.access_source,
    a.access_reason
  FROM accessible_chunks a
  LEFT JOIN vector_ranked vr ON vr.chunk_id = a.chunk_id
  LEFT JOIN keyword_ranked kr ON kr.chunk_id = a.chunk_id
  WHERE vr.chunk_id IS NOT NULL OR kr.chunk_id IS NOT NULL
  ORDER BY hybrid_score DESC, keyword_rank DESC, similarity DESC, start_seconds ASC
  LIMIT match_limit;
$$;
