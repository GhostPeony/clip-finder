"""User-owned YouTube OAuth connection helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

try:
    from .db import decrypt_api_key, encrypt_api_key
except ImportError:
    from db import decrypt_api_key, encrypt_api_key


YOUTUBE_OAUTH_TABLE = "youtube_oauth_connections"
YOUTUBE_READONLY_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"


def _response_data(result: Any) -> Any:
    return getattr(result, "data", None)


def _first_row(data: Any) -> dict | None:
    if isinstance(data, list):
        return data[0] if data else None
    if isinstance(data, dict):
        return data
    return None


def normalize_oauth_scopes(scopes: list[str] | str | None) -> list[str]:
    """Normalize provider scopes from Supabase/Google into stable unique values."""
    if scopes is None:
        return []
    if isinstance(scopes, str):
        raw_scopes = scopes.replace(",", " ").split()
    else:
        raw_scopes = scopes

    normalized: list[str] = []
    for scope in raw_scopes:
        trimmed = str(scope).strip()
        if trimmed and trimmed not in normalized:
            normalized.append(trimmed)
    return normalized


def _calculate_expires_at(expires_in: int | None, expires_at: str | None = None) -> str | None:
    if expires_at:
        return expires_at
    if expires_in is None or expires_in <= 0:
        return None
    resolved = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    return resolved.isoformat()


def _get_connection_row(supabase: Any, user_id: str) -> dict | None:
    result = (
        supabase.table(YOUTUBE_OAUTH_TABLE)
        .select("*")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    return _first_row(_response_data(result))


def format_youtube_oauth_status(row: dict | None) -> dict:
    """Return a token-safe status object for frontend and agent setup UI."""
    if not row:
        return {
            "connected": False,
            "needsReconnect": False,
            "youtubeReadonlyGranted": False,
            "hasRefreshToken": False,
            "scopes": [],
            "expiresAt": None,
            "connectedAt": None,
            "updatedAt": None,
            "lastError": None,
        }

    scopes = normalize_oauth_scopes(row.get("scopes"))
    has_refresh_token = bool(row.get("refresh_token_enc"))
    youtube_readonly_granted = YOUTUBE_READONLY_SCOPE in scopes
    has_any_token = bool(row.get("access_token_enc") or row.get("refresh_token_enc"))
    status = row.get("status", "active")

    return {
        "connected": bool(has_any_token and status == "active"),
        "needsReconnect": bool(not has_refresh_token or not youtube_readonly_granted),
        "youtubeReadonlyGranted": youtube_readonly_granted,
        "hasRefreshToken": has_refresh_token,
        "scopes": scopes,
        "expiresAt": row.get("expires_at"),
        "connectedAt": row.get("connected_at"),
        "updatedAt": row.get("updated_at"),
        "lastError": row.get("last_error"),
    }


def get_youtube_oauth_status(supabase: Any, user_id: str) -> dict:
    """Fetch the current user's token-safe YouTube connection status."""
    return format_youtube_oauth_status(_get_connection_row(supabase, user_id))


def get_youtube_oauth_access_token(supabase: Any, user_id: str) -> str | None:
    """Return a decrypted YouTube provider access token when the grant is usable."""
    row = _get_connection_row(supabase, user_id)
    if not row or row.get("status", "active") != "active":
        return None
    if YOUTUBE_READONLY_SCOPE not in normalize_oauth_scopes(row.get("scopes")):
        return None

    encrypted_access_token = row.get("access_token_enc")
    if not encrypted_access_token:
        return None
    return decrypt_api_key(str(encrypted_access_token))


def upsert_youtube_oauth_connection(
    supabase: Any,
    user_id: str,
    access_token: str | None = None,
    refresh_token: str | None = None,
    expires_in: int | None = None,
    expires_at: str | None = None,
    scopes: list[str] | str | None = None,
) -> dict:
    """Store encrypted Google provider tokens for later YouTube API playlist sync."""
    existing = _get_connection_row(supabase, user_id)
    normalized_scopes = normalize_oauth_scopes(scopes) or normalize_oauth_scopes(
        existing.get("scopes") if existing else None
    )

    encrypted_access_token = (
        encrypt_api_key(access_token) if access_token else (existing or {}).get("access_token_enc")
    )
    encrypted_refresh_token = (
        encrypt_api_key(refresh_token)
        if refresh_token
        else (existing or {}).get("refresh_token_enc")
    )

    if not encrypted_access_token and not encrypted_refresh_token:
        raise ValueError("A Google provider access token or refresh token is required")

    payload = {
        "user_id": user_id,
        "provider": "google",
        "status": "active",
        "scopes": normalized_scopes,
        "access_token_enc": encrypted_access_token,
        "refresh_token_enc": encrypted_refresh_token,
        "expires_at": _calculate_expires_at(expires_in, expires_at),
        "last_error": None,
    }

    result = supabase.table(YOUTUBE_OAUTH_TABLE).upsert(payload, on_conflict="user_id").execute()
    row = _first_row(_response_data(result)) or {**(existing or {}), **payload}
    return format_youtube_oauth_status(row)


def disconnect_youtube_oauth(supabase: Any, user_id: str) -> dict:
    """Remove the stored YouTube OAuth grant for this user."""
    supabase.table(YOUTUBE_OAUTH_TABLE).delete().eq("user_id", user_id).execute()
    return format_youtube_oauth_status(None)
