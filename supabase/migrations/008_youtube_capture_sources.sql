-- 008_youtube_capture_sources.sql
-- Standing YouTube capture sources for low-friction saved-video ingestion.

CREATE TABLE IF NOT EXISTS youtube_capture_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL DEFAULT 'playlist'
        CHECK (source_type IN ('playlist', 'liked_videos')),
    source_url TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'paused', 'error', 'archived')),
    visibility TEXT NOT NULL DEFAULT 'unknown'
        CHECK (visibility IN ('public', 'private', 'unlisted', 'unknown')),
    sync_cadence_minutes INT NOT NULL DEFAULT 60
        CHECK (sync_cadence_minutes >= 15),
    last_synced_at TIMESTAMPTZ,
    last_seen_item_at TIMESTAMPTZ,
    last_error TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT NOT NULL DEFAULT 'user'
        CHECK (created_by IN ('user', 'agent')),
    created_by_client TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, source_type, external_id)
);

CREATE INDEX IF NOT EXISTS youtube_capture_sources_user_status_idx
    ON youtube_capture_sources(user_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS youtube_capture_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    capture_source_id UUID NOT NULL REFERENCES youtube_capture_sources(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    youtube_video_id TEXT NOT NULL,
    playlist_item_id TEXT,
    source_added_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'discovered'
        CHECK (status IN ('discovered', 'queued', 'indexed', 'skipped', 'failed')),
    ingestion_job_id UUID REFERENCES ingestion_jobs(id) ON DELETE SET NULL,
    skip_reason TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (capture_source_id, youtube_video_id)
);

CREATE INDEX IF NOT EXISTS youtube_capture_items_source_status_idx
    ON youtube_capture_items(capture_source_id, status, discovered_at DESC);
CREATE INDEX IF NOT EXISTS youtube_capture_items_user_video_idx
    ON youtube_capture_items(user_id, youtube_video_id);

DROP TRIGGER IF EXISTS youtube_capture_sources_touch_updated_at ON youtube_capture_sources;
CREATE TRIGGER youtube_capture_sources_touch_updated_at
    BEFORE UPDATE ON youtube_capture_sources
    FOR EACH ROW EXECUTE FUNCTION touch_context_updated_at();

DROP TRIGGER IF EXISTS youtube_capture_items_touch_updated_at ON youtube_capture_items;
CREATE TRIGGER youtube_capture_items_touch_updated_at
    BEFORE UPDATE ON youtube_capture_items
    FOR EACH ROW EXECUTE FUNCTION touch_context_updated_at();

ALTER TABLE youtube_capture_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE youtube_capture_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY youtube_capture_sources_select ON youtube_capture_sources
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY youtube_capture_sources_insert ON youtube_capture_sources
    FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY youtube_capture_sources_update ON youtube_capture_sources
    FOR UPDATE USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
CREATE POLICY youtube_capture_sources_delete ON youtube_capture_sources
    FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY youtube_capture_items_select ON youtube_capture_items
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY youtube_capture_items_insert ON youtube_capture_items
    FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY youtube_capture_items_update ON youtube_capture_items
    FOR UPDATE USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
