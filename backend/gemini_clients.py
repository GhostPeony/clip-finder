"""Shared Gemini client factory plus retry/backoff helpers for ingestion paths.

One cached embeddings factory backs the module-level seams that tests
monkeypatch (`ingest.get_embeddings`, `rag._get_embeddings`,
`knowledge._get_source_index_embeddings`). Retry is deliberately applied only
to batch/background calls (document embedding, knowledge extraction) — the
interactive query-embedding path in search fails fast instead.
"""

from __future__ import annotations

import os
import random
import time
from typing import Any, Callable, Optional, TypeVar

from langchain_google_genai import GoogleGenerativeAIEmbeddings

try:
    from .config import get_embedding_dimensions, get_embedding_model
except ImportError:
    from config import get_embedding_dimensions, get_embedding_model

RETRIEVAL_DOCUMENT_TASK = "RETRIEVAL_DOCUMENT"
RETRIEVAL_QUERY_TASK = "RETRIEVAL_QUERY"

GEMINI_RETRY_ATTEMPTS = 4
GEMINI_RETRY_BASE_DELAY_SECONDS = 1.0
GEMINI_RETRY_JITTER_RATIO = 0.25

RETRYABLE_GEMINI_STATUS_CODES = {408, 429}

_RETRYABLE_MESSAGE_MARKERS = (
    "429",
    "500",
    "502",
    "503",
    "504",
    "rate limit",
    "resource exhausted",
    "resource_exhausted",
    "quota",
    "deadline exceeded",
    "timed out",
    "timeout",
    "temporarily unavailable",
    "service unavailable",
    "internal server error",
    "connection reset",
    "connection aborted",
)

T = TypeVar("T")

# Cache for embedding instances keyed by (api_key, task_type)
_embeddings_cache: dict[tuple[str, str], GoogleGenerativeAIEmbeddings] = {}


def get_embeddings_client(
    api_key: Optional[str] = None,
    task_type: str = RETRIEVAL_DOCUMENT_TASK,
) -> GoogleGenerativeAIEmbeddings:
    """Get a cached embeddings instance for the given API key and task type."""
    key_to_use = api_key or os.getenv("GEMINI_API_KEY")
    if not key_to_use or key_to_use == "PLACEHOLDER_API_KEY":
        raise ValueError(
            "No API key provided. Set GEMINI_API_KEY in .env.local or provide via header."
        )

    cache_key = (key_to_use, task_type)
    if cache_key in _embeddings_cache:
        return _embeddings_cache[cache_key]

    instance = GoogleGenerativeAIEmbeddings(
        model=get_embedding_model(),
        google_api_key=key_to_use,
        task_type=task_type,
        output_dimensionality=get_embedding_dimensions(),
    )
    _embeddings_cache[cache_key] = instance
    return instance


def is_retryable_gemini_error(exc: Exception) -> bool:
    """Return True for transient Gemini/transport failures worth retrying."""
    try:  # google-genai is optional in unit-test environments.
        from google.genai import errors as genai_errors
    except ImportError:
        genai_errors = None
    if genai_errors is not None and isinstance(exc, genai_errors.APIError):
        code = getattr(exc, "code", None)
        if isinstance(code, int):
            return code in RETRYABLE_GEMINI_STATUS_CODES or 500 <= code < 600
        return False

    try:  # httpx backs the google-genai transport.
        import httpx
    except ImportError:
        httpx = None
    if httpx is not None and isinstance(exc, httpx.TransportError):
        return True

    message = str(exc).lower()
    return any(marker in message for marker in _RETRYABLE_MESSAGE_MARKERS)


def call_with_gemini_retry(
    operation: Callable[[], T],
    *,
    description: str = "gemini call",
    attempts: int = GEMINI_RETRY_ATTEMPTS,
    base_delay_seconds: float = GEMINI_RETRY_BASE_DELAY_SECONDS,
    sleep: Callable[[float], Any] = time.sleep,
) -> T:
    """Run a Gemini call with bounded exponential backoff on transient errors.

    Worst case adds roughly eight seconds of backoff, so streaming ingestion
    stalls briefly instead of indefinitely.
    """
    for attempt in range(attempts):
        try:
            return operation()
        except Exception as exc:  # noqa: BLE001 - classification decides whether to retry.
            if attempt >= attempts - 1 or not is_retryable_gemini_error(exc):
                raise
            delay = base_delay_seconds * (2**attempt)
            delay += random.uniform(0, delay * GEMINI_RETRY_JITTER_RATIO)  # noqa: S311 - jitter, not crypto.
            print(
                f"[GEMINI_RETRY] {description} failed "
                f"(attempt {attempt + 1}/{attempts}); retrying in {delay:.1f}s: {exc}"
            )
            sleep(delay)
    raise RuntimeError(f"{description} exhausted retries without raising")  # pragma: no cover
