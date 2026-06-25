-- 024_source_knowledge_index.sql
-- Agent-facing source-knowledge retrieval layer for generated reports,
-- concepts, aliases, report sections, and timestamp references.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS source_knowledge_index (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    source_object_type TEXT NOT NULL
        CHECK (source_object_type IN (
            'source_concept',
            'knowledge_artifact',
            'report_section'
        )),
    source_object_id TEXT NOT NULL,
    section_key TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    aliases TEXT[] NOT NULL DEFAULT '{}',
    source_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding VECTOR(768),
    index_version TEXT NOT NULL DEFAULT 'source-knowledge-index-v1',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (video_id, source_object_type, source_object_id, section_key, index_version)
);

CREATE INDEX IF NOT EXISTS source_knowledge_index_video_idx
    ON source_knowledge_index(video_id);

CREATE INDEX IF NOT EXISTS source_knowledge_index_object_idx
    ON source_knowledge_index(source_object_type, source_object_id);

CREATE INDEX IF NOT EXISTS source_knowledge_index_search_idx
    ON source_knowledge_index
    USING gin (
        to_tsvector(
            'english',
            COALESCE(title, '') || ' ' ||
            COALESCE(body, '')
        )
    );

CREATE INDEX IF NOT EXISTS source_knowledge_index_embedding_idx
    ON source_knowledge_index
    USING hnsw (embedding vector_cosine_ops);

DROP TRIGGER IF EXISTS source_knowledge_index_touch_updated_at ON source_knowledge_index;
CREATE TRIGGER source_knowledge_index_touch_updated_at
    BEFORE UPDATE ON source_knowledge_index
    FOR EACH ROW EXECUTE FUNCTION touch_context_updated_at();

ALTER TABLE source_knowledge_index ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS source_knowledge_index_select ON source_knowledge_index;
CREATE POLICY source_knowledge_index_select ON source_knowledge_index
    FOR SELECT USING (
        EXISTS (
            SELECT 1
            FROM videos v
            LEFT JOIN user_channels uc
              ON uc.channel_id = v.channel_id
             AND uc.user_id = auth.uid()
            LEFT JOIN user_videos uv
              ON uv.video_id = v.id
             AND uv.user_id = auth.uid()
            WHERE v.id = source_knowledge_index.video_id
              AND (uc.user_id IS NOT NULL OR uv.user_id IS NOT NULL)
        )
    );

DROP FUNCTION IF EXISTS search_source_knowledge_hybrid(
    VECTOR(768),
    TEXT,
    UUID,
    INT,
    JSONB,
    TEXT
);

CREATE OR REPLACE FUNCTION search_source_knowledge_hybrid(
    query_embedding VECTOR(768),
    search_query TEXT,
    match_user_id UUID,
    match_limit INT DEFAULT 20,
    category_filters JSONB DEFAULT '{}'::jsonb,
    retrieval_mode TEXT DEFAULT 'hybrid'
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
