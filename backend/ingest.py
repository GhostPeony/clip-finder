"""
ingest.py - Supabase/pgvector ingestion pipeline

Primary ingestion module using PostgreSQL + pgvector storage.
Implements shared-on-demand model: channels are indexed once and shared
across users via the user_channels subscription table.

Reuses YouTube helpers from ingest_chroma.py (scraping, transcripts, URL detection).
Writes embeddings to Supabase chunks table as vector(768).

Updated: 2026-02-28
"""

import os
import re
import time
from datetime import datetime, timezone
from typing import Generator, Optional

from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings

try:
    from .config import (
        get_embedding_dimensions,
        get_embedding_model,
        get_free_indexed_transcript_seconds_total,
        get_free_indexed_videos_total,
        get_free_max_import_videos,
    )
    from .db import check_index_quota, get_supabase, get_user_profile, increment_index_usage
    from .youtube_utils import (
        describe_transcript_skip,
        detect_url_type,
        extract_channel_name,
        extract_video_title,
        fetch_transcript_chunks,
        fetch_video_metadata,
    )
except ImportError:
    from config import (
        get_embedding_dimensions,
        get_embedding_model,
        get_free_indexed_transcript_seconds_total,
        get_free_indexed_videos_total,
        get_free_max_import_videos,
    )
    from db import check_index_quota, get_supabase, get_user_profile, increment_index_usage
    from youtube_utils import (
        describe_transcript_skip,
        detect_url_type,
        extract_channel_name,
        extract_video_title,
        fetch_transcript_chunks,
        fetch_video_metadata,
    )

# Load environment variables
env_path = os.path.join(os.path.dirname(__file__), "..", ".env.local")
load_dotenv(env_path)

EMBEDDING_MODEL = get_embedding_model()

# Cache for embedding instances keyed by api_key
_embeddings_cache: dict[str, GoogleGenerativeAIEmbeddings] = {}


def _format_hours(seconds: int) -> str:
    return f"{seconds / 3600:.1f}"


def transcript_seconds_from_chunks(chunks: list[dict]) -> int:
    """Return the transcript duration represented by chunk end timestamps."""
    if not chunks:
        return 0
    return max(int(chunk.get("end_seconds", 0) or 0) for chunk in chunks)


def _index_quota_message(profile: dict, video_count: int, transcript_seconds: int = 0) -> str:
    video_limit = get_free_indexed_videos_total()
    seconds_limit = get_free_indexed_transcript_seconds_total()
    if profile.get("free_indexed_videos_total", 0) + video_count > video_limit:
        return (
            f"Free indexing limit reached. Free workspaces can index or access up to "
            f"{video_limit} videos. Contact us to unlock more capacity."
        )
    if profile.get("free_indexed_seconds_total", 0) + transcript_seconds > seconds_limit:
        return (
            "Free transcript-hour limit reached. Free workspaces can index or access up to "
            f"{_format_hours(seconds_limit)} transcript-hours. Contact us to unlock more capacity."
        )
    return "Free indexing limit reached. Contact us to unlock more capacity."


def get_embeddings(api_key: Optional[str] = None) -> GoogleGenerativeAIEmbeddings:
    """Get cached embedding instance for the given API key."""
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
        task_type="RETRIEVAL_DOCUMENT",
        output_dimensionality=get_embedding_dimensions(),
    )
    _embeddings_cache[key_to_use] = instance
    return instance


def _extract_handle_from_url(channel_url: str) -> str:
    """
    Extract a youtube handle from a channel URL.

    Handles patterns like:
        https://www.youtube.com/@ChannelName -> @ChannelName
        https://www.youtube.com/channel/UCxxx -> UCxxx
        https://www.youtube.com/c/Name -> Name
        https://www.youtube.com/user/Name -> Name
    """
    patterns = [
        r"youtube\.com/(@[a-zA-Z0-9_.-]+)",
        r"youtube\.com/channel/([a-zA-Z0-9_-]+)",
        r"youtube\.com/c/([a-zA-Z0-9_-]+)",
        r"youtube\.com/user/([a-zA-Z0-9_-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, channel_url)
        if match:
            return match.group(1)
    # Fallback: use the URL itself as the handle
    return channel_url


def _derive_handle_from_name(channel_name: str) -> str:
    """
    Derive a pseudo-handle from a channel name for single-video indexing.
    Used when we don't have a channel URL.
    """
    # Normalize: lowercase, strip spaces, prefix with @
    slug = re.sub(r"[^a-zA-Z0-9_-]", "", channel_name.replace(" ", ""))
    return f"@{slug}" if slug else f"@unknown-{int(time.time())}"


def get_or_create_channel(
    supabase,
    youtube_handle: str,
    channel_name: str,
    user_id: str,
) -> dict:
    """Find or create a channel row and return the channel dict."""
    # Check if channel already exists
    result = (
        supabase.table("channels")
        .select("*")
        .eq("youtube_handle", youtube_handle)
        .maybe_single()
        .execute()
    )

    if result.data:
        channel = result.data
    else:
        # Create new channel
        insert_result = (
            supabase.table("channels")
            .insert(
                {
                    "youtube_handle": youtube_handle,
                    "name": channel_name,
                    "indexed_by": user_id,
                }
            )
            .execute()
        )
        channel = insert_result.data[0]

    return channel


def get_channel_index_usage_pg(supabase, channel_id: str) -> dict:
    """Return existing indexed video and transcript-second usage for a channel."""
    result = (
        supabase.table("videos")
        .select("id, transcript_seconds")
        .eq("channel_id", channel_id)
        .execute()
    )
    videos = result.data or []
    return {
        "video_count": len(videos),
        "transcript_seconds": sum(int(video.get("transcript_seconds", 0) or 0) for video in videos),
    }


def ensure_user_channel_subscription(
    supabase,
    channel: dict,
    user_id: str,
    used_own_key: bool = False,
) -> str | None:
    """
    Subscribe a user to a channel, charging free-tier library access if needed.

    Returns a user-visible quota message when subscription should be blocked.
    """
    channel_id = channel["id"]
    existing = (
        supabase.table("user_channels")
        .select("user_id")
        .match({"user_id": user_id, "channel_id": channel_id})
        .maybe_single()
        .execute()
    )
    if existing.data:
        return None

    usage = get_channel_index_usage_pg(supabase, channel_id)
    video_count = usage["video_count"]
    transcript_seconds = usage["transcript_seconds"]

    if video_count > 0 or transcript_seconds > 0:
        profile = get_user_profile(supabase, user_id)
        if not check_index_quota(profile, video_count, transcript_seconds):
            return _index_quota_message(profile, video_count, transcript_seconds)

    supabase.table("user_channels").insert(
        {
            "user_id": user_id,
            "channel_id": channel_id,
        }
    ).execute()

    if video_count > 0 or transcript_seconds > 0:
        increment_index_usage(
            supabase,
            user_id,
            video_count,
            used_own_key,
            transcript_seconds,
        )

    return None


def get_indexed_video_ids_pg(supabase, channel_id: str) -> set[str]:
    """Return set of youtube_video_ids already indexed for a channel."""
    result = (
        supabase.table("videos").select("youtube_video_id").eq("channel_id", channel_id).execute()
    )
    return {row["youtube_video_id"] for row in (result.data or [])}


def index_video_to_pg(
    supabase,
    video_id: str,
    title: str,
    channel_name: str,
    channel_id: str,
    chunks: list[dict],
    transcript_seconds: int,
    api_key: Optional[str] = None,
) -> int:
    """
    Embed transcript chunks and write video + chunks to Supabase.

    Returns the number of chunks stored.
    """
    embeddings = get_embeddings(api_key)

    # Generate embeddings for all chunks in one batch call
    texts = [f"{title}\n\n{chunk['text']}" for chunk in chunks]
    vectors = embeddings.embed_documents(texts)

    # Create video row
    video_result = (
        supabase.table("videos")
        .insert(
            {
                "channel_id": channel_id,
                "youtube_video_id": video_id,
                "title": title,
                "thumbnail_url": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                "transcript_seconds": transcript_seconds,
            }
        )
        .execute()
    )
    db_video_id = video_result.data[0]["id"]

    # Build chunk rows
    chunk_rows = []
    for chunk, vector in zip(chunks, vectors):
        chunk_rows.append(
            {
                "video_id": db_video_id,
                "content": chunk["text"],
                "start_seconds": chunk["start_seconds"],
                "end_seconds": chunk["end_seconds"],
                "embedding": vector,
            }
        )

    # Insert chunks in batches to stay within payload limits
    BATCH_SIZE = 50
    for i in range(0, len(chunk_rows), BATCH_SIZE):
        batch = chunk_rows[i : i + BATCH_SIZE]
        supabase.table("chunks").insert(batch).execute()

    # Increment channel video count
    current = (
        supabase.table("channels").select("total_videos").eq("id", channel_id).single().execute()
    )
    new_total = (current.data.get("total_videos", 0) if current.data else 0) + 1
    supabase.table("channels").update(
        {
            "total_videos": new_total,
            "indexed_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("id", channel_id).execute()

    return len(chunk_rows)


def ingest_single_video_pg(
    video_id: str,
    user_id: str,
    api_key: Optional[str] = None,
    used_own_key: bool = False,
) -> Generator[str, None, None]:
    """
    Index a single YouTube video into Supabase/pgvector.

    Yields progress messages as plain strings.
    """
    supabase = get_supabase()

    yield f"Processing single video: {video_id}"

    # Fetch video metadata
    yield "Fetching video info..."
    video_title, channel_name = fetch_video_metadata(video_id)
    yield f"{video_title} by {channel_name}"

    # Derive a handle from channel name for single-video indexing
    youtube_handle = _derive_handle_from_name(channel_name)

    # Get or create the channel record before deciding whether to subscribe the user.
    channel = get_or_create_channel(supabase, youtube_handle, channel_name, user_id)
    channel_id = channel["id"]

    # Check if already indexed
    indexed_ids = get_indexed_video_ids_pg(supabase, channel_id)
    if video_id in indexed_ids:
        quota_message = ensure_user_channel_subscription(supabase, channel, user_id, used_own_key)
        if quota_message:
            yield quota_message
            return
        yield "This video is already indexed!"
        return

    profile = get_user_profile(supabase, user_id)
    if not check_index_quota(profile, 1, 0):
        yield _index_quota_message(profile, 1, 0)
        return

    quota_message = ensure_user_channel_subscription(supabase, channel, user_id, used_own_key)
    if quota_message:
        yield quota_message
        return

    # Get transcript chunks
    yield "Fetching transcript..."
    transcript_result = fetch_transcript_chunks(video_id)
    chunks = transcript_result.chunks

    if not chunks:
        reason = transcript_result.skip_reason or "transcript_fetch_error"
        yield f"Skipped: {reason} | {describe_transcript_skip(reason, video_id)}"
        return

    transcript_seconds = transcript_seconds_from_chunks(chunks)
    profile = get_user_profile(supabase, user_id)
    if not check_index_quota(profile, 1, transcript_seconds):
        yield _index_quota_message(profile, 1, transcript_seconds)
        return

    yield f"Found {len(chunks)} transcript chunks"

    try:
        count = index_video_to_pg(
            supabase,
            video_id,
            video_title,
            channel_name,
            channel_id,
            chunks,
            transcript_seconds,
            api_key,
        )
        increment_index_usage(supabase, user_id, 1, used_own_key, transcript_seconds)
        yield f"Indexed {count} clips from video"
    except Exception as e:
        yield f"Error indexing: {str(e)}"
        return

    yield "Complete!"


def ingest_channel_pg(
    channel_url: str,
    user_id: str,
    api_key: Optional[str] = None,
    used_own_key: bool = False,
) -> Generator[str, None, None]:
    """
    Index all videos from a YouTube channel into Supabase/pgvector.

    Only processes new videos not already in the database.
    Yields progress messages as plain strings.
    """
    import scrapetube

    supabase = get_supabase()

    yield "Scanning channel for videos..."

    try:
        videos = list(
            scrapetube.get_channel(
                channel_url=channel_url,
                sort_by="oldest",
                sleep=1.5,
            )
        )
    except Exception as e:
        yield f"Error scanning channel: {str(e)}"
        return

    total_videos = len(videos)
    yield f"Found {total_videos} videos in channel"

    # Get channel name from first video via oEmbed (more reliable)
    channel_name = "Unknown Channel"
    if videos:
        first_video_id = videos[0].get("videoId")
        if first_video_id:
            _, channel_name = fetch_video_metadata(first_video_id)
    yield f"Channel: {channel_name}"

    # Extract handle from URL
    youtube_handle = _extract_handle_from_url(channel_url)

    # Get or create channel and subscribe user after quota checks.
    channel = get_or_create_channel(supabase, youtube_handle, channel_name, user_id)
    channel_id = channel["id"]

    quota_message = ensure_user_channel_subscription(supabase, channel, user_id, used_own_key)
    if quota_message:
        yield quota_message
        return

    # Get already indexed video IDs for this channel
    indexed_ids = get_indexed_video_ids_pg(supabase, channel_id)
    yield f"Database contains {len(indexed_ids)} previously indexed videos"

    # Filter to only new videos
    new_videos = [v for v in videos if v.get("videoId") not in indexed_ids]

    if not new_videos:
        yield "All videos already indexed! Nothing new to process."
        return

    profile = get_user_profile(supabase, user_id)
    video_slots = max(
        0, get_free_indexed_videos_total() - profile.get("free_indexed_videos_total", 0)
    )
    max_import_videos = get_free_max_import_videos()
    allowed_count = min(len(new_videos), video_slots, max_import_videos)

    if allowed_count <= 0:
        yield _index_quota_message(profile, 1, 0)
        return

    if allowed_count < len(new_videos):
        yield (
            f"Free imports process the first {allowed_count} eligible videos "
            f"(limit: {max_import_videos} per import, {get_free_indexed_videos_total()} total)."
        )
        new_videos = new_videos[:allowed_count]

    yield f"{len(new_videos)} new videos to index"

    indexed_count = 0
    skipped_count = 0

    for i, video in enumerate(new_videos, 1):
        vid = video.get("videoId")
        title = extract_video_title(video)

        yield f"[{i}/{len(new_videos)}] Processing: {title[:50]}..."

        profile = get_user_profile(supabase, user_id)
        if not check_index_quota(profile, 1, 0):
            yield _index_quota_message(profile, 1, 0)
            break

        transcript_result = fetch_transcript_chunks(vid)
        chunks = transcript_result.chunks

        if not chunks:
            reason = transcript_result.skip_reason or "transcript_fetch_error"
            yield f"  Skipped: {reason} | {describe_transcript_skip(reason, vid)}"
            skipped_count += 1
            continue

        transcript_seconds = transcript_seconds_from_chunks(chunks)
        profile = get_user_profile(supabase, user_id)
        if not check_index_quota(profile, 1, transcript_seconds):
            yield _index_quota_message(profile, 1, transcript_seconds)
            break

        try:
            count = index_video_to_pg(
                supabase,
                vid,
                title,
                channel_name,
                channel_id,
                chunks,
                transcript_seconds,
                api_key,
            )
            increment_index_usage(supabase, user_id, 1, used_own_key, transcript_seconds)
            indexed_count += 1
            yield f"  Indexed {count} clips"
        except Exception as e:
            yield f"  Error indexing: {str(e)}"
            skipped_count += 1

        time.sleep(0.5)

    yield f"Complete! Indexed {indexed_count} videos ({skipped_count} skipped)"


def ingest_playlist_pg(
    playlist_id: str,
    user_id: str,
    api_key: Optional[str] = None,
    used_own_key: bool = False,
) -> Generator[str, None, None]:
    """
    Index all videos from a YouTube playlist into Supabase/pgvector.

    Yields progress messages as plain strings.
    """
    import scrapetube

    supabase = get_supabase()

    yield f"Scanning playlist: {playlist_id}"

    try:
        videos = list(scrapetube.get_playlist(playlist_id))
    except Exception as e:
        yield f"Error scanning playlist: {str(e)}"
        return

    total_videos = len(videos)
    yield f"Found {total_videos} videos in playlist"

    if not videos:
        return

    # Group videos by channel. Playlists can contain videos from multiple channels.
    # For simplicity, derive channel from each video's metadata.
    # First pass: get channel name from first video for the primary channel.
    first_video_id = videos[0].get("videoId")
    _, primary_channel_name = (
        fetch_video_metadata(first_video_id) if first_video_id else ("", "Unknown Channel")
    )

    # Use playlist ID as pseudo-handle for channel grouping
    # (playlists may span channels; we group under primary channel)
    youtube_handle = _derive_handle_from_name(primary_channel_name)

    channel = get_or_create_channel(supabase, youtube_handle, primary_channel_name, user_id)
    channel_id = channel["id"]

    quota_message = ensure_user_channel_subscription(supabase, channel, user_id, used_own_key)
    if quota_message:
        yield quota_message
        return

    indexed_ids = get_indexed_video_ids_pg(supabase, channel_id)
    yield f"Database contains {len(indexed_ids)} previously indexed videos"

    new_videos = [v for v in videos if v.get("videoId") not in indexed_ids]

    if not new_videos:
        yield "All playlist videos already indexed!"
        return

    profile = get_user_profile(supabase, user_id)
    video_slots = max(
        0, get_free_indexed_videos_total() - profile.get("free_indexed_videos_total", 0)
    )
    max_import_videos = get_free_max_import_videos()
    allowed_count = min(len(new_videos), video_slots, max_import_videos)

    if allowed_count <= 0:
        yield _index_quota_message(profile, 1, 0)
        return

    if allowed_count < len(new_videos):
        yield (
            f"Free imports process the first {allowed_count} eligible videos "
            f"(limit: {max_import_videos} per import, {get_free_indexed_videos_total()} total)."
        )
        new_videos = new_videos[:allowed_count]

    yield f"{len(new_videos)} new videos to index"

    indexed_count = 0
    skipped_count = 0

    for i, video in enumerate(new_videos, 1):
        vid = video.get("videoId")
        title = extract_video_title(video)
        channel_name = extract_channel_name(video)

        yield f"[{i}/{len(new_videos)}] Processing: {title[:50]}..."

        profile = get_user_profile(supabase, user_id)
        if not check_index_quota(profile, 1, 0):
            yield _index_quota_message(profile, 1, 0)
            break

        transcript_result = fetch_transcript_chunks(vid)
        chunks = transcript_result.chunks

        if not chunks:
            reason = transcript_result.skip_reason or "transcript_fetch_error"
            yield f"  Skipped: {reason} | {describe_transcript_skip(reason, vid)}"
            skipped_count += 1
            continue

        transcript_seconds = transcript_seconds_from_chunks(chunks)
        profile = get_user_profile(supabase, user_id)
        if not check_index_quota(profile, 1, transcript_seconds):
            yield _index_quota_message(profile, 1, transcript_seconds)
            break

        try:
            count = index_video_to_pg(
                supabase,
                vid,
                title,
                channel_name,
                channel_id,
                chunks,
                transcript_seconds,
                api_key,
            )
            increment_index_usage(supabase, user_id, 1, used_own_key, transcript_seconds)
            indexed_count += 1
            yield f"  Indexed {count} clips"
        except Exception as e:
            yield f"  Error indexing: {str(e)}"
            skipped_count += 1

        time.sleep(0.5)

    yield f"Complete! Indexed {indexed_count} videos ({skipped_count} skipped)"


def ingest_url_pg(
    url: str,
    user_id: str,
    api_key: Optional[str] = None,
    used_own_key: bool = False,
) -> Generator[str, None, None]:
    """
    Smart dispatcher: detect URL type and route to the correct ingest function.

    Supports channel, playlist, and single video URLs.
    """
    url_type, extracted_id = detect_url_type(url)

    yield f"Detected URL type: {url_type.upper()}"

    if url_type == "channel":
        yield from ingest_channel_pg(url, user_id, api_key, used_own_key)
    elif url_type == "playlist":
        yield from ingest_playlist_pg(extracted_id, user_id, api_key, used_own_key)
    elif url_type == "video":
        yield from ingest_single_video_pg(extracted_id, user_id, api_key, used_own_key)
    else:
        yield "Could not detect URL type. Please provide a valid YouTube channel, playlist, or video URL."
        yield "  Examples:"
        yield "  - Channel: https://www.youtube.com/@ChannelName"
        yield "  - Playlist: https://www.youtube.com/playlist?list=PLxxxxx"
        yield "  - Video: https://www.youtube.com/watch?v=xxxxx"
