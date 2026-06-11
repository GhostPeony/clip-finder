-- Durable ingestion job tracking for hosted production mode.

CREATE TABLE ingestion_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    source_url TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'unknown'
        CHECK (source_type IN ('channel', 'playlist', 'video', 'unknown')),
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'completed', 'failed', 'partial', 'cancelled')),
    requested_video_count INT NOT NULL DEFAULT 0,
    indexed_video_count INT NOT NULL DEFAULT 0,
    skipped_video_count INT NOT NULL DEFAULT 0,
    failed_video_count INT NOT NULL DEFAULT 0,
    last_message TEXT,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ingestion_jobs_user_created_idx ON ingestion_jobs(user_id, created_at DESC);
CREATE INDEX ingestion_jobs_status_idx ON ingestion_jobs(status);

CREATE TABLE ingestion_job_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES ingestion_jobs(id) ON DELETE CASCADE,
    level TEXT NOT NULL DEFAULT 'info'
        CHECK (level IN ('info', 'warning', 'error')),
    message TEXT NOT NULL,
    youtube_video_id TEXT,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ingestion_job_events_job_created_idx ON ingestion_job_events(job_id, created_at);

CREATE OR REPLACE FUNCTION touch_ingestion_jobs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER ingestion_jobs_touch_updated_at
    BEFORE UPDATE ON ingestion_jobs
    FOR EACH ROW EXECUTE FUNCTION touch_ingestion_jobs_updated_at();

ALTER TABLE ingestion_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE ingestion_job_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY ingestion_jobs_select ON ingestion_jobs
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY ingestion_job_events_select ON ingestion_job_events
    FOR SELECT USING (
        EXISTS (
            SELECT 1
            FROM ingestion_jobs
            WHERE ingestion_jobs.id = ingestion_job_events.job_id
              AND ingestion_jobs.user_id = auth.uid()
        )
    );
