"""
rag_pg.py - Supabase/pgvector search engine

Replaces ChromaDB-based search with PostgreSQL + pgvector similarity search.
Queries are scoped to channels the authenticated user is subscribed to via
the search_chunks RPC function.

Also provides library, transcript, and channel/video management helpers.

Updated: 2026-02-28
"""

import os
from typing import Optional

from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from db import get_supabase

# Load environment variables
env_path = os.path.join(os.path.dirname(__file__), '..', '.env.local')
load_dotenv(env_path)

EMBEDDING_MODEL = "models/gemini-embedding-001"

# Cache for embedding instances keyed by api_key prefix
_embeddings_cache: dict[str, GoogleGenerativeAIEmbeddings] = {}


def _get_embeddings(api_key: Optional[str] = None) -> GoogleGenerativeAIEmbeddings:
    """Get cached embedding instance configured for retrieval queries."""
    key_to_use = api_key or os.getenv("GEMINI_API_KEY")
    if not key_to_use or key_to_use == "PLACEHOLDER_API_KEY":
        raise ValueError(
            "No API key provided. Set GEMINI_API_KEY in .env.local or provide via header."
        )

    if key_to_use in _embeddings_cache:
        return _embeddings_cache[key_to_use]

    instance = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=key_to_use,
        task_type="RETRIEVAL_QUERY",
    )
    _embeddings_cache[key_to_use] = instance
    return instance


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def search_pg(
    query: str,
    user_id: str,
    api_key: Optional[str] = None,
    limit: int = 5,
) -> dict:
    """
    Semantic search scoped to a user's subscribed channels.

    Embeds the query, calls the search_chunks RPC function, and returns
    results in the same SearchResult format as rag.py.

    Args:
        query: The user's search text.
        user_id: Supabase auth user UUID.
        api_key: Optional Gemini API key override (BYOK).
        limit: Maximum number of clips to return.

    Returns:
        SearchResult dict with 'answer' (empty string) and 'relevantClips'.
    """
    print(f"[SEARCH_PG] Starting search for: {query[:50]}... (user={user_id[:8]}, limit={limit})")

    supabase = get_supabase()

    # 1. Embed the query
    embeddings = _get_embeddings(api_key)
    query_vector = embeddings.embed_query(query)
    print(f"[SEARCH_PG] Embedded query ({len(query_vector)} dims)")

    # 2. Call the search_chunks RPC function
    #    Request limit*2 to have room after any client-side filtering
    result = supabase.rpc("search_chunks", {
        "query_embedding": query_vector,
        "match_user_id": user_id,
        "match_limit": limit * 2,
        "min_start_seconds": 120,
    }).execute()

    rows = result.data or []
    print(f"[SEARCH_PG] RPC returned {len(rows)} rows")

    # 3. Map to VideoClip dicts (same format frontend expects)
    clips = []
    for i, row in enumerate(rows):
        if len(clips) >= limit:
            break

        clips.append({
            "id": f"clip_{i}",
            "videoId": row["youtube_video_id"],
            "title": row["title"],
            "channelName": row["channel_name"],
            "startSeconds": row["start_seconds"],
            "endSeconds": row["end_seconds"],
            "content": row["content"],
            "thumbnailUrl": row["thumbnail_url"] or "",
        })

    print(f"[SEARCH_PG] Returning {len(clips)} clips")

    return {
        "answer": "",
        "relevantClips": clips,
    }


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------

def get_library_pg(user_id: str) -> dict:
    """
    Return the user's subscribed channels with their videos and clip counts.

    Matches the LibraryData format expected by the frontend:
    {
        "channels": [{"name": "...", "videoCount": N, "videos": [...]}],
        "totalVideos": N,
        "totalClips": N,
    }
    """
    supabase = get_supabase()

    # Get user's subscribed channels
    uc_result = (
        supabase.table("user_channels")
        .select("channel_id, channels(id, name)")
        .eq("user_id", user_id)
        .execute()
    )

    subscriptions = uc_result.data or []

    channels_list = []
    total_videos = 0
    total_clips = 0

    for sub in subscriptions:
        channel_data = sub.get("channels")
        if not channel_data:
            continue

        channel_id = channel_data["id"]
        channel_name = channel_data["name"]

        # Get all videos for this channel
        videos_result = (
            supabase.table("videos")
            .select("id, youtube_video_id, title, thumbnail_url, indexed_at")
            .eq("channel_id", channel_id)
            .order("indexed_at", desc=True)
            .execute()
        )

        videos_data = videos_result.data or []
        channel_videos = []

        for video in videos_data:
            # Get clip count via RPC
            count_result = supabase.rpc(
                "count_chunks_for_video",
                {"vid_id": video["id"]},
            ).execute()
            clip_count = count_result.data if isinstance(count_result.data, int) else 0

            total_clips += clip_count

            # Parse indexed_at to unix timestamp
            indexed_at_ts = None
            if video.get("indexed_at"):
                from datetime import datetime
                try:
                    dt = datetime.fromisoformat(video["indexed_at"].replace("Z", "+00:00"))
                    indexed_at_ts = int(dt.timestamp())
                except (ValueError, AttributeError):
                    pass

            channel_videos.append({
                "videoId": video["youtube_video_id"],
                "title": video["title"],
                "thumbnailUrl": video["thumbnail_url"] or "",
                "clipCount": clip_count,
                "indexedAt": indexed_at_ts,
            })

        total_videos += len(channel_videos)

        channels_list.append({
            "name": channel_name,
            "videoCount": len(channel_videos),
            "videos": channel_videos,
        })

    return {
        "channels": channels_list,
        "totalVideos": total_videos,
        "totalClips": total_clips,
    }


# ---------------------------------------------------------------------------
# Channel / video management
# ---------------------------------------------------------------------------

def delete_user_channel(user_id: str, channel_id: str) -> dict:
    """
    Unsubscribe a user from a channel.

    If no other users are subscribed, the channel and all its data
    (videos, chunks) are cascade-deleted.

    Returns:
        {"deleted": True, "orphaned": bool} where orphaned indicates
        whether the channel data was also removed.
    """
    supabase = get_supabase()

    # Remove subscription
    supabase.table("user_channels").delete().match({
        "user_id": user_id,
        "channel_id": channel_id,
    }).execute()

    # Check if any other users are still subscribed
    remaining = (
        supabase.table("user_channels")
        .select("user_id", count="exact")
        .eq("channel_id", channel_id)
        .execute()
    )

    orphaned = (remaining.count or 0) == 0

    if orphaned:
        # No subscribers left -- delete channel (cascades to videos & chunks)
        supabase.table("channels").delete().eq("id", channel_id).execute()

    return {"deleted": True, "orphaned": orphaned}


def delete_video_pg(video_id_youtube: str, user_id: str) -> dict:
    """
    Remove a video by its YouTube video ID.

    Only deletes if the user is subscribed to the channel that owns this
    video. If the channel would become empty and no other users subscribe
    to it, the channel is also cleaned up.

    Returns:
        {"deleted": True} on success, {"deleted": False, "reason": "..."} otherwise.
    """
    supabase = get_supabase()

    # Look up the video
    video_result = (
        supabase.table("videos")
        .select("id, channel_id")
        .eq("youtube_video_id", video_id_youtube)
        .maybe_single()
        .execute()
    )

    if not video_result.data:
        return {"deleted": False, "reason": "Video not found"}

    video = video_result.data
    channel_id = video["channel_id"]

    # Verify user is subscribed to this channel
    sub_check = (
        supabase.table("user_channels")
        .select("user_id")
        .match({"user_id": user_id, "channel_id": channel_id})
        .maybe_single()
        .execute()
    )

    if not sub_check.data:
        return {"deleted": False, "reason": "Not subscribed to this channel"}

    # Delete the video (cascades to chunks)
    supabase.table("videos").delete().eq("id", video["id"]).execute()

    # Update channel video count
    count_result = (
        supabase.table("videos")
        .select("id", count="exact")
        .eq("channel_id", channel_id)
        .execute()
    )
    remaining_videos = count_result.count or 0

    supabase.table("channels").update({
        "total_videos": remaining_videos,
    }).eq("id", channel_id).execute()

    # If channel is now empty, check if we should clean it up
    if remaining_videos == 0:
        remaining_subs = (
            supabase.table("user_channels")
            .select("user_id", count="exact")
            .eq("channel_id", channel_id)
            .execute()
        )
        # Only one subscriber (the current user) or none -- clean up
        if (remaining_subs.count or 0) <= 1:
            supabase.table("user_channels").delete().eq("channel_id", channel_id).execute()
            supabase.table("channels").delete().eq("id", channel_id).execute()

    return {"deleted": True}


# ---------------------------------------------------------------------------
# Transcript export
# ---------------------------------------------------------------------------

def get_video_transcript_pg(video_id_youtube: str) -> list[dict]:
    """
    Get ordered transcript chunks for a video, suitable for SRT download.

    Args:
        video_id_youtube: YouTube video ID (e.g. 'dQw4w9WgXcB').

    Returns:
        List of dicts with keys: content, start_seconds, end_seconds,
        ordered by start_seconds ascending. Empty list if video not found.
    """
    supabase = get_supabase()

    # Look up internal video ID
    video_result = (
        supabase.table("videos")
        .select("id")
        .eq("youtube_video_id", video_id_youtube)
        .maybe_single()
        .execute()
    )

    if not video_result.data:
        return []

    db_video_id = video_result.data["id"]

    # Fetch chunks ordered by timestamp
    chunks_result = (
        supabase.table("chunks")
        .select("content, start_seconds, end_seconds")
        .eq("video_id", db_video_id)
        .order("start_seconds", desc=False)
        .execute()
    )

    return chunks_result.data or []
