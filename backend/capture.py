"""User-scoped YouTube capture source helpers."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import scrapetube

try:
    from .digest_depth import DEFAULT_DIGEST_DEPTH, normalize_digest_depth
    from .ingestion_costs import build_ingestion_cost_estimate
    from .jobs import create_ingestion_job, utc_now
    from .youtube_oauth import get_youtube_oauth_access_token
    from .youtube_utils import detect_url_type
except ImportError:
    from digest_depth import DEFAULT_DIGEST_DEPTH, normalize_digest_depth
    from ingestion_costs import build_ingestion_cost_estimate
    from jobs import create_ingestion_job, utc_now
    from youtube_oauth import get_youtube_oauth_access_token
    from youtube_utils import detect_url_type

YOUTUBE_PLAYLIST_ITEMS_URL = "https://www.googleapis.com/youtube/v3/playlistItems"


class YoutubePlaylistApiError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code

    @property
    def auth_failed(self) -> bool:
        return self.status_code in {401, 403}


def _rows(result: Any) -> list[dict]:
    data = getattr(result, "data", None)
    if data is None:
        return []
    if isinstance(data, list):
        return data
    return [data]


def _first(result: Any) -> dict | None:
    rows = _rows(result)
    return rows[0] if rows else None


def list_capture_sources(supabase: Any, user_id: str, limit: int = 50) -> list[dict]:
    """List user-owned capture sources such as YouTube playlists."""
    bounded_limit = max(1, min(limit, 100))
    return _rows(
        supabase.table("youtube_capture_sources")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(bounded_limit)
        .execute()
    )


def list_capture_source_items(
    supabase: Any,
    user_id: str,
    capture_source_id: str,
    limit: int = 10,
) -> list[dict]:
    """List recent discovered/queued items for a user-owned capture source."""
    bounded_limit = max(1, min(limit, 50))
    return _rows(
        supabase.table("youtube_capture_items")
        .select(
            "id, youtube_video_id, status, ingestion_job_id, skip_reason, "
            "metadata, discovered_at, updated_at"
        )
        .eq("user_id", user_id)
        .eq("capture_source_id", capture_source_id)
        .order("discovered_at", desc=True)
        .limit(bounded_limit)
        .execute()
    )


def create_playlist_capture_source(
    supabase: Any,
    user_id: str,
    playlist_url: str,
    title: str = "",
    created_by: str = "user",
    created_by_client: str | None = None,
) -> dict:
    """Create a user-selected YouTube playlist capture source."""
    source_url = " ".join(str(playlist_url).split()).strip()
    source_type, playlist_id = detect_url_type(source_url)
    if source_type != "playlist" or not playlist_id:
        raise ValueError("playlist_url must be a valid YouTube playlist URL")
    if created_by not in {"user", "agent"}:
        raise ValueError("created_by must be 'user' or 'agent'")

    payload = {
        "user_id": user_id,
        "source_type": "playlist",
        "source_url": source_url,
        "external_id": playlist_id,
        "title": _clean_title(title) or "YouTube playlist",
        "status": "active",
        "created_by": created_by,
    }
    if created_by_client:
        payload["created_by_client"] = created_by_client

    return _first(supabase.table("youtube_capture_sources").insert(payload).execute()) or payload


def build_capture_sources_context(supabase: Any, user_id: str, limit: int = 50) -> dict:
    """Return agent-readable capture source context."""
    sources = list_capture_sources(supabase, user_id, limit)
    decorated_sources = []
    for source in sources:
        source_id = source.get("id")
        recent_items = (
            list_capture_source_items(supabase, user_id, source_id, 10)
            if isinstance(source_id, str)
            else []
        )
        decorated_sources.append({**source, "recentItems": recent_items})

    return {
        "captureSources": decorated_sources,
        "guidance": (
            "Capture sources are standing user-selected inputs such as a dedicated "
            "YouTube playlist. Agents may read them to understand how new videos enter "
            "the knowledge base. Recent items expose discovered and queued status; source "
            "sync and ingestion jobs remain separately audited."
        ),
    }


def fetch_playlist_video_items(playlist_id: str, access_token: str | None = None) -> list[dict]:
    """Fetch basic video IDs and titles from a YouTube playlist."""
    playlist_id = str(playlist_id).strip()
    if not playlist_id:
        return []

    api_error: YoutubePlaylistApiError | None = None
    if access_token:
        try:
            api_items = _fetch_playlist_video_items_with_youtube_api(playlist_id, access_token)
            if api_items:
                return api_items
        except YoutubePlaylistApiError as exc:
            api_error = exc

    public_items = _fetch_playlist_video_items_with_scrapetube(playlist_id)
    if public_items:
        return public_items

    public_items = _fetch_playlist_video_items_with_ytdlp(playlist_id)
    if public_items:
        return public_items

    if api_error and api_error.auth_failed:
        raise ValueError("YouTube connection needs reconnect before this playlist can be synced")

    return []


def _fetch_playlist_video_items_with_scrapetube(playlist_id: str) -> list[dict]:
    """Fetch public playlist videos through scrapetube."""
    items = []
    for video in scrapetube.get_playlist(playlist_id):
        video_id = video.get("videoId")
        if not isinstance(video_id, str) or not video_id.strip():
            continue

        title = _extract_playlist_video_title(video)
        playlist_item_id = video.get("playlistVideoRenderer", {}).get("playlistVideoId")
        if not isinstance(playlist_item_id, str):
            playlist_item_id = video.get("playlistVideoId")
        items.append(
            {
                "youtube_video_id": video_id.strip(),
                "playlist_item_id": playlist_item_id if isinstance(playlist_item_id, str) else None,
                "title": title,
                "source_added_at": None,
                "metadata": {"title": title} if title else {},
            }
        )
    return items


def _fetch_playlist_video_items_with_youtube_api(playlist_id: str, access_token: str) -> list[dict]:
    """Fetch playlist videos through the user's YouTube readonly OAuth grant."""
    items: list[dict] = []
    page_token: str | None = None

    while True:
        params = {
            "part": "snippet,contentDetails",
            "playlistId": playlist_id,
            "maxResults": "50",
        }
        if page_token:
            params["pageToken"] = page_token

        url = f"{YOUTUBE_PLAYLIST_ITEMS_URL}?{urlencode(params)}"
        request = Request(url, headers={"Authorization": f"Bearer {access_token}"})
        try:
            with urlopen(request, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            message = _read_http_error_message(exc)
            raise YoutubePlaylistApiError(message, exc.code) from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise YoutubePlaylistApiError(f"YouTube playlist API request failed: {exc}") from exc

        for raw_item in payload.get("items", []):
            item = _normalize_youtube_api_playlist_item(raw_item)
            if item:
                items.append(item)

        page_token = payload.get("nextPageToken")
        if not page_token:
            break

    return items


def _fetch_playlist_video_items_with_ytdlp(playlist_id: str) -> list[dict]:
    """Fetch public playlist videos through yt-dlp when scrapetube returns no rows."""
    try:
        import yt_dlp
    except Exception:
        return []

    playlist_url = f"https://www.youtube.com/playlist?list={quote(playlist_id, safe='')}"
    try:
        with yt_dlp.YoutubeDL(
            {
                "extract_flat": "in_playlist",
                "ignoreerrors": True,
                "quiet": True,
                "skip_download": True,
            }
        ) as downloader:
            info = downloader.extract_info(playlist_url, download=False)
    except Exception:
        return []

    entries = info.get("entries", []) if isinstance(info, dict) else []
    items = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        video_id = entry.get("id") or entry.get("url")
        if not isinstance(video_id, str) or not video_id.strip():
            continue
        title = _clean_title(entry.get("title", ""))
        metadata = {"title": title} if title else {}
        if entry.get("duration"):
            metadata["duration"] = entry.get("duration")
        items.append(
            {
                "youtube_video_id": video_id.strip(),
                "playlist_item_id": None,
                "title": title,
                "source_added_at": None,
                "metadata": metadata,
            }
        )
    return items


def sync_playlist_capture_source(
    supabase: Any,
    user_id: str,
    capture_source_id: str,
    max_jobs: int = 1,
    playlist_items: list[dict] | None = None,
    digest_depth: str = DEFAULT_DIGEST_DEPTH,
) -> dict:
    """Discover playlist videos and queue the requested number of ingestion jobs."""
    digest_depth = normalize_digest_depth(digest_depth)
    source = _get_capture_source(supabase, user_id, capture_source_id)
    if not source:
        raise ValueError("Capture source not found")
    if source.get("source_type") != "playlist":
        raise ValueError("Only playlist capture sources can be synced")
    if source.get("status") not in {"active", "error"}:
        raise ValueError("Capture source must be active before it can be synced")

    try:
        access_token = (
            None
            if playlist_items is not None
            else get_youtube_oauth_access_token(supabase, user_id)
        )
        raw_items = (
            playlist_items
            if playlist_items is not None
            else fetch_playlist_video_items(
                str(source.get("external_id", "")),
                access_token=access_token,
            )
        )
    except Exception as exc:
        _update_capture_source(
            supabase,
            capture_source_id,
            {"last_error": str(exc), "status": "error", "last_synced_at": utc_now()},
        )
        raise

    existing_items = _list_capture_items(supabase, capture_source_id)
    existing_by_video_id = {
        item.get("youtube_video_id"): item
        for item in existing_items
        if isinstance(item.get("youtube_video_id"), str)
    }

    normalized_items = _normalize_playlist_items(raw_items)
    new_items = []
    for item in normalized_items:
        video_id = item["youtube_video_id"]
        if video_id in existing_by_video_id:
            continue
        inserted = _insert_capture_item(
            supabase,
            {
                "capture_source_id": capture_source_id,
                "user_id": user_id,
                "youtube_video_id": video_id,
                "playlist_item_id": item.get("playlist_item_id"),
                "source_added_at": item.get("source_added_at"),
                "status": "discovered",
                "metadata": item.get("metadata") or {},
            },
        )
        new_items.append(inserted)
        existing_by_video_id[video_id] = inserted

    queue_candidates = [
        item
        for item in list(existing_by_video_id.values())
        if item.get("status") == "discovered" and item.get("ingestion_job_id") is None
    ]
    queued_candidate_ids = [
        str(item.get("youtube_video_id", "")).strip()
        for item in queue_candidates
        if str(item.get("youtube_video_id", "")).strip()
    ]
    sync_cost_estimate = build_ingestion_cost_estimate(
        supabase,
        user_id,
        str(source.get("source_url") or ""),
        "playlist",
        queued_candidate_ids,
        digest_depth,
    )
    queue_candidate_count = len(queue_candidates)
    max_jobs_to_create = max(0, int(max_jobs or 0))
    jobs_to_create = min(max_jobs_to_create, queue_candidate_count)

    queued_jobs = []
    queued_items = []
    for item in queue_candidates[:jobs_to_create]:
        video_id = item["youtube_video_id"]
        job = create_ingestion_job(
            supabase,
            user_id,
            f"https://www.youtube.com/watch?v={video_id}",
            "video",
            build_ingestion_cost_estimate(
                supabase,
                user_id,
                f"https://www.youtube.com/watch?v={video_id}",
                "video",
                [video_id],
                digest_depth,
            ),
        )
        queued_jobs.append(job)
        updated_item = _update_capture_item(
            supabase,
            item["id"],
            {
                "status": "queued",
                "ingestion_job_id": job.get("id"),
                "skip_reason": None,
            },
        )
        queued_items.append(updated_item or {**item, "status": "queued"})

    _update_capture_source(
        supabase,
        capture_source_id,
        {
            "last_synced_at": utc_now(),
            "last_error": None,
            "status": "active",
            "last_seen_item_at": _latest_source_added_at(normalized_items),
        },
    )

    return {
        "captureSource": source,
        "discoveredCount": len(normalized_items),
        "newItemCount": len(new_items),
        "queueCandidateCount": queue_candidate_count,
        "queuedJobCount": len(queued_jobs),
        "requestedJobCount": max_jobs_to_create,
        "remainingQueueCount": max(0, queue_candidate_count - len(queued_jobs)),
        "skippedExistingCount": len(normalized_items) - len(new_items),
        "activeJobLimitReached": False,
        "costEstimate": sync_cost_estimate,
        "newItems": new_items,
        "queuedItems": queued_items,
        "queuedJobs": queued_jobs,
        "guidance": (
            "Playlist sync discovers saved videos separately from ingestion. "
            "Call sync with max_jobs=0 to preview the queue count, then queue the "
            "confirmed number of video jobs."
        ),
    }


def _clean_title(value: str) -> str:
    return " ".join(str(value).split())[:160].strip()


def _get_capture_source(supabase: Any, user_id: str, capture_source_id: str) -> dict | None:
    return _first(
        supabase.table("youtube_capture_sources")
        .select("*")
        .eq("id", capture_source_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )


def _list_capture_items(supabase: Any, capture_source_id: str) -> list[dict]:
    return _rows(
        supabase.table("youtube_capture_items")
        .select("id, youtube_video_id, status, ingestion_job_id")
        .eq("capture_source_id", capture_source_id)
        .execute()
    )


def _insert_capture_item(supabase: Any, payload: dict) -> dict:
    return _first(supabase.table("youtube_capture_items").insert(payload).execute()) or payload


def _update_capture_item(supabase: Any, capture_item_id: str, fields: dict) -> dict | None:
    return _first(
        supabase.table("youtube_capture_items").update(fields).eq("id", capture_item_id).execute()
    )


def _update_capture_source(supabase: Any, capture_source_id: str, fields: dict) -> dict | None:
    return _first(
        supabase.table("youtube_capture_sources")
        .update(fields)
        .eq("id", capture_source_id)
        .execute()
    )


def _normalize_playlist_items(raw_items: list[dict]) -> list[dict]:
    normalized = []
    seen_video_ids = set()
    for item in raw_items:
        video_id = item.get("youtube_video_id") or item.get("video_id") or item.get("videoId")
        if not isinstance(video_id, str) or not video_id.strip():
            continue
        video_id = video_id.strip()
        if video_id in seen_video_ids:
            continue
        seen_video_ids.add(video_id)

        title = _clean_title(item.get("title", ""))
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        if title:
            metadata = {**metadata, "title": title}
        normalized.append(
            {
                "youtube_video_id": video_id,
                "playlist_item_id": _optional_clean_string(item.get("playlist_item_id")),
                "source_added_at": _optional_clean_string(item.get("source_added_at")),
                "metadata": metadata,
            }
        )
    return normalized


def _extract_playlist_video_title(video: dict) -> str:
    title = video.get("title")
    if isinstance(title, dict):
        runs = title.get("runs", [])
        if runs and isinstance(runs[0], dict):
            return _clean_title(runs[0].get("text", ""))
    if isinstance(title, str):
        return _clean_title(title)
    return ""


def _normalize_youtube_api_playlist_item(raw_item: dict) -> dict | None:
    snippet = raw_item.get("snippet") if isinstance(raw_item.get("snippet"), dict) else {}
    content_details = (
        raw_item.get("contentDetails") if isinstance(raw_item.get("contentDetails"), dict) else {}
    )
    resource = snippet.get("resourceId") if isinstance(snippet.get("resourceId"), dict) else {}
    video_id = content_details.get("videoId") or resource.get("videoId")
    if not isinstance(video_id, str) or not video_id.strip():
        return None

    title = _clean_title(snippet.get("title", ""))
    metadata: dict[str, Any] = {}
    if title:
        metadata["title"] = title
    for source_key, metadata_key in [
        ("channelTitle", "channelTitle"),
        ("position", "position"),
        ("description", "description"),
    ]:
        value = snippet.get(source_key)
        if value not in (None, ""):
            metadata[metadata_key] = value

    playlist_item_id = raw_item.get("id")
    source_added_at = snippet.get("publishedAt")
    return {
        "youtube_video_id": video_id.strip(),
        "playlist_item_id": playlist_item_id if isinstance(playlist_item_id, str) else None,
        "title": title,
        "source_added_at": source_added_at if isinstance(source_added_at, str) else None,
        "metadata": metadata,
    }


def _read_http_error_message(exc: HTTPError) -> str:
    try:
        raw_body = exc.read().decode("utf-8")
        payload = json.loads(raw_body)
    except Exception:
        return f"YouTube playlist API request failed with HTTP {exc.code}"

    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    return f"YouTube playlist API request failed with HTTP {exc.code}"


def _optional_clean_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _latest_source_added_at(items: list[dict]) -> str | None:
    values = [
        item.get("source_added_at")
        for item in items
        if isinstance(item.get("source_added_at"), str) and item.get("source_added_at")
    ]
    return max(values) if values else None
