-- 004_search_chunks_rpc.sql
-- User-scoped vector search over chunks. Codifies the RPC the hosted app
-- depends on so fresh deploys do not silently lose per-user scoping.
-- Signature must match backend/rag.py search_pg(): search_chunks(
--   query_embedding, match_user_id, match_limit, min_start_seconds).

CREATE OR REPLACE FUNCTION search_chunks(
  query_embedding VECTOR(768),
  match_user_id UUID,
  match_limit INT DEFAULT 20,
  min_start_seconds INT DEFAULT 0
)
RETURNS TABLE (
  youtube_video_id TEXT,
  title TEXT,
  channel_name TEXT,
  start_seconds INT,
  end_seconds INT,
  content TEXT,
  thumbnail_url TEXT,
  similarity FLOAT
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT
    v.youtube_video_id,
    v.title,
    ch.name AS channel_name,
    c.start_seconds,
    c.end_seconds,
    c.content,
    v.thumbnail_url,
    1 - (c.embedding <=> query_embedding) AS similarity
  FROM chunks c
  JOIN videos v ON v.id = c.video_id
  JOIN channels ch ON ch.id = v.channel_id
  JOIN user_channels uc ON uc.channel_id = ch.id
  WHERE uc.user_id = match_user_id
    AND c.start_seconds >= min_start_seconds
  ORDER BY c.embedding <=> query_embedding
  LIMIT match_limit;
$$;
