"""
db.py - Supabase database client and auth utilities

Provides:
- Supabase client singleton (service role for backend operations)
- JWT validation middleware for FastAPI
- Quota checking helpers
"""

import base64
import hashlib
import json
import os
from datetime import date
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv
from fastapi import Header, HTTPException
from jose import JWTError, jwt

from supabase import Client, create_client

try:
    from .config import (
        get_free_indexed_transcript_seconds_total,
        get_free_indexed_videos_total,
        get_free_searches_per_month,
    )
except ImportError:
    from config import (
        get_free_indexed_transcript_seconds_total,
        get_free_indexed_videos_total,
        get_free_searches_per_month,
    )

# Load environment
env_path = os.path.join(os.path.dirname(__file__), "..", ".env.local")
load_dotenv(env_path)

SUPABASE_URL = os.getenv("VITE_SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("VITE_SUPABASE_ANON_KEY", os.getenv("SUPABASE_ANON_KEY", ""))
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
API_KEY_ENCRYPTION_KEY = os.getenv("API_KEY_ENCRYPTION_KEY", "")

# Singleton
_supabase_client: Optional[Client] = None


def _get_fernet() -> Fernet:
    """Build a Fernet cipher from API_KEY_ENCRYPTION_KEY."""
    if not API_KEY_ENCRYPTION_KEY:
        raise HTTPException(
            status_code=500,
            detail="API_KEY_ENCRYPTION_KEY must be set before storing user API keys",
        )

    key_bytes = hashlib.sha256(API_KEY_ENCRYPTION_KEY.encode("utf-8")).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)


def encrypt_api_key(api_key: str) -> str:
    """Encrypt a user-provided API key before writing it to the database."""
    return _get_fernet().encrypt(api_key.encode("utf-8")).decode("utf-8")


def decrypt_api_key(encrypted_value: str) -> str:
    """Decrypt a stored API key, with legacy plaintext fallback."""
    if not encrypted_value:
        return ""

    try:
        return _get_fernet().decrypt(encrypted_value.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        # Backward compatibility for existing plaintext rows created before encryption.
        return encrypted_value


def get_supabase() -> Client:
    """Get Supabase client with service role key (full database access)."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env.local")
    _supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _supabase_client


def _auth_server_user_url() -> str:
    return f"{SUPABASE_URL.rstrip('/')}/auth/v1/user"


def _get_user_from_auth_server(token: str) -> dict | None:
    """Validate a Supabase access token through the Auth server."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return None

    request = Request(
        _auth_server_user_url(),
        headers={
            "Authorization": f"Bearer {token}",
            "apikey": SUPABASE_ANON_KEY,
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=5) as response:  # noqa: S310 - trusted Supabase URL config.
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code in {401, 403}:
            raise HTTPException(status_code=401, detail="Invalid token") from exc
        raise
    except (TimeoutError, URLError, json.JSONDecodeError):
        return None

    user_id = data.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    return {
        "sub": user_id,
        "email": data.get("email"),
        "role": data.get("role", "authenticated"),
        "user_metadata": data.get("user_metadata", {}),
        "app_metadata": data.get("app_metadata", {}),
    }


def _get_user_from_jwt_secret(token: str) -> dict:
    if not SUPABASE_JWT_SECRET:
        raise HTTPException(status_code=500, detail="Supabase token validation is not configured")

    try:
        return jwt.decode(
            token, SUPABASE_JWT_SECRET, algorithms=["HS256"], audience="authenticated"
        )
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}") from e


async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """
    FastAPI dependency: extract and validate user from JWT.

    Usage:
        @app.get("/api/protected")
        async def protected(user: dict = Depends(get_current_user)):
            user_id = user["sub"]
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization.replace("Bearer ", "")

    auth_server_user = _get_user_from_auth_server(token)
    if auth_server_user:
        return auth_server_user

    return _get_user_from_jwt_secret(token)


def get_user_profile(supabase: Client, user_id: str) -> dict:
    """Fetch user profile, resetting rolling quotas when a new period starts."""
    result = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
    profile = result.data

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    updates = {}

    today = date.today().isoformat()
    if str(profile.get("last_search_reset", "")) != today:
        updates["free_searches_today"] = 0
        updates["last_search_reset"] = today

    current_month = date.today().replace(day=1).isoformat()
    if str(profile.get("last_search_month_reset", "")) != current_month:
        updates["free_searches_this_month"] = 0
        updates["last_search_month_reset"] = current_month

    if str(profile.get("last_index_reset", "")) != current_month:
        updates["free_indexes_this_month"] = 0
        updates["last_index_reset"] = current_month

    if updates:
        supabase.table("profiles").update(updates).eq("id", user_id).execute()
        profile.update(updates)

    return profile


def check_search_quota(profile: dict, used_own_key: bool = False) -> bool:
    """Check if a user can perform a hosted search."""
    if used_own_key:
        return True
    return profile.get("free_searches_this_month", 0) < get_free_searches_per_month()


def check_index_quota(profile: dict, video_count: int, transcript_seconds: int = 0) -> bool:
    """Check if a user can add hosted library/indexing usage."""
    video_remaining = get_free_indexed_videos_total() - profile.get("free_indexed_videos_total", 0)
    seconds_remaining = get_free_indexed_transcript_seconds_total() - profile.get(
        "free_indexed_seconds_total", 0
    )
    return video_remaining >= video_count and seconds_remaining >= transcript_seconds


def increment_search_usage(
    supabase: Client,
    user_id: str,
    used_own_key: bool,
    result_limit: int | None = None,
):
    """Increment search counter and log usage."""
    if not used_own_key:
        profile = (
            supabase.table("profiles")
            .select("free_searches_this_month")
            .eq("id", user_id)
            .single()
            .execute()
        )
        current = profile.data.get("free_searches_this_month", 0) if profile.data else 0
        supabase.table("profiles").update({"free_searches_this_month": current + 1}).eq(
            "id", user_id
        ).execute()

    log_payload = {"user_id": user_id, "action": "search", "used_own_key": used_own_key}
    if result_limit is not None:
        log_payload["result_limit"] = result_limit
    supabase.table("usage_logs").insert(log_payload).execute()


def increment_index_usage(
    supabase: Client,
    user_id: str,
    video_count: int,
    used_own_key: bool,
    transcript_seconds: int = 0,
):
    """Increment index counter and log usage."""
    profile = (
        supabase.table("profiles")
        .select("free_indexed_videos_total, free_indexed_seconds_total, free_indexes_this_month")
        .eq("id", user_id)
        .single()
        .execute()
    )
    current_videos = profile.data.get("free_indexed_videos_total", 0) if profile.data else 0
    current_seconds = profile.data.get("free_indexed_seconds_total", 0) if profile.data else 0
    current_monthly_indexes = profile.data.get("free_indexes_this_month", 0) if profile.data else 0
    supabase.table("profiles").update(
        {
            "free_indexed_videos_total": current_videos + video_count,
            "free_indexed_seconds_total": current_seconds + transcript_seconds,
            "free_indexes_this_month": current_monthly_indexes + video_count,
        }
    ).eq("id", user_id).execute()

    supabase.table("usage_logs").insert(
        {
            "user_id": user_id,
            "action": "index",
            "video_count": video_count,
            "transcript_seconds": transcript_seconds,
            "used_own_key": used_own_key,
        }
    ).execute()


def get_user_api_key(supabase: Client, user_id: str) -> Optional[str]:
    """Get the user's decrypted API key, or None if not set."""
    profile = supabase.table("profiles").select("api_key_enc").eq("id", user_id).single().execute()
    if profile.data:
        encrypted_value = profile.data.get("api_key_enc")
        return decrypt_api_key(encrypted_value) if encrypted_value else None
    return None
