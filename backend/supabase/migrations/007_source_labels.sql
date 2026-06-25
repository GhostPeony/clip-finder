-- 007_source_labels.sql
-- Read-only, ingestion-generated labels for agent browsing and category filters.

CREATE TABLE IF NOT EXISTS source_labels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    label_type TEXT NOT NULL
        CHECK (label_type IN (
            'topic',
            'domain',
            'content_type',
            'task_fit',
            'entity',
            'method',
            'tool',
            'difficulty',
            'maturity',
            'evidence_quality'
        )),
    label TEXT NOT NULL,
    confidence NUMERIC(4, 3)
        CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    source_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (video_id, label_type, label)
);

CREATE INDEX IF NOT EXISTS source_labels_video_idx ON source_labels(video_id);
CREATE INDEX IF NOT EXISTS source_labels_type_label_idx ON source_labels(label_type, label);
CREATE INDEX IF NOT EXISTS source_labels_search_idx
    ON source_labels USING gin (to_tsvector('english', label_type || ' ' || label));

DROP TRIGGER IF EXISTS source_labels_touch_updated_at ON source_labels;
CREATE TRIGGER source_labels_touch_updated_at
    BEFORE UPDATE ON source_labels
    FOR EACH ROW EXECUTE FUNCTION touch_context_updated_at();

ALTER TABLE source_labels ENABLE ROW LEVEL SECURITY;

CREATE POLICY source_labels_select ON source_labels
    FOR SELECT USING (
        EXISTS (
            SELECT 1
            FROM videos v
            JOIN user_channels uc ON uc.channel_id = v.channel_id
            WHERE v.id = source_labels.video_id
              AND uc.user_id = auth.uid()
        )
    );
