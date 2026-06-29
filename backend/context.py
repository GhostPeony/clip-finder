"""User-scoped context helpers for source knowledge and personal overlays."""

from __future__ import annotations

import json
import re
from base64 import urlsafe_b64decode, urlsafe_b64encode
from typing import Any

try:
    from .brain_sync import queue_brain_sync_event
    from .category_taxonomy import (
        category_filter_examples,
        get_category_taxonomy,
        labels_match_category_filters,
        normalize_category_filters,
    )
    from .projects import resolve_project_scope
    from .repo_context import normalize_repo_context, validate_repo_context
except ImportError:
    from brain_sync import queue_brain_sync_event
    from category_taxonomy import (
        category_filter_examples,
        get_category_taxonomy,
        labels_match_category_filters,
        normalize_category_filters,
    )
    from projects import resolve_project_scope
    from repo_context import normalize_repo_context, validate_repo_context


DETAIL_LEVEL_BUDGETS = {
    "compact": {
        "default_max_chars": 6000,
        "concept_summary_chars": 280,
        "artifact_summary_chars": 280,
        "artifact_excerpt_chars": 700,
        "source_ref_limit": 3,
    },
    "standard": {
        "default_max_chars": 12000,
        "concept_summary_chars": 700,
        "artifact_summary_chars": 700,
        "artifact_excerpt_chars": 1800,
        "source_ref_limit": 5,
    },
    "deep": {
        "default_max_chars": 24000,
        "concept_summary_chars": 1400,
        "artifact_summary_chars": 1400,
        "artifact_excerpt_chars": 8000,
        "source_ref_limit": 8,
    },
}
SOURCE_KNOWLEDGE_RETRIEVAL_MODES = {"hybrid", "semantic", "keyword"}
BRAIN_DIGEST_VERSION = "memexai-brain-digest-v1"
BRAIN_DIGEST_CURSOR_VERSION = 1
BRAIN_DIGEST_OBJECTS = {
    "videos",
    "labels",
    "concepts",
    "artifacts",
    "notes",
    "personal_concepts",
}
DEFAULT_BRAIN_DIGEST_OBJECTS = (
    "videos",
    "labels",
    "concepts",
    "artifacts",
    "notes",
    "personal_concepts",
)
LIBRARY_COMPONENT_TYPES = {
    "video",
    "source_label",
    "source_concept",
    "source_edge",
    "knowledge_artifact",
    "transcript_chunk",
    "agent_note",
    "personal_concept",
}
VIDEO_CONTEXT_COLUMNS = (
    "id, channel_id, youtube_video_id, title, thumbnail_url, transcript_seconds, indexed_at"
)
VIDEO_CONTEXT_COLUMNS_WITH_LEGACY_OWNER = f"{VIDEO_CONTEXT_COLUMNS}, indexed_by"


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


def _is_missing_legacy_indexed_by_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "indexed_by" in message and ("does not exist" in message or "42703" in message)


def _video_rows_with_optional_legacy_owner(query_factory: Any) -> list[dict]:
    try:
        return _rows(query_factory(VIDEO_CONTEXT_COLUMNS_WITH_LEGACY_OWNER).execute())
    except Exception as exc:
        if not _is_missing_legacy_indexed_by_error(exc):
            raise
        print("[WARN] videos.indexed_by unavailable; retrying video query without legacy owner")
        return _rows(query_factory(VIDEO_CONTEXT_COLUMNS).execute())


def _first_video_with_optional_legacy_owner(query_factory: Any) -> dict | None:
    rows = _video_rows_with_optional_legacy_owner(query_factory)
    return rows[0] if rows else None


def _context_access_metadata(
    has_channel_access: bool,
    video_grant: dict | None = None,
    legacy_owner_access: bool = False,
) -> dict:
    access_source = ""
    if isinstance(video_grant, dict):
        access_source = str(video_grant.get("access_source") or "").strip()

    if has_channel_access and access_source:
        return {
            "accessScope": "channel_and_video",
            "accessSource": access_source,
            "accessReason": "Visible through channel access and an explicit video grant.",
        }
    if has_channel_access:
        return {
            "accessScope": "channel",
            "accessSource": "channel",
            "accessReason": "Visible through a channel access grant.",
        }
    if legacy_owner_access:
        return {
            "accessScope": "user_library",
            "accessSource": "legacy_indexed_by",
            "accessReason": (
                "Visible because this user originally indexed the video before "
                "per-video grants were introduced."
            ),
        }
    return {
        "accessScope": "video",
        "accessSource": access_source or "ingest",
        "accessReason": "Visible through an explicit saved-video grant.",
    }


def _resolve_optional_project_scope(
    supabase: Any,
    user_id: str,
    project_id: str | None = None,
    project_slug: str | None = None,
) -> dict | None:
    return resolve_project_scope(supabase, user_id, project_id, project_slug)


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


def _select_video_for_user(supabase: Any, user_id: str, youtube_video_id: str) -> dict | None:
    video = _first_video_with_optional_legacy_owner(
        lambda columns: (
            supabase.table("videos")
            .select(columns)
            .eq("youtube_video_id", youtube_video_id)
            .maybe_single()
        )
    )
    if not video:
        return None

    subscription = _first(
        supabase.table("user_channels")
        .select("user_id")
        .match({"user_id": user_id, "channel_id": video["channel_id"]})
        .maybe_single()
        .execute()
    )
    video_grant = _first(
        supabase.table("user_videos")
        .select("user_id, access_source")
        .match({"user_id": user_id, "video_id": video["id"]})
        .maybe_single()
        .execute()
    )
    legacy_owner_access = video.get("indexed_by") == user_id
    if not subscription and not video_grant and not legacy_owner_access:
        return None

    channel = _first(
        supabase.table("channels")
        .select("id, name, youtube_handle")
        .eq("id", video["channel_id"])
        .maybe_single()
        .execute()
    )
    return {
        **video,
        "channel": channel or {},
        "access": _context_access_metadata(bool(subscription), video_grant, legacy_owner_access),
    }


def _select_video_by_db_id_for_user(
    supabase: Any,
    user_id: str,
    video_db_id: str | None,
) -> dict | None:
    if not video_db_id:
        return None

    video = _first_video_with_optional_legacy_owner(
        lambda columns: (
            supabase.table("videos").select(columns).eq("id", video_db_id).maybe_single()
        )
    )
    if not video:
        return None

    subscription = _first(
        supabase.table("user_channels")
        .select("user_id")
        .match({"user_id": user_id, "channel_id": video["channel_id"]})
        .maybe_single()
        .execute()
    )
    video_grant = _first(
        supabase.table("user_videos")
        .select("user_id, access_source")
        .match({"user_id": user_id, "video_id": video["id"]})
        .maybe_single()
        .execute()
    )
    legacy_owner_access = video.get("indexed_by") == user_id
    if not subscription and not video_grant and not legacy_owner_access:
        return None

    channel = _first(
        supabase.table("channels")
        .select("id, name, youtube_handle")
        .eq("id", video["channel_id"])
        .maybe_single()
        .execute()
    )
    return {
        **video,
        "channel": channel or {},
        "access": _context_access_metadata(bool(subscription), video_grant, legacy_owner_access),
    }


def get_video_context(
    supabase: Any,
    user_id: str,
    youtube_video_id: str,
    project_id: str | None = None,
    project_slug: str | None = None,
) -> dict | None:
    """Return source-derived context for a video if it belongs to the user's library."""
    project_scope = _resolve_optional_project_scope(supabase, user_id, project_id, project_slug)
    video = _select_video_for_user(supabase, user_id, youtube_video_id)
    if not video:
        return None
    if project_scope and video.get("id") not in set(project_scope.get("videoIds") or []):
        return None

    video_id = video["id"]
    transcript_lines = _rows(
        supabase.table("transcript_lines")
        .select("id, content, start_seconds, end_seconds, source, language, metadata")
        .eq("video_id", video_id)
        .order("start_seconds", desc=False)
        .execute()
    )
    transcript_chunks = _rows(
        supabase.table("chunks")
        .select("id, content, start_seconds, end_seconds")
        .eq("video_id", video_id)
        .order("start_seconds", desc=False)
        .execute()
    )
    concepts = _rows(
        supabase.table("source_concepts")
        .select("id, concept_type, name, summary, source_refs, metadata")
        .eq("video_id", video_id)
        .order("created_at", desc=False)
        .execute()
    )
    edges = _rows(
        supabase.table("source_edges")
        .select("id, relation, from_ref, to_ref, evidence_refs, metadata")
        .eq("video_id", video_id)
        .order("created_at", desc=False)
        .execute()
    )
    artifacts = _rows(
        supabase.table("knowledge_artifacts")
        .select(
            "id, artifact_type, title, summary, content, source_refs, metadata, created_by, updated_at"
        )
        .eq("video_id", video_id)
        .or_(f"user_id.is.null,user_id.eq.{user_id}")
        .order("updated_at", desc=True)
        .execute()
    )

    return {
        "video": {
            "id": video["id"],
            "videoId": video["youtube_video_id"],
            "title": video["title"],
            "thumbnailUrl": video.get("thumbnail_url", ""),
            "transcriptSeconds": video.get("transcript_seconds", 0),
            "indexedAt": video.get("indexed_at"),
            "channel": video.get("channel", {}),
            **video.get("access", {}),
        },
        "transcriptLines": transcript_lines,
        "transcriptChunks": transcript_chunks,
        "sourceConcepts": concepts,
        "sourceEdges": edges,
        "knowledgeArtifacts": artifacts,
        "projectScope": _project_scope_response(project_scope),
    }


def list_video_library_context(
    supabase: Any,
    user_id: str,
    limit: int = 50,
    project_id: str | None = None,
    project_slug: str | None = None,
) -> dict:
    """Return indexed channels and recent videos available to the current user."""
    normalized_limit = max(1, min(limit, 100))
    project_scope = _resolve_optional_project_scope(supabase, user_id, project_id, project_slug)
    videos = _user_video_rows(
        supabase,
        user_id,
        normalized_limit,
        scope_video_ids=project_scope.get("videoIds") if project_scope else None,
    )
    channel_ids = sorted(
        {
            video.get("channel_id")
            for video in videos
            if isinstance(video.get("channel_id"), str) and video.get("channel_id")
        }
    )
    if not videos:
        return {
            "channels": [],
            "totalChannels": 0,
            "returnedVideos": 0,
            "limit": normalized_limit,
            "projectScope": _project_scope_response(project_scope),
            "guidance": (
                "No indexed videos were found in this project scope."
                if project_scope
                else (
                    "No indexed channels were found for this user. Ingest videos in the app "
                    "before asking agents to use saved video context."
                )
            ),
        }

    channel_rows = _rows(
        supabase.table("channels")
        .select("id, name, youtube_handle")
        .in_("id", channel_ids)
        .execute()
    )

    channel_by_id = {row.get("id"): row for row in channel_rows if row.get("id")}
    videos_by_channel: dict[str, list[dict]] = {channel_id: [] for channel_id in channel_ids}
    for video in videos:
        channel_id = video.get("channel_id")
        if channel_id not in videos_by_channel:
            continue
        videos_by_channel[channel_id].append(
            {
                "id": video.get("id"),
                "videoId": video.get("youtube_video_id"),
                "title": video.get("title"),
                "thumbnailUrl": video.get("thumbnail_url", ""),
                "transcriptSeconds": video.get("transcript_seconds", 0),
                "indexedAt": video.get("indexed_at"),
                **video.get("access", {}),
            }
        )

    channels = []
    for channel_id in channel_ids:
        channel = channel_by_id.get(channel_id, {})
        channel_videos = videos_by_channel.get(channel_id, [])
        channels.append(
            {
                "id": channel_id,
                "name": channel.get("name") or "Unknown channel",
                "youtubeHandle": channel.get("youtube_handle"),
                "returnedVideoCount": len(channel_videos),
                "videos": channel_videos,
            }
        )

    return {
        "channels": channels,
        "totalChannels": len(channels),
        "returnedVideos": len(videos),
        "limit": normalized_limit,
        "projectScope": _project_scope_response(project_scope),
        "guidance": (
            "Use videoId with get_video_context for full transcript-derived context, "
            "search_video_moments with retrieval_mode=hybrid for timestamp search, or build_agent_brief "
            "for spec and implementation planning."
        ),
    }


def list_agent_notes(supabase: Any, user_id: str, limit: int = 50) -> list[dict]:
    """Return recent notes from the user's writable context overlay."""
    return _rows(
        supabase.table("agent_notes")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )


def build_brain_digest_export(
    supabase: Any,
    user_id: str,
    cursor: str | None = None,
    since: str | None = None,
    objects: list[str] | None = None,
    limit: int = 20,
    detail_level: str = "compact",
    max_chars: int | None = None,
    max_context_tokens: int | None = None,
) -> dict:
    """Build a compact incremental export for external personal brains."""
    normalized_limit = max(1, min(limit, 50))
    normalized_detail = normalize_detail_level(detail_level)
    effective_max_chars = response_char_budget(normalized_detail, max_chars, max_context_tokens)
    requested_objects = _normalize_brain_digest_objects(objects)
    cursor_state = _decode_brain_digest_cursor(cursor)
    effective_since = _clean_optional_string(since) or _clean_optional_string(
        cursor_state.get("since")
    )

    accessible_videos: list[dict] = []
    video_ids: list[str] = []
    channel_by_id: dict[str, dict] = {}
    video_by_id: dict[str, dict] = {}
    if requested_objects & {"videos", "labels", "concepts", "artifacts"}:
        accessible_videos = _user_video_rows(supabase, user_id, normalized_limit * 3)
        video_ids = [video.get("id") for video in accessible_videos if video.get("id")]
        channel_by_id = _channel_map(supabase, accessible_videos)
        video_by_id = {
            video.get("id"): _digest_video(video, channel_by_id)
            for video in accessible_videos
            if video.get("id")
        }

    digest = {
        "videos": [],
        "sourceLabels": [],
        "sourceConcepts": [],
        "knowledgeArtifacts": [],
        "agentNotes": [],
        "personalConcepts": [],
    }
    emitted_rows = []

    if "videos" in requested_objects:
        digest["videos"] = [
            _digest_video(video, channel_by_id)
            for video in accessible_videos
            if _row_changed_after(video, effective_since, ["indexed_at"])
        ][:normalized_limit]
        emitted_rows.extend(digest["videos"])

    if video_ids and "labels" in requested_objects:
        labels = _rows(
            supabase.table("source_labels")
            .select(
                "id, video_id, label_type, label, confidence, source_refs, metadata, created_at"
            )
            .in_("video_id", video_ids)
            .order("created_at", desc=True)
            .limit(normalized_limit * 3)
            .execute()
        )
        digest["sourceLabels"] = [
            _digest_label(label, video_by_id)
            for label in labels
            if _row_changed_after(label, effective_since, ["updated_at", "created_at"])
        ][: normalized_limit * 2]
        emitted_rows.extend(digest["sourceLabels"])

    if video_ids and "concepts" in requested_objects:
        concepts = _rows(
            supabase.table("source_concepts")
            .select("id, video_id, concept_type, name, summary, source_refs, metadata, updated_at")
            .in_("video_id", video_ids)
            .order("updated_at", desc=True)
            .limit(normalized_limit * 2)
            .execute()
        )
        digest["sourceConcepts"] = [
            _digest_concept(concept, video_by_id, normalized_detail)
            for concept in concepts
            if _row_changed_after(concept, effective_since, ["updated_at", "created_at"])
        ][:normalized_limit]
        emitted_rows.extend(digest["sourceConcepts"])

    if video_ids and "artifacts" in requested_objects:
        artifacts = _rows(
            supabase.table("knowledge_artifacts")
            .select(
                "id, video_id, artifact_type, title, summary, content, source_refs, "
                "metadata, updated_at"
            )
            .in_("video_id", video_ids)
            .or_(f"user_id.is.null,user_id.eq.{user_id}")
            .order("updated_at", desc=True)
            .limit(normalized_limit)
            .execute()
        )
        digest["knowledgeArtifacts"] = [
            _digest_artifact(artifact, video_by_id, normalized_detail)
            for artifact in artifacts
            if _row_changed_after(artifact, effective_since, ["updated_at", "created_at"])
        ][:normalized_limit]
        emitted_rows.extend(digest["knowledgeArtifacts"])

    if "notes" in requested_objects:
        notes = _rows(
            supabase.table("agent_notes")
            .select("id, content, source_refs, tags, created_by, created_by_client, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(normalized_limit)
            .execute()
        )
        digest["agentNotes"] = [
            _digest_note(note, normalized_detail)
            for note in notes
            if _row_changed_after(note, effective_since, ["updated_at", "created_at"])
        ][:normalized_limit]
        emitted_rows.extend(digest["agentNotes"])

    if "personal_concepts" in requested_objects:
        personal_concepts = _rows(
            supabase.table("personal_concepts")
            .select("id, name, summary, status, source_refs, updated_at")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .limit(normalized_limit)
            .execute()
        )
        digest["personalConcepts"] = [
            _digest_personal_concept(concept, normalized_detail)
            for concept in personal_concepts
            if _row_changed_after(concept, effective_since, ["updated_at", "created_at"])
        ][:normalized_limit]
        emitted_rows.extend(digest["personalConcepts"])

    latest_timestamp = _latest_row_timestamp(emitted_rows) or effective_since
    payload = {
        "version": BRAIN_DIGEST_VERSION,
        "userId": user_id,
        "sync": {
            "cursor": cursor or None,
            "since": effective_since,
            "nextCursor": _encode_brain_digest_cursor(
                {"version": BRAIN_DIGEST_CURSOR_VERSION, "since": latest_timestamp}
            ),
            "hasMore": False,
            "objects": sorted(requested_objects),
            "limit": normalized_limit,
        },
        "detailLevel": normalized_detail,
        "accessModel": {
            "scope": "current_user_grants",
            "globalSearch": "not_exposed",
            "provenanceFields": ["accessScope", "accessSource", "accessReason"],
        },
        "digest": digest,
        "guidance": (
            "Sync compact source refs and summaries into the external brain. Keep raw "
            "transcripts out of durable memory unless the user asks for deep evidence; use "
            "videoId and sourceRefs to pull timestamp context later."
        ),
        "exportBudget": {
            "detailLevel": normalized_detail,
            "maxChars": effective_max_chars,
            "maxContextTokens": max_context_tokens,
            "estimatedResponseChars": 0,
            "truncatedToBudget": False,
        },
    }
    return _fit_brain_digest_to_budget(payload, effective_max_chars)


def create_agent_note(
    supabase: Any,
    user_id: str,
    content: str,
    source_refs: list[dict] | None = None,
    tags: list[str] | None = None,
    created_by: str = "agent",
    created_by_client: str | None = None,
) -> dict:
    """Create a user-scoped note without mutating source video context."""
    payload = {
        "user_id": user_id,
        "content": content,
        "source_refs": source_refs or [],
        "tags": tags or [],
        "created_by": created_by,
    }
    if created_by_client:
        payload["created_by_client"] = created_by_client

    note = _first(supabase.table("agent_notes").insert(payload).execute()) or payload
    _queue_overlay_note_created_event(supabase, user_id, note)
    return note


def upsert_personal_concept(
    supabase: Any,
    user_id: str,
    name: str,
    summary: str = "",
    source_refs: list[dict] | None = None,
    status: str = "active",
    created_by: str = "agent",
    created_by_client: str | None = None,
) -> dict:
    """Create or update a user-specific concept in the writable overlay."""
    payload = {
        "user_id": user_id,
        "name": name,
        "summary": summary,
        "source_refs": source_refs or [],
        "status": status,
        "created_by": created_by,
    }
    if created_by_client:
        payload["created_by_client"] = created_by_client

    result = (
        supabase.table("personal_concepts").upsert(payload, on_conflict="user_id,name").execute()
    )
    return _first(result) or payload


def _queue_overlay_note_created_event(supabase: Any, user_id: str, note: dict) -> None:
    """Notify connected external brains about a new personal overlay note."""
    note_id = str(note.get("id") or "").strip()
    source_refs = note.get("source_refs") if isinstance(note.get("source_refs"), list) else []
    try:
        queue_brain_sync_event(
            supabase,
            user_id,
            "overlay.note.created",
            payload={
                "noteId": note_id or None,
                "contentPreview": _truncate_text(note.get("content"), 600),
                "tags": note.get("tags") if isinstance(note.get("tags"), list) else [],
                "sourceRefs": source_refs[:5],
                "createdBy": note.get("created_by") or "agent",
                "createdByClient": note.get("created_by_client"),
            },
            source_ref={"type": "agent_note", "id": note_id} if note_id else {},
            metadata={"trigger": "overlay.note.created"},
            idempotency_key=f"overlay.note.created:{note_id}" if note_id else None,
        )
    except Exception as exc:  # noqa: BLE001 - outbound sync must never block overlay writes.
        print(f"[BRAIN_SYNC] Failed to queue overlay note event: {exc}")


def _query_terms(query: str) -> list[str]:
    return [term for term in re.findall(r"[a-zA-Z0-9_+#.-]+", query.lower()) if len(term) >= 3]


def _row_matches_terms(row: dict, terms: list[str], fields: list[str]) -> bool:
    if not terms:
        return True
    haystack = " ".join(str(row.get(field, "")) for field in fields).lower()
    return any(term in haystack for term in terms)


def _row_term_score(row: dict, terms: list[str], fields: list[str]) -> float:
    if not terms:
        return 0.0
    haystack = " ".join(str(row.get(field, "")) for field in fields).lower()
    matches = sum(1 for term in terms if term in haystack)
    return round(matches / max(len(terms), 1), 3)


def _query_focused_excerpt(value: Any, terms: list[str], max_chars: int) -> dict:
    text = _normalize_excerpt_text(value)
    if not text:
        return {
            "excerpt": "",
            "startChar": 0,
            "strategy": "empty",
            "matchedTerms": [],
            "matchedHeadings": [],
        }

    lower = text.lower()
    matched_terms = [term for term in terms if term in lower]
    if not matched_terms:
        return {
            "excerpt": _truncate_text(text, max_chars),
            "startChar": 0,
            "strategy": "prefix",
            "matchedTerms": [],
            "matchedHeadings": _headings_in_text(text[:max_chars]),
        }

    first_match = min(lower.find(term) for term in matched_terms if lower.find(term) >= 0)
    heading_start = _nearest_heading_start(text, first_match)
    if heading_start is not None and first_match - heading_start <= max_chars // 2:
        start = heading_start
        strategy = "matched_heading"
    else:
        start = max(0, first_match - max_chars // 3)
        strategy = "matched_terms"

    excerpt = text[start : start + max_chars].strip()
    return {
        "excerpt": excerpt,
        "startChar": start,
        "strategy": strategy,
        "matchedTerms": matched_terms[:8],
        "matchedHeadings": _headings_in_text(excerpt),
    }


def _nearest_heading_start(text: str, char_index: int) -> int | None:
    heading_matches = list(re.finditer(r"(?:^|\n)#{1,4}\s+.+", text[: char_index + 1]))
    if not heading_matches:
        return None
    return heading_matches[-1].start()


def _headings_in_text(text: str) -> list[str]:
    headings = []
    for match in re.finditer(r"(?:^|\n)#{1,4}\s+(.+?)(?=\n|$)", text):
        heading = _truncate_text(match.group(1), 120)
        if heading:
            headings.append(heading)
    return headings[:5]


def _normalize_excerpt_text(value: Any) -> str:
    if value is None:
        return ""
    lines = [" ".join(line.split()) for line in str(value).splitlines()]
    text = "\n".join(line for line in lines if line).strip()
    return re.sub(r"\n{3,}", "\n\n", text)


def _truncate_text(value: Any, max_chars: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 1].rstrip()}…"


def _clean_optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def normalize_detail_level(value: Any = None) -> str:
    if value is None:
        return "compact"
    if not isinstance(value, str):
        return "compact"
    normalized = value.strip().lower()
    return normalized if normalized in DETAIL_LEVEL_BUDGETS else "compact"


def response_char_budget(
    detail_level: str,
    max_chars: Any = None,
    max_context_tokens: Any = None,
) -> int:
    budget = DETAIL_LEVEL_BUDGETS[normalize_detail_level(detail_level)]["default_max_chars"]
    if isinstance(max_context_tokens, int) and not isinstance(max_context_tokens, bool):
        budget = min(budget, max_context_tokens * 4)
    if isinstance(max_chars, int) and not isinstance(max_chars, bool):
        budget = min(budget, max_chars)
    return max(1000, min(30000, budget))


def _estimated_json_chars(payload: dict) -> int:
    return len(json.dumps(payload, ensure_ascii=False, default=str))


def _fit_results_to_budget(payload: dict, results_key: str, max_chars: int) -> dict:
    payload["retrievalBudget"]["estimatedResponseChars"] = _estimated_json_chars(payload)
    payload["retrievalBudget"]["truncatedToBudget"] = False
    results = payload.get(results_key)
    if not isinstance(results, list):
        return payload

    while len(results) > 1 and payload["retrievalBudget"]["estimatedResponseChars"] > max_chars:
        results.pop()
        payload["retrievalBudget"]["truncatedToBudget"] = True
        payload["retrievalBudget"]["estimatedResponseChars"] = _estimated_json_chars(payload)
    if payload["retrievalBudget"]["estimatedResponseChars"] > max_chars:
        payload["retrievalBudget"]["truncatedToBudget"] = True

    payload["retrievalBudget"]["returnedResults"] = len(results)
    return payload


def _normalize_brain_digest_objects(objects: list[str] | None) -> set[str]:
    if not objects:
        return set(DEFAULT_BRAIN_DIGEST_OBJECTS)
    normalized = {
        str(item).strip().lower().replace("-", "_") for item in objects if str(item).strip()
    }
    selected = normalized & BRAIN_DIGEST_OBJECTS
    return selected or set(DEFAULT_BRAIN_DIGEST_OBJECTS)


def _encode_brain_digest_cursor(state: dict) -> str:
    raw = json.dumps(state, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
    return urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_brain_digest_cursor(cursor: str | None) -> dict:
    if not isinstance(cursor, str) or not cursor.strip():
        return {}
    try:
        padded = cursor.strip() + ("=" * (-len(cursor.strip()) % 4))
        decoded = urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        parsed = json.loads(decoded)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _row_timestamp(row: dict, keys: list[str] | None = None) -> str:
    for key in keys or ["updated_at", "indexedAt", "indexed_at", "created_at"]:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _row_changed_after(row: dict, since: str | None, keys: list[str] | None = None) -> bool:
    if not since:
        return True
    timestamp = _row_timestamp(row, keys)
    return not timestamp or timestamp > since


def _latest_row_timestamp(rows: list[dict]) -> str | None:
    timestamps = [_row_timestamp(row) for row in rows]
    timestamps = [timestamp for timestamp in timestamps if timestamp]
    return max(timestamps) if timestamps else None


def _channel_map(supabase: Any, videos: list[dict]) -> dict[str, dict]:
    channel_ids = sorted(
        {
            video.get("channel_id")
            for video in videos
            if isinstance(video.get("channel_id"), str) and video.get("channel_id")
        }
    )
    if not channel_ids:
        return {}
    rows = _rows(
        supabase.table("channels")
        .select("id, name, youtube_handle")
        .in_("id", channel_ids)
        .execute()
    )
    return {row.get("id"): row for row in rows if row.get("id")}


def _digest_video(video: dict, channel_by_id: dict[str, dict]) -> dict:
    channel = channel_by_id.get(video.get("channel_id"), {})
    return {
        "id": video.get("id"),
        "objectType": "video",
        "videoId": video.get("youtube_video_id") or video.get("videoId"),
        "title": video.get("title", ""),
        "youtubeUrl": (
            f"https://www.youtube.com/watch?v={video.get('youtube_video_id')}"
            if video.get("youtube_video_id")
            else None
        ),
        "thumbnailUrl": video.get("thumbnail_url", ""),
        "transcriptSeconds": video.get("transcript_seconds", 0),
        "indexedAt": video.get("indexed_at") or video.get("indexedAt"),
        "channel": {
            "id": video.get("channel_id"),
            "name": channel.get("name") or "Unknown channel",
            "youtubeHandle": channel.get("youtube_handle"),
        },
        **video.get("access", {}),
    }


def _source_refs(row: dict, limit: int) -> list[dict]:
    refs = row.get("source_refs")
    if not isinstance(refs, list):
        refs = row.get("sourceRefs")
    return refs[:limit] if isinstance(refs, list) else []


def _source_refs_with_snippets(
    row: dict,
    limit: int,
    video: dict,
    chunks_by_video_id: dict[str, list[dict]],
) -> list[dict]:
    refs = [dict(ref) for ref in _source_refs(row, limit) if isinstance(ref, dict)]
    video_id = video.get("id")
    youtube_video_id = video.get("videoId")
    chunks = chunks_by_video_id.get(video_id, []) if video_id else []
    for ref in refs:
        if not ref.get("youtube_video_id") and youtube_video_id:
            ref["youtube_video_id"] = youtube_video_id
        if ref.get("quote"):
            continue
        quote = _source_ref_quote(ref, chunks)
        if quote:
            ref["quote"] = quote
    return refs


def _source_ref_quote(ref: dict, chunks: list[dict]) -> str:
    start = ref.get("start_seconds")
    if not isinstance(start, (int, float)) or isinstance(start, bool):
        return ""
    for chunk in chunks:
        chunk_start = chunk.get("start_seconds")
        chunk_end = chunk.get("end_seconds")
        if not isinstance(chunk_start, (int, float)) or isinstance(chunk_start, bool):
            continue
        if not isinstance(chunk_end, (int, float)) or isinstance(chunk_end, bool):
            chunk_end = chunk_start
        if int(chunk_start) <= int(start) <= int(chunk_end):
            return _truncate_text(chunk.get("content"), 260)
    return ""


def _digest_video_ref(video: dict | None) -> dict:
    video = video or {}
    return {
        "id": video.get("id"),
        "videoId": video.get("videoId"),
        "title": video.get("title", ""),
        "accessScope": video.get("accessScope"),
        "accessSource": video.get("accessSource"),
        "accessReason": video.get("accessReason"),
    }


def _digest_label(label: dict, video_by_id: dict[str, dict]) -> dict:
    video = video_by_id.get(label.get("video_id"), {})
    return {
        "id": label.get("id"),
        "objectType": "source_label",
        "labelType": label.get("label_type"),
        "label": label.get("label"),
        "confidence": label.get("confidence"),
        "video": _digest_video_ref(video),
        "sourceRefs": _source_refs(label, 3),
        "created_at": label.get("created_at"),
        "updated_at": label.get("updated_at") or label.get("created_at"),
    }


def _digest_concept(concept: dict, video_by_id: dict[str, dict], detail_level: str) -> dict:
    budget = DETAIL_LEVEL_BUDGETS[normalize_detail_level(detail_level)]
    video = video_by_id.get(concept.get("video_id"), {})
    return {
        "id": concept.get("id"),
        "objectType": "source_concept",
        "conceptType": concept.get("concept_type"),
        "name": concept.get("name", ""),
        "summary": _truncate_text(concept.get("summary", ""), budget["concept_summary_chars"]),
        "video": _digest_video_ref(video),
        "sourceRefs": _source_refs(concept, budget["source_ref_limit"]),
        "updated_at": concept.get("updated_at"),
    }


def _digest_artifact(artifact: dict, video_by_id: dict[str, dict], detail_level: str) -> dict:
    budget = DETAIL_LEVEL_BUDGETS[normalize_detail_level(detail_level)]
    video = video_by_id.get(artifact.get("video_id"), {})
    return {
        "id": artifact.get("id"),
        "objectType": "knowledge_artifact",
        "artifactType": artifact.get("artifact_type"),
        "title": artifact.get("title", ""),
        "summary": _truncate_text(artifact.get("summary", ""), budget["artifact_summary_chars"]),
        "contentExcerpt": _truncate_text(
            artifact.get("content", ""), budget["artifact_excerpt_chars"]
        ),
        "video": _digest_video_ref(video),
        "sourceRefs": _source_refs(artifact, budget["source_ref_limit"]),
        "updated_at": artifact.get("updated_at"),
    }


def _digest_note(note: dict, detail_level: str) -> dict:
    budget = DETAIL_LEVEL_BUDGETS[normalize_detail_level(detail_level)]
    return {
        "id": note.get("id"),
        "objectType": "agent_note",
        "content": _truncate_text(note.get("content", ""), budget["artifact_excerpt_chars"]),
        "tags": note.get("tags", []) if isinstance(note.get("tags"), list) else [],
        "sourceRefs": _source_refs(note, budget["source_ref_limit"]),
        "createdBy": note.get("created_by"),
        "createdByClient": note.get("created_by_client"),
        "created_at": note.get("created_at"),
        "updated_at": note.get("updated_at") or note.get("created_at"),
    }


def _digest_personal_concept(concept: dict, detail_level: str) -> dict:
    budget = DETAIL_LEVEL_BUDGETS[normalize_detail_level(detail_level)]
    return {
        "id": concept.get("id"),
        "objectType": "personal_concept",
        "name": concept.get("name", ""),
        "summary": _truncate_text(concept.get("summary", ""), budget["concept_summary_chars"]),
        "status": concept.get("status", "active"),
        "sourceRefs": _source_refs(concept, budget["source_ref_limit"]),
        "updated_at": concept.get("updated_at"),
    }


def build_library_source_graph(
    supabase: Any,
    user_id: str,
    limit: int = 50,
    *,
    include_artifact_content: bool = True,
    include_auxiliary_nodes: bool = True,
    include_review_flags: bool = True,
    project_id: str | None = None,
    project_slug: str | None = None,
) -> dict:
    """Return a user-scoped graph snapshot for library source inspection."""
    normalized_limit = max(1, min(limit, 100))
    project_scope = _resolve_optional_project_scope(supabase, user_id, project_id, project_slug)
    videos = _user_video_rows(
        supabase,
        user_id,
        normalized_limit,
        scope_video_ids=project_scope.get("videoIds") if project_scope else None,
    )
    channel_by_id = _channel_map(supabase, videos)
    video_by_id = {
        video.get("id"): _digest_video(video, channel_by_id) for video in videos if video.get("id")
    }
    rows = _library_component_rows(
        supabase,
        user_id,
        videos,
        normalized_limit,
        include_auxiliary=include_auxiliary_nodes,
    )
    graph = _build_source_graph_nodes(
        video_by_id,
        channel_by_id,
        rows,
        include_artifact_content=include_artifact_content,
        include_auxiliary_nodes=include_auxiliary_nodes,
    )
    review_flags = _library_review_flags(video_by_id, rows) if include_review_flags else []

    return {
        "version": "memexai-library-source-graph-v1",
        "limit": normalized_limit,
        "accessModel": {
            "scope": "current_user_grants",
            "visibilityGrants": ["user_videos", "user_channels"],
            "sourceTruth": "read_only",
            "provenanceFields": ["accessScope", "accessSource", "accessReason"],
        },
        "projectScope": _project_scope_response(project_scope),
        "videos": list(video_by_id.values()),
        "componentCounts": {
            "videos": len(video_by_id),
            "channels": len(channel_by_id),
            "sourceLabels": len(rows["source_labels"]),
            "sourceConcepts": len(rows["source_concepts"]),
            "sourceEdges": len(rows["source_edges"]),
            "knowledgeArtifacts": len(rows["knowledge_artifacts"]),
            "transcriptChunksSampled": len(rows["transcript_chunks"]),
            "agentNotes": len(rows["agent_notes"]),
            "personalConcepts": len(rows["personal_concepts"]),
            "reviewFlags": len(review_flags),
        },
        "graph": graph,
        "reviewFlags": review_flags,
        "edgeCaseHandling": _library_edge_case_handling(),
        "guidance": (
            "Use this graph to inspect the exact source components available to agents. "
            "Search is exact keyword/component search and does not embed, call an LLM, "
            "or merge conflicting claims into a single truth."
        ),
    }


def search_library_components(
    supabase: Any,
    user_id: str,
    query: str,
    limit: int = 20,
    component_types: list[str] | None = None,
    project_id: str | None = None,
    project_slug: str | None = None,
) -> dict:
    """Search graph components with deterministic keyword matching only."""
    normalized_query = " ".join(str(query or "").split())
    normalized_limit = max(1, min(limit, 50))
    selected_types = _normalize_component_types(component_types)
    project_scope = _resolve_optional_project_scope(supabase, user_id, project_id, project_slug)
    terms = _library_search_terms(normalized_query)
    if not normalized_query or not terms:
        return _empty_library_component_search(
            normalized_query,
            normalized_limit,
            selected_types,
            project_scope,
        )

    videos = _user_video_rows(
        supabase,
        user_id,
        max(normalized_limit * 3, normalized_limit),
        scope_video_ids=project_scope.get("videoIds") if project_scope else None,
    )
    channel_by_id = _channel_map(supabase, videos)
    video_by_id = {
        video.get("id"): _digest_video(video, channel_by_id) for video in videos if video.get("id")
    }
    rows = _library_component_rows(supabase, user_id, videos, normalized_limit)

    results: list[dict] = []
    for video in video_by_id.values():
        video_id = str(video.get("videoId") or "")
        channel_name = str(video.get("channel", {}).get("name") or "")
        video_summary = " ".join(
            item
            for item in [
                channel_name,
                video_id,
                video.get("youtubeUrl"),
            ]
            if item
        )
        _append_component_result(
            results,
            selected_types,
            "video",
            video.get("id"),
            "video_metadata",
            video.get("title", ""),
            video_summary,
            video,
            [],
            terms,
            ["title", "summary"],
            metadata={"youtubeVideoId": video_id, "youtubeUrl": video.get("youtubeUrl")},
        )

    for label in rows["source_labels"]:
        video = video_by_id.get(label.get("video_id"), {})
        _append_component_result(
            results,
            selected_types,
            "source_label",
            label.get("id"),
            "label_keyword",
            f"{label.get('label_type', 'label')}: {label.get('label', '')}",
            f"Confidence: {label.get('confidence')}",
            video,
            _source_refs(label, 5),
            terms,
            ["title", "summary"],
            metadata={"labelType": label.get("label_type"), "confidence": label.get("confidence")},
        )

    for concept in rows["source_concepts"]:
        video = video_by_id.get(concept.get("video_id"), {})
        _append_component_result(
            results,
            selected_types,
            "source_concept",
            concept.get("id"),
            "concept_keyword",
            concept.get("name", ""),
            concept.get("summary", ""),
            video,
            _source_refs(concept, 5),
            terms,
            ["title", "summary"],
            metadata={"conceptType": concept.get("concept_type")},
        )

    for edge in rows["source_edges"]:
        video = video_by_id.get(edge.get("video_id"), {})
        title = _edge_title(edge)
        summary = f"Relation: {edge.get('relation', 'related_to')}"
        _append_component_result(
            results,
            selected_types,
            "source_edge",
            edge.get("id"),
            "edge_keyword",
            title,
            summary,
            video,
            _edge_refs(edge, 5),
            terms,
            ["title", "summary"],
            metadata={"relation": edge.get("relation")},
        )

    for artifact in rows["knowledge_artifacts"]:
        video = video_by_id.get(artifact.get("video_id"), {})
        _append_component_result(
            results,
            selected_types,
            "knowledge_artifact",
            artifact.get("id"),
            "artifact_keyword",
            artifact.get("title", ""),
            " ".join(
                [
                    str(artifact.get("summary", "")),
                    _truncate_text(artifact.get("content", ""), 900),
                ]
            ),
            video,
            _source_refs(artifact, 5),
            terms,
            ["title", "summary"],
            metadata={"artifactType": artifact.get("artifact_type")},
        )

    for chunk in rows["transcript_chunks"]:
        video = video_by_id.get(chunk.get("video_id"), {})
        youtube_video_id = video.get("videoId")
        source_refs = []
        if youtube_video_id:
            source_refs.append(
                {
                    "source_type": "transcript",
                    "youtube_video_id": youtube_video_id,
                    "start_seconds": chunk.get("start_seconds"),
                    "end_seconds": chunk.get("end_seconds"),
                }
            )
        _append_component_result(
            results,
            selected_types,
            "transcript_chunk",
            chunk.get("id"),
            "transcript_keyword",
            f"{video.get('title', 'Transcript')} @ {chunk.get('start_seconds', 0)}s",
            chunk.get("content", ""),
            video,
            source_refs,
            terms,
            ["title", "summary"],
        )

    for note in rows["agent_notes"]:
        _append_component_result(
            results,
            selected_types,
            "agent_note",
            note.get("id"),
            "note_keyword",
            "Agent note",
            " ".join([str(note.get("content", "")), " ".join(note.get("tags", []) or [])]),
            {},
            _source_refs(note, 5),
            terms,
            ["title", "summary"],
            metadata={"createdByClient": note.get("created_by_client")},
        )

    for concept in rows["personal_concepts"]:
        _append_component_result(
            results,
            selected_types,
            "personal_concept",
            concept.get("id"),
            "personal_concept_keyword",
            concept.get("name", ""),
            concept.get("summary", ""),
            {},
            _source_refs(concept, 5),
            terms,
            ["title", "summary"],
            metadata={"status": concept.get("status")},
        )

    results.sort(
        key=lambda item: (
            -float(item.get("score") or 0),
            _component_type_sort_key(str(item.get("resultType") or "")),
            str(item.get("title") or "").lower(),
        )
    )
    results = results[:normalized_limit]

    return {
        "query": normalized_query,
        "retrievalMode": "component_keyword",
        "results": results,
        "componentTypes": sorted(selected_types),
        "projectScope": _project_scope_response(project_scope),
        "accessModel": {
            "scope": "project" if project_scope else "current_user_grants",
            "embeddingUsed": False,
            "llmAnswerUsed": False,
        },
        "retrievalBudget": {
            "embeddingCalls": 0,
            "llmCalls": 0,
            "maxResults": normalized_limit,
            "searchedVideos": len(video_by_id),
            "returnedResults": len(results),
        },
        "guidance": (
            "Component search is exact keyword matching across video metadata, source "
            "labels, source concepts, source edges, knowledge artifacts, transcript "
            "chunks, and the user's personal overlay."
        ),
    }


def get_library_artifact(supabase: Any, user_id: str, artifact_id: str) -> dict | None:
    """Return one source report/artifact if the user can access its video."""
    normalized_artifact_id = str(artifact_id or "").removeprefix("artifact:").strip()
    if not normalized_artifact_id:
        return None

    artifact = _first(
        supabase.table("knowledge_artifacts")
        .select(
            "id, video_id, artifact_type, title, summary, content, source_refs, "
            "metadata, updated_at"
        )
        .eq("id", normalized_artifact_id)
        .or_(f"user_id.is.null,user_id.eq.{user_id}")
        .maybe_single()
        .execute()
    )
    if not artifact:
        return None

    video = _select_video_by_db_id_for_user(supabase, user_id, artifact.get("video_id"))
    if not video:
        return None

    video_id = video.get("id")
    chunks = _rows(
        supabase.table("chunks")
        .select("id, video_id, content, start_seconds, end_seconds")
        .eq("video_id", video_id)
        .order("start_seconds", desc=False)
        .execute()
    )
    channel_by_id = {video.get("channel_id"): video.get("channel") or {}}
    video_ref = _digest_video(video, channel_by_id)
    content = str(artifact.get("content") or "")
    summary = artifact.get("summary") or _truncate_text(content, 700)
    return {
        "id": f"artifact:{artifact.get('id')}",
        "type": "knowledge_artifact",
        "label": artifact.get("title") or "Artifact",
        "summary": _truncate_text(summary, 900),
        "content": content,
        "video": _digest_video_ref(video_ref),
        "sourceRefs": _source_refs_with_snippets(
            artifact,
            8,
            video_ref,
            {video_id: chunks} if video_id else {},
        ),
        "metadata": {
            "artifactType": artifact.get("artifact_type"),
            "contentChars": len(content),
            **(artifact.get("metadata") or {}),
        },
        "weight": 3,
    }


def _library_component_rows(
    supabase: Any,
    user_id: str,
    videos: list[dict],
    limit: int,
    *,
    include_auxiliary: bool = True,
) -> dict[str, list[dict]]:
    video_ids = [video.get("id") for video in videos if video.get("id")]
    rows: dict[str, list[dict]] = {
        "source_labels": [],
        "source_concepts": [],
        "source_edges": [],
        "knowledge_artifacts": [],
        "transcript_chunks": [],
        "agent_notes": [],
        "personal_concepts": [],
    }
    if video_ids:
        if include_auxiliary:
            rows["source_labels"] = _rows(
                supabase.table("source_labels")
                .select(
                    "id, video_id, label_type, label, confidence, source_refs, metadata, created_at"
                )
                .in_("video_id", video_ids)
                .order("label_type", desc=False)
                .limit(max(limit * 8, limit))
                .execute()
            )
        rows["source_concepts"] = _rows(
            supabase.table("source_concepts")
            .select("id, video_id, concept_type, name, summary, source_refs, metadata, updated_at")
            .in_("video_id", video_ids)
            .order("updated_at", desc=True)
            .limit(max(limit * 4, limit))
            .execute()
        )
        if include_auxiliary:
            rows["source_edges"] = _rows(
                supabase.table("source_edges")
                .select(
                    "id, video_id, relation, from_ref, to_ref, evidence_refs, metadata, created_at"
                )
                .in_("video_id", video_ids)
                .order("created_at", desc=False)
                .limit(max(limit * 4, limit))
                .execute()
            )
        rows["knowledge_artifacts"] = _rows(
            supabase.table("knowledge_artifacts")
            .select(
                "id, video_id, artifact_type, title, summary, content, source_refs, "
                "metadata, updated_at"
            )
            .in_("video_id", video_ids)
            .or_(f"user_id.is.null,user_id.eq.{user_id}")
            .order("updated_at", desc=True)
            .limit(max(limit * 2, limit))
            .execute()
        )
        rows["transcript_chunks"] = _rows(
            supabase.table("chunks")
            .select("id, video_id, content, start_seconds, end_seconds")
            .in_("video_id", video_ids)
            .order("start_seconds", desc=False)
            .limit(max(limit * 6, limit))
            .execute()
        )

    if include_auxiliary:
        rows["agent_notes"] = _rows(
            supabase.table("agent_notes")
            .select("id, content, source_refs, tags, created_by_client, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(min(max(limit, 10), 50))
            .execute()
        )
        rows["personal_concepts"] = _rows(
            supabase.table("personal_concepts")
            .select("id, name, summary, status, source_refs, updated_at")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .limit(min(max(limit, 10), 50))
            .execute()
        )
    return rows


def _build_source_graph_nodes(
    video_by_id: dict[str, dict],
    channel_by_id: dict[str, dict],
    rows: dict[str, list[dict]],
    *,
    include_artifact_content: bool = True,
    include_auxiliary_nodes: bool = True,
) -> dict:
    nodes: list[dict] = []
    edges: list[dict] = []
    node_ids = set()

    def add_node(node: dict) -> None:
        node_id = str(node.get("id") or "")
        if not node_id or node_id in node_ids:
            return
        node_ids.add(node_id)
        nodes.append(node)

    def add_edge(edge: dict) -> None:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source and target and source in node_ids and target in node_ids:
            edges.append(edge)

    chunks_by_video_id: dict[str, list[dict]] = {}
    for chunk in rows["transcript_chunks"]:
        video_id = chunk.get("video_id")
        if isinstance(video_id, str):
            chunks_by_video_id.setdefault(video_id, []).append(chunk)

    if include_auxiliary_nodes:
        for channel_id, channel in channel_by_id.items():
            add_node(
                {
                    "id": f"channel:{channel_id}",
                    "type": "channel",
                    "label": channel.get("name") or "Unknown channel",
                    "summary": channel.get("youtube_handle") or "",
                    "weight": 2,
                }
            )

    for video in video_by_id.values():
        video_node_id = _video_node_id(video)
        add_node(
            {
                "id": video_node_id,
                "type": "video",
                "label": video.get("title") or video.get("videoId"),
                "summary": video.get("channel", {}).get("name", ""),
                "thumbnailUrl": video.get("thumbnailUrl"),
                "video": video,
                "weight": 4,
            }
        )
        channel_id = video.get("channel", {}).get("id")
        if include_auxiliary_nodes and channel_id:
            add_edge(
                {
                    "id": f"channel:{channel_id}->video:{video.get('videoId')}",
                    "source": f"channel:{channel_id}",
                    "target": video_node_id,
                    "relation": "contains",
                }
            )

    concept_node_by_key = {}
    for concept in rows["source_concepts"]:
        video = video_by_id.get(concept.get("video_id"), {})
        node_id = f"concept:{concept.get('id')}"
        concept_node_by_key[
            (concept.get("video_id"), _normalize_component_key(concept.get("name")))
        ] = node_id
        add_node(
            {
                "id": node_id,
                "type": "source_concept",
                "label": concept.get("name") or "Concept",
                "summary": _truncate_text(concept.get("summary"), 700),
                "video": _digest_video_ref(video),
                "sourceRefs": _source_refs_with_snippets(
                    concept,
                    3,
                    video,
                    chunks_by_video_id,
                ),
                "metadata": {"conceptType": concept.get("concept_type")},
                "weight": 3,
            }
        )
        add_edge(
            {
                "id": f"{_video_node_id(video)}->{node_id}",
                "source": _video_node_id(video),
                "target": node_id,
                "relation": "extracts",
            }
        )

    if include_auxiliary_nodes:
        for label in rows["source_labels"]:
            video = video_by_id.get(label.get("video_id"), {})
            node_id = (
                "label:"
                f"{_normalize_component_key(label.get('label_type'))}:"
                f"{_normalize_component_key(label.get('label'))}"
            )
            add_node(
                {
                    "id": node_id,
                    "type": "source_label",
                    "label": label.get("label") or "Label",
                    "summary": label.get("label_type") or "",
                    "sourceRefs": _source_refs(label, 3),
                    "metadata": {
                        "labelType": label.get("label_type"),
                        "confidence": label.get("confidence"),
                    },
                    "weight": 2,
                }
            )
            add_edge(
                {
                    "id": f"{_video_node_id(video)}->{node_id}",
                    "source": _video_node_id(video),
                    "target": node_id,
                    "relation": "tagged",
                }
            )

        for edge in rows["source_edges"]:
            from_node = concept_node_by_key.get(
                (
                    edge.get("video_id"),
                    _normalize_component_key(_named_ref_name(edge.get("from_ref"))),
                )
            )
            to_node = concept_node_by_key.get(
                (
                    edge.get("video_id"),
                    _normalize_component_key(_named_ref_name(edge.get("to_ref"))),
                )
            )
            if from_node and to_node:
                add_edge(
                    {
                        "id": f"source-edge:{edge.get('id')}",
                        "source": from_node,
                        "target": to_node,
                        "relation": edge.get("relation") or "related_to",
                        "sourceRefs": _edge_refs(edge, 3),
                    }
                )

    for artifact in rows["knowledge_artifacts"]:
        video = video_by_id.get(artifact.get("video_id"), {})
        node_id = f"artifact:{artifact.get('id')}"
        content = str(artifact.get("content") or "")
        summary = artifact.get("summary") or _truncate_text(content, 700)
        add_node(
            {
                "id": node_id,
                "type": "knowledge_artifact",
                "label": artifact.get("title") or "Artifact",
                "summary": _truncate_text(summary, 900),
                "video": _digest_video_ref(video),
                "sourceRefs": _source_refs_with_snippets(
                    artifact,
                    5,
                    video,
                    chunks_by_video_id,
                ),
                "metadata": {
                    "artifactType": artifact.get("artifact_type"),
                    "contentChars": len(content),
                },
                "weight": 3,
            }
            | ({"content": content} if include_artifact_content else {})
        )
        add_edge(
            {
                "id": f"{_video_node_id(video)}->{node_id}",
                "source": _video_node_id(video),
                "target": node_id,
                "relation": "generates",
            }
        )

    if include_auxiliary_nodes:
        for chunk in rows["transcript_chunks"][:60]:
            video = video_by_id.get(chunk.get("video_id"), {})
            node_id = f"chunk:{chunk.get('id')}"
            add_node(
                {
                    "id": node_id,
                    "type": "transcript_chunk",
                    "label": f"{chunk.get('start_seconds', 0)}s transcript",
                    "summary": _truncate_text(chunk.get("content"), 180),
                    "video": _digest_video_ref(video),
                    "weight": 1,
                }
            )
            add_edge(
                {
                    "id": f"{_video_node_id(video)}->{node_id}",
                    "source": _video_node_id(video),
                    "target": node_id,
                    "relation": "has_chunk",
                }
            )

        for note in rows["agent_notes"]:
            node_id = f"note:{note.get('id')}"
            add_node(
                {
                    "id": node_id,
                    "type": "agent_note",
                    "label": "Agent note",
                    "summary": _truncate_text(note.get("content"), 220),
                    "sourceRefs": _source_refs(note, 3),
                    "metadata": {"createdByClient": note.get("created_by_client")},
                    "weight": 2,
                }
            )
            _connect_source_refs_to_node(
                edges, node_ids, video_by_id, _source_refs(note, 10), node_id
            )

        for concept in rows["personal_concepts"]:
            node_id = f"personal:{concept.get('id')}"
            add_node(
                {
                    "id": node_id,
                    "type": "personal_concept",
                    "label": concept.get("name") or "Personal concept",
                    "summary": _truncate_text(concept.get("summary"), 220),
                    "sourceRefs": _source_refs(concept, 3),
                    "metadata": {"status": concept.get("status")},
                    "weight": 2,
                }
            )
            _connect_source_refs_to_node(
                edges, node_ids, video_by_id, _source_refs(concept, 10), node_id
            )

    return {
        "nodes": nodes,
        "edges": edges,
        "selectedNodeId": nodes[0]["id"] if nodes else None,
    }


def _connect_source_refs_to_node(
    edges: list[dict],
    node_ids: set[str],
    video_by_id: dict[str, dict],
    source_refs: list[dict],
    target_node_id: str,
) -> None:
    for ref in source_refs:
        youtube_video_id = ref.get("youtube_video_id") or ref.get("source_id")
        if not youtube_video_id:
            continue
        video_node_id = f"video:{youtube_video_id}"
        if video_node_id not in node_ids:
            continue
        edges.append(
            {
                "id": f"{video_node_id}->{target_node_id}",
                "source": video_node_id,
                "target": target_node_id,
                "relation": "cited_by",
            }
        )


def _library_review_flags(video_by_id: dict[str, dict], rows: dict[str, list[dict]]) -> list[dict]:
    flags: list[dict] = []
    counts_by_video: dict[str, dict[str, int]] = {
        video_id: {
            "sourceLabels": 0,
            "sourceConcepts": 0,
            "sourceEdges": 0,
            "knowledgeArtifacts": 0,
            "transcriptChunks": 0,
        }
        for video_id in video_by_id
    }
    for key, count_key in [
        ("source_labels", "sourceLabels"),
        ("source_concepts", "sourceConcepts"),
        ("source_edges", "sourceEdges"),
        ("knowledge_artifacts", "knowledgeArtifacts"),
        ("transcript_chunks", "transcriptChunks"),
    ]:
        for row in rows[key]:
            video_id = row.get("video_id")
            if video_id in counts_by_video:
                counts_by_video[video_id][count_key] += 1

    for video_id, video in video_by_id.items():
        counts = counts_by_video.get(video_id, {})
        if not video.get("thumbnailUrl"):
            flags.append(_review_flag("missing_thumbnail", "warning", video, "Missing thumbnail"))
        if not video.get("indexedAt"):
            flags.append(_review_flag("stale_metadata", "review", video, "Missing indexed date"))
        if int(video.get("transcriptSeconds") or 0) <= 0 or counts.get("transcriptChunks", 0) == 0:
            flags.append(
                _review_flag(
                    "missing_transcript",
                    "blocking",
                    video,
                    "No sampled transcript chunks were found",
                )
            )
        if (
            counts.get("sourceLabels", 0)
            + counts.get("sourceConcepts", 0)
            + counts.get("knowledgeArtifacts", 0)
            == 0
        ):
            flags.append(
                _review_flag(
                    "missing_source_knowledge",
                    "warning",
                    video,
                    "No source labels, concepts, or artifacts found",
                )
            )
        if video.get("accessScope") == "channel_and_video":
            flags.append(
                _review_flag(
                    "duplicate_access_grant",
                    "info",
                    video,
                    "Visible through both channel and explicit video grants",
                )
            )

    weak_evidence = [
        row
        for row in [
            *rows["source_labels"],
            *rows["source_concepts"],
            *rows["knowledge_artifacts"],
        ]
        if not _source_refs(row, 1)
    ]
    if weak_evidence:
        flags.append(
            {
                "id": "weak-evidence-refs",
                "type": "weak_evidence_refs",
                "severity": "review",
                "title": "Some source components lack timestamp refs",
                "message": (
                    f"{len(weak_evidence)} labels, concepts, or artifacts need source-ref review."
                ),
                "count": len(weak_evidence),
                "videoIds": sorted(
                    {
                        video_by_id.get(row.get("video_id"), {}).get("videoId")
                        for row in weak_evidence
                        if video_by_id.get(row.get("video_id"), {}).get("videoId")
                    }
                ),
            }
        )

    flags.extend(
        _potential_conflict_flags(video_by_id, rows["source_concepts"], rows["source_edges"])
    )
    return flags


def _review_flag(flag_type: str, severity: str, video: dict, title: str) -> dict:
    return {
        "id": f"{flag_type}:{video.get('videoId') or video.get('id')}",
        "type": flag_type,
        "severity": severity,
        "title": title,
        "message": title,
        "videoIds": [video.get("videoId")] if video.get("videoId") else [],
        "video": _digest_video_ref(video),
    }


def _potential_conflict_flags(
    video_by_id: dict[str, dict],
    concepts: list[dict],
    edges: list[dict],
) -> list[dict]:
    flags: list[dict] = []
    grouped: dict[str, list[dict]] = {}
    for concept in concepts:
        if concept.get("concept_type") not in {"claim", "concept", "method", "pitfall"}:
            continue
        key = _normalize_component_key(concept.get("name"))
        if not key:
            continue
        grouped.setdefault(key, []).append(concept)

    for key, items in grouped.items():
        video_ids = {
            video_by_id.get(item.get("video_id"), {}).get("videoId")
            for item in items
            if video_by_id.get(item.get("video_id"), {}).get("videoId")
        }
        summaries = {
            _normalize_component_key(_truncate_text(item.get("summary"), 160)) for item in items
        }
        if len(video_ids) > 1 and len(summaries) > 1:
            flags.append(
                {
                    "id": f"potential-conflict:{key}",
                    "type": "potential_conflict",
                    "severity": "review",
                    "title": f"Review cross-video claim: {items[0].get('name')}",
                    "message": (
                        "Multiple videos contain this claim/concept with different summaries. "
                        "Keep the competing source refs visible before using it in an agent answer."
                    ),
                    "videoIds": sorted(video_ids),
                    "sourceRefs": [ref for item in items for ref in _source_refs(item, 2)][:6],
                }
            )

    contrast_edges = [edge for edge in edges if edge.get("relation") == "contrasts_with"]
    if contrast_edges:
        flags.append(
            {
                "id": "contrast-edges",
                "type": "potential_conflict",
                "severity": "review",
                "title": "Contrasting source edges present",
                "message": (
                    f"{len(contrast_edges)} graph edge"
                    f"{'' if len(contrast_edges) == 1 else 's'} explicitly contrast concepts."
                ),
                "count": len(contrast_edges),
                "sourceRefs": [ref for edge in contrast_edges for ref in _edge_refs(edge, 2)][:6],
            }
        )
    return flags


def _library_edge_case_handling() -> list[dict]:
    return [
        {
            "edgeCase": "Conflicting information between videos",
            "handling": (
                "Memexai preserves source-specific claims and citations instead of merging "
                "them into one truth. The library flags repeated claim names across videos "
                "and explicit contrasts for human review."
            ),
        },
        {
            "edgeCase": "Already-indexed duplicate videos",
            "handling": (
                "Canonical video rows and embeddings are reused; user_videos grants make "
                "the video visible to the current user without exposing a global corpus."
            ),
        },
        {
            "edgeCase": "Missing captions or failed digestion",
            "handling": (
                "The review surface flags videos without transcript chunks or source "
                "knowledge so the user can re-ingest, lower digest depth, or remove them."
            ),
        },
        {
            "edgeCase": "Weak source refs",
            "handling": (
                "Components without timestamp refs are surfaced as QA issues so agents do "
                "not treat uncited summaries as strong evidence."
            ),
        },
        {
            "edgeCase": "Access ambiguity",
            "handling": (
                "Every video and search hit keeps accessScope/accessSource/accessReason so "
                "agents can explain why a shared canonical source is visible."
            ),
        },
    ]


def _empty_library_component_search(
    query: str,
    limit: int,
    component_types: set[str],
    project_scope: dict | None = None,
) -> dict:
    return {
        "query": query,
        "retrievalMode": "component_keyword",
        "results": [],
        "componentTypes": sorted(component_types),
        "projectScope": _project_scope_response(project_scope),
        "accessModel": {
            "scope": "project" if project_scope else "current_user_grants",
            "embeddingUsed": False,
            "llmAnswerUsed": False,
        },
        "retrievalBudget": {
            "embeddingCalls": 0,
            "llmCalls": 0,
            "maxResults": limit,
            "searchedVideos": 0,
            "returnedResults": 0,
        },
        "guidance": "Enter at least one searchable term to inspect library components.",
    }


def _append_component_result(
    results: list[dict],
    selected_types: set[str],
    result_type: str,
    row_id: Any,
    match_type: str,
    title: str,
    summary: str,
    video: dict,
    source_refs: list[dict],
    terms: list[str],
    fields: list[str],
    metadata: dict | None = None,
) -> None:
    if result_type not in selected_types:
        return
    row = {"title": title, "summary": summary}
    score = _component_term_score(row, terms, fields)
    if score <= 0:
        return
    results.append(
        {
            "id": row_id,
            "resultType": result_type,
            "matchType": match_type,
            "title": title,
            "summary": _truncate_text(summary, 420),
            "matchSnippet": _component_snippet(" ".join([title, summary]), terms),
            "video": _digest_video_ref(video) if video else {},
            "sourceRefs": source_refs,
            "score": score,
            "metadata": metadata or {},
        }
    )


def _normalize_component_types(component_types: list[str] | None) -> set[str]:
    if not component_types:
        return set(LIBRARY_COMPONENT_TYPES)
    normalized = {
        str(item).strip().lower().replace("-", "_") for item in component_types if str(item).strip()
    }
    return normalized & LIBRARY_COMPONENT_TYPES or set(LIBRARY_COMPONENT_TYPES)


def _library_search_terms(query: str) -> list[str]:
    return [term for term in re.findall(r"[a-zA-Z0-9_+#.-]+", query.lower()) if len(term) >= 2]


def _component_term_score(row: dict, terms: list[str], fields: list[str]) -> float:
    haystack = " ".join(str(row.get(field, "")) for field in fields).lower()
    if not haystack:
        return 0.0
    matches = sum(1 for term in terms if term in haystack)
    if matches == 0:
        return 0.0
    density = matches / max(len(terms), 1)
    exact_bonus = 0.25 if " ".join(terms) in haystack else 0
    return round(min(1.0, density + exact_bonus), 3)


def _component_snippet(text: str, terms: list[str], max_chars: int = 260) -> str:
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= max_chars:
        return normalized
    lower = normalized.lower()
    positions = [lower.find(term) for term in terms if lower.find(term) >= 0]
    if not positions:
        return _truncate_text(normalized, max_chars)
    start = max(0, min(positions) - 80)
    end = min(len(normalized), start + max_chars)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(normalized) else ""
    return f"{prefix}{normalized[start:end].strip()}{suffix}"


def _component_type_sort_key(result_type: str) -> int:
    order = [
        "video",
        "source_concept",
        "knowledge_artifact",
        "transcript_chunk",
        "source_label",
        "source_edge",
        "personal_concept",
        "agent_note",
    ]
    return order.index(result_type) if result_type in order else len(order)


def _source_ref_list(value: Any) -> list[dict]:
    return value if isinstance(value, list) else []


def _edge_refs(edge: dict, limit: int) -> list[dict]:
    return _source_ref_list(edge.get("evidence_refs"))[:limit]


def _named_ref_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or "")
    return str(value or "")


def _edge_title(edge: dict) -> str:
    from_name = _named_ref_name(edge.get("from_ref")) or "Source concept"
    to_name = _named_ref_name(edge.get("to_ref")) or "Target concept"
    return f"{from_name} {edge.get('relation') or 'related_to'} {to_name}"


def _normalize_component_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")


def _video_node_id(video: dict) -> str:
    return f"video:{video.get('videoId') or video.get('youtube_video_id') or video.get('id')}"


def _fit_brain_digest_to_budget(payload: dict, max_chars: int) -> dict:
    payload["exportBudget"]["estimatedResponseChars"] = _estimated_json_chars(payload)
    if payload["exportBudget"]["estimatedResponseChars"] <= max_chars:
        return payload

    collections = [
        payload["digest"]["knowledgeArtifacts"],
        payload["digest"]["sourceConcepts"],
        payload["digest"]["sourceLabels"],
        payload["digest"]["agentNotes"],
        payload["digest"]["personalConcepts"],
        payload["digest"]["videos"],
    ]
    while payload["exportBudget"]["estimatedResponseChars"] > max_chars:
        trimmed = False
        for collection in collections:
            if len(collection) > 1:
                collection.pop()
                trimmed = True
                break
        payload["exportBudget"]["truncatedToBudget"] = True
        payload["sync"]["hasMore"] = True
        payload["exportBudget"]["estimatedResponseChars"] = _estimated_json_chars(payload)
        if not trimmed:
            break
    return payload


def _user_video_rows(
    supabase: Any,
    user_id: str,
    limit: int,
    *,
    scope_video_ids: list[str] | None = None,
) -> list[dict]:
    subscriptions = _rows(
        supabase.table("user_channels").select("channel_id").eq("user_id", user_id).execute()
    )
    channel_ids = [row.get("channel_id") for row in subscriptions if row.get("channel_id")]
    explicit_grants = _rows(
        supabase.table("user_videos")
        .select("video_id, access_source")
        .eq("user_id", user_id)
        .execute()
    )
    explicit_video_ids = [row.get("video_id") for row in explicit_grants if row.get("video_id")]
    explicit_grants_by_video_id = {
        row.get("video_id"): row for row in explicit_grants if row.get("video_id")
    }

    videos = []
    seen_video_ids = set()
    scoped_ids = (
        [str(video_id) for video_id in scope_video_ids if video_id]
        if scope_video_ids is not None
        else None
    )

    if scoped_ids is not None:
        if scoped_ids:
            videos.extend(
                _video_rows_with_optional_legacy_owner(
                    lambda columns: (
                        supabase.table("videos")
                        .select(columns)
                        .in_("id", scoped_ids)
                        .order("indexed_at", desc=True)
                        .limit(limit)
                    )
                )
            )
    elif channel_ids:
        videos.extend(
            _video_rows_with_optional_legacy_owner(
                lambda columns: (
                    supabase.table("videos")
                    .select(columns)
                    .in_("channel_id", channel_ids)
                    .order("indexed_at", desc=True)
                    .limit(limit)
                )
            )
        )

    remaining_limit = max(0, limit - len(videos))
    if scoped_ids is None and explicit_video_ids and remaining_limit:
        videos.extend(
            _video_rows_with_optional_legacy_owner(
                lambda columns: (
                    supabase.table("videos")
                    .select(columns)
                    .in_("id", explicit_video_ids)
                    .order("indexed_at", desc=True)
                    .limit(remaining_limit)
                )
            )
        )

    remaining_limit = max(0, limit - len(videos))
    if scoped_ids is None and remaining_limit:
        try:
            videos.extend(
                _rows(
                    supabase.table("videos")
                    .select(VIDEO_CONTEXT_COLUMNS_WITH_LEGACY_OWNER)
                    .eq("indexed_by", user_id)
                    .order("indexed_at", desc=True)
                    .limit(remaining_limit)
                    .execute()
                )
            )
        except Exception as exc:
            if not _is_missing_legacy_indexed_by_error(exc):
                raise
            print("[WARN] videos.indexed_by unavailable; skipping legacy owner fallback")

    deduped = []
    for video in videos:
        video_id = video.get("id")
        if not video_id or video_id in seen_video_ids:
            continue
        seen_video_ids.add(video_id)
        has_channel_access = video.get("channel_id") in channel_ids
        video_grant = explicit_grants_by_video_id.get(video_id)
        legacy_owner_access = video.get("indexed_by") == user_id
        if scoped_ids is not None and not (
            has_channel_access or video_grant or legacy_owner_access
        ):
            continue
        deduped.append(
            {
                **video,
                "access": _context_access_metadata(
                    has_channel_access,
                    video_grant,
                    legacy_owner_access,
                ),
            }
        )
    return deduped[:limit]


def _list_user_source_context(
    supabase: Any,
    user_id: str,
    query: str,
    limit: int,
    category_filters: dict | None = None,
    project_scope: dict | None = None,
) -> dict:
    """Return source-derived concepts/artifacts from videos the user can access."""
    videos = _user_video_rows(
        supabase,
        user_id,
        max(limit * 4, limit),
        scope_video_ids=project_scope.get("videoIds") if project_scope else None,
    )
    video_ids = [video.get("id") for video in videos if video.get("id")]
    normalized_filters = normalize_category_filters(category_filters)
    if not video_ids:
        return {
            "videos": [],
            "sourceLabels": [],
            "sourceConcepts": [],
            "sourceEdges": [],
            "knowledgeArtifacts": [],
            "categoryFilters": normalized_filters,
            "projectScope": _project_scope_response(project_scope),
        }

    source_labels = _rows(
        supabase.table("source_labels")
        .select("id, video_id, label_type, label, confidence, source_refs, metadata")
        .in_("video_id", video_ids)
        .order("label_type", desc=False)
        .limit(max(limit * 8, limit))
        .execute()
    )
    if normalized_filters:
        labels_by_video_id = _labels_by_video_id(source_labels)
        matching_video_ids = {
            video_id
            for video_id in video_ids
            if labels_match_category_filters(
                labels_by_video_id.get(video_id, []), normalized_filters
            )
        }
        videos = [video for video in videos if video.get("id") in matching_video_ids]
        video_ids = [video.get("id") for video in videos if video.get("id")]
        source_labels = [
            label for label in source_labels if label.get("video_id") in matching_video_ids
        ]

    if not video_ids:
        return {
            "videos": [],
            "sourceLabels": [],
            "sourceConcepts": [],
            "sourceEdges": [],
            "knowledgeArtifacts": [],
            "categoryFilters": normalized_filters,
            "projectScope": _project_scope_response(project_scope),
        }

    terms = _query_terms(query)
    concepts = _rows(
        supabase.table("source_concepts")
        .select("id, video_id, concept_type, name, summary, source_refs, metadata")
        .in_("video_id", video_ids)
        .order("updated_at", desc=True)
        .limit(max(limit * 4, limit))
        .execute()
    )
    artifacts = _rows(
        supabase.table("knowledge_artifacts")
        .select("id, video_id, artifact_type, title, summary, content, source_refs, metadata")
        .in_("video_id", video_ids)
        .or_(f"user_id.is.null,user_id.eq.{user_id}")
        .order("updated_at", desc=True)
        .limit(max(limit * 2, limit))
        .execute()
    )
    edges = _rows(
        supabase.table("source_edges")
        .select("id, video_id, relation, from_ref, to_ref, evidence_refs, metadata")
        .in_("video_id", video_ids)
        .order("created_at", desc=False)
        .limit(max(limit * 4, limit))
        .execute()
    )

    matched_concepts = [
        concept
        for concept in concepts
        if _row_matches_terms(concept, terms, ["name", "summary", "concept_type"])
    ][:limit]
    matched_artifacts = [
        {
            **artifact,
            "content": str(artifact.get("content", ""))[:1500],
        }
        for artifact in artifacts
        if _row_matches_terms(artifact, terms, ["title", "summary", "content", "artifact_type"])
    ][:limit]

    matched_video_ids = {
        item.get("video_id")
        for item in [*matched_concepts, *matched_artifacts]
        if item.get("video_id")
    }
    if not matched_video_ids and not terms:
        matched_video_ids = set(video_ids)

    matched_edges = [
        edge for edge in edges if not matched_video_ids or edge.get("video_id") in matched_video_ids
    ][:limit]
    matched_videos = [
        {
            "id": video.get("id"),
            "videoId": video.get("youtube_video_id"),
            "title": video.get("title"),
            "thumbnailUrl": video.get("thumbnail_url", ""),
            "transcriptSeconds": video.get("transcript_seconds", 0),
            **video.get("access", {}),
        }
        for video in videos
        if not matched_video_ids or video.get("id") in matched_video_ids
    ][:limit]

    return {
        "videos": matched_videos,
        "sourceLabels": source_labels[: max(limit * 2, limit)],
        "sourceConcepts": matched_concepts,
        "sourceEdges": matched_edges,
        "knowledgeArtifacts": matched_artifacts,
        "categoryFilters": normalized_filters,
        "projectScope": _project_scope_response(project_scope),
        "categoryFilterGuidance": (
            "categoryFilters use OR within one facet and AND across facets. "
            "Call list_context_categories when you need available labels."
        ),
    }


def _labels_by_video_id(source_labels: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for label in source_labels:
        video_id = label.get("video_id")
        if not isinstance(video_id, str):
            continue
        grouped.setdefault(video_id, []).append(label)
    return grouped


def search_source_knowledge(
    supabase: Any,
    user_id: str,
    query: str,
    limit: int = 8,
    category_filters: dict | None = None,
    detail_level: str = "compact",
    max_chars: int | None = None,
    max_context_tokens: int | None = None,
    *,
    retrieval_mode: str = "hybrid",
    embedding_provider: Any | None = None,
    project_id: str | None = None,
    project_slug: str | None = None,
) -> dict:
    """Search indexed source knowledge with hybrid retrieval and keyword fallback."""
    normalized_limit = max(1, min(limit, 20))
    normalized_detail = normalize_detail_level(detail_level)
    detail_budget = DETAIL_LEVEL_BUDGETS[normalized_detail]
    effective_max_chars = response_char_budget(normalized_detail, max_chars, max_context_tokens)
    normalized_filters = normalize_category_filters(category_filters)
    normalized_mode = _normalize_source_knowledge_retrieval_mode(retrieval_mode)
    project_scope = _resolve_optional_project_scope(supabase, user_id, project_id, project_slug)
    embedding_calls = 0
    embedding_error = ""
    query_embedding = None
    index_rpc_available = hasattr(supabase, "rpc")
    if normalized_mode != "keyword" and index_rpc_available:
        try:
            query_embedding = _embed_source_query(embedding_provider, query)
            embedding_calls = 1
        except Exception as exc:  # noqa: BLE001 - keyword fallback is intentional.
            embedding_error = str(exc)

    index_rows = _search_source_knowledge_index_rows(
        supabase,
        user_id,
        query,
        normalized_limit,
        normalized_filters,
        normalized_mode,
        query_embedding,
        project_scope.get("id") if project_scope else None,
    )
    use_keyword_empty_fallback = (
        index_rows is not None and not index_rows and normalized_mode == "keyword"
    )
    if index_rows is not None and not use_keyword_empty_fallback:
        terms = _query_terms(query)
        results = [
            _format_source_index_result(row, terms, detail_budget, normalized_detail, query)
            for row in index_rows
        ][:normalized_limit]
        payload = {
            "query": query,
            "retrievalMode": normalized_mode,
            "detailLevel": normalized_detail,
            "categoryFilters": normalized_filters,
            "projectScope": _project_scope_response(project_scope),
            "results": results,
            "retrievalPlan": {
                "primary": (
                    "source_knowledge_index_hybrid_vector_keyword"
                    if normalized_mode == "hybrid"
                    else (
                        "source_knowledge_index_vector"
                        if normalized_mode == "semantic"
                        else "source_knowledge_index_keyword"
                    )
                ),
                "embeddingUsed": embedding_calls > 0,
                "llmAnswerUsed": False,
                "fallbackUsed": False,
                "candidateMultiplier": 4,
                "fallback": (
                    "Use get_video_knowledge_map for a candidate video, then "
                    "search_video_moments for timestamp evidence. Use get_video_context "
                    "with include_transcript=true only when the report/map/clips are insufficient."
                ),
            },
            "retrievalBudget": {
                "embeddingCalls": embedding_calls,
                "llmCalls": 0,
                "maxResults": normalized_limit,
                "maxChars": effective_max_chars,
                "maxContextTokens": max_context_tokens,
            },
            "next_mcp_call": _source_search_next_call(results, query),
            "guidance": _source_knowledge_search_guidance(),
        }
        if embedding_error:
            payload["retrievalPlan"]["embeddingError"] = embedding_error
        return _fit_results_to_budget(payload, "results", effective_max_chars)

    fallback_payload = _search_source_knowledge_keyword_fallback(
        supabase,
        user_id,
        query,
        normalized_limit,
        normalized_filters,
        normalized_detail,
        detail_budget,
        effective_max_chars,
        max_context_tokens,
        project_scope,
    )
    fallback_payload["retrievalMode"] = normalized_mode
    fallback_payload["retrievalPlan"]["fallbackUsed"] = True
    fallback_payload["retrievalPlan"]["fallbackReason"] = (
        "source_knowledge_index keyword search returned no matches; searched legacy source tables."
        if use_keyword_empty_fallback
        else (
            embedding_error
            or "source_knowledge_index RPC unavailable or not yet deployed; searched legacy source tables."
        )
    )
    fallback_payload["retrievalBudget"]["embeddingCalls"] = embedding_calls
    return fallback_payload


def _search_source_knowledge_keyword_fallback(
    supabase: Any,
    user_id: str,
    query: str,
    normalized_limit: int,
    normalized_filters: dict,
    normalized_detail: str,
    detail_budget: dict,
    effective_max_chars: int,
    max_context_tokens: int | None,
    project_scope: dict | None = None,
) -> dict:
    source_context = _list_user_source_context(
        supabase,
        user_id,
        query,
        normalized_limit,
        normalized_filters,
        project_scope,
    )
    video_by_id = {
        video.get("id"): video for video in source_context.get("videos", []) if video.get("id")
    }
    terms = _query_terms(query)

    results = []
    for concept in source_context.get("sourceConcepts", []):
        video = video_by_id.get(concept.get("video_id"), {})
        results.append(
            {
                "id": concept.get("id"),
                "resultType": "source_concept",
                "matchType": "concept_keyword",
                "conceptType": concept.get("concept_type", "concept"),
                "name": concept.get("name", ""),
                "summary": _truncate_text(
                    concept.get("summary", ""),
                    detail_budget["concept_summary_chars"],
                ),
                "video": {
                    "id": video.get("id") or concept.get("video_id"),
                    "videoId": video.get("videoId"),
                    "title": video.get("title", ""),
                    "accessScope": video.get("accessScope"),
                    "accessSource": video.get("accessSource"),
                    "accessReason": video.get("accessReason"),
                },
                "sourceRefs": (
                    concept.get("source_refs", [])
                    if isinstance(concept.get("source_refs"), list)
                    else []
                )[: detail_budget["source_ref_limit"]],
                "score": _row_term_score(
                    concept,
                    terms,
                    ["name", "summary", "concept_type"],
                ),
                "next_mcp_call": _next_call_for_video_knowledge_map(
                    video.get("videoId"),
                    normalized_detail,
                ),
            }
        )

    for artifact in source_context.get("knowledgeArtifacts", []):
        video = video_by_id.get(artifact.get("video_id"), {})
        artifact_focus = _query_focused_excerpt(
            artifact.get("content", ""),
            terms,
            detail_budget["artifact_excerpt_chars"],
        )
        results.append(
            {
                "id": artifact.get("id"),
                "resultType": "knowledge_artifact",
                "matchType": "artifact_keyword",
                "artifactType": artifact.get("artifact_type", ""),
                "title": artifact.get("title", ""),
                "summary": _truncate_text(
                    artifact.get("summary", ""),
                    detail_budget["artifact_summary_chars"],
                ),
                "contentExcerpt": artifact_focus["excerpt"],
                "contentExcerptStart": artifact_focus["startChar"],
                "contentExcerptStrategy": artifact_focus["strategy"],
                "matchedTerms": artifact_focus["matchedTerms"],
                "matchedHeadings": artifact_focus["matchedHeadings"],
                "video": {
                    "id": video.get("id") or artifact.get("video_id"),
                    "videoId": video.get("videoId"),
                    "title": video.get("title", ""),
                    "accessScope": video.get("accessScope"),
                    "accessSource": video.get("accessSource"),
                    "accessReason": video.get("accessReason"),
                },
                "sourceRefs": (
                    artifact.get("source_refs", [])
                    if isinstance(artifact.get("source_refs"), list)
                    else []
                )[: detail_budget["source_ref_limit"]],
                "score": _row_term_score(
                    artifact,
                    terms,
                    ["title", "summary", "content", "artifact_type"],
                ),
                "next_mcp_call": _next_call_for_video_knowledge_map(
                    video.get("videoId"),
                    normalized_detail,
                ),
            }
        )

    results.sort(
        key=lambda item: (
            -float(item.get("score") or 0),
            0 if item.get("resultType") == "source_concept" else 1,
            str(item.get("name") or item.get("title") or "").lower(),
        )
    )
    results = results[:normalized_limit]

    payload = {
        "query": query,
        "retrievalMode": "keyword",
        "detailLevel": normalized_detail,
        "categoryFilters": normalized_filters,
        "projectScope": _project_scope_response(project_scope),
        "results": results,
        "retrievalPlan": {
            "primary": "legacy_source_concepts_and_artifacts_keyword",
            "embeddingUsed": False,
            "llmAnswerUsed": False,
            "fallbackUsed": True,
            "fallback": (
                "Use get_video_knowledge_map for a candidate video, then "
                "search_video_moments with retrieval_mode=hybrid for timestamp evidence."
            ),
        },
        "retrievalBudget": {
            "embeddingCalls": 0,
            "llmCalls": 0,
            "maxResults": normalized_limit,
            "maxChars": effective_max_chars,
            "maxContextTokens": max_context_tokens,
        },
        "next_mcp_call": _source_search_next_call(results, query),
        "guidance": (_source_knowledge_search_guidance()),
    }
    return _fit_results_to_budget(payload, "results", effective_max_chars)


def _normalize_source_knowledge_retrieval_mode(value: Any) -> str:
    normalized = str(value or "hybrid").strip().lower()
    if normalized not in SOURCE_KNOWLEDGE_RETRIEVAL_MODES:
        raise ValueError("retrieval_mode must be one of: hybrid, semantic, keyword")
    return normalized


def _embed_source_query(embedding_provider: Any | None, query: str) -> list[float]:
    if embedding_provider is None:
        raise ValueError("source knowledge embedding provider is not configured")
    if callable(embedding_provider):
        vector = embedding_provider(query)
    elif hasattr(embedding_provider, "embed_query"):
        vector = embedding_provider.embed_query(query)
    else:
        raise ValueError("source knowledge embedding provider is not callable")
    if not isinstance(vector, list) or not vector:
        raise ValueError("source knowledge embedding provider returned an empty vector")
    return vector


def _search_source_knowledge_index_rows(
    supabase: Any,
    user_id: str,
    query: str,
    limit: int,
    category_filters: dict,
    retrieval_mode: str,
    query_embedding: list[float] | None,
    project_id: str | None = None,
) -> list[dict] | None:
    if retrieval_mode in {"hybrid", "semantic"} and query_embedding is None:
        return None
    if not hasattr(supabase, "rpc"):
        return None
    try:
        result = supabase.rpc(
            "search_source_knowledge_hybrid",
            {
                "query_embedding": query_embedding,
                "search_query": query,
                "match_user_id": user_id,
                "match_limit": limit * 4,
                "category_filters": category_filters,
                "retrieval_mode": retrieval_mode,
                "match_project_id": project_id,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001 - local/older DBs fall back to legacy tables.
        print(f"[SOURCE_KNOWLEDGE] Index search unavailable; falling back: {exc}")
        return None
    return _rows(result)


def _format_source_index_result(
    row: dict,
    terms: list[str],
    detail_budget: dict,
    detail_level: str,
    query: str,
) -> dict:
    result_type = str(row.get("source_object_type") or "source_knowledge")
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    title = row.get("title") or ""
    body = row.get("body") or ""
    excerpt_budget = (
        detail_budget["concept_summary_chars"]
        if result_type == "source_concept"
        else detail_budget["artifact_excerpt_chars"]
    )
    focused = _query_focused_excerpt(row.get("headline") or body, terms, excerpt_budget)
    source_refs = _source_refs(row, detail_budget["source_ref_limit"])
    video = {
        "id": row.get("video_id"),
        "videoId": row.get("youtube_video_id"),
        "title": row.get("video_title") or "",
        "channelName": row.get("channel_name") or "",
        "thumbnailUrl": row.get("thumbnail_url") or "",
        "transcriptSeconds": row.get("transcript_seconds") or 0,
        "accessScope": row.get("access_scope"),
        "accessSource": row.get("access_source"),
        "accessReason": row.get("access_reason"),
    }
    base = {
        "id": row.get("id"),
        "resultType": result_type,
        "matchType": row.get("match_type") or "source_knowledge",
        "title": title,
        "summary": _truncate_text(
            metadata.get("summary") or body,
            detail_budget["artifact_summary_chars"],
        ),
        "contentExcerpt": focused["excerpt"],
        "contentExcerptStart": focused["startChar"],
        "contentExcerptStrategy": focused["strategy"],
        "matchedTerms": focused["matchedTerms"],
        "matchedHeadings": focused["matchedHeadings"],
        "aliases": row.get("aliases") if isinstance(row.get("aliases"), list) else [],
        "sourceRefs": source_refs,
        "video": video,
        "score": _source_index_score(row),
        "similarity": row.get("similarity"),
        "keywordRank": row.get("keyword_rank"),
        "hybridScore": row.get("hybrid_score"),
        "metadata": {
            key: value
            for key, value in metadata.items()
            if key
            in {
                "artifactType",
                "conceptType",
                "displayArtifactType",
                "sectionHeading",
                "sectionOrder",
                "indexVersion",
                "embeddingStatus",
            }
        },
        "next_mcp_call": _next_call_for_video_knowledge_map(
            row.get("youtube_video_id"),
            detail_level,
        ),
    }
    if result_type == "source_concept":
        base["name"] = title
        base["conceptType"] = metadata.get("conceptType") or "concept"
        base["summary"] = _truncate_text(body, detail_budget["concept_summary_chars"])
    elif result_type == "knowledge_artifact":
        base["artifactType"] = metadata.get("artifactType") or ""
    elif result_type == "report_section":
        base["sectionKey"] = row.get("section_key") or ""
        base["sectionHeading"] = metadata.get("sectionHeading") or title
    base["next_mcp_call"]["queryHint"] = query
    return base


def _source_index_score(row: dict) -> float:
    for key in ("hybrid_score", "keyword_rank", "similarity"):
        value = row.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return round(float(value), 4)
    return 0.0


def _next_call_for_video_knowledge_map(video_id: Any, detail_level: str = "compact") -> dict:
    return {
        "name": "get_video_knowledge_map",
        "arguments": {
            "youtube_video_id": str(video_id or ""),
            "detail_level": detail_level,
        },
    }


def _source_search_next_call(results: list[dict], query: str) -> dict:
    if results:
        video_id = (results[0].get("video") or {}).get("videoId")
        if video_id:
            return {
                "name": "get_video_knowledge_map",
                "reason": "Inspect the winning video's source-report sections and timestamp-backed objects before pulling transcript clips.",
                "arguments": {"youtube_video_id": video_id, "detail_level": "compact"},
            }
    return {
        "name": "search_video_moments",
        "reason": "No source-knowledge result was returned; fall back to timestamped transcript retrieval.",
        "arguments": {"query": query, "retrieval_mode": "hybrid", "limit": 5},
    }


def _source_knowledge_search_guidance() -> str:
    return (
        "Use this source-knowledge search before transcript retrieval. Results are generated "
        "concepts, TLDRs, source reports, and report sections, not raw transcript chunks. "
        "For a promising video, call get_video_knowledge_map, then search_video_moments for "
        "timestamp evidence. Pull get_video_context/include_transcript only when the map and "
        "clips are insufficient."
    )


def build_video_knowledge_map(
    supabase: Any,
    user_id: str,
    youtube_video_id: str,
    detail_level: str = "compact",
    max_chars: int | None = None,
    max_context_tokens: int | None = None,
    project_id: str | None = None,
    project_slug: str | None = None,
) -> dict:
    """Return a compact navigable table of contents for one saved video."""
    normalized_detail = normalize_detail_level(detail_level)
    detail_budget = DETAIL_LEVEL_BUDGETS[normalized_detail]
    effective_max_chars = response_char_budget(normalized_detail, max_chars, max_context_tokens)
    context = get_video_context(
        supabase,
        user_id,
        youtube_video_id,
        project_id=project_id,
        project_slug=project_slug,
    )
    if not context:
        return {
            "found": False,
            "videoId": youtube_video_id,
            "detailLevel": normalized_detail,
            "guidance": "The requested video is not visible through this user's saved-video grants.",
        }

    video = context["video"]
    index_rows = _source_index_rows_for_video(supabase, video.get("id"))
    section_rows = [row for row in index_rows if row.get("source_object_type") == "report_section"]
    artifact_rows = [
        row for row in index_rows if row.get("source_object_type") == "knowledge_artifact"
    ]
    concept_rows = [row for row in index_rows if row.get("source_object_type") == "source_concept"]

    report_sections = _knowledge_map_sections_from_index(
        section_rows, detail_budget
    ) or _knowledge_map_sections_from_artifacts(
        context.get("knowledgeArtifacts", []),
        detail_budget,
    )
    artifacts = (
        _knowledge_map_artifacts_from_index(artifact_rows, detail_budget)
        or [
            _knowledge_map_artifact(artifact, detail_budget)
            for artifact in context.get("knowledgeArtifacts", [])
        ][:8]
    )
    concepts = (
        _knowledge_map_concepts_from_index(concept_rows, detail_budget)
        or [
            _knowledge_map_concept(concept, detail_budget)
            for concept in context.get("sourceConcepts", [])
        ][:16]
    )
    claims = _knowledge_map_filtered_concepts(concepts, {"claim"})
    people_orgs_tools = _knowledge_map_filtered_concepts(concepts, {"entity", "tool"})
    decisions = _knowledge_map_section_items(report_sections, {"decisions", "decision"})
    timeline = _knowledge_map_timeline(context.get("sourceConcepts", []), report_sections)

    payload = {
        "found": True,
        "version": "memexai-video-knowledge-map-v1",
        "detailLevel": normalized_detail,
        "video": video,
        "projectScope": context.get("projectScope") or _project_scope_response(None),
        "reportSections": report_sections,
        "knowledgeArtifacts": artifacts,
        "coreConcepts": concepts,
        "peopleOrganizationsTools": people_orgs_tools,
        "claims": claims or _knowledge_map_section_items(report_sections, {"claims", "claim"}),
        "decisions": decisions,
        "timeline": timeline,
        "timestampRefs": _knowledge_map_timestamp_refs(concepts, artifacts, report_sections),
        "suggestedFollowUpQueries": _knowledge_map_follow_up_queries(
            video,
            concepts,
            artifacts,
            report_sections,
        ),
        "next_mcp_call": {
            "name": "search_video_moments",
            "reason": "Use timestamped transcript clips to verify a selected map item.",
            "argumentsTemplate": {
                "query": "<topic, claim, section, or tool from this map>",
                "retrieval_mode": "hybrid",
                "limit": 5,
                "project_id": project_id,
                "project_slug": project_slug,
            },
        },
        "fallback_mcp_call": {
            "name": "get_video_context",
            "reason": "Use only when the map and timestamp clips do not contain enough source detail.",
            "arguments": {
                "youtube_video_id": video.get("videoId"),
                "include_transcript": True,
                "detail_level": normalized_detail,
                "project_id": project_id,
                "project_slug": project_slug,
            },
        },
        "retrievalBudget": {
            "embeddingCalls": 0,
            "llmCalls": 0,
            "maxChars": effective_max_chars,
            "maxContextTokens": max_context_tokens,
        },
        "guidance": (
            "Use this map as the video's table of contents. It is designed for agent "
            "navigation: pick a section/concept/timestamp, then call search_video_moments "
            "for evidence instead of reading the full transcript."
        ),
    }
    return _fit_video_knowledge_map_to_budget(payload, effective_max_chars)


def _source_index_rows_for_video(supabase: Any, video_db_id: Any) -> list[dict]:
    if not video_db_id:
        return []
    try:
        return _rows(
            supabase.table("source_knowledge_index")
            .select(
                "id, video_id, source_object_type, source_object_id, section_key, title, "
                "body, aliases, source_refs, metadata, index_version"
            )
            .eq("video_id", video_db_id)
            .order("source_object_type", desc=False)
            .limit(200)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001 - older schemas fall back to artifacts/concepts.
        print(f"[SOURCE_KNOWLEDGE] Knowledge map index unavailable; falling back: {exc}")
        return []


def _knowledge_map_sections_from_index(rows: list[dict], detail_budget: dict) -> list[dict]:
    sections = []
    sorted_rows = sorted(
        rows,
        key=lambda row: (
            _metadata_int(row.get("metadata"), "sectionOrder", 999),
            str(row.get("title") or "").lower(),
        ),
    )
    for row in sorted_rows[:16]:
        sections.append(
            {
                "id": row.get("id"),
                "title": row.get("title", ""),
                "contentExcerpt": _truncate_text(
                    row.get("body", ""),
                    detail_budget["artifact_summary_chars"],
                ),
                "aliases": row.get("aliases") if isinstance(row.get("aliases"), list) else [],
                "sourceRefs": _source_refs(row, detail_budget["source_ref_limit"]),
                "next_mcp_call": {
                    "name": "search_video_moments",
                    "arguments": {
                        "query": row.get("title") or "",
                        "retrieval_mode": "hybrid",
                        "limit": 5,
                    },
                },
            }
        )
    return sections


def _knowledge_map_sections_from_artifacts(
    artifacts: list[dict],
    detail_budget: dict,
) -> list[dict]:
    sections = []
    for artifact in artifacts:
        content = str(artifact.get("content") or "")
        for section in _markdown_sections(content):
            sections.append(
                {
                    "id": f"{artifact.get('id')}:{_component_key(section['title'])}",
                    "title": section["title"],
                    "contentExcerpt": _truncate_text(
                        section["body"],
                        detail_budget["artifact_summary_chars"],
                    ),
                    "sourceRefs": _source_refs(artifact, detail_budget["source_ref_limit"]),
                    "next_mcp_call": {
                        "name": "search_video_moments",
                        "arguments": {
                            "query": section["title"],
                            "retrieval_mode": "hybrid",
                            "limit": 5,
                        },
                    },
                }
            )
            if len(sections) >= 16:
                return sections
    return sections


def _knowledge_map_artifacts_from_index(rows: list[dict], detail_budget: dict) -> list[dict]:
    return [
        {
            "id": row.get("id"),
            "resultType": "knowledge_artifact",
            "title": row.get("title", ""),
            "summary": _truncate_text(
                (row.get("metadata") or {}).get("summary") or row.get("body", ""),
                detail_budget["artifact_summary_chars"],
            ),
            "aliases": row.get("aliases") if isinstance(row.get("aliases"), list) else [],
            "sourceRefs": _source_refs(row, detail_budget["source_ref_limit"]),
        }
        for row in rows[:8]
    ]


def _knowledge_map_artifact(artifact: dict, detail_budget: dict) -> dict:
    return {
        "id": artifact.get("id"),
        "resultType": "knowledge_artifact",
        "title": artifact.get("title", ""),
        "summary": _truncate_text(
            artifact.get("summary") or artifact.get("content", ""),
            detail_budget["artifact_summary_chars"],
        ),
        "sourceRefs": _source_refs(artifact, detail_budget["source_ref_limit"]),
    }


def _knowledge_map_concepts_from_index(rows: list[dict], detail_budget: dict) -> list[dict]:
    concepts = []
    for row in rows[:24]:
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        concepts.append(
            {
                "id": row.get("id"),
                "resultType": "source_concept",
                "name": row.get("title", ""),
                "conceptType": metadata.get("conceptType") or "concept",
                "summary": _truncate_text(
                    row.get("body", ""), detail_budget["concept_summary_chars"]
                ),
                "aliases": row.get("aliases") if isinstance(row.get("aliases"), list) else [],
                "sourceRefs": _source_refs(row, detail_budget["source_ref_limit"]),
                "next_mcp_call": {
                    "name": "search_video_moments",
                    "arguments": {
                        "query": row.get("title") or "",
                        "retrieval_mode": "hybrid",
                        "limit": 5,
                    },
                },
            }
        )
    return concepts


def _knowledge_map_concept(concept: dict, detail_budget: dict) -> dict:
    return {
        "id": concept.get("id"),
        "resultType": "source_concept",
        "name": concept.get("name", ""),
        "conceptType": concept.get("concept_type", "concept"),
        "summary": _truncate_text(
            concept.get("summary", ""), detail_budget["concept_summary_chars"]
        ),
        "sourceRefs": _source_refs(concept, detail_budget["source_ref_limit"]),
        "next_mcp_call": {
            "name": "search_video_moments",
            "arguments": {
                "query": concept.get("name") or "",
                "retrieval_mode": "hybrid",
                "limit": 5,
            },
        },
    }


def _knowledge_map_filtered_concepts(concepts: list[dict], concept_types: set[str]) -> list[dict]:
    return [
        concept
        for concept in concepts
        if str(concept.get("conceptType") or "").lower() in concept_types
    ][:12]


def _knowledge_map_section_items(
    sections: list[dict],
    heading_terms: set[str],
) -> list[dict]:
    items = []
    for section in sections:
        title = str(section.get("title") or "").lower()
        if not any(term in title for term in heading_terms):
            continue
        items.append(section)
    return items[:8]


def _knowledge_map_timeline(
    concepts: list[dict],
    sections: list[dict],
) -> list[dict]:
    timeline = []
    for concept in concepts:
        for ref in _source_refs(concept, 3):
            start = ref.get("start_seconds")
            if isinstance(start, (int, float)) and not isinstance(start, bool):
                timeline.append(
                    {
                        "startSeconds": start,
                        "endSeconds": ref.get("end_seconds"),
                        "title": concept.get("name") or concept.get("title") or "Concept",
                        "sourceRef": ref,
                    }
                )
    for section in sections:
        if "timeline" not in str(section.get("title") or "").lower():
            continue
        for ref in _source_refs(section, 5):
            start = ref.get("start_seconds")
            if isinstance(start, (int, float)) and not isinstance(start, bool):
                timeline.append(
                    {
                        "startSeconds": start,
                        "endSeconds": ref.get("end_seconds"),
                        "title": section.get("title") or "Timeline",
                        "sourceRef": ref,
                    }
                )
    timeline.sort(key=lambda item: item.get("startSeconds") or 0)
    return timeline[:20]


def _knowledge_map_timestamp_refs(
    concepts: list[dict],
    artifacts: list[dict],
    sections: list[dict],
) -> list[dict]:
    refs = []
    seen = set()
    for item in [*concepts, *artifacts, *sections]:
        label = item.get("name") or item.get("title") or item.get("resultType")
        for ref in _source_refs(item, 5):
            key = (
                ref.get("youtube_video_id"),
                ref.get("start_seconds"),
                ref.get("end_seconds"),
                label,
            )
            if key in seen:
                continue
            seen.add(key)
            refs.append({"label": label, **ref})
            if len(refs) >= 24:
                return refs
    return refs


def _knowledge_map_follow_up_queries(
    video: dict,
    concepts: list[dict],
    artifacts: list[dict],
    sections: list[dict],
) -> list[str]:
    candidates = []
    candidates.extend(item.get("name") for item in concepts[:6])
    candidates.extend(item.get("title") for item in sections[:4])
    candidates.extend(item.get("title") for item in artifacts[:3])
    if video.get("title"):
        candidates.append(video["title"])
    deduped = []
    seen = set()
    for candidate in candidates:
        text = _truncate_text(candidate, 120)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(text)
    return deduped[:10]


def _markdown_sections(value: str) -> list[dict]:
    matches = list(re.finditer(r"(?m)^(#{1,3})\s+(.+?)\s*$", value or ""))
    if not matches:
        text = str(value or "").strip()
        return [{"title": "Source Report", "body": text}] if text else []
    sections = []
    for index, match in enumerate(matches):
        if match.group(1) == "#" and len(matches) > 1:
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(value)
        body = value[start:end].strip()
        title = _truncate_text(match.group(2), 180)
        if title and body:
            sections.append({"title": title, "body": body})
    return sections


def _metadata_int(metadata: Any, key: str, default: int) -> int:
    if isinstance(metadata, dict):
        value = metadata.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return default


def _component_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-") or "item"


def _fit_video_knowledge_map_to_budget(payload: dict, max_chars: int) -> dict:
    payload["retrievalBudget"]["estimatedResponseChars"] = _estimated_json_chars(payload)
    payload["retrievalBudget"]["truncatedToBudget"] = False
    trim_order = [
        "timestampRefs",
        "timeline",
        "coreConcepts",
        "reportSections",
        "knowledgeArtifacts",
        "peopleOrganizationsTools",
        "claims",
        "decisions",
    ]
    while payload["retrievalBudget"]["estimatedResponseChars"] > max_chars:
        trimmed = False
        for key in trim_order:
            values = payload.get(key)
            if isinstance(values, list) and len(values) > 1:
                values.pop()
                trimmed = True
                break
        if not trimmed:
            break
        payload["retrievalBudget"]["truncatedToBudget"] = True
        payload["retrievalBudget"]["estimatedResponseChars"] = _estimated_json_chars(payload)
    return payload


def list_context_categories(
    supabase: Any,
    user_id: str,
    limit: int = 100,
    project_id: str | None = None,
    project_slug: str | None = None,
) -> dict:
    """Return browsable source and personal categories for agent discovery."""
    normalized_limit = max(1, min(limit, 200))
    project_scope = _resolve_optional_project_scope(supabase, user_id, project_id, project_slug)
    videos = _user_video_rows(
        supabase,
        user_id,
        normalized_limit,
        scope_video_ids=project_scope.get("videoIds") if project_scope else None,
    )
    video_ids = [video.get("id") for video in videos if video.get("id")]
    video_by_id = {video.get("id"): video for video in videos if video.get("id")}

    source_labels = []
    source_concepts = []
    artifacts = []
    if video_ids:
        source_labels = _rows(
            supabase.table("source_labels")
            .select("id, video_id, label_type, label, confidence, source_refs, metadata")
            .in_("video_id", video_ids)
            .order("label_type", desc=False)
            .limit(normalized_limit * 4)
            .execute()
        )
        source_concepts = _rows(
            supabase.table("source_concepts")
            .select("id, video_id, concept_type, name, summary, source_refs, metadata")
            .in_("video_id", video_ids)
            .order("updated_at", desc=True)
            .limit(normalized_limit * 2)
            .execute()
        )
        artifacts = _rows(
            supabase.table("knowledge_artifacts")
            .select("id, video_id, artifact_type, title, summary, source_refs, metadata")
            .in_("video_id", video_ids)
            .or_(f"user_id.is.null,user_id.eq.{user_id}")
            .order("updated_at", desc=True)
            .limit(normalized_limit)
            .execute()
        )

    personal_concepts = _rows(
        supabase.table("personal_concepts")
        .select("id, name, summary, status, source_refs, updated_at")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .limit(min(normalized_limit, 50))
        .execute()
    )

    categories = _aggregate_source_categories(
        source_labels,
        source_concepts,
        artifacts,
        video_by_id,
        normalized_limit,
    )
    facets = _build_category_facets(categories)

    return {
        "categories": categories,
        "facets": facets,
        "taxonomy": get_category_taxonomy(),
        "filterExamples": category_filter_examples(),
        "personalConcepts": personal_concepts,
        "projectScope": _project_scope_response(project_scope),
        "videoCount": len(videos),
        "sourceLabelCount": len(source_labels),
        "guidance": (
            "Browse categories before searching when the agent does not know a video ID. "
            "Use source labels for filtering and planning; use personalConcepts only as "
            "user-specific overlay context. Source labels are read-only."
        ),
    }


def build_project_context_map(
    supabase: Any,
    user_id: str,
    project_id: str | None = None,
    project_slug: str | None = None,
    limit: int = 50,
    detail_level: str = "compact",
    max_chars: int | None = None,
    max_context_tokens: int | None = None,
) -> dict:
    """Return a compact navigable map for one project-scoped video context set."""
    normalized_detail = normalize_detail_level(detail_level)
    normalized_limit = max(1, min(int(limit or 50), 100))
    effective_max_chars = response_char_budget(normalized_detail, max_chars, max_context_tokens)
    project_scope = _resolve_optional_project_scope(supabase, user_id, project_id, project_slug)
    if not project_scope:
        return {
            "found": False,
            "projectId": project_id,
            "projectSlug": project_slug,
            "detailLevel": normalized_detail,
            "guidance": "Project scope is required. Call list_projects first if the user intent is ambiguous.",
        }

    library = list_video_library_context(
        supabase,
        user_id,
        limit=normalized_limit,
        project_id=project_scope.get("id"),
    )
    graph = build_library_source_graph(
        supabase,
        user_id,
        limit=normalized_limit,
        include_artifact_content=False,
        include_auxiliary_nodes=False,
        include_review_flags=False,
        project_id=project_scope.get("id"),
    )
    categories = list_context_categories(
        supabase,
        user_id,
        limit=100,
        project_id=project_scope.get("id"),
    )
    videos = [
        {
            "videoId": video.get("videoId"),
            "title": video.get("title"),
            "channel": channel.get("name"),
            "transcriptSeconds": video.get("transcriptSeconds"),
            "indexedAt": video.get("indexedAt"),
            "next_mcp_call": {
                "name": "get_video_knowledge_map",
                "arguments": {
                    "youtube_video_id": video.get("videoId"),
                    "project_id": project_scope.get("id"),
                    "detail_level": normalized_detail,
                },
            },
        }
        for channel in library.get("channels", [])
        for video in channel.get("videos", [])
    ]
    payload = {
        "found": True,
        "version": "memexai-project-context-map-v1",
        "detailLevel": normalized_detail,
        "project": {
            "id": project_scope.get("id"),
            "name": project_scope.get("name"),
            "slug": project_scope.get("slug"),
            "description": project_scope.get("description", ""),
            "status": project_scope.get("status", "active"),
            "videoCount": len(project_scope.get("videoIds") or []),
            "captureSources": project_scope.get("captureSources", []),
        },
        "videos": videos,
        "componentCounts": graph.get("componentCounts", {}),
        "facets": categories.get("facets", {}),
        "suggestedFollowUpQueries": _project_follow_up_queries(
            project_scope,
            videos,
            categories.get("categories", []),
        ),
        "next_mcp_call": {
            "name": "search_video_concepts",
            "reason": "Search generated reports, concepts, aliases, and timestamp refs within this project.",
            "argumentsTemplate": {
                "query": "<specific project topic or user question>",
                "project_id": project_scope.get("id"),
                "retrieval_mode": "hybrid",
                "limit": 8,
            },
        },
        "fallback_mcp_call": {
            "name": "search_video_concepts",
            "reason": "Broaden only after scoped recall is weak or the user asks across all saved videos.",
            "argumentsTemplate": {
                "query": "<same query>",
                "retrieval_mode": "hybrid",
                "limit": 8,
            },
        },
        "retrievalBudget": {
            "embeddingCalls": 0,
            "llmCalls": 0,
            "limit": normalized_limit,
            "maxChars": effective_max_chars,
            "maxContextTokens": max_context_tokens,
        },
        "guidance": (
            "Use this project map before searching when the user's request maps to a "
            "specific workstream. Ask the user to choose a project when intent is ambiguous."
        ),
    }
    return _fit_results_to_budget(payload, "videos", effective_max_chars)


def _project_follow_up_queries(
    project_scope: dict,
    videos: list[dict],
    categories: list[dict],
) -> list[str]:
    queries = []
    project_name = project_scope.get("name") or "this project"
    for category in categories[:5]:
        label = category.get("label")
        if label:
            queries.append(f"{label} in {project_name}")
    for video in videos[:3]:
        title = video.get("title")
        if title:
            queries.append(f"key takeaways from {title}")
    queries.append(f"what should I know for {project_name}?")
    seen = set()
    deduped = []
    for query in queries:
        normalized = query.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(query)
    return deduped[:8]


def _aggregate_source_categories(
    source_labels: list[dict],
    source_concepts: list[dict],
    artifacts: list[dict],
    video_by_id: dict[str, dict],
    limit: int,
) -> list[dict]:
    grouped: dict[tuple[str, str], dict] = {}

    def add_category(
        label_type: str,
        label: str,
        video_id: str | None,
        source: str,
        confidence: float | None = None,
        source_refs: list[dict] | None = None,
    ) -> None:
        clean_label = " ".join(str(label).split()).strip()
        clean_type = _clean_label_type(label_type)
        if not clean_label:
            return
        key = (clean_type, clean_label.lower())
        entry = grouped.setdefault(
            key,
            {
                "labelType": clean_type,
                "label": clean_label,
                "count": 0,
                "sources": [],
                "videos": [],
                "sourceRefs": [],
                "confidence": None,
            },
        )
        entry["count"] += 1
        if source not in entry["sources"]:
            entry["sources"].append(source)
        if isinstance(confidence, (int, float)) and not isinstance(confidence, bool):
            existing = entry.get("confidence")
            entry["confidence"] = confidence if existing is None else max(existing, confidence)
        for ref in source_refs or []:
            if isinstance(ref, dict) and ref not in entry["sourceRefs"]:
                entry["sourceRefs"].append(ref)

        if video_id and video_id in video_by_id:
            video = video_by_id[video_id]
            candidate = {
                "id": video.get("id"),
                "videoId": video.get("youtube_video_id"),
                "title": video.get("title"),
            }
            if candidate not in entry["videos"]:
                entry["videos"].append(candidate)

    for row in source_labels:
        add_category(
            row.get("label_type", "topic"),
            row.get("label", ""),
            row.get("video_id"),
            "source_label",
            row.get("confidence"),
            row.get("source_refs") if isinstance(row.get("source_refs"), list) else [],
        )

    for row in source_concepts:
        add_category(
            "concept_type",
            row.get("concept_type", "concept"),
            row.get("video_id"),
            "source_concept",
            source_refs=row.get("source_refs") if isinstance(row.get("source_refs"), list) else [],
        )
        add_category(
            "concept",
            row.get("name", ""),
            row.get("video_id"),
            "source_concept",
            source_refs=row.get("source_refs") if isinstance(row.get("source_refs"), list) else [],
        )

    for row in artifacts:
        add_category(
            "artifact_type",
            row.get("artifact_type", ""),
            row.get("video_id"),
            "knowledge_artifact",
            source_refs=row.get("source_refs") if isinstance(row.get("source_refs"), list) else [],
        )

    categories = list(grouped.values())
    for category in categories:
        category["videos"] = category["videos"][:5]
        category["sourceRefs"] = category["sourceRefs"][:5]

    categories.sort(key=lambda item: (-item["count"], item["labelType"], item["label"].lower()))
    return categories[:limit]


def _clean_label_type(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", str(value).lower()).strip("_")
    return normalized or "topic"


def _build_category_facets(categories: list[dict]) -> dict:
    facets: dict[str, list[str]] = {}
    for category in categories:
        label_type = category.get("labelType")
        label = category.get("label")
        if not label_type or not label:
            continue
        facets.setdefault(label_type, [])
        if label not in facets[label_type]:
            facets[label_type].append(label)
    return facets


def build_context_bundle(
    supabase: Any,
    user_id: str,
    query: str,
    repo_context: dict | None = None,
    limit: int = 8,
    category_filters: dict | None = None,
) -> dict:
    """Build an agent-friendly context bundle from personal overlay data.

    Repo context is intentionally accepted as request-supplied context so agents
    can bring repository information over MCP without forcing a hosted GitHub
    connection first.
    """
    notes = _rows(
        supabase.table("agent_notes")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    personal_concepts = _rows(
        supabase.table("personal_concepts")
        .select("*")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )

    normalized_filters = normalize_category_filters(category_filters)
    repo_context_validation = validate_repo_context(repo_context)
    normalized_repo_context = repo_context_validation["normalized"]
    source_context = _list_user_source_context(supabase, user_id, query, limit, normalized_filters)

    return {
        "query": query,
        "repoContext": normalized_repo_context,
        "repoContextValidation": {
            "valid": repo_context_validation["valid"],
            "warnings": repo_context_validation["warnings"],
            "missingRecommended": repo_context_validation["missingRecommended"],
            "readiness": repo_context_validation["readiness"],
            "next_mcp_call": repo_context_validation["next_mcp_call"],
        },
        "categoryFilters": normalized_filters,
        "sourceContext": source_context,
        "personalConcepts": personal_concepts,
        "agentNotes": notes,
        "guidance": (
            "Use sourceContext and source_refs as citations. Treat repoContext as "
            "agent-supplied context, not stored source truth, unless the user explicitly "
            "saves a note or concept."
        ),
    }


def build_agent_brief(
    supabase: Any,
    user_id: str,
    query: str,
    repo_context: dict | None = None,
    limit: int = 8,
    category_filters: dict | None = None,
    *,
    embedding_provider: Any | None = None,
    retrieval_mode: str = "hybrid",
) -> dict:
    """Build a spec/prompt-oriented brief from source knowledge and personal overlay."""
    bundle = build_context_bundle(
        supabase,
        user_id,
        query,
        repo_context,
        limit,
        category_filters,
    )
    source_context = bundle["sourceContext"]
    concepts = source_context["sourceConcepts"]
    artifacts = source_context["knowledgeArtifacts"]
    personal_concepts = bundle["personalConcepts"]
    agent_notes = bundle["agentNotes"]
    effective_repo_context = normalize_repo_context(repo_context)
    indexed_source = _brief_source_knowledge_search(
        supabase,
        user_id,
        query,
        effective_repo_context,
        limit,
        category_filters,
        embedding_provider,
        retrieval_mode,
    )

    if indexed_source and indexed_source.get("results"):
        key_concepts, source_highlights = _brief_items_from_source_results(
            indexed_source.get("results", []),
            concepts,
            artifacts,
            limit,
        )
    else:
        key_concepts = _brief_key_concepts_from_legacy(concepts, limit)
        source_highlights = _brief_highlights_from_legacy(artifacts, limit)
    repo_touchpoints = _repo_touchpoints(effective_repo_context)
    repo_target_map = _repo_target_map(effective_repo_context)
    repo_readiness = bundle["repoContextValidation"].get("readiness", {})

    return {
        "query": query,
        "title": f"Agent Brief: {query}"[:160],
        "summary": _brief_summary(query, key_concepts, source_highlights, repo_touchpoints),
        "repoContext": effective_repo_context,
        "repoContextValidation": bundle["repoContextValidation"],
        "categoryFilters": bundle["categoryFilters"],
        "repoFit": {
            "provided": bool(effective_repo_context),
            "candidateTouchpoints": repo_touchpoints,
            "targetMap": repo_target_map,
            "guidance": (
                "Repo context came from the calling agent. Use it as working context, "
                "not as persisted source truth."
            ),
        },
        "keyConcepts": key_concepts,
        "sourceHighlights": source_highlights,
        "sourceRetrieval": {
            "usedSourceKnowledgeIndex": bool(indexed_source and indexed_source.get("results")),
            "retrievalMode": (indexed_source or {}).get("retrievalMode") or "legacy_keyword",
            "fallbackUsed": (indexed_source or {}).get("retrievalPlan", {}).get("fallbackUsed"),
            "embeddingCalls": (indexed_source or {})
            .get("retrievalBudget", {})
            .get("embeddingCalls", 0),
            "resultCount": len((indexed_source or {}).get("results") or []),
        },
        "implementationGuidance": _implementation_guidance(key_concepts, repo_touchpoints),
        "personalOverlay": {
            "concepts": personal_concepts[:limit],
            "notes": agent_notes[:limit],
        },
        "citations": _collect_source_refs(key_concepts, source_highlights, limit),
        "suggestedNextActions": _brief_next_actions(repo_readiness),
    }


def _brief_source_knowledge_search(
    supabase: Any,
    user_id: str,
    query: str,
    repo_context: dict,
    limit: int,
    category_filters: dict | None,
    embedding_provider: Any | None,
    retrieval_mode: str,
) -> dict | None:
    if embedding_provider is None and retrieval_mode != "keyword":
        return None
    try:
        return search_source_knowledge(
            supabase,
            user_id,
            _brief_retrieval_query(query, repo_context),
            limit,
            category_filters,
            detail_level="standard",
            max_chars=16_000,
            retrieval_mode=retrieval_mode,
            embedding_provider=embedding_provider,
        )
    except Exception:  # noqa: BLE001 - brief generation must keep legacy fallback available.
        return None


def _brief_retrieval_query(query: str, repo_context: dict) -> str:
    parts = [query]
    for key in ("features", "modules", "symbols", "entrypoints"):
        parts.extend(_repo_values(repo_context, key)[:6])

    deduped = []
    seen = set()
    for part in parts:
        normalized = " ".join(str(part).split())
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return " ".join(deduped)[:900]


def _brief_items_from_source_results(
    results: list[dict],
    fallback_concepts: list[dict],
    fallback_artifacts: list[dict],
    limit: int,
) -> tuple[list[dict], list[dict]]:
    key_concepts = []
    source_highlights = []
    for result in results[: max(limit * 2, limit)]:
        source_refs = result.get("sourceRefs") if isinstance(result.get("sourceRefs"), list) else []
        result_type = result.get("resultType")
        if result_type == "source_concept":
            key_concepts.append(
                {
                    "name": result.get("name") or result.get("title", ""),
                    "type": result.get("conceptType")
                    or result.get("metadata", {}).get("conceptType")
                    or "concept",
                    "summary": result.get("summary", ""),
                    "source_refs": source_refs,
                }
            )
        else:
            source_highlights.append(
                {
                    "title": result.get("title") or result.get("sectionHeading", ""),
                    "artifactType": (
                        result.get("artifactType")
                        or result.get("metadata", {}).get("artifactType")
                        or result_type
                        or ""
                    ),
                    "summary": result.get("summary") or result.get("contentExcerpt", ""),
                    "contentExcerpt": result.get("contentExcerpt", ""),
                    "source_refs": source_refs,
                }
            )

    if not key_concepts:
        key_concepts = _brief_key_concepts_from_legacy(fallback_concepts, limit)
    if not source_highlights:
        source_highlights = _brief_highlights_from_legacy(fallback_artifacts, limit)
    return key_concepts[:limit], source_highlights[:limit]


def _brief_key_concepts_from_legacy(concepts: list[dict], limit: int) -> list[dict]:
    return [
        {
            "name": concept.get("name", ""),
            "type": concept.get("concept_type", "concept"),
            "summary": concept.get("summary", ""),
            "source_refs": concept.get("source_refs", []),
        }
        for concept in concepts[:limit]
    ]


def _brief_highlights_from_legacy(artifacts: list[dict], limit: int) -> list[dict]:
    return [
        {
            "title": artifact.get("title", ""),
            "artifactType": artifact.get("artifact_type", ""),
            "summary": artifact.get("summary", ""),
            "contentExcerpt": str(artifact.get("content", ""))[:900],
            "source_refs": artifact.get("source_refs", []),
        }
        for artifact in artifacts[:limit]
    ]


def _repo_touchpoints(repo_context: dict) -> list[str]:
    touchpoints = []
    for key in (
        "features",
        "modules",
        "symbols",
        "locations",
        "files",
        "entrypoints",
        "dependencies",
        "commands",
        "tests",
        "deployment",
        "active_changes",
        "areas",
        "packages",
    ):
        values = repo_context.get(key)
        if isinstance(values, list):
            touchpoints.extend(str(value) for value in values if str(value).strip())
        elif isinstance(values, str) and values.strip():
            touchpoints.append(values.strip())

    repo_name = repo_context.get("repo")
    if isinstance(repo_name, str) and repo_name.strip():
        touchpoints.insert(0, repo_name.strip())

    seen = set()
    deduped = []
    for item in touchpoints:
        normalized = item.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(item)
    return deduped[:12]


def _repo_values(repo_context: dict, key: str) -> list[str]:
    values = repo_context.get(key)
    if isinstance(values, list):
        return [str(value).strip() for value in values if str(value).strip()]
    if isinstance(values, str) and values.strip():
        return [values.strip()]
    return []


def _dedupe_limit(values: list[str], limit: int = 12) -> list[str]:
    seen = set()
    deduped = []
    for value in values:
        normalized = value.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(value)
    return deduped[:limit]


def _repo_target_map(repo_context: dict) -> dict:
    repo = repo_context.get("repo", "")
    branch = repo_context.get("branch", "")
    target_map = {
        "repo": repo.strip() if isinstance(repo, str) else "",
        "branch": branch.strip() if isinstance(branch, str) else "",
        "features": _repo_values(repo_context, "features"),
        "modules": _repo_values(repo_context, "modules"),
        "symbols": _repo_values(repo_context, "symbols"),
        "locations": _repo_values(repo_context, "locations"),
        "files": _repo_values(repo_context, "files"),
        "entrypoints": _repo_values(repo_context, "entrypoints"),
        "dependencies": _repo_values(repo_context, "dependencies"),
        "commands": _repo_values(repo_context, "commands"),
        "tests": _repo_values(repo_context, "tests"),
        "deployment": _repo_values(repo_context, "deployment"),
        "activeChanges": _repo_values(repo_context, "active_changes"),
        "constraints": _repo_values(repo_context, "constraints"),
        "openQuestions": _repo_values(repo_context, "open_questions"),
    }
    target_map["implementationTargets"] = _dedupe_limit(
        [
            *target_map["locations"],
            *target_map["symbols"],
            *target_map["files"],
            *target_map["entrypoints"],
            *target_map["modules"],
            *target_map["features"],
        ]
    )
    target_map["verificationTargets"] = _dedupe_limit(
        [*target_map["commands"], *target_map["tests"]]
    )
    target_map["runtimeTargets"] = _dedupe_limit(
        [*target_map["dependencies"], *target_map["deployment"]]
    )
    return target_map


def _brief_summary(
    query: str,
    key_concepts: list[dict],
    source_highlights: list[dict],
    repo_touchpoints: list[str],
) -> str:
    if source_highlights and source_highlights[0].get("summary"):
        base = source_highlights[0]["summary"]
    elif key_concepts:
        names = ", ".join(concept["name"] for concept in key_concepts[:4] if concept.get("name"))
        base = f"Relevant saved-video concepts for '{query}' include {names}."
    else:
        base = f"No strong saved-video concepts were found for '{query}'."

    if repo_touchpoints:
        return f"{base} Review this against repo context: {', '.join(repo_touchpoints[:4])}."
    return base


def _implementation_guidance(key_concepts: list[dict], repo_touchpoints: list[str]) -> list[str]:
    guidance = []
    target = ", ".join(repo_touchpoints[:3]) if repo_touchpoints else "the current project"
    for concept in key_concepts:
        name = concept.get("name")
        summary = concept.get("summary")
        concept_type = concept.get("type")
        if not name:
            continue
        if concept_type in {"algorithm", "method", "tool"}:
            guidance.append(f"Evaluate whether {name} can be applied in {target}. {summary}")
        elif concept_type == "pitfall":
            guidance.append(f"Check for {name} as a risk before implementation. {summary}")
        elif concept_type == "implementation_note":
            guidance.append(f"Translate {name} into a concrete task for {target}. {summary}")
        else:
            guidance.append(f"Use {name} as context when planning changes in {target}. {summary}")
    return [item.strip() for item in guidance if item.strip()][:10]


def _brief_next_actions(repo_readiness: dict) -> list[str]:
    actions = []
    readiness_level = repo_readiness.get("level")
    if readiness_level == "implementation_ready":
        actions.append(
            "Repo context is implementation-ready; use the provided commands, tests, and runtime constraints when drafting changes."
        )
    elif isinstance(repo_readiness.get("suggestedAgentNextSteps"), list):
        actions.extend(
            "Improve repo_context before implementation planning: " + step
            for step in repo_readiness["suggestedAgentNextSteps"][:3]
            if isinstance(step, str) and step.strip()
        )

    actions.extend(
        [
            "Use search_video_moments for exact timestamp evidence before quoting a claim.",
            "Use get_video_context when a brief item needs full transcript or concept context.",
            "Save durable project-specific takeaways with add_context_note or upsert_personal_concept.",
        ]
    )
    return actions


def _collect_source_refs(
    key_concepts: list[dict],
    source_highlights: list[dict],
    limit: int,
) -> list[dict]:
    refs = []
    for item in [*key_concepts, *source_highlights]:
        item_refs = item.get("source_refs", [])
        if isinstance(item_refs, list):
            refs.extend(ref for ref in item_refs if isinstance(ref, dict))

    deduped = []
    seen = set()
    for ref in refs:
        key = (
            ref.get("youtube_video_id") or ref.get("source_id") or ref.get("source_type"),
            ref.get("start_seconds"),
            ref.get("end_seconds"),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ref)
    return deduped[: max(1, limit)]
