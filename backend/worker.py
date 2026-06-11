"""Synchronous ingestion job runner for future Queue/Container consumers."""

from __future__ import annotations

from typing import Optional

try:
    from .jobs import (
        classify_ingestion_event_level,
        extract_ingestion_event_reason,
        record_ingestion_job_event,
        summarize_ingestion_messages,
        update_ingestion_job,
        utc_now,
    )
    from .storage import ingest_url
except ImportError:
    from jobs import (
        classify_ingestion_event_level,
        extract_ingestion_event_reason,
        record_ingestion_job_event,
        summarize_ingestion_messages,
        update_ingestion_job,
        utc_now,
    )
    from storage import ingest_url


def process_ingestion_job(supabase, job: dict, api_key: Optional[str] = None) -> dict:
    """
    Process one queued ingestion job.

    This runner is intentionally platform-neutral so it can be called from a
    local script, a container worker, or a future Cloudflare Queue consumer.
    """
    job_id = job["id"]
    user_id = job["user_id"]
    source_url = job["source_url"]
    messages: list[str] = []

    try:
        update_ingestion_job(
            supabase,
            job_id,
            status="running",
            started_at=utc_now(),
            last_message="Starting ingestion",
        )

        for message in ingest_url(source_url, user_id, api_key):
            messages.append(message)
            record_ingestion_job_event(
                supabase,
                job_id,
                classify_ingestion_event_level(message),
                message,
                reason=extract_ingestion_event_reason(message),
            )
            update_ingestion_job(supabase, job_id, last_message=message)

        summary = summarize_ingestion_messages(messages)
        update_ingestion_job(
            supabase,
            job_id,
            requested_video_count=summary["requested_video_count"],
            indexed_video_count=summary["indexed_video_count"],
            skipped_video_count=summary["skipped_video_count"],
            failed_video_count=summary["failed_video_count"],
            status=summary["status"],
            last_message=messages[-1] if messages else "Complete",
        )
        return summary
    except Exception as exc:
        error_message = f"Error: {str(exc)}"
        update_ingestion_job(
            supabase,
            job_id,
            status="failed",
            error=str(exc),
            last_message=error_message,
        )
        record_ingestion_job_event(supabase, job_id, "error", error_message)
        raise
