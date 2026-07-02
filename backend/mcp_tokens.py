"""Hashed MCP token creation and verification helpers."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any

MCP_AUTH_PREFIX = "emt"
DEFAULT_MCP_SCOPES = ["context:read", "overlay:write"]
ALLOWED_MCP_SCOPES = [
    "context:read",
    "overlay:write",
    "ingest:write",
    "capture:write",
    "project:write",
]
TOKEN_PREFIX_CHARS = 10
TOKEN_SECRET_BYTES = 32
LAST_USED_TOUCH_SECONDS = 60


def create_mcp_token(
    supabase: Any,
    user_id: str,
    name: str = "MCP token",
    scopes: list[str] | None = None,
    expires_at: str | None = None,
    oauth_client_id: str | None = None,
) -> dict:
    """Create an MCP token and return the raw token exactly once."""
    token = _new_token()
    token_prefix = _display_prefix(token)
    payload = {
        "user_id": user_id,
        "name": _clean_name(name),
        "token_hash": _hash_token(token),
        "token_prefix": token_prefix,
        "scopes": _clean_scopes(scopes),
        "expires_at": expires_at,
    }
    if oauth_client_id:
        payload["oauth_client_id"] = oauth_client_id
    record = _first(supabase.table("mcp_tokens").insert(payload).execute()) or payload
    return {"token": token, "record": sanitize_mcp_token_record(record)}


def list_mcp_tokens(supabase: Any, user_id: str) -> list[dict]:
    """List active MCP token metadata without hashes."""
    records = _rows(
        supabase.table("mcp_tokens")
        .select(
            "id, name, token_prefix, scopes, oauth_client_id, last_used_at, expires_at, created_at"
        )
        .eq("user_id", user_id)
        .is_("revoked_at", "null")
        .order("created_at", desc=True)
        .execute()
    )
    return [sanitize_mcp_token_record(record) for record in records]


def revoke_mcp_token(supabase: Any, user_id: str, token_id: str) -> dict:
    """Revoke a user-owned MCP token."""
    now = datetime.now(timezone.utc).isoformat()
    result = (
        supabase.table("mcp_tokens")
        .update({"revoked_at": now})
        .eq("id", token_id)
        .eq("user_id", user_id)
        .is_("revoked_at", "null")
        .execute()
    )
    record = _first(result)
    return {"revoked": bool(record), "token": sanitize_mcp_token_record(record) if record else None}


def authenticate_mcp_token(supabase: Any, authorization: str | None) -> dict | None:
    """Validate a Bearer MCP token and return a user dict when valid."""
    token = _extract_bearer_token(authorization)
    if not token or not token.startswith(f"{MCP_AUTH_PREFIX}_"):
        return None

    result = (
        supabase.table("mcp_tokens")
        .select("id, user_id, scopes, expires_at, revoked_at, last_used_at")
        .eq("token_hash", _hash_token(token))
        .maybe_single()
        .execute()
    )
    record = _first(result)
    if not record or record.get("revoked_at") or _is_expired(record.get("expires_at")):
        return None

    now = datetime.now(timezone.utc)
    if _should_touch_last_used(record.get("last_used_at"), now):
        supabase.table("mcp_tokens").update({"last_used_at": now.isoformat()}).eq(
            "id", record["id"]
        ).execute()
    return {
        "sub": record["user_id"],
        "auth": "mcp_token",
        "mcp_token_id": record["id"],
        "scopes": record.get("scopes") or DEFAULT_MCP_SCOPES,
    }


def sanitize_mcp_token_record(record: dict) -> dict:
    """Remove sensitive columns from an MCP token row."""
    return {
        "id": record.get("id"),
        "name": record.get("name", "MCP token"),
        "tokenPrefix": record.get("token_prefix"),
        "scopes": record.get("scopes") or DEFAULT_MCP_SCOPES,
        "oauthClientId": record.get("oauth_client_id"),
        "lastUsedAt": record.get("last_used_at"),
        "expiresAt": record.get("expires_at"),
        "createdAt": record.get("created_at"),
    }


def _new_token() -> str:
    prefix = secrets.token_urlsafe(8)[:TOKEN_PREFIX_CHARS]
    secret = secrets.token_urlsafe(TOKEN_SECRET_BYTES)
    return f"{MCP_AUTH_PREFIX}_{prefix}_{secret}"


def _display_prefix(token: str) -> str:
    parts = token.split("_")
    return "_".join(parts[:2]) if len(parts) >= 2 else token[:14]


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return authorization.removeprefix("Bearer ").strip()


def _clean_name(name: str) -> str:
    normalized = " ".join(str(name).split())[:80].strip()
    return normalized or "MCP token"


def _clean_scopes(scopes: list[str] | None) -> list[str]:
    allowed = set(ALLOWED_MCP_SCOPES)
    requested = scopes or DEFAULT_MCP_SCOPES
    cleaned = [scope for scope in requested if scope in allowed]
    return cleaned or DEFAULT_MCP_SCOPES


def _should_touch_last_used(last_used_at: str | None, now: datetime) -> bool:
    """Debounce last_used_at writes so hot tokens do not update on every call."""
    if not last_used_at:
        return True
    try:
        parsed = datetime.fromisoformat(last_used_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (now - parsed).total_seconds() >= LAST_USED_TOUCH_SECONDS


def _is_expired(expires_at: str | None) -> bool:
    if not expires_at:
        return False
    try:
        normalized = expires_at.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized) <= datetime.now(timezone.utc)
    except ValueError:
        return True


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
