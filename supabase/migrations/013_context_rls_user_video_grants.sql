-- 013_context_rls_user_video_grants.sql
-- Keep read-only source context RLS aligned with precise user_videos grants.
--
-- Canonical video context is shared for storage/compute efficiency, but visibility
-- is user-scoped through either user_channels or user_videos. Earlier source
-- context policies only checked channel grants; this migration lets users with
-- an explicit saved-video grant read the same transcript-derived context.

DROP POLICY IF EXISTS transcript_lines_select ON transcript_lines;
CREATE POLICY transcript_lines_select ON transcript_lines
    FOR SELECT USING (
        EXISTS (
            SELECT 1
            FROM videos v
            WHERE v.id = transcript_lines.video_id
              AND (
                EXISTS (
                    SELECT 1
                    FROM user_channels uc
                    WHERE uc.user_id = auth.uid()
                      AND uc.channel_id = v.channel_id
                )
                OR EXISTS (
                    SELECT 1
                    FROM user_videos uv
                    WHERE uv.user_id = auth.uid()
                      AND uv.video_id = v.id
                )
              )
        )
    );

DROP POLICY IF EXISTS source_concepts_select ON source_concepts;
CREATE POLICY source_concepts_select ON source_concepts
    FOR SELECT USING (
        video_id IS NULL OR EXISTS (
            SELECT 1
            FROM videos v
            WHERE v.id = source_concepts.video_id
              AND (
                EXISTS (
                    SELECT 1
                    FROM user_channels uc
                    WHERE uc.user_id = auth.uid()
                      AND uc.channel_id = v.channel_id
                )
                OR EXISTS (
                    SELECT 1
                    FROM user_videos uv
                    WHERE uv.user_id = auth.uid()
                      AND uv.video_id = v.id
                )
              )
        )
    );

DROP POLICY IF EXISTS source_edges_select ON source_edges;
CREATE POLICY source_edges_select ON source_edges
    FOR SELECT USING (
        video_id IS NULL OR EXISTS (
            SELECT 1
            FROM videos v
            WHERE v.id = source_edges.video_id
              AND (
                EXISTS (
                    SELECT 1
                    FROM user_channels uc
                    WHERE uc.user_id = auth.uid()
                      AND uc.channel_id = v.channel_id
                )
                OR EXISTS (
                    SELECT 1
                    FROM user_videos uv
                    WHERE uv.user_id = auth.uid()
                      AND uv.video_id = v.id
                )
              )
        )
    );

DROP POLICY IF EXISTS knowledge_artifacts_select ON knowledge_artifacts;
CREATE POLICY knowledge_artifacts_select ON knowledge_artifacts
    FOR SELECT USING (
        user_id = auth.uid()
        OR (
            user_id IS NULL
            AND (
                video_id IS NULL OR EXISTS (
                    SELECT 1
                    FROM videos v
                    WHERE v.id = knowledge_artifacts.video_id
                      AND (
                        EXISTS (
                            SELECT 1
                            FROM user_channels uc
                            WHERE uc.user_id = auth.uid()
                              AND uc.channel_id = v.channel_id
                        )
                        OR EXISTS (
                            SELECT 1
                            FROM user_videos uv
                            WHERE uv.user_id = auth.uid()
                              AND uv.video_id = v.id
                        )
                      )
                )
            )
        )
    );

DROP POLICY IF EXISTS source_labels_select ON source_labels;
CREATE POLICY source_labels_select ON source_labels
    FOR SELECT USING (
        EXISTS (
            SELECT 1
            FROM videos v
            WHERE v.id = source_labels.video_id
              AND (
                EXISTS (
                    SELECT 1
                    FROM user_channels uc
                    WHERE uc.user_id = auth.uid()
                      AND uc.channel_id = v.channel_id
                )
                OR EXISTS (
                    SELECT 1
                    FROM user_videos uv
                    WHERE uv.user_id = auth.uid()
                      AND uv.video_id = v.id
                )
              )
        )
    );
