"""User-owned project helpers for scoping saved-video context."""

from __future__ import annotations

import re
from typing import Any

PROJECT_STATUSES = {"active", "archived"}
PROJECT_VIDEO_SOURCES = {"manual", "capture_sync", "ingest", "agent"}


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


def _clean_string(value: Any, *, max_length: int = 200) -> str:
    return " ".join(str(value or "").split()).strip()[:max_length]


def slugify_project_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(name or "").lower()).strip("-")
    return slug[:80].strip("-") or "project"


def list_projects(supabase: Any, user_id: str, limit: int = 50) -> dict:
    """Return projects with compact counts and linked capture sources."""
    bounded_limit = max(1, min(limit, 100))
    projects = _rows(
        supabase.table("user_projects")
        .select("*")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .limit(bounded_limit)
        .execute()
    )
    project_ids = [project.get("id") for project in projects if project.get("id")]
    counts = _project_video_counts(supabase, user_id, project_ids)
    capture_sources = _project_capture_sources(supabase, user_id, project_ids)
    decorated = [
        _decorate_project(project, counts, capture_sources)
        for project in projects
        if project.get("status") != "archived"
    ]
    archived = [
        _decorate_project(project, counts, capture_sources)
        for project in projects
        if project.get("status") == "archived"
    ]
    return {
        "projects": decorated,
        "archivedProjects": archived,
        "totalProjects": len(decorated),
        "totalArchivedProjects": len(archived),
        "limit": bounded_limit,
        "guidance": (
            "Projects scope saved-video retrieval without granting access by themselves. "
            "Use a project scope when the user's task maps to a specific workstream; "
            "broaden to all library only when scoped recall is weak or the user asks broadly."
        ),
    }


def get_project(
    supabase: Any,
    user_id: str,
    project_id: str | None = None,
    project_slug: str | None = None,
) -> dict | None:
    """Resolve one active/archived project by ID or slug."""
    clean_id = _clean_string(project_id)
    clean_slug = _clean_string(project_slug, max_length=100)
    if not clean_id and not clean_slug:
        return None
    query = supabase.table("user_projects").select("*").eq("user_id", user_id)
    if clean_id:
        query = query.eq("id", clean_id)
    else:
        query = query.eq("slug", clean_slug)
    project = _first(query.maybe_single().execute())
    if not project:
        return None
    counts = _project_video_counts(supabase, user_id, [project.get("id")])
    capture_sources = _project_capture_sources(supabase, user_id, [project.get("id")])
    return _decorate_project(project, counts, capture_sources)


def create_project(
    supabase: Any,
    user_id: str,
    name: str,
    description: str = "",
    metadata: dict | None = None,
) -> dict:
    """Create a user-owned project with a stable readable slug."""
    clean_name = _clean_string(name, max_length=120)
    if not clean_name:
        raise ValueError("Project name is required")
    slug = _available_project_slug(supabase, user_id, slugify_project_name(clean_name))
    payload = {
        "user_id": user_id,
        "name": clean_name,
        "slug": slug,
        "description": _clean_string(description, max_length=2000),
        "status": "active",
        "metadata": metadata if isinstance(metadata, dict) else {},
    }
    project = _first(supabase.table("user_projects").insert(payload).execute()) or payload
    return _decorate_project(project, {}, {})


def update_project(
    supabase: Any,
    user_id: str,
    project_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    status: str | None = None,
    metadata: dict | None = None,
) -> dict | None:
    """Update project display fields. Slugs remain stable after creation."""
    project = get_project(supabase, user_id, project_id=project_id)
    if not project:
        return None

    fields: dict[str, Any] = {}
    if name is not None:
        clean_name = _clean_string(name, max_length=120)
        if not clean_name:
            raise ValueError("Project name cannot be empty")
        fields["name"] = clean_name
    if description is not None:
        fields["description"] = _clean_string(description, max_length=2000)
    if status is not None:
        clean_status = _clean_string(status, max_length=40)
        if clean_status not in PROJECT_STATUSES:
            raise ValueError("Project status must be active or archived")
        fields["status"] = clean_status
    if metadata is not None:
        if not isinstance(metadata, dict):
            raise ValueError("Project metadata must be an object")
        fields["metadata"] = metadata
    if not fields:
        return project

    updated = _first(
        supabase.table("user_projects")
        .update(fields)
        .eq("user_id", user_id)
        .eq("id", project_id)
        .execute()
    )
    return _decorate_project(updated or {**project, **fields}, {}, {})


def delete_project(supabase: Any, user_id: str, project_id: str) -> bool:
    """Delete a project and its memberships. Source videos remain untouched."""
    project = get_project(supabase, user_id, project_id=project_id)
    if not project:
        return False
    supabase.table("user_projects").delete().eq("user_id", user_id).eq("id", project_id).execute()
    return True


def add_videos_to_project(
    supabase: Any,
    user_id: str,
    project_id: str,
    *,
    video_ids: list[str] | None = None,
    youtube_video_ids: list[str] | None = None,
    added_source: str = "manual",
    capture_source_id: str | None = None,
) -> dict:
    """Assign already accessible videos to a project."""
    project = get_project(supabase, user_id, project_id=project_id)
    if not project:
        raise ValueError("Project not found")
    source = _clean_string(added_source, max_length=40) or "manual"
    if source not in PROJECT_VIDEO_SOURCES:
        raise ValueError("added_source must be manual, capture_sync, ingest, or agent")

    resolved_videos = _resolve_accessible_videos(
        supabase,
        user_id,
        video_ids or [],
        youtube_video_ids or [],
    )
    rows = [
        {
            "project_id": project_id,
            "user_id": user_id,
            "video_id": video["id"],
            "added_source": source,
            "capture_source_id": capture_source_id,
            "metadata": {},
        }
        for video in resolved_videos
        if video.get("id")
    ]
    if rows:
        supabase.table("user_project_videos").upsert(
            rows,
            on_conflict="project_id,video_id",
        ).execute()

    return {
        "project": project,
        "addedCount": len(rows),
        "addedVideos": [
            video.get("youtube_video_id")
            for video in resolved_videos
            if video.get("youtube_video_id")
        ],
        "requestedCount": len(set([*(video_ids or []), *(youtube_video_ids or [])])),
        "videos": [
            {
                "id": video.get("id"),
                "videoId": video.get("youtube_video_id"),
                "title": video.get("title", ""),
            }
            for video in resolved_videos
        ],
    }


def remove_video_from_project(
    supabase: Any,
    user_id: str,
    project_id: str,
    video_id: str,
) -> bool:
    """Remove one video from a project without touching the user's library grant."""
    project = get_project(supabase, user_id, project_id=project_id)
    if not project:
        return False
    video = _accessible_video_by_any_id(supabase, user_id, video_id)
    if not video:
        return False
    supabase.table("user_project_videos").delete().eq("user_id", user_id).eq(
        "project_id", project_id
    ).eq("video_id", video["id"]).execute()
    return True


def set_capture_source_project(
    supabase: Any,
    user_id: str,
    capture_source_id: str,
    project_id: str | None,
) -> dict | None:
    """Attach or detach one capture source's default project target."""
    if project_id and not get_project(supabase, user_id, project_id=project_id):
        raise ValueError("Project not found")
    updated = _first(
        supabase.table("youtube_capture_sources")
        .update({"project_id": project_id})
        .eq("user_id", user_id)
        .eq("id", capture_source_id)
        .execute()
    )
    return updated


def project_video_ids(supabase: Any, user_id: str, project_id: str | None) -> list[str]:
    """Return DB video IDs assigned to a user project."""
    if not project_id:
        return []
    rows = _rows(
        supabase.table("user_project_videos")
        .select("video_id")
        .eq("user_id", user_id)
        .eq("project_id", project_id)
        .execute()
    )
    return [row.get("video_id") for row in rows if row.get("video_id")]


def resolve_project_scope(
    supabase: Any,
    user_id: str,
    project_id: str | None = None,
    project_slug: str | None = None,
) -> dict | None:
    """Resolve an optional project scope and include its assigned video IDs."""
    project = get_project(supabase, user_id, project_id=project_id, project_slug=project_slug)
    if not project:
        if _clean_string(project_id) or _clean_string(project_slug):
            raise ValueError("Project not found")
        return None
    return {
        "id": project.get("id"),
        "name": project.get("name"),
        "slug": project.get("slug"),
        "description": project.get("description", ""),
        "status": project.get("status", "active"),
        "videoCount": project.get("videoCount", 0),
        "linkedCaptureSourceCount": project.get("linkedCaptureSourceCount", 0),
        "captureSources": project.get("captureSources", []),
        "videoIds": project_video_ids(supabase, user_id, project.get("id")),
    }


def _available_project_slug(supabase: Any, user_id: str, base_slug: str) -> str:
    rows = _rows(supabase.table("user_projects").select("slug").eq("user_id", user_id).execute())
    existing = {str(row.get("slug") or "") for row in rows}
    if base_slug not in existing:
        return base_slug
    for index in range(2, 1000):
        candidate = f"{base_slug}-{index}"
        if candidate not in existing:
            return candidate
    raise ValueError("Could not create a unique project slug")


def _decorate_project(
    project: dict, counts: dict[str, int], capture_sources: dict[str, list]
) -> dict:
    project_id = str(project.get("id") or "")
    linked_sources = capture_sources.get(project_id, [])
    return {
        "id": project.get("id"),
        "name": project.get("name", ""),
        "slug": project.get("slug", ""),
        "description": project.get("description", ""),
        "status": project.get("status", "active"),
        "metadata": project.get("metadata") if isinstance(project.get("metadata"), dict) else {},
        "videoCount": counts.get(project_id, 0),
        "linkedCaptureSourceCount": len(linked_sources),
        "captureSources": linked_sources,
        "createdAt": project.get("created_at"),
        "updatedAt": project.get("updated_at"),
    }


def _project_video_counts(supabase: Any, user_id: str, project_ids: list[str]) -> dict[str, int]:
    if not project_ids:
        return {}
    rows = _rows(
        supabase.table("user_project_videos")
        .select("project_id, video_id")
        .eq("user_id", user_id)
        .in_("project_id", project_ids)
        .execute()
    )
    counts: dict[str, int] = {str(project_id): 0 for project_id in project_ids}
    seen: set[tuple[str, str]] = set()
    for row in rows:
        project_id = str(row.get("project_id") or "")
        video_id = str(row.get("video_id") or "")
        key = (project_id, video_id)
        if project_id and video_id and key not in seen:
            counts[project_id] = counts.get(project_id, 0) + 1
            seen.add(key)
    return counts


def _project_capture_sources(
    supabase: Any,
    user_id: str,
    project_ids: list[str],
) -> dict[str, list[dict]]:
    if not project_ids:
        return {}
    rows = _rows(
        supabase.table("youtube_capture_sources")
        .select(
            "id, project_id, source_type, source_url, external_id, title, status, "
            "last_synced_at, last_error"
        )
        .eq("user_id", user_id)
        .in_("project_id", project_ids)
        .execute()
    )
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        project_id = str(row.get("project_id") or "")
        if not project_id:
            continue
        grouped.setdefault(project_id, []).append(row)
    return grouped


def _resolve_accessible_videos(
    supabase: Any,
    user_id: str,
    video_ids: list[str],
    youtube_video_ids: list[str],
) -> list[dict]:
    resolved = []
    seen = set()
    for video_id in video_ids:
        video = _accessible_video_by_db_id(supabase, user_id, video_id)
        if video and video.get("id") not in seen:
            resolved.append(video)
            seen.add(video.get("id"))
    for youtube_video_id in youtube_video_ids:
        video = _accessible_video_by_youtube_id(supabase, user_id, youtube_video_id)
        if video and video.get("id") not in seen:
            resolved.append(video)
            seen.add(video.get("id"))
    return resolved


def _accessible_video_by_any_id(supabase: Any, user_id: str, video_id: str) -> dict | None:
    return _accessible_video_by_db_id(
        supabase, user_id, video_id
    ) or _accessible_video_by_youtube_id(supabase, user_id, video_id)


def _accessible_video_by_db_id(supabase: Any, user_id: str, video_id: Any) -> dict | None:
    clean_id = _clean_string(video_id, max_length=100)
    if not clean_id:
        return None
    video = _first(
        supabase.table("videos")
        .select("id, channel_id, youtube_video_id, title")
        .eq("id", clean_id)
        .maybe_single()
        .execute()
    )
    return video if video and _user_can_access_video(supabase, user_id, video) else None


def _accessible_video_by_youtube_id(
    supabase: Any, user_id: str, youtube_video_id: Any
) -> dict | None:
    clean_id = _clean_string(youtube_video_id, max_length=100)
    if not clean_id:
        return None
    video = _first(
        supabase.table("videos")
        .select("id, channel_id, youtube_video_id, title")
        .eq("youtube_video_id", clean_id)
        .maybe_single()
        .execute()
    )
    return video if video and _user_can_access_video(supabase, user_id, video) else None


def _user_can_access_video(supabase: Any, user_id: str, video: dict) -> bool:
    channel_id = video.get("channel_id")
    video_id = video.get("id")
    if channel_id:
        channel_access = _first(
            supabase.table("user_channels")
            .select("user_id")
            .eq("user_id", user_id)
            .eq("channel_id", channel_id)
            .maybe_single()
            .execute()
        )
        if channel_access:
            return True
    if video_id:
        video_access = _first(
            supabase.table("user_videos")
            .select("user_id")
            .eq("user_id", user_id)
            .eq("video_id", video_id)
            .maybe_single()
            .execute()
        )
        return bool(video_access)
    return False
