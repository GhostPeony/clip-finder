"""Hosted ingestion processing shared by API and queue consumers."""

from __future__ import annotations

import re
import time

try:
    from .config import (
        API_KEY_BYOK,
        API_KEY_HYBRID,
        API_KEY_SERVER,
        get_api_key_mode,
        get_server_api_key,
    )
    from .db import decrypt_api_key, get_supabase, get_user_profile
    from .jobs import (
        failed_ingestion_fields,
        record_ingestion_job_event,
        update_ingestion_job,
        utc_now,
    )
    from .storage import is_supabase_mode
    from .worker import process_ingestion_job
except ImportError:
    from config import (
        API_KEY_BYOK,
        API_KEY_HYBRID,
        API_KEY_SERVER,
        get_api_key_mode,
        get_server_api_key,
    )
    from db import decrypt_api_key, get_supabase, get_user_profile
    from jobs import (
        failed_ingestion_fields,
        record_ingestion_job_event,
        update_ingestion_job,
        utc_now,
    )
    from storage import is_supabase_mode
    from worker import process_ingestion_job


def get_profile_api_key(profile: dict) -> tuple[str | None, bool]:
    """Resolve the stored BYOK value from a Supabase profile."""
    stored_key = profile.get("api_key_enc")
    if not stored_key:
        return None, False
    return decrypt_api_key(stored_key), True


def resolve_api_key(
    profile: dict | None = None, x_api_key: str | None = None
) -> tuple[str | None, bool]:
    """Resolve Gemini credentials according to the configured hosted key mode."""
    server_key = get_server_api_key()
    stored_key = None
    has_stored_key = False
    if profile:
        stored_key, has_stored_key = get_profile_api_key(profile)

    mode = get_api_key_mode()
    if mode == API_KEY_SERVER:
        return server_key, False
    if mode == API_KEY_HYBRID:
        if has_stored_key:
            return stored_key, True
        if x_api_key:
            return x_api_key, True
        return server_key, False
    if mode == API_KEY_BYOK:
        if has_stored_key:
            return stored_key, True
        return x_api_key, bool(x_api_key)

    raise ValueError("Invalid API key mode")


MAX_RATE_LIMIT_RETRIES = 3
MAX_SEQUENTIAL_CHAIN_JOBS = 10


def process_hosted_ingestion_job(job: dict, chain_remaining: bool = True) -> dict | None:
    """Process a queued hosted ingestion job from background or queue contexts."""
    if not is_supabase_mode():
        return None

    supabase = get_supabase()
    job_id = job.get("id")
    user_id = job.get("user_id")
    if not isinstance(job_id, str) or not isinstance(user_id, str):
        print("[WARN] Cannot process malformed ingestion job")
        return None

    entered_worker = False
    try:
        profile = get_user_profile(supabase, user_id)
        api_key, used_own_key = resolve_api_key(profile)
        entered_worker = True
        result = _process_with_rate_limit_retries(supabase, job, api_key, used_own_key)
        if chain_remaining:
            _process_next_queued_jobs(supabase, user_id, job_id, api_key, used_own_key)
        return result
    except Exception as exc:  # noqa: BLE001 - background jobs should fail durably.
        if not entered_worker:
            try:
                update_ingestion_job(
                    supabase,
                    job_id,
                    status="failed",
                    error=str(exc),
                    last_message=f"Error: {str(exc)}",
                    **failed_ingestion_fields(job),
                )
                record_ingestion_job_event(supabase, job_id, "error", f"Error: {str(exc)}")
            except Exception as job_err:  # noqa: BLE001
                print(f"[WARN] Failed to mark hosted ingestion job failed: {job_err}")
        print(f"[WARN] Hosted ingestion job {job_id} failed: {exc}")
        raise


def _process_with_rate_limit_retries(
    supabase,
    job: dict,
    api_key: str | None,
    used_own_key: bool,
) -> dict:
    job_id = job["id"]
    for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
        try:
            result = process_ingestion_job(supabase, job, api_key, used_own_key)
            rate_limit_message = _rate_limit_failure_message(supabase, job_id, result)
            if rate_limit_message and attempt < MAX_RATE_LIMIT_RETRIES:
                _requeue_rate_limited_job(
                    supabase, job_id, RuntimeError(rate_limit_message), attempt
                )
                job = {**job, "status": "queued", "started_at": utc_now()}
                continue
            return result
        except Exception as exc:
            if not _is_rate_limit_error(exc) or attempt >= MAX_RATE_LIMIT_RETRIES:
                raise
            _requeue_rate_limited_job(supabase, job_id, exc, attempt)
            job = {**job, "status": "queued", "started_at": utc_now()}

    raise RuntimeError("Rate limit retry loop exited unexpectedly")


def _process_next_queued_jobs(
    supabase,
    user_id: str,
    completed_job_id: str,
    api_key: str | None,
    used_own_key: bool,
) -> None:
    processed_count = 0
    seen_job_ids = {completed_job_id}
    while processed_count < MAX_SEQUENTIAL_CHAIN_JOBS:
        next_job = _next_queued_job(supabase, user_id, seen_job_ids)
        if not next_job:
            return
        next_job_id = str(next_job.get("id") or "")
        seen_job_ids.add(next_job_id)
        processed_count += 1
        try:
            _process_with_rate_limit_retries(supabase, next_job, api_key, used_own_key)
        except Exception as exc:  # noqa: BLE001 - one failed queued job must not hide later jobs.
            print(f"[WARN] Sequential ingestion job {next_job_id} failed: {exc}")


def _next_queued_job(supabase, user_id: str, seen_job_ids: set[str]) -> dict | None:
    result = (
        supabase.table("ingestion_jobs")
        .select("*")
        .eq("user_id", user_id)
        .eq("status", "queued")
        .order("created_at", desc=False)
        .limit(10)
        .execute()
    )
    rows = result.data or []
    for row in rows:
        job_id = str(row.get("id") or "")
        if job_id and job_id not in seen_job_ids:
            return row
    return None


def _is_rate_limit_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "resource_exhausted" in message or "rate limit" in message or "429" in message


def _rate_limit_failure_message(supabase, job_id: str, result: dict) -> str | None:
    if str(result.get("status") or "").lower() not in {"failed", "partial"}:
        return None
    if int(result.get("failed_video_count") or 0) <= 0:
        return None

    row = _latest_ingestion_job_row(supabase, job_id)
    message = " ".join(
        str(row.get(field) or "")
        for field in (
            "last_message",
            "error",
        )
    ).strip()
    if not message:
        return None
    return message if _is_rate_limit_error(RuntimeError(message)) else None


def _latest_ingestion_job_row(supabase, job_id: str) -> dict:
    try:
        result = (
            supabase.table("ingestion_jobs")
            .select("last_message, error")
            .eq("id", job_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001 - retry detection should not mask the job result.
        print(f"[WARN] Failed to inspect ingestion job {job_id} after processing: {exc}")
        return {}
    rows = result.data or []
    return rows[0] if rows else {}


def _requeue_rate_limited_job(supabase, job_id: str, exc: Exception, attempt: int) -> None:
    wait_seconds = _rate_limit_retry_seconds(exc, attempt)
    message = f"Rate limited by model provider. Retrying in {wait_seconds}s."
    update_ingestion_job(
        supabase,
        job_id,
        status="queued",
        error=None,
        completed_at=None,
        failed_video_count=0,
        last_message=message,
    )
    _mark_capture_item_retrying(supabase, job_id)
    record_ingestion_job_event(supabase, job_id, "warning", message, reason="rate_limited")
    time.sleep(wait_seconds)


def _rate_limit_retry_seconds(exc: Exception, attempt: int) -> int:
    message = str(exc)
    match = re.search(r"retry in\s+([0-9.]+)s", message, flags=re.IGNORECASE)
    if match:
        try:
            return max(5, min(90, int(float(match.group(1))) + 2))
        except ValueError:
            pass
    return min(90, 15 * (attempt + 1))


def _mark_capture_item_retrying(supabase, job_id: str) -> None:
    try:
        supabase.table("youtube_capture_items").update(
            {
                "status": "queued",
                "skip_reason": None,
                "updated_at": utc_now(),
            }
        ).eq("ingestion_job_id", job_id).execute()
    except Exception as exc:  # noqa: BLE001 - retry state should not hide job retry.
        print(f"[CAPTURE] Failed to mark capture item retrying for job {job_id}: {exc}")
