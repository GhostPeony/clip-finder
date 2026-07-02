-- 028_chunk_idempotency.sql
-- Make chunk writes idempotent: dedupe any historical duplicate rows, then
-- enforce one chunk per (video_id, start_seconds) so ingestion can upsert
-- instead of blindly inserting (partial-ingest repair depends on this).

DELETE FROM chunks a
USING chunks b
WHERE a.video_id = b.video_id
  AND a.start_seconds = b.start_seconds
  AND a.ctid > b.ctid;

CREATE UNIQUE INDEX IF NOT EXISTS chunks_video_start_uidx
    ON chunks (video_id, start_seconds);
