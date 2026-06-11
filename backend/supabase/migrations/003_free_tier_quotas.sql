-- Cost-aware hosted free-tier quotas.

ALTER TABLE profiles
    ADD COLUMN IF NOT EXISTS free_searches_this_month INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS last_search_month_reset DATE NOT NULL DEFAULT (DATE_TRUNC('month', CURRENT_DATE))::DATE,
    ADD COLUMN IF NOT EXISTS free_indexed_videos_total INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS free_indexed_seconds_total INT NOT NULL DEFAULT 0;

ALTER TABLE videos
    ADD COLUMN IF NOT EXISTS transcript_seconds INT NOT NULL DEFAULT 0;

ALTER TABLE usage_logs
    ADD COLUMN IF NOT EXISTS transcript_seconds INT,
    ADD COLUMN IF NOT EXISTS result_limit INT;

WITH video_seconds AS (
    SELECT
        videos.id,
        COALESCE(MAX(chunks.end_seconds), 0)::INT AS seconds
    FROM videos
    LEFT JOIN chunks ON chunks.video_id = videos.id
    GROUP BY videos.id
)
UPDATE videos
SET transcript_seconds = video_seconds.seconds
FROM video_seconds
WHERE videos.id = video_seconds.id;

WITH user_video_totals AS (
    SELECT
        user_channels.user_id,
        COUNT(DISTINCT videos.id)::INT AS video_count,
        COALESCE(SUM(videos.transcript_seconds), 0)::INT AS transcript_seconds
    FROM user_channels
    JOIN videos ON videos.channel_id = user_channels.channel_id
    GROUP BY user_channels.user_id
)
UPDATE profiles
SET
    free_indexed_videos_total = user_video_totals.video_count,
    free_indexed_seconds_total = user_video_totals.transcript_seconds
FROM user_video_totals
WHERE profiles.id = user_video_totals.user_id;

WITH current_month_searches AS (
    SELECT
        user_id,
        COUNT(*)::INT AS search_count
    FROM usage_logs
    WHERE action = 'search'
      AND used_own_key = FALSE
      AND created_at >= DATE_TRUNC('month', CURRENT_DATE)
    GROUP BY user_id
)
UPDATE profiles
SET
    free_searches_this_month = current_month_searches.search_count,
    last_search_month_reset = (DATE_TRUNC('month', CURRENT_DATE))::DATE
FROM current_month_searches
WHERE profiles.id = current_month_searches.user_id;

CREATE UNIQUE INDEX IF NOT EXISTS ingestion_jobs_one_active_per_user_idx
    ON ingestion_jobs(user_id)
    WHERE status IN ('queued', 'running');
