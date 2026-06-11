"""Storage dispatch layer for local Chroma and Supabase pgvector modes."""

from __future__ import annotations

import os
from typing import Generator, Optional

try:
    from .config import LOCAL_STORAGE, SUPABASE_STORAGE, get_storage_mode
    from .ingest import ingest_url_pg
    from .ingest_chroma import delete_video as delete_video_local
    from .ingest_chroma import get_library as get_library_local
    from .ingest_chroma import get_video_transcript as get_video_transcript_local
    from .ingest_chroma import ingest_url as ingest_url_local
    from .rag import (
        delete_video_pg,
        get_library_pg,
        get_video_transcript_pg,
        search_pg,
    )
    from .rag_chroma import search as search_local
except ImportError:
    from config import LOCAL_STORAGE, SUPABASE_STORAGE, get_storage_mode
    from ingest import ingest_url_pg
    from ingest_chroma import delete_video as delete_video_local
    from ingest_chroma import get_library as get_library_local
    from ingest_chroma import get_video_transcript as get_video_transcript_local
    from ingest_chroma import ingest_url as ingest_url_local
    from rag import delete_video_pg, get_library_pg, get_video_transcript_pg, search_pg
    from rag_chroma import search as search_local


LOCAL_USER_ID = "local"


def is_supabase_mode() -> bool:
    return get_storage_mode() == SUPABASE_STORAGE


def is_local_mode() -> bool:
    return get_storage_mode() == LOCAL_STORAGE


def resolve_api_key(user_api_key: Optional[str] = None) -> tuple[Optional[str], bool]:
    """Return the API key and whether it came from the user."""
    if user_api_key:
        return user_api_key, True
    return os.getenv("GEMINI_API_KEY"), False


def ingest_url(
    url: str,
    user_id: str = LOCAL_USER_ID,
    api_key: Optional[str] = None,
    used_own_key: bool = False,
) -> Generator[str, None, None]:
    if is_supabase_mode():
        yield from ingest_url_pg(url, user_id, api_key, used_own_key)
    else:
        yield from ingest_url_local(url, api_key=api_key)


def search(
    query: str,
    user_id: str = LOCAL_USER_ID,
    api_key: Optional[str] = None,
    limit: int = 5,
) -> dict:
    if is_supabase_mode():
        return search_pg(query, user_id, api_key, limit)
    return search_local(query, api_key=api_key, limit=limit)


def get_library(user_id: str = LOCAL_USER_ID) -> dict:
    if is_supabase_mode():
        return get_library_pg(user_id)
    return get_library_local()


def delete_video(video_id: str, user_id: str = LOCAL_USER_ID) -> dict:
    if is_supabase_mode():
        result = delete_video_pg(video_id, user_id)
        return {
            "success": bool(result.get("deleted")),
            "deletedClips": result.get("deletedClips", 0),
            "error": result.get("reason"),
        }

    result = delete_video_local(video_id)
    return {
        "success": bool(result.get("success")),
        "deletedClips": result.get("deletedClips", 0),
        "error": result.get("error"),
    }


def get_video_transcript(video_id: str, user_id: str = LOCAL_USER_ID) -> list[dict]:
    if is_supabase_mode():
        return get_video_transcript_pg(video_id, user_id)

    result = get_video_transcript_local(video_id)
    if not result.get("success"):
        return []

    return [
        {
            "content": chunk.get("text", ""),
            "start_seconds": chunk.get("start_seconds", 0),
            "end_seconds": chunk.get("end_seconds", 0),
        }
        for chunk in result.get("chunks", [])
    ]
