"""
ingest.py - Supabase/pgvector ingestion pipeline

Primary ingestion module using PostgreSQL + pgvector storage.
Implements shared-on-demand model: channels are indexed once and shared
across users via the user_channels subscription table.

Writes embeddings to Supabase chunks table as vector(768).

Updated: 2026-02-28
"""

import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Generator, Optional

from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings

try:
    from .billing import resolve_user_entitlements
    from .config import (
        get_free_indexed_transcript_seconds_total,
        get_free_indexed_videos_total,
        get_free_max_import_videos,
    )
    from .db import (
        check_index_quota,
        get_supabase,
        increment_index_usage,
    )
    from .db import (
        get_user_profile as get_db_user_profile,
    )
    from .digest_depth import DEFAULT_DIGEST_DEPTH, normalize_digest_depth
    from .gemini_clients import (
        RETRIEVAL_DOCUMENT_TASK,
        call_with_gemini_retry,
        get_embeddings_client,
    )
    from .jobs import format_ingestion_error
    from .knowledge import (
        refresh_existing_video_source_knowledge,
        source_knowledge_needs_refresh,
        store_video_knowledge,
    )
    from .youtube_utils import (
        describe_transcript_skip,
        detect_url_type,
        extract_channel_name,
        extract_video_title,
        fetch_transcript_chunks,
        fetch_video_metadata,
    )
except ImportError:
    from billing import resolve_user_entitlements
    from config import (
        get_free_indexed_transcript_seconds_total,
        get_free_indexed_videos_total,
        get_free_max_import_videos,
    )
    from db import (
        check_index_quota,
        get_supabase,
        increment_index_usage,
    )
    from db import (
        get_user_profile as get_db_user_profile,
    )
    from digest_depth import DEFAULT_DIGEST_DEPTH, normalize_digest_depth
    from gemini_clients import (
        RETRIEVAL_DOCUMENT_TASK,
        call_with_gemini_retry,
        get_embeddings_client,
    )
    from jobs import format_ingestion_error
    from knowledge import (
        refresh_existing_video_source_knowledge,
        source_knowledge_needs_refresh,
        store_video_knowledge,
    )
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

USER_VIDEO_ACCESS_SOURCES = frozenset(
    {"ingest", "channel", "playlist", "capture_sync", "shared_existing", "agent"}
)


def get_user_profile(supabase, user_id: str) -> dict:
    """Fetch profile plus hosted plan quota context when billing tables exist."""
    profile = get_db_user_profile(supabase, user_id)
    try:
        resolved = resolve_user_entitlements(supabase, user_id, profile)
        profile["_entitlements"] = resolved["entitlements"]
        profile["_period_usage"] = resolved["usage"]
    except Exception as exc:  # noqa: BLE001 - free-tier fallback keeps ingestion usable.
        print(f"[WARN] Failed to resolve billing entitlements for ingestion: {exc}")
    return profile


def _result_data(result: Any) -> Any:
    """Return Supabase response data, tolerating empty/None response objects."""
    return getattr(result, "data", None)


def _result_rows(result: Any) -> list[dict]:
    data = _result_data(result)
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    return []


def _first_result_row(result: Any) -> dict | None:
    rows = _result_rows(result)
    return rows[0] if rows else None


def _format_hours(seconds: int) -> str:
    return f"{seconds / 3600:.1f}"


def transcript_seconds_from_chunks(chunks: list[dict]) -> int:
    """Return the transcript duration represented by chunk end timestamps."""
    if not chunks:
        return 0
    return max(int(chunk.get("end_seconds", 0) or 0) for chunk in chunks)


def _index_quota_message(profile: dict, video_count: int, transcript_seconds: int = 0) -> str:
    entitlements = profile.get("_entitlements") or {}
    plan_key = str(entitlements.get("planKey") or "free")
    plan_label = plan_key.title()
    video_limit = int(entitlements.get("indexedVideosTotal") or get_free_indexed_videos_total())
    library_seconds_limit = int(
        entitlements.get("libraryTranscriptSeconds") or get_free_indexed_transcript_seconds_total()
    )
    monthly_seconds_limit = int(
        entitlements.get("monthlyIndexedTranscriptSeconds") or library_seconds_limit
    )
    period_usage = profile.get("_period_usage") or {}
    if profile.get("free_indexed_videos_total", 0) + video_count > video_limit:
        return (
            f"{plan_label} video limit reached. This plan can index or access up to "
            f"{video_limit} videos. Upgrade to unlock more capacity."
        )
    if profile.get("free_indexed_seconds_total", 0) + transcript_seconds > library_seconds_limit:
        return (
            f"{plan_label} total library limit reached. This plan can store up to "
            f"{_format_hours(library_seconds_limit)} transcript-hours. Upgrade to unlock more capacity."
        )
    if int(period_usage.get("indexedTranscriptSeconds", 0) or 0) + transcript_seconds > (
        monthly_seconds_limit
    ):
        return (
            f"{plan_label} monthly transcript-hour limit reached. This plan can index "
            f"{_format_hours(monthly_seconds_limit)} new transcript-hours per billing period."
        )
    return f"{plan_label} indexing limit reached. Upgrade to unlock more capacity."


def get_embeddings(api_key: Optional[str] = None) -> GoogleGenerativeAIEmbeddings:
    """Get cached embedding instance for the given API key."""
    return get_embeddings_client(api_key, RETRIEVAL_DOCUMENT_TASK)


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

    existing_channel = _first_result_row(result)
    if existing_channel:
        channel = existing_channel
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
        channel = _first_result_row(insert_result)
        if not channel:
            # Some Supabase clients/configurations can return no insert body. Re-read
            # before failing so duplicate/race-safe channel creation still works.
            refetch = (
                supabase.table("channels")
                .select("*")
                .eq("youtube_handle", youtube_handle)
                .maybe_single()
                .execute()
            )
            channel = _first_result_row(refetch)
        if not channel:
            raise RuntimeError("Could not create or load the source channel")

    return channel


def get_channel_index_usage_pg(supabase, channel_id: str) -> dict:
    """Return existing indexed video and transcript-second usage for a channel."""
    result = (
        supabase.table("videos")
        .select("id, transcript_seconds")
        .eq("channel_id", channel_id)
        .execute()
    )
    videos = _result_rows(result)
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
    if _result_data(existing):
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
    return {row["youtube_video_id"] for row in _result_rows(result)}


def get_indexed_video_pg(supabase, youtube_video_id: str) -> dict | None:
    """Return an existing canonical video row by YouTube ID, if already indexed."""
    result = (
        supabase.table("videos")
        .select("id, channel_id, youtube_video_id, title, thumbnail_url, transcript_seconds")
        .eq("youtube_video_id", youtube_video_id)
        .maybe_single()
        .execute()
    )
    return _first_result_row(result)


def refresh_existing_video_source_context_if_needed(
    supabase,
    video: dict,
    api_key: Optional[str],
    digest_depth: str,
    user_id: str,
) -> str | None:
    """Regenerate weak canonical source knowledge without re-embedding the video."""
    try:
        if not source_knowledge_needs_refresh(supabase, video["id"], digest_depth):
            return None
        result = refresh_existing_video_source_knowledge(
            supabase,
            video,
            api_key=api_key,
            digest_depth=digest_depth,
            published_for_user_id=user_id,
        )
        if result.get("refreshed"):
            counts = result.get("counts") or {}
            return (
                "Updated source report and timestamped topics from the existing transcript "
                f"({counts.get('knowledge_artifacts', 0)} reports, "
                f"{counts.get('source_concepts', 0)} topics)."
            )
    except Exception as exc:  # noqa: BLE001 - repair should not block library access.
        print(f"[KNOWLEDGE] Failed to refresh existing source knowledge: {exc}")
    return None


def grant_user_video_access(
    supabase,
    user_id: str,
    video: dict,
    used_own_key: bool = False,
    access_source: str = "shared_existing",
    source_url: str | None = None,
    charge_usage: bool = True,
) -> str | None:
    """
    Grant a user access to an existing canonical video without re-embedding it.

    Returns a user-visible quota message when the access grant should be blocked.
    """
    if access_source not in USER_VIDEO_ACCESS_SOURCES:
        allowed = ", ".join(sorted(USER_VIDEO_ACCESS_SOURCES))
        raise ValueError(
            f"Unsupported user_videos access_source '{access_source}'. Use one of: {allowed}"
        )

    video_id = video["id"]
    existing = (
        supabase.table("user_videos")
        .select("user_id")
        .match({"user_id": user_id, "video_id": video_id})
        .maybe_single()
        .execute()
    )
    if _result_data(existing):
        return None

    transcript_seconds = int(video.get("transcript_seconds", 0) or 0)
    if charge_usage:
        profile = get_user_profile(supabase, user_id)
        if not check_index_quota(profile, 1, transcript_seconds):
            return _index_quota_message(profile, 1, transcript_seconds)

    payload = {
        "user_id": user_id,
        "video_id": video_id,
        "access_source": access_source,
    }
    if source_url:
        payload["source_url"] = source_url
    supabase.table("user_videos").insert(payload).execute()

    if charge_usage:
        increment_index_usage(supabase, user_id, 1, used_own_key, transcript_seconds)

    return None


def _upsert_chunk_rows(supabase, chunk_rows: list[dict], batch_size: int = 50) -> None:
    """Write chunk rows idempotently, falling back to insert on unmigrated DBs.

    Databases without migration 028's unique index reject the ON CONFLICT
    clause with SQLSTATE 42P10; those batches fall back to plain inserts
    (today's behavior).
    """
    for index in range(0, len(chunk_rows), batch_size):
        batch = chunk_rows[index : index + batch_size]
        try:
            supabase.table("chunks").upsert(
                batch,
                on_conflict="video_id,start_seconds",
            ).execute()
        except Exception as exc:  # noqa: BLE001 - only the missing-index error falls back.
            message = str(exc)
            if "42P10" not in message and "no unique or exclusion constraint" not in message:
                raise
            print(
                "[INGEST] chunks upsert unavailable (missing unique index); falling back to insert"
            )
            supabase.table("chunks").insert(batch).execute()


def _embed_chunk_texts(
    embeddings: GoogleGenerativeAIEmbeddings,
    title: str,
    chunks: list[dict],
    video_id: str,
) -> list[list[float]]:
    """Embed transcript chunks with retry/backoff on transient Gemini errors."""
    texts = [f"{title}\n\n{chunk['text']}" for chunk in chunks]
    return call_with_gemini_retry(
        lambda: embeddings.embed_documents(texts),
        description=f"chunk embedding for {video_id}",
    )


def _build_chunk_rows(
    db_video_id: str,
    chunks: list[dict],
    vectors: list[list[float]],
) -> list[dict]:
    return [
        {
            "video_id": db_video_id,
            "content": chunk["text"],
            "start_seconds": chunk["start_seconds"],
            "end_seconds": chunk["end_seconds"],
            "embedding": vector,
        }
        for chunk, vector in zip(chunks, vectors)
    ]


def _stored_chunk_count(supabase, video_db_id: str) -> int | None:
    """Return a video's stored chunk count, or None when it cannot be determined."""
    try:
        result = supabase.rpc(
            "count_chunks_for_videos",
            {"video_ids": [str(video_db_id)]},
        ).execute()
        rows = _result_rows(result)
        if rows or isinstance(_result_data(result), list):
            for row in rows:
                if str(row.get("video_id") or "") == str(video_db_id):
                    try:
                        return int(row.get("chunk_count", row.get("count", 0)) or 0)
                    except (TypeError, ValueError):
                        return 0
            return 0
    except Exception as exc:  # noqa: BLE001 - deployments may not have the bulk helper yet.
        print(f"[INGEST] count_chunks_for_videos RPC unavailable, falling back to count: {exc}")

    try:
        count_result = (
            supabase.table("chunks")
            .select("id", count="exact")
            .eq("video_id", video_db_id)
            .execute()
        )
        if isinstance(getattr(count_result, "count", None), int):
            return count_result.count
        rows = getattr(count_result, "data", None)
        if isinstance(rows, list):
            return len(rows)
    except Exception as exc:  # noqa: BLE001 - never guess a repair when counting fails.
        print(f"[INGEST] Could not count chunks for video {video_db_id}: {exc}")
    return None


def repair_missing_video_chunks_if_needed(
    supabase,
    video: dict,
    api_key: Optional[str] = None,
) -> str | None:
    """Restore transcript embeddings for an already-indexed video with zero chunks.

    Detection is deliberately count == 0 only (the catastrophic partial-ingest
    case); partially written batches self-heal through the chunk upsert on a
    future re-index. Usage is never incremented — the user was already charged
    for this video. Returns a user-visible message when a repair ran.
    """
    try:
        video_db_id = video.get("id")
        youtube_video_id = str(video.get("youtube_video_id") or video.get("videoId") or "")
        if not video_db_id or not youtube_video_id:
            return None
        if _stored_chunk_count(supabase, video_db_id) != 0:
            return None

        print(f"[INGEST] Detected missing chunks for indexed video {youtube_video_id}; repairing")
        transcript_result = fetch_transcript_chunks(youtube_video_id)
        chunks = transcript_result.chunks
        if not chunks:
            reason = transcript_result.skip_reason or "transcript_fetch_error"
            print(
                f"[INGEST] Could not repair {youtube_video_id}: "
                f"{describe_transcript_skip(reason, youtube_video_id)}"
            )
            return None

        title = str(video.get("title") or youtube_video_id)
        embeddings = get_embeddings(api_key)
        vectors = _embed_chunk_texts(embeddings, title, chunks, youtube_video_id)
        chunk_rows = _build_chunk_rows(video_db_id, chunks, vectors)
        _upsert_chunk_rows(supabase, chunk_rows)

        transcript_seconds = transcript_seconds_from_chunks(chunks)
        supabase.table("videos").update({"transcript_seconds": transcript_seconds}).eq(
            "id", video_db_id
        ).execute()
        video["transcript_seconds"] = transcript_seconds
        return f"Repaired missing transcript embeddings ({len(chunk_rows)} clips restored)."
    except Exception as exc:  # noqa: BLE001 - repair should not block library access.
        print(f"[INGEST] Failed to repair missing chunks for {video.get('id')}: {exc}")
    return None


def index_video_to_pg(
    supabase,
    video_id: str,
    title: str,
    channel_name: str,
    channel_id: str,
    chunks: list[dict],
    transcript_seconds: int,
    api_key: Optional[str] = None,
    digest_depth: str = DEFAULT_DIGEST_DEPTH,
    published_for_user_id: str | None = None,
) -> int:
    """
    Embed transcript chunks and write video + chunks to Supabase.

    Returns the number of chunks stored.
    """
    embeddings = get_embeddings(api_key)

    # Generate embeddings for all chunks in one batch call (with retry/backoff)
    vectors = _embed_chunk_texts(embeddings, title, chunks, video_id)

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
    video_row = _first_result_row(video_result)
    if not video_row:
        existing_video = get_indexed_video_pg(supabase, video_id)
        video_row = existing_video
    if not video_row:
        raise RuntimeError("Could not store video metadata")
    db_video_id = video_row["id"]

    # Build chunk rows and write them idempotently in batches
    chunk_rows = _build_chunk_rows(db_video_id, chunks, vectors)
    _upsert_chunk_rows(supabase, chunk_rows)

    try:
        store_video_knowledge(
            supabase,
            db_video_id,
            video_id,
            title,
            channel_name,
            chunks,
            api_key,
            normalize_digest_depth(digest_depth),
            published_for_user_id,
        )
    except Exception as exc:  # noqa: BLE001 - source knowledge should not break indexing.
        print(f"[KNOWLEDGE] Failed to store source knowledge for {video_id}: {exc}")

    # Increment channel video count
    current = (
        supabase.table("channels").select("total_videos").eq("id", channel_id).single().execute()
    )
    current_data = _result_data(current) or {}
    new_total = (current_data.get("total_videos", 0) if isinstance(current_data, dict) else 0) + 1
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
    digest_depth: str = DEFAULT_DIGEST_DEPTH,
) -> Generator[str, None, None]:
    """
    Index a single YouTube video into Supabase/pgvector.

    Yields progress messages as plain strings.
    """
    supabase = get_supabase()
    digest_depth = normalize_digest_depth(digest_depth)

    yield f"Processing single video: {video_id}"
    yield f"Digest depth: {digest_depth}"

    existing_video = get_indexed_video_pg(supabase, video_id)
    if existing_video:
        quota_message = grant_user_video_access(
            supabase,
            user_id,
            existing_video,
            used_own_key,
            access_source="shared_existing",
            source_url=f"https://www.youtube.com/watch?v={video_id}",
        )
        if quota_message:
            yield quota_message
            return
        repair_message = repair_missing_video_chunks_if_needed(
            supabase,
            existing_video,
            api_key,
        )
        if repair_message:
            yield repair_message
        refresh_message = refresh_existing_video_source_context_if_needed(
            supabase,
            existing_video,
            api_key,
            digest_depth,
            user_id,
        )
        if refresh_message:
            yield refresh_message
        yield "This video is already indexed. Added the existing embeddings to your library."
        yield "Complete!"
        return

    # Fetch video metadata
    yield "Fetching video info..."
    video_title, channel_name = fetch_video_metadata(video_id)
    yield f"{video_title} by {channel_name}"

    # Derive a handle from channel name for single-video indexing
    youtube_handle = _derive_handle_from_name(channel_name)

    # Get or create the channel record before deciding whether to subscribe the user.
    channel = get_or_create_channel(supabase, youtube_handle, channel_name, user_id)
    channel_id = channel["id"]

    profile = get_user_profile(supabase, user_id)
    if not check_index_quota(profile, 1, 0):
        yield _index_quota_message(profile, 1, 0)
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
            digest_depth,
            published_for_user_id=user_id,
        )
        indexed_video = get_indexed_video_pg(supabase, video_id)
        if indexed_video:
            grant_message = grant_user_video_access(
                supabase,
                user_id,
                indexed_video,
                used_own_key,
                access_source="ingest",
                source_url=f"https://www.youtube.com/watch?v={video_id}",
                charge_usage=False,
            )
            if grant_message:
                yield grant_message
                return
        increment_index_usage(supabase, user_id, 1, used_own_key, transcript_seconds)
        yield f"Indexed {count} clips from video"
        yield "Added video to your library"
    except Exception as e:
        yield f"Error indexing: {format_ingestion_error(e)}"
        return

    yield "Complete!"


def _plan_import_batch(profile: dict, new_videos: list[dict]) -> tuple[list[dict], str | None]:
    """Slice a bulk import to the plan's video slots and per-import cap.

    Returns (videos_to_process, message). An empty video list means the import
    is blocked and the message is the quota explanation; a non-empty list with
    a message means the batch was truncated.
    """
    entitlements = profile.get("_entitlements") or {}
    video_limit = int(entitlements.get("indexedVideosTotal") or get_free_indexed_videos_total())
    video_slots = max(0, video_limit - profile.get("free_indexed_videos_total", 0))
    max_import_videos = int(entitlements.get("maxImportVideos") or get_free_max_import_videos())
    allowed_count = min(len(new_videos), video_slots, max_import_videos)

    if allowed_count <= 0:
        return [], _index_quota_message(profile, 1, 0)

    if allowed_count < len(new_videos):
        truncation_message = (
            f"{str(entitlements.get('planKey') or 'free').title()} imports process the first "
            f"{allowed_count} eligible videos (limit: {max_import_videos} per import, "
            f"{video_limit} total)."
        )
        return new_videos[:allowed_count], truncation_message

    return new_videos, None


def _ingest_video_batch_pg(
    supabase,
    new_videos: list[dict],
    user_id: str,
    fallback_channel_name: str,
    channel_id: str,
    access_source: str,
    api_key: Optional[str] = None,
    used_own_key: bool = False,
    digest_depth: str = DEFAULT_DIGEST_DEPTH,
) -> Generator[str, None, None]:
    """Index a batch of channel/playlist videos, yielding progress messages.

    Message strings are load-bearing: hosted job classification keys off the
    "  Skipped: ..." and "  Error indexing: ..." prefixes.
    """
    indexed_count = 0
    skipped_count = 0

    for i, video in enumerate(new_videos, 1):
        vid = video.get("videoId")
        title = extract_video_title(video)
        channel_name = extract_channel_name(video)
        if channel_name == "Unknown Channel":
            channel_name = fallback_channel_name

        yield f"[{i}/{len(new_videos)}] Processing: {title[:50]}..."

        profile = get_user_profile(supabase, user_id)
        if not check_index_quota(profile, 1, 0):
            yield _index_quota_message(profile, 1, 0)
            break

        existing_video = get_indexed_video_pg(supabase, vid)
        if existing_video:
            quota_message = grant_user_video_access(
                supabase,
                user_id,
                existing_video,
                used_own_key,
                access_source=access_source,
                source_url=f"https://www.youtube.com/watch?v={vid}",
            )
            if quota_message:
                yield quota_message
                break
            repair_message = repair_missing_video_chunks_if_needed(
                supabase,
                existing_video,
                api_key,
            )
            refresh_message = refresh_existing_video_source_context_if_needed(
                supabase,
                existing_video,
                api_key,
                digest_depth,
                user_id,
            )
            indexed_count += 1
            if repair_message:
                yield f"  {repair_message}"
            if refresh_message:
                yield f"  {refresh_message}"
            yield "  Reused existing indexed video (no embedding compute)"
            continue

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
                digest_depth,
                published_for_user_id=user_id,
            )
            increment_index_usage(supabase, user_id, 1, used_own_key, transcript_seconds)
            indexed_count += 1
            yield f"  Indexed {count} clips"
        except Exception as e:
            yield f"  Error indexing: {format_ingestion_error(e)}"
            skipped_count += 1

        time.sleep(0.5)

    yield f"Complete! Indexed {indexed_count} videos ({skipped_count} skipped)"


def ingest_channel_pg(
    channel_url: str,
    user_id: str,
    api_key: Optional[str] = None,
    used_own_key: bool = False,
    digest_depth: str = DEFAULT_DIGEST_DEPTH,
) -> Generator[str, None, None]:
    """
    Index all videos from a YouTube channel into Supabase/pgvector.

    Only processes new videos not already in the database.
    Yields progress messages as plain strings.
    """
    import scrapetube

    supabase = get_supabase()
    digest_depth = normalize_digest_depth(digest_depth)

    yield "Scanning channel for videos..."
    yield f"Digest depth: {digest_depth}"

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
    new_videos, batch_message = _plan_import_batch(profile, new_videos)
    if not new_videos:
        yield batch_message
        return
    if batch_message:
        yield batch_message

    yield f"{len(new_videos)} new videos to index"

    yield from _ingest_video_batch_pg(
        supabase,
        new_videos,
        user_id,
        channel_name,
        channel_id,
        "channel",
        api_key,
        used_own_key,
        digest_depth,
    )


def ingest_playlist_pg(
    playlist_id: str,
    user_id: str,
    api_key: Optional[str] = None,
    used_own_key: bool = False,
    digest_depth: str = DEFAULT_DIGEST_DEPTH,
) -> Generator[str, None, None]:
    """
    Index all videos from a YouTube playlist into Supabase/pgvector.

    Yields progress messages as plain strings.
    """
    import scrapetube

    supabase = get_supabase()
    digest_depth = normalize_digest_depth(digest_depth)

    yield f"Scanning playlist: {playlist_id}"
    yield f"Digest depth: {digest_depth}"

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
    new_videos, batch_message = _plan_import_batch(profile, new_videos)
    if not new_videos:
        yield batch_message
        return
    if batch_message:
        yield batch_message

    yield f"{len(new_videos)} new videos to index"

    yield from _ingest_video_batch_pg(
        supabase,
        new_videos,
        user_id,
        primary_channel_name,
        channel_id,
        "playlist",
        api_key,
        used_own_key,
        digest_depth,
    )


def ingest_url_pg(
    url: str,
    user_id: str,
    api_key: Optional[str] = None,
    used_own_key: bool = False,
    digest_depth: str = DEFAULT_DIGEST_DEPTH,
) -> Generator[str, None, None]:
    """
    Smart dispatcher: detect URL type and route to the correct ingest function.

    Supports channel, playlist, and single video URLs.
    """
    url_type, extracted_id = detect_url_type(url)
    digest_depth = normalize_digest_depth(digest_depth)

    yield f"Detected URL type: {url_type.upper()}"

    if url_type == "channel":
        yield from ingest_channel_pg(
            extracted_id or url,
            user_id,
            api_key,
            used_own_key,
            digest_depth,
        )
    elif url_type == "playlist":
        yield from ingest_playlist_pg(extracted_id, user_id, api_key, used_own_key, digest_depth)
    elif url_type == "video":
        yield from ingest_single_video_pg(
            extracted_id, user_id, api_key, used_own_key, digest_depth
        )
    else:
        yield "Could not detect URL type. Please provide a valid YouTube channel, playlist, or video URL."
        yield "  Examples:"
        yield "  - Channel: https://www.youtube.com/@ChannelName"
        yield "  - Playlist: https://www.youtube.com/playlist?list=PLxxxxx"
        yield "  - Video: https://www.youtube.com/watch?v=xxxxx"
