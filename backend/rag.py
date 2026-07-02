"""
rag.py - Supabase/pgvector search engine

Primary search module using PostgreSQL + pgvector similarity search.
Queries are scoped to videos the authenticated user can access via channel
subscriptions or precise per-video grants in the search_chunks RPC function.

Also provides library, transcript, and channel/video management helpers.

Updated: 2026-02-28
"""

import os
import re
from typing import Any, Optional

from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings

try:
    from .answers import generate_answer
    from .category_taxonomy import normalize_category_filters
    from .clip_selection import select_clips
    from .db import get_supabase
    from .gemini_clients import RETRIEVAL_QUERY_TASK, get_embeddings_client
    from .projects import resolve_project_scope
except ImportError:
    from answers import generate_answer
    from category_taxonomy import normalize_category_filters
    from clip_selection import select_clips
    from db import get_supabase
    from gemini_clients import RETRIEVAL_QUERY_TASK, get_embeddings_client
    from projects import resolve_project_scope

# Load environment variables
env_path = os.path.join(os.path.dirname(__file__), "..", ".env.local")
load_dotenv(env_path)

RETRIEVAL_MODES = {"auto", "hybrid", "semantic", "keyword"}

# "auto" routes on query shape: an explicit quoted phrase is a strong signal the
# user wants literal matching, everything else gets hybrid retrieval.
_QUOTED_PHRASE_PATTERN = re.compile(r'"[^"]{2,}"|“[^”]{2,}”')
KEYWORD_FALLBACK_STOPWORDS = {
    "about",
    "after",
    "does",
    "from",
    "how",
    "into",
    "that",
    "the",
    "this",
    "what",
    "when",
    "where",
    "which",
    "why",
    "with",
}


def _get_embeddings(api_key: Optional[str] = None) -> GoogleGenerativeAIEmbeddings:
    """Get cached embedding instance configured for retrieval queries.

    Interactive query embedding fails fast on purpose — no retry wrapper here.
    """
    return get_embeddings_client(api_key, RETRIEVAL_QUERY_TASK)


def _match_snippet(content: str, max_length: int = 240) -> str:
    """Create a compact transcript snippet for search result trust cues."""
    normalized = " ".join(content.split())
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[: max_length - 1].rstrip()}…"


def _access_metadata(row: dict) -> dict:
    """Return human and agent friendly provenance for a scoped search hit."""
    access_scope = row.get("access_scope") or "user_library"
    access_reason = (
        row.get("access_reason")
        or "Visible through the current user's saved video or channel access grants."
    )
    metadata = {
        "accessScope": access_scope,
        "accessReason": access_reason,
    }
    if row.get("access_source"):
        metadata["accessSource"] = row["access_source"]
    return metadata


def _normalize_retrieval_mode(mode: str | None) -> str:
    normalized = str(mode or "hybrid").strip().lower()
    if normalized not in RETRIEVAL_MODES:
        raise ValueError("retrieval_mode must be one of: auto, hybrid, semantic, keyword")
    return normalized


def resolve_retrieval_mode(query: str, mode: str | None) -> str:
    """Return the effective retrieval mode, routing 'auto' on query shape."""
    normalized = _normalize_retrieval_mode(mode)
    if normalized != "auto":
        return normalized
    if _QUOTED_PHRASE_PATTERN.search(query or ""):
        return "keyword"
    return "hybrid"


def _project_scope_response(scope: dict | None) -> dict:
    if not scope:
        return {
            "scope": "all_library",
            "projectId": None,
            "projectSlug": None,
            "projectName": None,
            "videoCount": None,
        }
    return {
        "scope": "project",
        "projectId": scope.get("id"),
        "projectSlug": scope.get("slug"),
        "projectName": scope.get("name"),
        "videoCount": len(scope.get("videoIds") or []),
    }


def _relevance_reason(retrieval_mode: str, row: dict) -> str:
    match_type = row.get("match_type") or ""
    if retrieval_mode == "hybrid":
        if match_type == "hybrid":
            return "Hybrid match: semantic transcript similarity plus keyword/title evidence."
        if match_type in {"title_keyword", "transcript_keyword"}:
            return "Keyword/title match included in hybrid retrieval."
        return "Semantic transcript match included in hybrid retrieval."
    return "Semantic match in the transcript near this timestamp."


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def search_pg(
    query: str,
    user_id: str,
    api_key: Optional[str] = None,
    limit: int = 5,
    category_filters: dict | None = None,
    retrieval_mode: str = "hybrid",
    project_id: str | None = None,
    project_slug: str | None = None,
    youtube_video_id: str | None = None,
) -> dict:
    """
    Semantic search scoped to a user's authorized video library.

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
    normalized_mode = resolve_retrieval_mode(query, retrieval_mode)
    supabase = get_supabase()
    project_scope = resolve_project_scope(supabase, user_id, project_id, project_slug)
    scoped_youtube_video_id = _clean_video_scope(youtube_video_id)
    if normalized_mode == "keyword":
        if project_scope:
            return search_transcript_text_pg(
                query,
                user_id,
                limit,
                category_filters,
                project_scope=project_scope,
                youtube_video_id=scoped_youtube_video_id,
            )
        return search_transcript_text_pg(
            query,
            user_id,
            limit,
            category_filters,
            youtube_video_id=scoped_youtube_video_id,
        )

    normalized_filters = normalize_category_filters(category_filters)
    print(
        f"[SEARCH_PG] Starting search for: {query[:50]}... "
        f"(user={user_id[:8]}, limit={limit}, mode={normalized_mode}, "
        f"filters={bool(normalized_filters)}, video={scoped_youtube_video_id or 'any'})"
    )

    # 1. Embed the query
    embeddings = _get_embeddings(api_key)
    query_vector = embeddings.embed_query(query)
    print(f"[SEARCH_PG] Embedded query ({len(query_vector)} dims)")

    # 2. Call the retrieval RPC function.
    #    min_start_seconds=0: intro filtering is now a soft preference applied
    #    in select_clips(), so short videos still return results.
    rpc_name = "search_chunks_hybrid" if normalized_mode == "hybrid" else "search_chunks"
    rpc_payload = {
        "query_embedding": query_vector,
        "match_user_id": user_id,
        "match_limit": _match_limit_for_scope(limit, scoped_youtube_video_id),
        "min_start_seconds": 0,
        "category_filters": normalized_filters,
    }
    if project_scope:
        rpc_payload["match_project_id"] = project_scope.get("id")
    if normalized_mode == "hybrid":
        rpc_payload["search_query"] = query

    if scoped_youtube_video_id:
        rpc_payload["match_youtube_video_id"] = scoped_youtube_video_id
        rows = _execute_scoped_search_rpc(supabase, rpc_name, rpc_payload, limit)
        rows = _filter_rows_by_youtube_video_id(rows, scoped_youtube_video_id)
    else:
        result = supabase.rpc(
            rpc_name,
            rpc_payload,
        ).execute()
        rows = result.data or []
    print(f"[SEARCH_PG] RPC returned {len(rows)} rows")

    # 3. Map to VideoClip dicts, then apply shared selection + cited answer.
    candidates = [
        {
            "id": "clip_pending",
            "videoId": row["youtube_video_id"],
            "title": row["title"],
            "channelName": row["channel_name"],
            "startSeconds": row["start_seconds"],
            "endSeconds": row["end_seconds"],
            "content": row["content"],
            "thumbnailUrl": row["thumbnail_url"] or "",
            "similarity": row.get("similarity"),
            "keywordRank": row.get("keyword_rank"),
            "hybridScore": row.get("hybrid_score"),
            "matchType": row.get("match_type") or "semantic_transcript",
            "matchSnippet": _match_snippet(row.get("headline") or row["content"]),
            "relevanceReason": _relevance_reason(normalized_mode, row),
            **_access_metadata(row),
        }
        for row in rows
    ]

    clips = select_clips(
        candidates,
        limit,
        per_video_cap=0 if scoped_youtube_video_id else None,
    )
    answer = generate_answer(query, clips, api_key)

    print(f"[SEARCH_PG] Returning {len(clips)} clips (answer: {len(answer)} chars)")

    return {
        "answer": answer,
        "relevantClips": clips,
        "categoryFilters": normalized_filters,
        "retrievalMode": normalized_mode,
        "projectScope": _project_scope_response(project_scope),
        "videoScope": _video_scope_response(scoped_youtube_video_id),
        "retrievalPlan": {
            "primary": (
                "hybrid_vector_keyword_rrf"
                if normalized_mode == "hybrid"
                else "semantic_vector_transcript"
            ),
            "embeddingUsed": True,
            "llmAnswerUsed": bool(answer),
            "candidateMultiplier": 4,
            "projectScoped": bool(project_scope),
            "videoScoped": bool(scoped_youtube_video_id),
            "fallback": (
                "Use search_transcript_text for exact phrase checks or "
                "search_video_concepts for source concepts and generated artifacts."
            ),
        },
        "retrievalBudget": {
            "embeddingCalls": 1,
            "llmCalls": 1 if answer else 0,
            "maxClips": limit,
            "candidateMultiplier": 4,
        },
    }


def search_transcript_text_pg(
    query: str,
    user_id: str,
    limit: int = 5,
    category_filters: dict | None = None,
    project_id: str | None = None,
    project_slug: str | None = None,
    project_scope: dict | None = None,
    youtube_video_id: str | None = None,
) -> dict:
    """
    Keyword/entity search scoped to a user's authorized video library.

    This path does not embed the query or call an LLM. It is intended as a
    cheap, deterministic fallback for exact phrases, names, acronyms, product
    terms, and title/entity-heavy agent searches.
    """
    normalized_filters = normalize_category_filters(category_filters)
    scoped_youtube_video_id = _clean_video_scope(youtube_video_id)
    supabase = get_supabase()
    if project_scope is None:
        project_scope = resolve_project_scope(supabase, user_id, project_id, project_slug)
    print(
        f"[SEARCH_TEXT_PG] Starting keyword search for: {query[:50]}... "
        f"(user={user_id[:8]}, limit={limit}, filters={bool(normalized_filters)}, "
        f"video={scoped_youtube_video_id or 'any'})"
    )

    rows = _search_keyword_rpc(
        supabase,
        query,
        user_id,
        limit,
        normalized_filters,
        project_scope.get("id") if project_scope else None,
        scoped_youtube_video_id,
    )
    fallback_query = None
    if not rows:
        for candidate_query in _keyword_fallback_queries(query):
            if candidate_query == query:
                continue
            fallback_rows = _search_keyword_rpc(
                supabase,
                candidate_query,
                user_id,
                limit,
                normalized_filters,
                project_scope.get("id") if project_scope else None,
                scoped_youtube_video_id,
            )
            if fallback_rows:
                rows = fallback_rows
                fallback_query = candidate_query
                break
    print(f"[SEARCH_TEXT_PG] RPC returned {len(rows)} rows")

    candidates = [
        {
            "id": "clip_pending",
            "videoId": row["youtube_video_id"],
            "title": row["title"],
            "channelName": row["channel_name"],
            "startSeconds": row["start_seconds"],
            "endSeconds": row["end_seconds"],
            "content": row["content"],
            "thumbnailUrl": row["thumbnail_url"] or "",
            "keywordRank": row.get("keyword_rank"),
            "matchType": row.get("match_type") or "transcript_keyword",
            "matchSnippet": _match_snippet(row.get("headline") or row["content"]),
            "relevanceReason": (
                "Keyword match in the transcript/title. Use semantic search next if "
                "the user wants broader conceptual neighbors."
            ),
            **_access_metadata(row),
        }
        for row in rows
    ]

    clips = select_clips(
        candidates,
        limit,
        per_video_cap=0 if scoped_youtube_video_id else None,
    )
    return {
        "answer": "",
        "relevantClips": clips,
        "categoryFilters": normalized_filters,
        "retrievalMode": "keyword",
        "projectScope": _project_scope_response(project_scope),
        "videoScope": _video_scope_response(scoped_youtube_video_id),
        "retrievalPlan": {
            "primary": "keyword_full_text",
            "embeddingUsed": False,
            "llmAnswerUsed": False,
            "fallbackQuery": fallback_query,
            "projectScoped": bool(project_scope),
            "videoScoped": bool(scoped_youtube_video_id),
            "fallback": "Use search_video_moments for semantic neighbors if exact search is sparse.",
        },
        "retrievalBudget": {
            "embeddingCalls": 0,
            "llmCalls": 0,
            "maxClips": limit,
            "candidateMultiplier": 4,
        },
    }


def _search_keyword_rpc(
    supabase: Any,
    query: str,
    user_id: str,
    limit: int,
    normalized_filters: dict,
    project_id: str | None = None,
    youtube_video_id: str | None = None,
) -> list[dict]:
    payload = {
        "search_query": query,
        "match_user_id": user_id,
        "match_limit": _match_limit_for_scope(limit, youtube_video_id),
        "min_start_seconds": 0,
        "category_filters": normalized_filters,
    }
    if project_id:
        payload["match_project_id"] = project_id
    if youtube_video_id:
        payload["match_youtube_video_id"] = youtube_video_id
        rows = _execute_scoped_search_rpc(supabase, "search_chunks_keyword", payload, limit)
        rows = _filter_rows_by_youtube_video_id(rows, youtube_video_id)
        return rows
    result = supabase.rpc("search_chunks_keyword", payload).execute()
    return result.data or []


def _execute_scoped_search_rpc(
    supabase: Any,
    rpc_name: str,
    payload: dict,
    limit: int,
) -> list[dict]:
    """Run a video-scoped search RPC, retrying once with the legacy payload.

    Databases that have not applied migration 027 reject the
    match_youtube_video_id parameter; the retry confines that breakage to the
    previous behavior (wide match_limit plus Python-side filtering).
    """
    try:
        result = supabase.rpc(rpc_name, payload).execute()
        return result.data or []
    except Exception as exc:  # noqa: BLE001 - unmigrated DBs lack the scoped signature.
        print(f"[SEARCH_PG] Scoped {rpc_name} RPC failed; retrying with legacy payload: {exc}")

    legacy_payload = {
        key: value for key, value in payload.items() if key != "match_youtube_video_id"
    }
    legacy_payload["match_limit"] = _legacy_scoped_match_limit(limit)
    result = supabase.rpc(rpc_name, legacy_payload).execute()
    return result.data or []


def _clean_video_scope(youtube_video_id: str | None) -> str | None:
    if not isinstance(youtube_video_id, str):
        return None
    cleaned = youtube_video_id.strip()
    return cleaned or None


def _match_limit_for_scope(limit: int, youtube_video_id: str | None = None) -> int:
    if youtube_video_id:
        return max(limit * 8, 40)
    return limit * 4


def _legacy_scoped_match_limit(limit: int) -> int:
    return max(limit * 20, 100)


def _filter_rows_by_youtube_video_id(rows: list[dict], youtube_video_id: str) -> list[dict]:
    return [row for row in rows if row.get("youtube_video_id") == youtube_video_id]


def _video_scope_response(youtube_video_id: str | None) -> dict:
    return {
        "scope": "video" if youtube_video_id else "all_videos",
        "youtubeVideoId": youtube_video_id,
    }


def _keyword_fallback_queries(query: str) -> list[str]:
    terms = [
        term
        for term in re.findall(r"[a-zA-Z0-9+#.-]+", query)
        if len(term) >= 3 and term.lower() not in KEYWORD_FALLBACK_STOPWORDS
    ]
    return [" ".join(terms[:size]) for size in range(len(terms) - 1, 1, -1)]


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------


def get_library_pg(
    user_id: str,
    project_id: str | None = None,
    project_slug: str | None = None,
) -> dict:
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
    project_scope = resolve_project_scope(supabase, user_id, project_id, project_slug)
    scoped_video_ids = set(project_scope.get("videoIds") or []) if project_scope else None

    # Get user's subscribed channels
    uc_result = (
        supabase.table("user_channels")
        .select("channel_id, channels(id, name)")
        .eq("user_id", user_id)
        .execute()
    )

    subscriptions = uc_result.data or []

    explicit_result = (
        supabase.table("user_videos")
        .select("video_id")
        .eq("user_id", user_id)
        .order("added_at", desc=True)
        .execute()
    )
    explicit_video_ids = [
        row.get("video_id") for row in (explicit_result.data or []) if row.get("video_id")
    ]

    channel_video_groups: list[tuple[str, list[dict]]] = []
    explicit_video_groups: dict[str, dict] = {}
    included_video_ids = set()
    all_video_ids: list[str] = []

    for sub in subscriptions:
        channel_data = sub.get("channels")
        if not channel_data:
            continue

        channel_id = channel_data["id"]
        channel_name = channel_data["name"]

        # Get all videos for this channel
        videos_query = (
            supabase.table("videos")
            .select("id, youtube_video_id, title, thumbnail_url, indexed_at")
            .eq("channel_id", channel_id)
            .order("indexed_at", desc=True)
        )
        if scoped_video_ids is not None:
            if not scoped_video_ids:
                continue
            videos_query = videos_query.in_("id", list(scoped_video_ids))

        videos_result = videos_query.execute()

        videos_data = videos_result.data or []
        for video in videos_data:
            included_video_ids.add(video["id"])
            all_video_ids.append(video["id"])

        channel_video_groups.append((channel_name, videos_data))

    remaining_explicit_video_ids = [
        video_id for video_id in explicit_video_ids if video_id not in included_video_ids
    ]
    if scoped_video_ids is not None:
        remaining_explicit_video_ids = [
            video_id for video_id in remaining_explicit_video_ids if video_id in scoped_video_ids
        ]
    if remaining_explicit_video_ids:
        videos_result = (
            supabase.table("videos")
            .select(
                "id, channel_id, youtube_video_id, title, thumbnail_url, indexed_at, channels(id, name)"
            )
            .in_("id", remaining_explicit_video_ids)
            .order("indexed_at", desc=True)
            .execute()
        )
        grouped: dict[str, dict] = {}
        for video in videos_result.data or []:
            channel = video.get("channels") or {}
            channel_id = video.get("channel_id") or channel.get("id") or "shared"
            entry = grouped.setdefault(
                channel_id,
                {
                    "name": channel.get("name") or "Shared videos",
                    "videos": [],
                },
            )
            entry["videos"].append(video)
            all_video_ids.append(video["id"])
        explicit_video_groups = grouped

    chunk_counts = _chunk_counts_for_videos(supabase, all_video_ids)
    channels_list = []
    total_videos = 0
    total_clips = 0

    for channel_name, videos_data in channel_video_groups:
        channel_videos = []
        for video in videos_data:
            clip_count = chunk_counts.get(str(video["id"]), 0)
            total_clips += clip_count
            channel_videos.append(
                {
                    "videoId": video["youtube_video_id"],
                    "title": video["title"],
                    "thumbnailUrl": video["thumbnail_url"] or "",
                    "clipCount": clip_count,
                    "indexedAt": _parse_indexed_at(video.get("indexed_at")),
                }
            )

        if scoped_video_ids is not None and not channel_videos:
            continue
        total_videos += len(channel_videos)
        channels_list.append(
            {
                "name": channel_name,
                "videoCount": len(channel_videos),
                "videos": channel_videos,
            }
        )

    for entry in explicit_video_groups.values():
        explicit_videos = []
        for video in entry["videos"]:
            clip_count = chunk_counts.get(str(video["id"]), 0)
            total_clips += clip_count
            explicit_videos.append(
                {
                    "videoId": video["youtube_video_id"],
                    "title": video["title"],
                    "thumbnailUrl": video["thumbnail_url"] or "",
                    "clipCount": clip_count,
                    "indexedAt": _parse_indexed_at(video.get("indexed_at")),
                    "access": "video",
                }
            )
        entry["videos"] = explicit_videos
        entry["videoCount"] = len(explicit_videos)
        total_videos += len(explicit_videos)
        channels_list.append(entry)

    return {
        "channels": channels_list,
        "totalVideos": total_videos,
        "totalClips": total_clips,
        "projectScope": _project_scope_response(project_scope),
    }


def _chunk_counts_for_videos(supabase, video_db_ids: list[str]) -> dict[str, int]:
    """Return transcript chunk counts for many videos without an N+1 query loop."""
    unique_ids = list(dict.fromkeys(str(video_id) for video_id in video_db_ids if video_id))
    if not unique_ids:
        return {}

    try:
        result = supabase.rpc(
            "count_chunks_for_videos",
            {"video_ids": unique_ids},
        ).execute()
        rows = result.data or []
        if isinstance(rows, list):
            counts: dict[str, int] = {}
            for row in rows:
                if not isinstance(row, dict):
                    continue
                video_id = str(row.get("video_id") or "")
                if not video_id:
                    continue
                count_value = row.get("chunk_count", row.get("count", 0))
                try:
                    counts[video_id] = int(count_value or 0)
                except (TypeError, ValueError):
                    counts[video_id] = 0
            return {video_id: counts.get(video_id, 0) for video_id in unique_ids}
    except Exception as exc:  # noqa: BLE001 - deployments may not have the bulk helper yet.
        print(f"[WARN] count_chunks_for_videos RPC unavailable, falling back to chunk scan: {exc}")

    try:
        count_result = (
            supabase.table("chunks")
            .select("video_id", count="exact")
            .in_("video_id", unique_ids)
            .execute()
        )
        rows = getattr(count_result, "data", None)
        if isinstance(rows, list) and rows:
            counts = {video_id: 0 for video_id in unique_ids}
            for row in rows:
                if not isinstance(row, dict):
                    continue
                video_id = str(row.get("video_id") or "")
                if video_id in counts:
                    counts[video_id] += 1
            return counts
        if len(unique_ids) == 1 and isinstance(getattr(count_result, "count", None), int):
            return {unique_ids[0]: count_result.count}
    except Exception as exc:  # noqa: BLE001 - keep the old per-video fallback as a last resort.
        print(f"[WARN] Could not bulk-count chunks for library videos: {exc}")

    return {video_id: _count_chunks_for_video(supabase, video_id) for video_id in unique_ids}


def _count_chunks_for_video(supabase, video_db_id: str) -> int:
    """Return a video's transcript chunk count without requiring a deployed RPC helper."""
    try:
        count_result = supabase.rpc(
            "count_chunks_for_video",
            {"vid_id": video_db_id},
        ).execute()
        if isinstance(count_result.data, int):
            return count_result.data
    except Exception as exc:  # noqa: BLE001 - library should not disappear if this helper is absent.
        print(f"[WARN] count_chunks_for_video RPC unavailable, falling back to chunk count: {exc}")

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
        return len(rows) if isinstance(rows, list) else 0
    except Exception as exc:  # noqa: BLE001 - one count failure should not hide saved videos.
        print(f"[WARN] Could not count chunks for video {video_db_id}: {exc}")
        return 0


def _parse_indexed_at(value: str | None) -> int | None:
    if not value:
        return None
    from datetime import datetime

    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except (ValueError, AttributeError):
        return None


def _user_has_video_access(supabase, user_id: str, video: dict) -> bool:
    sub_check = (
        supabase.table("user_channels")
        .select("user_id")
        .match({"user_id": user_id, "channel_id": video["channel_id"]})
        .maybe_single()
        .execute()
    )
    if sub_check.data:
        return True

    video_check = (
        supabase.table("user_videos")
        .select("user_id")
        .match({"user_id": user_id, "video_id": video["id"]})
        .maybe_single()
        .execute()
    )
    return bool(video_check.data)


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
    supabase.table("user_channels").delete().match(
        {
            "user_id": user_id,
            "channel_id": channel_id,
        }
    ).execute()

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
    Remove a user's explicit video grant by YouTube video ID.

    Returns:
        {"deleted": True} on success, {"deleted": False, "reason": "..."} otherwise.

    Canonical video, transcript, chunk, and source-knowledge rows are shared
    across users. They should be cleaned by a separate orphaned-source garbage
    collector, not by an individual user's library action.
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

    explicit_check = (
        supabase.table("user_videos")
        .select("user_id")
        .match({"user_id": user_id, "video_id": video["id"]})
        .maybe_single()
        .execute()
    )
    if explicit_check.data:
        supabase.table("user_videos").delete().match(
            {"user_id": user_id, "video_id": video["id"]}
        ).execute()
        return {"deleted": True, "deletedClips": 0, "reason": "Removed from your library"}

    if not _user_has_video_access(supabase, user_id, video):
        return {"deleted": False, "reason": "No access to this video"}

    return {
        "deleted": False,
        "reason": (
            "This video is available through a channel or playlist grant. "
            "Per-video hiding for bulk sources is not available yet."
        ),
    }


# ---------------------------------------------------------------------------
# Transcript export
# ---------------------------------------------------------------------------


def get_video_transcript_pg(video_id_youtube: str, user_id: str) -> list[dict]:
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
        .select("id, channel_id")
        .eq("youtube_video_id", video_id_youtube)
        .maybe_single()
        .execute()
    )

    if not video_result.data:
        return []

    if not _user_has_video_access(supabase, user_id, video_result.data):
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
