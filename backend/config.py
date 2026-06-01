"""Runtime configuration helpers for SearchTube."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env.local")
load_dotenv(ENV_PATH)

LOCAL_STORAGE = "local"
SUPABASE_STORAGE = "supabase"

NO_AUTH = "none"
SUPABASE_AUTH = "supabase"

DEFAULT_EMBEDDING_MODEL = "models/gemini-embedding-001"
DEFAULT_EMBEDDING_DIMENSIONS = 768
DEFAULT_LLM_MODEL = "gemini-3.1-flash-lite"

API_KEY_SERVER = "server"
API_KEY_BYOK = "byok"
API_KEY_HYBRID = "hybrid"


def _normalized_env(name: str, default: str) -> str:
    return os.getenv(name, default).strip().lower()


def get_storage_mode() -> str:
    """Return the configured storage mode."""
    mode = _normalized_env("SEARCHTUBE_STORAGE", LOCAL_STORAGE)
    if mode not in {LOCAL_STORAGE, SUPABASE_STORAGE}:
        raise ValueError("SEARCHTUBE_STORAGE must be 'local' or 'supabase'")
    return mode


def get_auth_mode() -> str:
    """Return the effective auth mode."""
    configured = _normalized_env("SEARCHTUBE_AUTH_MODE", "")
    if configured:
        if configured not in {NO_AUTH, SUPABASE_AUTH}:
            raise ValueError("SEARCHTUBE_AUTH_MODE must be 'none' or 'supabase'")
        return configured
    return SUPABASE_AUTH if get_storage_mode() == SUPABASE_STORAGE else NO_AUTH


def get_embedding_model() -> str:
    return os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL).strip()


def get_embedding_dimensions() -> int:
    raw_value = os.getenv("EMBEDDING_DIMENSIONS", str(DEFAULT_EMBEDDING_DIMENSIONS))
    try:
        dimensions = int(raw_value)
    except ValueError as exc:
        raise ValueError("EMBEDDING_DIMENSIONS must be an integer") from exc

    if dimensions <= 0:
        raise ValueError("EMBEDDING_DIMENSIONS must be positive")
    return dimensions


def get_llm_model() -> str:
    return os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL).strip()


def get_server_api_key() -> str | None:
    """Return the configured server-side Gemini API key, if usable."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "PLACEHOLDER_API_KEY":
        return None
    return api_key


def get_api_key_mode() -> str:
    """Return how hosted mode should resolve Gemini API keys."""
    default = API_KEY_SERVER if get_server_api_key() else API_KEY_BYOK
    mode = _normalized_env("SEARCHTUBE_API_KEY_MODE", default)
    if mode not in {API_KEY_SERVER, API_KEY_BYOK, API_KEY_HYBRID}:
        raise ValueError("SEARCHTUBE_API_KEY_MODE must be 'server', 'byok', or 'hybrid'")
    return mode


def allow_user_keys() -> bool:
    return get_api_key_mode() in {API_KEY_BYOK, API_KEY_HYBRID}


@dataclass(frozen=True)
class PublicConfig:
    storage: str
    authMode: str
    hasServerKey: bool
    apiKeyMode: str
    allowUserKeys: bool


def get_public_config() -> PublicConfig:
    api_key_mode = get_api_key_mode()
    return PublicConfig(
        storage=get_storage_mode(),
        authMode=get_auth_mode(),
        hasServerKey=bool(get_server_api_key()),
        apiKeyMode=api_key_mode,
        allowUserKeys=api_key_mode in {API_KEY_BYOK, API_KEY_HYBRID},
    )
