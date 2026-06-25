-- Allow confirmed playlist syncs to queue multiple ingestion jobs for one user.
--
-- Older free-tier enforcement allowed only one queued/running job per user. That
-- conflicts with playlist capture sync, where the user explicitly confirms all
-- newly discovered videos before jobs are created. Runtime quota checks still
-- control plan limits; the database should not silently reject the second job.

DROP INDEX IF EXISTS ingestion_jobs_one_active_per_user_idx;
