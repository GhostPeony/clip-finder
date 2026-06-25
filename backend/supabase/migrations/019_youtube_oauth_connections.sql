-- 019_youtube_oauth_connections.sql
-- Encrypted per-user Google/YouTube OAuth grants for playlist capture sync.

CREATE TABLE IF NOT EXISTS youtube_oauth_connections (
    user_id UUID PRIMARY KEY REFERENCES profiles(id) ON DELETE CASCADE,
    provider TEXT NOT NULL DEFAULT 'google'
        CHECK (provider IN ('google')),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'error', 'revoked')),
    scopes TEXT[] NOT NULL DEFAULT '{}',
    access_token_enc TEXT,
    refresh_token_enc TEXT,
    expires_at TIMESTAMPTZ,
    connected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_error TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS youtube_oauth_connections_status_idx
    ON youtube_oauth_connections(status, updated_at DESC);

DROP TRIGGER IF EXISTS youtube_oauth_connections_touch_updated_at
    ON youtube_oauth_connections;
CREATE TRIGGER youtube_oauth_connections_touch_updated_at
    BEFORE UPDATE ON youtube_oauth_connections
    FOR EACH ROW EXECUTE FUNCTION touch_context_updated_at();

ALTER TABLE youtube_oauth_connections ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS youtube_oauth_connections_select ON youtube_oauth_connections;
DROP POLICY IF EXISTS youtube_oauth_connections_insert ON youtube_oauth_connections;
DROP POLICY IF EXISTS youtube_oauth_connections_update ON youtube_oauth_connections;
DROP POLICY IF EXISTS youtube_oauth_connections_delete ON youtube_oauth_connections;

CREATE POLICY youtube_oauth_connections_select ON youtube_oauth_connections
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY youtube_oauth_connections_insert ON youtube_oauth_connections
    FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY youtube_oauth_connections_update ON youtube_oauth_connections
    FOR UPDATE USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
CREATE POLICY youtube_oauth_connections_delete ON youtube_oauth_connections
    FOR DELETE USING (auth.uid() = user_id);
