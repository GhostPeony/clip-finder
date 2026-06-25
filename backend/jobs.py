"""Supabase-backed ingestion job helpers for hosted mode."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

INGESTION_JOB_SOURCE_TYPES = frozenset({"channel", "playlist", "video", "unknown"})
INGESTION_JOB_STATUSES = frozenset(
    {"queued", "running", "completed", "failed", "partial", "cancelled"}
)
INGESTION_EVENT_LEVELS = frozenset({"info", "warning", "error"})

TERMINAL_JOB_STATUSES = frozenset({"completed", "failed", "partial"})
ACTIVE_JOB_STATUSES = frozenset({"queued", "running"})
CLEARABLE_JOB_STATUSES = TERMINAL_JOB_STATUSES | frozenset({"cancelled"})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def classify_ingestion_event_level(message: str) -> str:
    """Classify a progress message for durable job event storage."""
    stripped = message.strip()
    if stripped.startswith("Error") or "Error indexing:" in stripped:
        return "error"
    if "Skipped:" in stripped:
        return "warning"
    return "info"


def normalize_ingestion_source_type(source_type: Any) -> str:
    """Return a DB-safe ingestion source type."""
    normalized = str(source_type or "").strip().lower()
    if normalized in INGESTION_JOB_SOURCE_TYPES:
        return normalized
    return "unknown"


def validate_ingestion_job_status(status: Any) -> str:
    """Validate an ingestion job status before writing to Postgres."""
    normalized = str(status or "").strip().lower()
    if normalized not in INGESTION_JOB_STATUSES:
        allowed = ", ".join(sorted(INGESTION_JOB_STATUSES))
        raise ValueError(f"Unsupported ingestion job status '{status}'. Use one of: {allowed}")
    return normalized


def validate_ingestion_event_level(level: Any) -> str:
    """Validate an ingestion event level before writing to Postgres."""
    normalized = str(level or "").strip().lower()
    if normalized not in INGESTION_EVENT_LEVELS:
        allowed = ", ".join(sorted(INGESTION_EVENT_LEVELS))
        raise ValueError(f"Unsupported ingestion event level '{level}'. Use one of: {allowed}")
    return normalized


def format_ingestion_error(error: Any) -> str:
    """Return a user-safe ingestion error string from exceptions or API payloads."""
    payload = _exception_payload(error)
    message = str(payload.get("message") or payload.get("error") or error).strip()
    details = str(payload.get("details") or "").strip()
    combined = f"{message} {details}".lower()

    if "violates check constraint" in combined:
        return (
            "Database schema rejected an internal import value. "
            "The import was stopped before saving inconsistent access metadata."
        )
    if message.startswith("{'message':") or message.startswith('{"message":'):
        return "Database rejected the import metadata. Please retry after the latest deployment."
    return message or "Unknown ingestion error"


def _exception_payload(error: Any) -> dict:
    if isinstance(error, dict):
        return error
    for attr in ("message", "details", "hint", "code"):
        value = getattr(error, attr, None)
        if value:
            return {"message": value}
    args = getattr(error, "args", ())
    if args and isinstance(args[0], dict):
        return args[0]
    return {}


def extract_ingestion_event_reason(message: str) -> str | None:
    """Extract stable skip/error reason from an ingestion progress message."""
    match = re.search(r"(?:Skipped|Error indexing):\s*([a-zA-Z0-9_ -]+?)(?:\s*\||$)", message)
    if not match:
        return None
    reason = match.group(1).strip().lower().replace(" ", "_").replace("-", "_")
    return reason or None


def summarize_ingestion_messages(messages: list[str]) -> dict:
    """Summarize user-visible ingest messages into durable job counters."""
    summary = {
        "requested_video_count": 0,
        "indexed_video_count": 0,
        "skipped_video_count": 0,
        "failed_video_count": 0,
        "status": "completed",
    }

    for message in messages:
        found_match = re.search(r"Found\s+(\d+)\s+videos?", message, flags=re.IGNORECASE)
        new_match = re.search(r"(\d+)\s+new videos? to index", message, flags=re.IGNORECASE)
        if new_match:
            summary["requested_video_count"] = int(new_match.group(1))
        elif found_match and not summary["requested_video_count"]:
            summary["requested_video_count"] = int(found_match.group(1))

        if (
            "Indexed" in message and "clips" in message
        ) or "Reused existing indexed video" in message:
            summary["indexed_video_count"] += 1
        if "Skipped:" in message:
            summary["skipped_video_count"] += 1
        if "Error indexing:" in message or "Error scanning" in message:
            summary["failed_video_count"] += 1

    if (
        summary["failed_video_count"]
        and not summary["indexed_video_count"]
        and not summary["skipped_video_count"]
    ):
        summary["status"] = "failed"
    elif summary["skipped_video_count"] or summary["failed_video_count"]:
        summary["status"] = "partial"

    return summary


def failed_ingestion_fields(job: dict | None = None) -> dict[str, int]:
    """Return durable counters for a job that failed before progress was summarized."""
    failed_count = 0
    requested_count = 0
    source_type = ""
    if isinstance(job, dict):
        source_type = normalize_ingestion_source_type(job.get("source_type"))
        try:
            failed_count = int(job.get("failed_video_count") or 0)
        except (TypeError, ValueError):
            failed_count = 0
        try:
            requested_count = int(job.get("requested_video_count") or 0)
        except (TypeError, ValueError):
            requested_count = 0

    fields = {"failed_video_count": max(1, failed_count)}
    if source_type == "video":
        fields["requested_video_count"] = max(1, requested_count)
    return fields


def create_ingestion_job(
    supabase: Any,
    user_id: str,
    source_url: str,
    source_type: str = "unknown",
    cost_estimate: dict | None = None,
) -> dict:
    """Create a queued ingestion job and return the inserted row."""
    payload = {
        "user_id": user_id,
        "source_url": source_url,
        "source_type": normalize_ingestion_source_type(source_type),
        "status": "queued",
    }
    if cost_estimate is not None:
        payload["cost_estimate"] = cost_estimate

    result = supabase.table("ingestion_jobs").insert(payload).execute()
    return (result.data or [{}])[0]


def count_active_ingestion_jobs(supabase: Any, user_id: str) -> int:
    """Return queued/running ingestion jobs for a user."""
    result = (
        supabase.table("ingestion_jobs")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .in_("status", sorted(ACTIVE_JOB_STATUSES))
        .execute()
    )
    return result.count or 0


def update_ingestion_job(
    supabase: Any,
    job_id: str,
    **fields: Any,
) -> dict:
    """Patch an ingestion job and return the updated row."""
    if "status" in fields:
        fields["status"] = validate_ingestion_job_status(fields["status"])
        if fields["status"] in TERMINAL_JOB_STATUSES:
            fields.setdefault("completed_at", utc_now())

    result = supabase.table("ingestion_jobs").update(fields).eq("id", job_id).execute()
    return (result.data or [{}])[0]


def record_ingestion_job_event(
    supabase: Any,
    job_id: str,
    level: str,
    message: str,
    video_id: str | None = None,
    reason: str | None = None,
) -> dict:
    """Record a user-visible ingestion event."""
    payload = {
        "job_id": job_id,
        "level": validate_ingestion_event_level(level),
        "message": message,
    }
    if video_id:
        payload["youtube_video_id"] = video_id
    if reason:
        payload["reason"] = reason

    result = supabase.table("ingestion_job_events").insert(payload).execute()
    return (result.data or [{}])[0]


def list_ingestion_jobs(supabase: Any, user_id: str, limit: int = 20) -> list[dict]:
    """List recent ingestion jobs scoped to a user."""
    result = (
        supabase.table("ingestion_jobs")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


def get_ingestion_job(supabase: Any, user_id: str, job_id: str) -> dict | None:
    """Fetch one ingestion job with events, scoped to a user."""
    result = (
        supabase.table("ingestion_jobs")
        .select("*, ingestion_job_events(*)")
        .eq("id", job_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    return result.data


def clear_ingestion_job_history(supabase: Any, user_id: str) -> int:
    """Delete settled ingestion jobs for a user and leave active jobs untouched."""
    result = (
        supabase.table("ingestion_jobs")
        .delete()
        .eq("user_id", user_id)
        .in_("status", sorted(CLEARABLE_JOB_STATUSES))
        .execute()
    )
    return len(result.data or [])
