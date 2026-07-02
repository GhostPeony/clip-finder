-- Fast library summary support: count transcript chunks for many saved videos in one call.

CREATE OR REPLACE FUNCTION public.count_chunks_for_videos(video_ids uuid[])
RETURNS TABLE(video_id uuid, chunk_count bigint)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT chunks.video_id, COUNT(*)::bigint AS chunk_count
  FROM public.chunks
  WHERE chunks.video_id = ANY(video_ids)
  GROUP BY chunks.video_id
$$;
