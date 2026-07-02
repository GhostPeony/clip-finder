"""Runtime configuration helpers for Memexai."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env.local")
load_dotenv(ENV_PATH)

SUPABASE_STORAGE = "supabase"

NO_AUTH = "none"
SUPABASE_AUTH = "supabase"

DEFAULT_EMBEDDING_MODEL = "models/gemini-embedding-001"
DEFAULT_EMBEDDING_DIMENSIONS = 768
DEFAULT_LLM_MODEL = "gemini-3.1-flash-lite"
DEFAULT_FREE_SEARCHES_PER_MONTH = 100
DEFAULT_FREE_INDEXED_VIDEOS_TOTAL = 15
DEFAULT_FREE_INDEXED_TRANSCRIPT_SECONDS_TOTAL = 18_000
DEFAULT_FREE_MAX_IMPORT_VIDEOS = 10
DEFAULT_FREE_MAX_SEARCH_RESULTS = 5
DEFAULT_FREE_MAX_ACTIVE_INGESTION_JOBS = 1
DEFAULT_STRIPE_PLUS_MONTHLY_LOOKUP_KEY = "memexai_plus_monthly_v1"
DEFAULT_STRIPE_PLUS_ANNUAL_LOOKUP_KEY = "memexai_plus_annual_v1"
DEFAULT_STRIPE_PRO_MONTHLY_LOOKUP_KEY = "memexai_pro_monthly_v1"
DEFAULT_STRIPE_PRO_ANNUAL_LOOKUP_KEY = "memexai_pro_annual_v1"
DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]

API_KEY_SERVER = "server"
API_KEY_BYOK = "byok"
API_KEY_HYBRID = "hybrid"

INGESTION_DISPATCH_BACKGROUND = "background"
INGESTION_DISPATCH_CLOUDFLARE_QUEUE = "cloudflare_queue"


def _normalized_env(name: str, default: str) -> str:
    return os.getenv(name, default).strip().lower()


def _positive_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc

    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def get_storage_mode() -> str:
    """Return the configured storage mode."""
    mode = _normalized_env("SEARCHTUBE_STORAGE", SUPABASE_STORAGE)
    if mode != SUPABASE_STORAGE:
        raise ValueError("SEARCHTUBE_STORAGE must be 'supabase'; local Chroma mode was removed")
    return mode


def get_auth_mode() -> str:
    """Return the effective auth mode."""
    configured = _normalized_env("SEARCHTUBE_AUTH_MODE", SUPABASE_AUTH)
    if configured not in {NO_AUTH, SUPABASE_AUTH}:
        raise ValueError("SEARCHTUBE_AUTH_MODE must be 'none' or 'supabase'")
    return configured


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


def get_free_searches_per_month() -> int:
    return _positive_int_env("FREE_SEARCHES_PER_MONTH", DEFAULT_FREE_SEARCHES_PER_MONTH)


def get_free_indexed_videos_total() -> int:
    return _positive_int_env("FREE_INDEXED_VIDEOS_TOTAL", DEFAULT_FREE_INDEXED_VIDEOS_TOTAL)


def get_free_indexed_transcript_seconds_total() -> int:
    return _positive_int_env(
        "FREE_INDEXED_TRANSCRIPT_SECONDS_TOTAL",
        DEFAULT_FREE_INDEXED_TRANSCRIPT_SECONDS_TOTAL,
    )


def get_free_max_import_videos() -> int:
    return _positive_int_env("FREE_MAX_IMPORT_VIDEOS", DEFAULT_FREE_MAX_IMPORT_VIDEOS)


def get_free_max_search_results() -> int:
    return _positive_int_env("FREE_MAX_SEARCH_RESULTS", DEFAULT_FREE_MAX_SEARCH_RESULTS)


def get_free_max_active_ingestion_jobs() -> int:
    return _positive_int_env(
        "FREE_MAX_ACTIVE_INGESTION_JOBS",
        DEFAULT_FREE_MAX_ACTIVE_INGESTION_JOBS,
    )


def get_stripe_secret_key() -> str | None:
    secret_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    return secret_key or None


def get_stripe_webhook_secret() -> str | None:
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
    return webhook_secret or None


def get_stripe_success_url() -> str:
    configured = os.getenv("STRIPE_SUCCESS_URL", "").strip()
    if configured:
        return configured
    app_url = get_public_app_url("http://localhost:5173")
    return f"{app_url}/?billing=success"


def get_stripe_cancel_url() -> str:
    configured = os.getenv("STRIPE_CANCEL_URL", "").strip()
    if configured:
        return configured
    app_url = get_public_app_url("http://localhost:5173")
    return f"{app_url}/?billing=cancelled"


def get_stripe_portal_return_url() -> str:
    configured = os.getenv("STRIPE_PORTAL_RETURN_URL", "").strip()
    if configured:
        return configured
    app_url = get_public_app_url("http://localhost:5173")
    return f"{app_url}/?settings=billing"


def get_stripe_price_lookup_keys() -> dict[str, str]:
    return {
        "plus_monthly": os.getenv(
            "STRIPE_PLUS_MONTHLY_LOOKUP_KEY",
            DEFAULT_STRIPE_PLUS_MONTHLY_LOOKUP_KEY,
        ).strip(),
        "plus_annual": os.getenv(
            "STRIPE_PLUS_ANNUAL_LOOKUP_KEY",
            DEFAULT_STRIPE_PLUS_ANNUAL_LOOKUP_KEY,
        ).strip(),
        "pro_monthly": os.getenv(
            "STRIPE_PRO_MONTHLY_LOOKUP_KEY",
            DEFAULT_STRIPE_PRO_MONTHLY_LOOKUP_KEY,
        ).strip(),
        "pro_annual": os.getenv(
            "STRIPE_PRO_ANNUAL_LOOKUP_KEY",
            DEFAULT_STRIPE_PRO_ANNUAL_LOOKUP_KEY,
        ).strip(),
    }


def get_promo_trial_codes() -> dict[str, dict]:
    """Parse PROMO_TRIAL_CODES entries of the form ``code:plan:days``.

    Example: ``PROMO_TRIAL_CODES=producthunt:plus:14,launchweek:pro:7``.
    Codes are matched case-insensitively; malformed entries are skipped so a
    config typo cannot take down checkout.
    """
    raw_value = os.getenv("PROMO_TRIAL_CODES", "").strip()
    codes: dict[str, dict] = {}
    if not raw_value:
        return codes
    for entry in raw_value.split(","):
        parts = [part.strip() for part in entry.strip().split(":")]
        if len(parts) != 3:
            continue
        code, plan_key, days_raw = parts[0].lower(), parts[1].lower(), parts[2]
        try:
            trial_days = int(days_raw)
        except ValueError:
            continue
        if not code or plan_key not in {"plus", "pro"} or trial_days <= 0:
            continue
        codes[code] = {"code": code, "plan_key": plan_key, "trial_days": trial_days}
    return codes


def get_stripe_price_id_overrides() -> dict[str, str]:
    return {
        key: value
        for key, value in {
            get_stripe_price_lookup_keys()["plus_monthly"]: os.getenv(
                "STRIPE_PLUS_MONTHLY_PRICE_ID", ""
            ).strip(),
            get_stripe_price_lookup_keys()["plus_annual"]: os.getenv(
                "STRIPE_PLUS_ANNUAL_PRICE_ID", ""
            ).strip(),
            get_stripe_price_lookup_keys()["pro_monthly"]: os.getenv(
                "STRIPE_PRO_MONTHLY_PRICE_ID", ""
            ).strip(),
            get_stripe_price_lookup_keys()["pro_annual"]: os.getenv(
                "STRIPE_PRO_ANNUAL_PRICE_ID", ""
            ).strip(),
        }.items()
        if value
    }


def get_allowed_origins() -> list[str]:
    """Return comma-separated CORS origins for the API."""
    raw_value = os.getenv("SEARCHTUBE_ALLOWED_ORIGINS", "").strip()
    if not raw_value:
        return DEFAULT_ALLOWED_ORIGINS

    origins = [origin.strip().rstrip("/") for origin in raw_value.split(",") if origin.strip()]
    if not origins:
        raise ValueError("SEARCHTUBE_ALLOWED_ORIGINS must include at least one origin")
    return origins


def get_public_app_url(fallback: str | None = None) -> str:
    """Return the browser app URL used for auth handoffs."""
    configured = (
        os.getenv("MEMEXAI_APP_URL", "").strip()
        or os.getenv("PUBLIC_APP_URL", "").strip()
        or os.getenv("SEARCHTUBE_APP_URL", "").strip()
    )
    return (configured or fallback or "").rstrip("/")


def get_server_api_key() -> str | None:
    """Return the configured server-side Gemini API key, if usable."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "PLACEHOLDER_API_KEY":
        return None
    return api_key


def get_api_key_mode() -> str:
    """Return how hosted mode should resolve Gemini API keys."""
    mode = _normalized_env("SEARCHTUBE_API_KEY_MODE", API_KEY_SERVER)
    if mode not in {API_KEY_SERVER, API_KEY_BYOK, API_KEY_HYBRID}:
        raise ValueError("SEARCHTUBE_API_KEY_MODE must be 'server', 'byok', or 'hybrid'")
    return mode


def allow_user_keys() -> bool:
    return get_api_key_mode() in {API_KEY_BYOK, API_KEY_HYBRID}


def get_ingestion_dispatch_mode() -> str:
    """Return how hosted background ingestion jobs should be dispatched."""
    mode = _normalized_env("INGESTION_DISPATCH_MODE", INGESTION_DISPATCH_BACKGROUND)
    if mode not in {INGESTION_DISPATCH_BACKGROUND, INGESTION_DISPATCH_CLOUDFLARE_QUEUE}:
        raise ValueError("INGESTION_DISPATCH_MODE must be 'background' or 'cloudflare_queue'")
    return mode


def get_cloudflare_queue_api_url() -> str:
    """Build the Cloudflare Queue HTTP producer URL from env configuration."""
    explicit_url = os.getenv("CLOUDFLARE_INGESTION_QUEUE_API_URL", "").strip()
    if explicit_url:
        return explicit_url

    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    queue_id = os.getenv("CLOUDFLARE_INGESTION_QUEUE_ID", "").strip()
    if not account_id or not queue_id:
        raise ValueError(
            "CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_INGESTION_QUEUE_ID are required "
            "when INGESTION_DISPATCH_MODE=cloudflare_queue"
        )
    return f"https://api.cloudflare.com/client/v4/accounts/{account_id}/queues/{queue_id}/messages"


def _cloudflare_queue_action_url(action: str) -> str:
    explicit_url = os.getenv(f"CLOUDFLARE_INGESTION_QUEUE_{action.upper()}_API_URL", "").strip()
    if explicit_url:
        return explicit_url

    messages_url = get_cloudflare_queue_api_url().rstrip("/")
    return f"{messages_url}/{action}"


def get_cloudflare_queue_pull_api_url() -> str:
    """Build the Cloudflare Queue HTTP pull-consumer URL."""
    return _cloudflare_queue_action_url("pull")


def get_cloudflare_queue_ack_api_url() -> str:
    """Build the Cloudflare Queue HTTP acknowledge/retry URL."""
    return _cloudflare_queue_action_url("ack")


def get_cloudflare_queue_api_token() -> str:
    """Return the Cloudflare API token used for direct Queue publishing."""
    token = os.getenv("CLOUDFLARE_QUEUES_API_TOKEN", "").strip()
    if not token:
        raise ValueError(
            "CLOUDFLARE_QUEUES_API_TOKEN is required when INGESTION_DISPATCH_MODE=cloudflare_queue"
        )
    return token


def get_workflow_internal_secret() -> str | None:
    """Return the shared secret used by Cloudflare Workflows internal calls."""
    secret = os.getenv("WORKFLOW_INTERNAL_SECRET", "").strip()
    return secret or None


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
