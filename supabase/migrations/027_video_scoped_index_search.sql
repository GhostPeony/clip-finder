-- 027_video_scoped_index_search.sql
-- Consolidate the copy-pasted search access gates into one SECURITY DEFINER
-- helper, add SQL-side video scoping (match_youtube_video_id), and make the
-- keyword/hybrid lanes index-friendly: GIN-driven candidate selects, ranking
-- on candidates only, ts_headline on the final rows only.
--
-- Documented semantic delta: multi-term AND queries whose terms are split
-- across title and content no longer match the keyword lane (candidates are
-- a UNION of content-FTS and title-FTS matches). Such rows remain reachable
-- through the vector lane in hybrid retrieval.

DROP FUNCTION IF EXISTS accessible_video_ids(UUID, UUID, JSONB, TEXT);

CREATE OR REPLACE FUNCTION accessible_video_ids(
  match_user_id UUID,
  match_project_id UUID DEFAULT NULL,
  category_filters JSONB DEFAULT '{}'::jsonb,
  match_youtube_video_id TEXT DEFAULT NULL
)
RETURNS TABLE (
  video_id UUID,
  youtube_video_id TEXT,
  title TEXT,
  channel_name TEXT,
  thumbnail_url TEXT,
  has_channel_access BOOLEAN,
  video_access_source TEXT
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT
    v.id AS video_id,
    v.youtube_video_id,
    v.title,
    ch.name AS channel_name,
    v.thumbnail_url,
    COALESCE(channel_access.has_access, FALSE) AS has_channel_access,
    video_access.access_source AS video_access_source
  FROM videos v
  JOIN channels ch ON ch.id = v.channel_id
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
  WHERE (
      COALESCE(channel_access.has_access, FALSE)
      OR video_access.access_source IS NOT NULL
    )
    AND (
      match_youtube_video_id IS NULL
      OR v.youtube_video_id = match_youtube_video_id
    )
    AND (
      match_project_id IS NULL
      OR EXISTS (
        SELECT 1
        FROM user_project_videos upv
        WHERE upv.user_id = match_user_id
          AND upv.project_id = match_project_id
          AND upv.video_id = v.id
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
    );
$$;

REVOKE ALL ON FUNCTION accessible_video_ids(UUID, UUID, JSONB, TEXT)
  FROM PUBLIC, anon, authenticated;

DROP FUNCTION IF EXISTS search_chunks(VECTOR(768), UUID, INT, INT, JSONB, UUID);
DROP FUNCTION IF EXISTS search_chunks(VECTOR(768), UUID, INT, INT, JSONB, UUID, TEXT);

CREATE OR REPLACE FUNCTION search_chunks(
  query_embedding VECTOR(768),
  match_user_id UUID,
  match_limit INT DEFAULT 20,
  min_start_seconds INT DEFAULT 0,
  category_filters JSONB DEFAULT '{}'::jsonb,
  match_project_id UUID DEFAULT NULL,
  match_youtube_video_id TEXT DEFAULT NULL
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
  access_scope TEXT,
  access_source TEXT,
  access_reason TEXT
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  WITH allowed AS (
    SELECT *
    FROM accessible_video_ids(
      match_user_id,
      match_project_id,
      category_filters,
      match_youtube_video_id
    )
  )
  SELECT
    a.youtube_video_id,
    a.title,
    a.channel_name,
    c.start_seconds,
    c.end_seconds,
    c.content,
    a.thumbnail_url,
    1 - (c.embedding <=> query_embedding) AS similarity,
    CASE
      WHEN a.has_channel_access
        AND a.video_access_source IS NOT NULL
        THEN 'channel_and_video'
      WHEN a.has_channel_access
        THEN 'channel'
      ELSE 'video'
    END AS access_scope,
    COALESCE(a.video_access_source, 'channel') AS access_source,
    CASE
      WHEN a.has_channel_access
        AND a.video_access_source IS NOT NULL
        THEN 'Visible through channel access and an explicit video grant.'
      WHEN a.has_channel_access
        THEN 'Visible through a channel access grant.'
      ELSE 'Visible through an explicit saved-video grant.'
    END AS access_reason
  FROM chunks c
  JOIN allowed a ON a.video_id = c.video_id
  WHERE c.start_seconds >= min_start_seconds
  ORDER BY c.embedding <=> query_embedding
  LIMIT match_limit;
$$;

DROP FUNCTION IF EXISTS search_chunks_keyword(TEXT, UUID, INT, INT, JSONB, UUID);
DROP FUNCTION IF EXISTS search_chunks_keyword(TEXT, UUID, INT, INT, JSONB, UUID, TEXT);

CREATE OR REPLACE FUNCTION search_chunks_keyword(
  search_query TEXT,
  match_user_id UUID,
  match_limit INT DEFAULT 20,
  min_start_seconds INT DEFAULT 0,
  category_filters JSONB DEFAULT '{}'::jsonb,
  match_project_id UUID DEFAULT NULL,
  match_youtube_video_id TEXT DEFAULT NULL
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
  ),
  allowed AS (
    SELECT *
    FROM accessible_video_ids(
      match_user_id,
      match_project_id,
      category_filters,
      match_youtube_video_id
    )
  ),
  candidates AS (
    SELECT c.id AS chunk_id
    FROM chunks c
    JOIN allowed a ON a.video_id = c.video_id
    CROSS JOIN query
    WHERE numnode(query.tsq) > 0
      AND c.start_seconds >= min_start_seconds
      AND to_tsvector('english', COALESCE(c.content, '')) @@ query.tsq
    UNION
    SELECT c.id AS chunk_id
    FROM chunks c
    JOIN allowed a ON a.video_id = c.video_id
    CROSS JOIN query
    WHERE numnode(query.tsq) > 0
      AND c.start_seconds >= min_start_seconds
      AND to_tsvector('english', COALESCE(a.title, '')) @@ query.tsq
  ),
  ranked AS (
    SELECT
      a.youtube_video_id,
      a.title,
      a.channel_name,
      c.start_seconds,
      c.end_seconds,
      c.content,
      a.thumbnail_url,
      ts_rank_cd(
        setweight(to_tsvector('english', COALESCE(a.title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(c.content, '')), 'B'),
        query.tsq
      )::float AS keyword_rank,
      a.has_channel_access,
      a.video_access_source
    FROM chunks c
    JOIN candidates cand ON cand.chunk_id = c.id
    JOIN allowed a ON a.video_id = c.video_id
    CROSS JOIN query
    ORDER BY keyword_rank DESC, c.start_seconds ASC
    LIMIT match_limit
  )
  SELECT
    r.youtube_video_id,
    r.title,
    r.channel_name,
    r.start_seconds,
    r.end_seconds,
    r.content,
    r.thumbnail_url,
    r.keyword_rank,
    ts_headline(
      'english',
      r.content,
      query.tsq,
      'StartSel=<mark>, StopSel=</mark>, MaxWords=36, MinWords=12'
    ) AS headline,
    CASE
      WHEN to_tsvector('english', COALESCE(r.title, '')) @@ query.tsq
        THEN 'title_keyword'
      ELSE 'transcript_keyword'
    END AS match_type,
    CASE
      WHEN r.has_channel_access
        AND r.video_access_source IS NOT NULL
        THEN 'channel_and_video'
      WHEN r.has_channel_access
        THEN 'channel'
      ELSE 'video'
    END AS access_scope,
    COALESCE(r.video_access_source, 'channel') AS access_source,
    CASE
      WHEN r.has_channel_access
        AND r.video_access_source IS NOT NULL
        THEN 'Visible through channel access and an explicit video grant.'
      WHEN r.has_channel_access
        THEN 'Visible through a channel access grant.'
      ELSE 'Visible through an explicit saved-video grant.'
    END AS access_reason
  FROM ranked r
  CROSS JOIN query
  ORDER BY r.keyword_rank DESC, r.start_seconds ASC;
$$;

DROP FUNCTION IF EXISTS search_chunks_hybrid(VECTOR(768), TEXT, UUID, INT, INT, JSONB, UUID);
DROP FUNCTION IF EXISTS search_chunks_hybrid(VECTOR(768), TEXT, UUID, INT, INT, JSONB, UUID, TEXT);

CREATE OR REPLACE FUNCTION search_chunks_hybrid(
  query_embedding VECTOR(768),
  search_query TEXT,
  match_user_id UUID,
  match_limit INT DEFAULT 20,
  min_start_seconds INT DEFAULT 0,
  category_filters JSONB DEFAULT '{}'::jsonb,
  match_project_id UUID DEFAULT NULL,
  match_youtube_video_id TEXT DEFAULT NULL
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
  allowed AS (
    SELECT *
    FROM accessible_video_ids(
      match_user_id,
      match_project_id,
      category_filters,
      match_youtube_video_id
    )
  ),
  vector_candidates AS (
    SELECT
      c.id AS chunk_id,
      c.embedding <=> query_embedding AS embedding_distance
    FROM chunks c
    JOIN allowed a ON a.video_id = c.video_id
    WHERE c.start_seconds >= min_start_seconds
    ORDER BY c.embedding <=> query_embedding ASC
    LIMIT GREATEST(match_limit * 4, match_limit)
  ),
  vector_ranked AS (
    SELECT
      chunk_id,
      ROW_NUMBER() OVER (ORDER BY embedding_distance ASC) AS vector_position
    FROM vector_candidates
  ),
  keyword_candidates AS (
    SELECT c.id AS chunk_id
    FROM chunks c
    JOIN allowed a ON a.video_id = c.video_id
    CROSS JOIN query
    WHERE numnode(query.tsq) > 0
      AND c.start_seconds >= min_start_seconds
      AND to_tsvector('english', COALESCE(c.content, '')) @@ query.tsq
    UNION
    SELECT c.id AS chunk_id
    FROM chunks c
    JOIN allowed a ON a.video_id = c.video_id
    CROSS JOIN query
    WHERE numnode(query.tsq) > 0
      AND c.start_seconds >= min_start_seconds
      AND to_tsvector('english', COALESCE(a.title, '')) @@ query.tsq
  ),
  keyword_scored AS (
    SELECT
      c.id AS chunk_id,
      ts_rank_cd(
        setweight(to_tsvector('english', COALESCE(a.title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(c.content, '')), 'B'),
        query.tsq
      )::float AS keyword_rank,
      c.start_seconds
    FROM chunks c
    JOIN keyword_candidates cand ON cand.chunk_id = c.id
    JOIN allowed a ON a.video_id = c.video_id
    CROSS JOIN query
    ORDER BY keyword_rank DESC, c.start_seconds ASC
    LIMIT GREATEST(match_limit * 4, match_limit)
  ),
  keyword_ranked AS (
    SELECT
      chunk_id,
      ROW_NUMBER() OVER (ORDER BY keyword_rank DESC, start_seconds ASC) AS keyword_position
    FROM keyword_scored
  ),
  fused AS (
    SELECT
      COALESCE(vr.chunk_id, kr.chunk_id) AS chunk_id,
      vr.vector_position,
      kr.keyword_position,
      (
        COALESCE(1.0 / (60 + vr.vector_position), 0) +
        COALESCE(1.0 / (60 + kr.keyword_position), 0)
      )::float AS hybrid_score
    FROM vector_ranked vr
    FULL OUTER JOIN keyword_ranked kr ON kr.chunk_id = vr.chunk_id
  ),
  scored AS (
    SELECT
      a.youtube_video_id,
      a.title,
      a.channel_name,
      c.start_seconds,
      c.end_seconds,
      c.content,
      a.thumbnail_url,
      (1 - (c.embedding <=> query_embedding))::float AS similarity,
      CASE
        WHEN numnode(query.tsq) > 0 THEN ts_rank_cd(
          setweight(to_tsvector('english', COALESCE(a.title, '')), 'A') ||
          setweight(to_tsvector('english', COALESCE(c.content, '')), 'B'),
          query.tsq
        )::float
        ELSE 0::float
      END AS keyword_rank,
      f.vector_position,
      f.keyword_position,
      f.hybrid_score,
      a.has_channel_access,
      a.video_access_source
    FROM fused f
    JOIN chunks c ON c.id = f.chunk_id
    JOIN allowed a ON a.video_id = c.video_id
    CROSS JOIN query
    ORDER BY f.hybrid_score DESC, keyword_rank DESC, similarity DESC, c.start_seconds ASC
    LIMIT match_limit
  )
  SELECT
    s.youtube_video_id,
    s.title,
    s.channel_name,
    s.start_seconds,
    s.end_seconds,
    s.content,
    s.thumbnail_url,
    s.similarity,
    s.keyword_rank,
    CASE
      WHEN numnode(query.tsq) > 0 THEN ts_headline(
        'english',
        s.content,
        query.tsq,
        'StartSel=<mark>, StopSel=</mark>, MaxWords=36, MinWords=12'
      )
      ELSE NULL
    END AS headline,
    CASE
      WHEN s.vector_position IS NOT NULL AND s.keyword_position IS NOT NULL
        THEN 'hybrid'
      WHEN s.keyword_position IS NOT NULL
        THEN CASE
          WHEN numnode(query.tsq) > 0
            AND to_tsvector('english', COALESCE(s.title, '')) @@ query.tsq
            THEN 'title_keyword'
          WHEN numnode(query.tsq) > 0
            AND to_tsvector('english', COALESCE(s.content, '')) @@ query.tsq
            THEN 'transcript_keyword'
          ELSE 'semantic_transcript'
        END
      ELSE 'semantic_transcript'
    END AS match_type,
    s.hybrid_score,
    CASE
      WHEN s.has_channel_access
        AND s.video_access_source IS NOT NULL
        THEN 'channel_and_video'
      WHEN s.has_channel_access
        THEN 'channel'
      ELSE 'video'
    END AS access_scope,
    COALESCE(s.video_access_source, 'channel') AS access_source,
    CASE
      WHEN s.has_channel_access
        AND s.video_access_source IS NOT NULL
        THEN 'Visible through channel access and an explicit video grant.'
      WHEN s.has_channel_access
        THEN 'Visible through a channel access grant.'
      ELSE 'Visible through an explicit saved-video grant.'
    END AS access_reason
  FROM scored s
  CROSS JOIN query
  ORDER BY s.hybrid_score DESC, s.keyword_rank DESC, s.similarity DESC, s.start_seconds ASC;
$$;

-- Let the HNSW index stream extra candidates past filtered-out rows instead of
-- stopping at ef_search. Guarded: pgvector < 0.8 has no hnsw.iterative_scan.
-- Harmless because both vector-lane RPCs re-sort the bounded candidate set.
DO $do$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_settings WHERE name = 'hnsw.iterative_scan') THEN
    EXECUTE 'ALTER FUNCTION search_chunks(VECTOR(768), UUID, INT, INT, JSONB, UUID, TEXT) '
      'SET hnsw.iterative_scan = relaxed_order';
    EXECUTE 'ALTER FUNCTION search_chunks_hybrid(VECTOR(768), TEXT, UUID, INT, INT, JSONB, UUID, TEXT) '
      'SET hnsw.iterative_scan = relaxed_order';
  END IF;
END
$do$;
