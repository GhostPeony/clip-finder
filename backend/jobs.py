"""Supabase-backed ingestion job helpers for hosted mode."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

TERMINAL_JOB_STATUSES = {"completed", "failed", "partial"}
ACTIVE_JOB_STATUSES = {"queued", "running"}


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

        if "Indexed" in message and "clips" in message:
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


def create_ingestion_job(
    supabase: Any,
    user_id: str,
    source_url: str,
    source_type: str = "unknown",
) -> dict:
    """Create a queued ingestion job and return the inserted row."""
    result = (
        supabase.table("ingestion_jobs")
        .insert(
            {
                "user_id": user_id,
                "source_url": source_url,
                "source_type": source_type,
                "status": "queued",
            }
        )
        .execute()
    )
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
    if "status" in fields and fields["status"] in TERMINAL_JOB_STATUSES:
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
        "level": level,
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
