-- Vector similarity search scoped to user's subscribed channels
CREATE OR REPLACE FUNCTION search_chunks(
    query_embedding VECTOR(768),
    match_user_id UUID,
    match_limit INT DEFAULT 10,
    min_start_seconds INT DEFAULT 120
)
RETURNS TABLE (
    chunk_id UUID,
    content TEXT,
    start_seconds INT,
    end_seconds INT,
    youtube_video_id TEXT,
    title TEXT,
    channel_name TEXT,
    thumbnail_url TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id AS chunk_id,
        c.content,
        c.start_seconds,
        c.end_seconds,
        v.youtube_video_id,
        v.title,
        ch.name AS channel_name,
        v.thumbnail_url,
        1 - (c.embedding <=> query_embedding) AS similarity
    FROM chunks c
    JOIN videos v ON c.video_id = v.id
    JOIN channels ch ON v.channel_id = ch.id
    JOIN user_channels uc ON ch.id = uc.channel_id
    WHERE uc.user_id = match_user_id
      AND c.start_seconds >= min_start_seconds
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_limit;
END;
$$;

-- Helper: count chunks for a video
CREATE OR REPLACE FUNCTION count_chunks_for_video(vid_id UUID)
RETURNS INT
LANGUAGE sql
AS $$
    SELECT COUNT(*)::INT FROM chunks WHERE video_id = vid_id;
$$;
