-- 016_ingestion_job_cost_estimate.sql
-- Store preflight ingestion estimates directly on durable ingestion jobs so
-- users and agents can inspect expected cost before/while work runs.

ALTER TABLE ingestion_jobs
    ADD COLUMN IF NOT EXISTS cost_estimate JSONB NOT NULL DEFAULT '{}'::jsonb;
