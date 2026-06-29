-- 026_project_scoped_context.sql
-- User-owned projects that scope saved-video context without replacing
-- user_videos/user_channels access grants.

CREATE TABLE IF NOT EXISTS user_projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'archived')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, slug)
);

CREATE INDEX IF NOT EXISTS user_projects_user_status_idx
    ON user_projects(user_id, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS user_project_videos (
    project_id UUID NOT NULL REFERENCES user_projects(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    added_source TEXT NOT NULL DEFAULT 'manual'
        CHECK (added_source IN ('manual', 'capture_sync', 'ingest', 'agent')),
    capture_source_id UUID REFERENCES youtube_capture_sources(id) ON DELETE SET NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (project_id, video_id)
);

CREATE INDEX IF NOT EXISTS user_project_videos_user_project_idx
    ON user_project_videos(user_id, project_id, added_at DESC);
CREATE INDEX IF NOT EXISTS user_project_videos_user_video_idx
    ON user_project_videos(user_id, video_id);

ALTER TABLE youtube_capture_sources
    ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES user_projects(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS youtube_capture_sources_project_idx
    ON youtube_capture_sources(user_id, project_id)
    WHERE project_id IS NOT NULL;

DROP TRIGGER IF EXISTS user_projects_touch_updated_at ON user_projects;
CREATE TRIGGER user_projects_touch_updated_at
    BEFORE UPDATE ON user_projects
    FOR EACH ROW EXECUTE FUNCTION touch_context_updated_at();

ALTER TABLE user_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_project_videos ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS user_projects_select ON user_projects;
CREATE POLICY user_projects_select ON user_projects
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS user_projects_insert ON user_projects;
CREATE POLICY user_projects_insert ON user_projects
    FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS user_projects_update ON user_projects;
CREATE POLICY user_projects_update ON user_projects
    FOR UPDATE USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS user_projects_delete ON user_projects;
CREATE POLICY user_projects_delete ON user_projects
    FOR DELETE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS user_project_videos_select ON user_project_videos;
CREATE POLICY user_project_videos_select ON user_project_videos
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS user_project_videos_insert ON user_project_videos;
CREATE POLICY user_project_videos_insert ON user_project_videos
    FOR INSERT WITH CHECK (
        auth.uid() = user_id
        AND EXISTS (
            SELECT 1 FROM user_projects up
            WHERE up.id = user_project_videos.project_id
              AND up.user_id = user_project_videos.user_id
        )
        AND EXISTS (
            SELECT 1
            FROM videos v
            LEFT JOIN user_channels uc
              ON uc.channel_id = v.channel_id
             AND uc.user_id = user_project_videos.user_id
            LEFT JOIN user_videos uv
              ON uv.video_id = v.id
             AND uv.user_id = user_project_videos.user_id
            WHERE v.id = user_project_videos.video_id
              AND (uc.user_id IS NOT NULL OR uv.user_id IS NOT NULL)
        )
    );

DROP POLICY IF EXISTS user_project_videos_delete ON user_project_videos;
CREATE POLICY user_project_videos_delete ON user_project_videos
    FOR DELETE USING (auth.uid() = user_id);

DROP FUNCTION IF EXISTS search_chunks(VECTOR(768), UUID, INT, INT, JSONB);
DROP FUNCTION IF EXISTS search_chunks(VECTOR(768), UUID, INT, INT, JSONB, UUID);

CREATE OR REPLACE FUNCTION search_chunks(
  query_embedding VECTOR(768),
  match_user_id UUID,
  match_limit INT DEFAULT 20,
  min_start_seconds INT DEFAULT 0,
  category_filters JSONB DEFAULT '{}'::jsonb,
  match_project_id UUID DEFAULT NULL
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
  SELECT
    v.youtube_video_id,
    v.title,
    ch.name AS channel_name,
    c.start_seconds,
    c.end_seconds,
    c.content,
    v.thumbnail_url,
    1 - (c.embedding <=> query_embedding) AS similarity,
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
    )
  ORDER BY c.embedding <=> query_embedding
  LIMIT match_limit;
$$;

DROP FUNCTION IF EXISTS search_chunks_keyword(TEXT, UUID, INT, INT, JSONB);
DROP FUNCTION IF EXISTS search_chunks_keyword(TEXT, UUID, INT, INT, JSONB, UUID);

CREATE OR REPLACE FUNCTION search_chunks_keyword(
  search_query TEXT,
  match_user_id UUID,
  match_limit INT DEFAULT 20,
  min_start_seconds INT DEFAULT 0,
  category_filters JSONB DEFAULT '{}'::jsonb,
  match_project_id UUID DEFAULT NULL
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

DROP FUNCTION IF EXISTS search_chunks_hybrid(VECTOR(768), TEXT, UUID, INT, INT, JSONB);
DROP FUNCTION IF EXISTS search_chunks_hybrid(VECTOR(768), TEXT, UUID, INT, INT, JSONB, UUID);

CREATE OR REPLACE FUNCTION search_chunks_hybrid(
  query_embedding VECTOR(768),
  search_query TEXT,
  match_user_id UUID,
  match_limit INT DEFAULT 20,
  min_start_seconds INT DEFAULT 0,
  category_filters JSONB DEFAULT '{}'::jsonb,
  match_project_id UUID DEFAULT NULL
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
      v.id AS video_db_id,
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

DROP FUNCTION IF EXISTS search_source_knowledge_hybrid(VECTOR(768), TEXT, UUID, INT, JSONB, TEXT);
DROP FUNCTION IF EXISTS search_source_knowledge_hybrid(VECTOR(768), TEXT, UUID, INT, JSONB, TEXT, UUID);

CREATE OR REPLACE FUNCTION search_source_knowledge_hybrid(
    query_embedding VECTOR(768),
    search_query TEXT,
    match_user_id UUID,
    match_limit INT DEFAULT 20,
    category_filters JSONB DEFAULT '{}'::jsonb,
    retrieval_mode TEXT DEFAULT 'hybrid',
    match_project_id UUID DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    video_id UUID,
    source_object_type TEXT,
    source_object_id TEXT,
    section_key TEXT,
    title TEXT,
    body TEXT,
    aliases TEXT[],
    source_refs JSONB,
    metadata JSONB,
    index_version TEXT,
    youtube_video_id TEXT,
    video_title TEXT,
    channel_name TEXT,
    thumbnail_url TEXT,
    transcript_seconds INT,
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
    WITH settings AS (
        SELECT
            CASE
                WHEN LOWER(COALESCE(retrieval_mode, 'hybrid')) IN ('hybrid', 'semantic', 'keyword')
                    THEN LOWER(COALESCE(retrieval_mode, 'hybrid'))
                ELSE 'hybrid'
            END AS mode,
            websearch_to_tsquery('english', COALESCE(search_query, '')) AS tsq
    ),
    accessible AS (
        SELECT
            ski.id AS index_id,
            ski.video_id,
            ski.source_object_type,
            ski.source_object_id,
            ski.section_key,
            ski.title,
            ski.body,
            ski.aliases,
            ski.source_refs,
            ski.metadata,
            ski.index_version,
            v.youtube_video_id,
            v.title AS video_title,
            ch.name AS channel_name,
            v.thumbnail_url,
            v.transcript_seconds,
            CASE
                WHEN query_embedding IS NOT NULL AND ski.embedding IS NOT NULL
                    THEN ski.embedding <=> query_embedding
                ELSE NULL
            END AS embedding_distance,
            CASE
                WHEN query_embedding IS NOT NULL AND ski.embedding IS NOT NULL
                    THEN 1 - (ski.embedding <=> query_embedding)
                ELSE NULL
            END AS similarity,
            CASE
                WHEN numnode(settings.tsq) > 0 THEN ts_rank_cd(search_doc.document, settings.tsq)::float
                ELSE 0::float
            END AS keyword_rank,
            CASE
                WHEN numnode(settings.tsq) > 0 THEN ts_headline(
                    'english',
                    COALESCE(NULLIF(ski.body, ''), ski.title),
                    settings.tsq,
                    'StartSel=<mark>, StopSel=</mark>, MaxWords=42, MinWords=12'
                )
                ELSE NULL
            END AS headline,
            CASE
                WHEN numnode(settings.tsq) > 0
                  AND (
                    to_tsvector('english', COALESCE(ski.title, '')) @@ settings.tsq
                    OR to_tsvector('english', COALESCE(array_to_string(ski.aliases, ' '), '')) @@ settings.tsq
                  )
                    THEN 'title_alias_keyword'
                WHEN numnode(settings.tsq) > 0
                  AND to_tsvector('english', COALESCE(v.title, '')) @@ settings.tsq
                    THEN 'video_title_keyword'
                WHEN numnode(settings.tsq) > 0
                  AND search_doc.document @@ settings.tsq
                    THEN 'source_knowledge_keyword'
                ELSE 'semantic_source_knowledge'
            END AS keyword_match_type,
            settings.mode,
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
        FROM source_knowledge_index ski
        JOIN videos v ON v.id = ski.video_id
        JOIN channels ch ON ch.id = v.channel_id
        CROSS JOIN settings
        CROSS JOIN LATERAL (
            SELECT
                setweight(to_tsvector('english', COALESCE(ski.title, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(ski.aliases, ' '), '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(v.title, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(ski.body, '')), 'C') AS document
        ) search_doc
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
          )
    ),
    vector_ranked AS (
        SELECT
            index_id,
            ROW_NUMBER() OVER (ORDER BY embedding_distance ASC) AS vector_position
        FROM accessible
        WHERE mode IN ('hybrid', 'semantic')
          AND embedding_distance IS NOT NULL
        ORDER BY embedding_distance ASC
        LIMIT GREATEST(match_limit * 4, match_limit)
    ),
    keyword_ranked AS (
        SELECT
            index_id,
            ROW_NUMBER() OVER (
                ORDER BY
                    keyword_rank DESC,
                    CASE source_object_type
                        WHEN 'source_concept' THEN 0
                        WHEN 'report_section' THEN 1
                        ELSE 2
                    END,
                    title ASC
            ) AS keyword_position
        FROM accessible
        WHERE mode IN ('hybrid', 'keyword')
          AND keyword_rank > 0
        ORDER BY keyword_rank DESC, title ASC
        LIMIT GREATEST(match_limit * 4, match_limit)
    )
    SELECT
        a.index_id AS id,
        a.video_id,
        a.source_object_type,
        a.source_object_id,
        a.section_key,
        a.title,
        a.body,
        a.aliases,
        a.source_refs,
        a.metadata,
        a.index_version,
        a.youtube_video_id,
        a.video_title,
        a.channel_name,
        a.thumbnail_url,
        a.transcript_seconds,
        a.similarity::float,
        a.keyword_rank::float,
        a.headline,
        CASE
            WHEN vr.vector_position IS NOT NULL AND kr.keyword_position IS NOT NULL
                THEN 'hybrid'
            WHEN kr.keyword_position IS NOT NULL
                THEN a.keyword_match_type
            ELSE 'semantic_source_knowledge'
        END AS match_type,
        (
            COALESCE(1.0 / (60 + vr.vector_position), 0) +
            COALESCE(1.0 / (60 + kr.keyword_position), 0) +
            CASE a.source_object_type
                WHEN 'source_concept' THEN 0.004
                WHEN 'report_section' THEN 0.003
                ELSE 0.002
            END +
            CASE WHEN jsonb_array_length(COALESCE(a.source_refs, '[]'::jsonb)) > 0 THEN 0.003 ELSE 0 END
        )::float AS hybrid_score,
        a.access_scope,
        a.access_source,
        a.access_reason
    FROM accessible a
    LEFT JOIN vector_ranked vr ON vr.index_id = a.index_id
    LEFT JOIN keyword_ranked kr ON kr.index_id = a.index_id
    WHERE (
        a.mode = 'hybrid'
        AND (vr.index_id IS NOT NULL OR kr.index_id IS NOT NULL)
    ) OR (
        a.mode = 'semantic'
        AND vr.index_id IS NOT NULL
    ) OR (
        a.mode = 'keyword'
        AND kr.index_id IS NOT NULL
    )
    ORDER BY
        hybrid_score DESC,
        keyword_rank DESC,
        similarity DESC NULLS LAST,
        title ASC
    LIMIT match_limit;
$$;
