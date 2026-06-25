"""Hosted Supabase storage adapter."""

from __future__ import annotations

import os
from typing import Generator, Optional

try:
    from .config import SUPABASE_STORAGE, get_storage_mode
    from .digest_depth import DEFAULT_DIGEST_DEPTH
    from .ingest import ingest_url_pg
    from .rag import (
        delete_video_pg,
        get_library_pg,
        get_video_transcript_pg,
        search_pg,
        search_transcript_text_pg,
    )
except ImportError:
    from config import SUPABASE_STORAGE, get_storage_mode
    from digest_depth import DEFAULT_DIGEST_DEPTH
    from ingest import ingest_url_pg
    from rag import (
        delete_video_pg,
        get_library_pg,
        get_video_transcript_pg,
        search_pg,
        search_transcript_text_pg,
    )


LOCAL_USER_ID = "local"


def is_supabase_mode() -> bool:
    return get_storage_mode() == SUPABASE_STORAGE


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
    digest_depth: str = DEFAULT_DIGEST_DEPTH,
) -> Generator[str, None, None]:
    yield from ingest_url_pg(url, user_id, api_key, used_own_key, digest_depth)


def search(
    query: str,
    user_id: str = LOCAL_USER_ID,
    api_key: Optional[str] = None,
    limit: int = 5,
    category_filters: dict | None = None,
    retrieval_mode: str = "hybrid",
) -> dict:
    return search_pg(query, user_id, api_key, limit, category_filters, retrieval_mode)


def search_transcript_text(
    query: str,
    user_id: str = LOCAL_USER_ID,
    limit: int = 5,
    category_filters: dict | None = None,
) -> dict:
    return search_transcript_text_pg(query, user_id, limit, category_filters)


def get_library(user_id: str = LOCAL_USER_ID) -> dict:
    return get_library_pg(user_id)


def delete_video(video_id: str, user_id: str = LOCAL_USER_ID) -> dict:
    result = delete_video_pg(video_id, user_id)
    return {
        "success": bool(result.get("deleted")),
        "deletedClips": result.get("deletedClips", 0),
        "error": result.get("reason"),
    }


def get_video_transcript(video_id: str, user_id: str = LOCAL_USER_ID) -> list[dict]:
    return get_video_transcript_pg(video_id, user_id)
