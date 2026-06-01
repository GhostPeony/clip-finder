"""
db.py - Supabase database client and auth utilities

Provides:
- Supabase client singleton (service role for backend operations)
- JWT validation middleware for FastAPI
- Quota checking helpers
"""

import os
import base64
import hashlib
from datetime import date

from dotenv import load_dotenv
from supabase import create_client, Client
from jose import jwt, JWTError
from fastapi import HTTPException, Header
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken

# Load environment
env_path = os.path.join(os.path.dirname(__file__), '..', '.env.local')
load_dotenv(env_path)

SUPABASE_URL = os.getenv("VITE_SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
API_KEY_ENCRYPTION_KEY = os.getenv("API_KEY_ENCRYPTION_KEY", "")

# Free tier limits
FREE_SEARCHES_PER_DAY = 20
FREE_INDEXES_PER_MONTH = 50

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

    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated"
        )
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


def get_user_profile(supabase: Client, user_id: str) -> dict:
    """Fetch user profile, resetting quotas if a new day/month has started."""
    result = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
    profile = result.data

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    today = date.today().isoformat()
    updates = {}

    # Reset daily search counter if new day
    if str(profile.get("last_search_reset", "")) != today:
        updates["free_searches_today"] = 0
        updates["last_search_reset"] = today

    # Reset monthly index counter if new month
    current_month = date.today().replace(day=1).isoformat()
    if str(profile.get("last_index_reset", "")) != current_month:
        updates["free_indexes_this_month"] = 0
        updates["last_index_reset"] = current_month

    if updates:
        supabase.table("profiles").update(updates).eq("id", user_id).execute()
        profile.update(updates)

    return profile


def check_search_quota(profile: dict) -> bool:
    """Check if user can perform a search. Returns True if allowed."""
    if profile.get("api_key_enc"):
        return True  # BYOK users have no limits
    return profile.get("free_searches_today", 0) < FREE_SEARCHES_PER_DAY


def check_index_quota(profile: dict, video_count: int) -> bool:
    """Check if user can index N videos. Returns True if allowed."""
    if profile.get("api_key_enc"):
        return True  # BYOK users have no limits
    remaining = FREE_INDEXES_PER_MONTH - profile.get("free_indexes_this_month", 0)
    return remaining >= video_count


def increment_search_usage(supabase: Client, user_id: str, used_own_key: bool):
    """Increment search counter and log usage."""
    if not used_own_key:
        # Fetch current count and increment
        profile = supabase.table("profiles").select("free_searches_today").eq("id", user_id).single().execute()
        current = profile.data.get("free_searches_today", 0) if profile.data else 0
        supabase.table("profiles").update({
            "free_searches_today": current + 1
        }).eq("id", user_id).execute()

    supabase.table("usage_logs").insert({
        "user_id": user_id,
        "action": "search",
        "used_own_key": used_own_key
    }).execute()


def increment_index_usage(supabase: Client, user_id: str, video_count: int, used_own_key: bool):
    """Increment index counter and log usage."""
    if not used_own_key:
        profile = supabase.table("profiles").select("free_indexes_this_month").eq("id", user_id).single().execute()
        current = profile.data.get("free_indexes_this_month", 0) if profile.data else 0
        supabase.table("profiles").update({
            "free_indexes_this_month": current + video_count
        }).eq("id", user_id).execute()

    supabase.table("usage_logs").insert({
        "user_id": user_id,
        "action": "index",
        "video_count": video_count,
        "used_own_key": used_own_key
    }).execute()


def get_user_api_key(supabase: Client, user_id: str) -> Optional[str]:
    """Get the user's decrypted API key, or None if not set."""
    profile = supabase.table("profiles").select("api_key_enc").eq("id", user_id).single().execute()
    if profile.data:
        encrypted_value = profile.data.get("api_key_enc")
        return decrypt_api_key(encrypted_value) if encrypted_value else None
    return None
