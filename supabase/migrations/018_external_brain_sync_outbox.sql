-- 018_external_brain_sync_outbox.sql
-- Bounded outbound sync foundation for external personal brains.
--
-- Source transcript/context tables remain read-only. These tables only track
-- user-owned external brain connections and queued outbound sync events.

CREATE TABLE IF NOT EXISTS external_brain_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    provider TEXT NOT NULL DEFAULT 'custom_webhook'
        CHECK (provider IN (
            'custom_webhook',
            'mcp',
            'notion',
            'obsidian',
            'supermemory',
            'openmemory',
            'other'
        )),
    display_name TEXT NOT NULL DEFAULT '',
    external_id TEXT,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'paused', 'error', 'revoked', 'archived')),
    event_types TEXT[] NOT NULL DEFAULT '{}'
        CHECK (
            event_types <@ ARRAY[
                'video.ingested',
                'knowledge.published',
                'overlay.note.created',
                'capture_source.synced'
            ]::TEXT[]
        ),
    target_url TEXT,
    secret_ref TEXT,
    settings JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_synced_at TIMESTAMPTZ,
    last_error TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT NOT NULL DEFAULT 'user'
        CHECK (created_by IN ('user', 'agent', 'system')),
    created_by_client TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS external_brain_connections_user_status_idx
    ON external_brain_connections(user_id, status, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS external_brain_connections_user_external_idx
    ON external_brain_connections(user_id, provider, external_id)
    WHERE external_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS external_brain_sync_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id UUID NOT NULL REFERENCES external_brain_connections(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL
        CHECK (event_type IN (
            'video.ingested',
            'knowledge.published',
            'overlay.note.created',
            'capture_source.synced'
        )),
    source_ref JSONB NOT NULL DEFAULT '{}'::jsonb,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN (
            'queued',
            'processing',
            'delivered',
            'failed',
            'skipped',
            'dead_letter'
        )),
    idempotency_key TEXT NOT NULL,
    attempt_count INT NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    locked_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (connection_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS external_brain_sync_events_user_status_idx
    ON external_brain_sync_events(user_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS external_brain_sync_events_connection_status_idx
    ON external_brain_sync_events(connection_id, status, available_at);
CREATE INDEX IF NOT EXISTS external_brain_sync_events_type_idx
    ON external_brain_sync_events(event_type, created_at DESC);

DROP TRIGGER IF EXISTS external_brain_connections_touch_updated_at
    ON external_brain_connections;
CREATE TRIGGER external_brain_connections_touch_updated_at
    BEFORE UPDATE ON external_brain_connections
    FOR EACH ROW EXECUTE FUNCTION touch_context_updated_at();

DROP TRIGGER IF EXISTS external_brain_sync_events_touch_updated_at
    ON external_brain_sync_events;
CREATE TRIGGER external_brain_sync_events_touch_updated_at
    BEFORE UPDATE ON external_brain_sync_events
    FOR EACH ROW EXECUTE FUNCTION touch_context_updated_at();

ALTER TABLE external_brain_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE external_brain_sync_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS external_brain_connections_select ON external_brain_connections;
DROP POLICY IF EXISTS external_brain_connections_insert ON external_brain_connections;
DROP POLICY IF EXISTS external_brain_connections_update ON external_brain_connections;
DROP POLICY IF EXISTS external_brain_connections_delete ON external_brain_connections;
DROP POLICY IF EXISTS external_brain_sync_events_select ON external_brain_sync_events;
DROP POLICY IF EXISTS external_brain_sync_events_insert ON external_brain_sync_events;

CREATE POLICY external_brain_connections_select ON external_brain_connections
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY external_brain_connections_insert ON external_brain_connections
    FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY external_brain_connections_update ON external_brain_connections
    FOR UPDATE USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
CREATE POLICY external_brain_connections_delete ON external_brain_connections
    FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY external_brain_sync_events_select ON external_brain_sync_events
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY external_brain_sync_events_insert ON external_brain_sync_events
    FOR INSERT WITH CHECK (
        auth.uid() = user_id
        AND EXISTS (
            SELECT 1
            FROM external_brain_connections ebc
            WHERE ebc.id = external_brain_sync_events.connection_id
              AND ebc.user_id = auth.uid()
        )
    );
