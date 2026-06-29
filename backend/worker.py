"""Synchronous ingestion job runner for future Queue/Container consumers."""

from __future__ import annotations

from typing import Optional

try:
    from .brain_sync import queue_brain_sync_event
    from .digest_depth import DEFAULT_DIGEST_DEPTH, normalize_digest_depth
    from .jobs import (
        classify_ingestion_event_level,
        extract_ingestion_event_reason,
        failed_ingestion_fields,
        record_ingestion_job_event,
        summarize_ingestion_messages,
        update_ingestion_job,
        utc_now,
    )
    from .projects import add_videos_to_project
    from .storage import ingest_url
    from .youtube_utils import detect_url_type
except ImportError:
    from brain_sync import queue_brain_sync_event
    from digest_depth import DEFAULT_DIGEST_DEPTH, normalize_digest_depth
    from jobs import (
        classify_ingestion_event_level,
        extract_ingestion_event_reason,
        failed_ingestion_fields,
        record_ingestion_job_event,
        summarize_ingestion_messages,
        update_ingestion_job,
        utc_now,
    )
    from projects import add_videos_to_project
    from storage import ingest_url
    from youtube_utils import detect_url_type


def process_ingestion_job(
    supabase,
    job: dict,
    api_key: Optional[str] = None,
    used_own_key: bool = False,
) -> dict:
    """
    Process one queued ingestion job.

    This runner is intentionally platform-neutral so it can be called from a
    local script, a container worker, or a future Cloudflare Queue consumer.
    """
    job_id = job["id"]
    user_id = job["user_id"]
    source_url = job["source_url"]
    digest_depth = _job_digest_depth(job)
    messages: list[str] = []

    try:
        update_ingestion_job(
            supabase,
            job_id,
            status="running",
            started_at=utc_now(),
            last_message="Starting ingestion",
        )

        for message in ingest_url(source_url, user_id, api_key, used_own_key, digest_depth):
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
        completed_job = update_ingestion_job(
            supabase,
            job_id,
            requested_video_count=summary["requested_video_count"],
            indexed_video_count=summary["indexed_video_count"],
            skipped_video_count=summary["skipped_video_count"],
            failed_video_count=summary["failed_video_count"],
            status=summary["status"],
            last_message=messages[-1] if messages else "Complete",
        )
        _sync_capture_item_status(supabase, job_id, summary)
        _assign_agent_ingestion_to_project(supabase, job, summary)
        _queue_video_ingested_event(
            supabase,
            user_id,
            job,
            summary,
            completed_job,
            digest_depth,
            used_own_key,
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
            **failed_ingestion_fields(job),
        )
        _mark_capture_item_failed(supabase, job_id, "ingestion_failed")
        record_ingestion_job_event(supabase, job_id, "error", error_message)
        raise


def _job_digest_depth(job: dict) -> str:
    """Read the digest depth stored in the job estimate payload."""
    cost_estimate = job.get("cost_estimate")
    if isinstance(cost_estimate, dict):
        return normalize_digest_depth(cost_estimate.get("digestDepth"))
    return DEFAULT_DIGEST_DEPTH


def _sync_capture_item_status(supabase, job_id: str, summary: dict) -> None:
    """Mirror a settled ingestion job onto any playlist capture item that queued it."""
    if int(summary.get("indexed_video_count") or 0) > 0:
        status = "indexed"
        skip_reason = None
    elif int(summary.get("failed_video_count") or 0) > 0:
        status = "failed"
        skip_reason = "ingestion_failed"
    elif int(summary.get("skipped_video_count") or 0) > 0:
        status = "skipped"
        skip_reason = "captions_unavailable"
    else:
        status = "indexed"
        skip_reason = None

    try:
        supabase.table("youtube_capture_items").update(
            {
                "status": status,
                "skip_reason": skip_reason,
                "updated_at": utc_now(),
            }
        ).eq("ingestion_job_id", job_id).execute()
        if status == "indexed":
            _assign_indexed_capture_item_to_project(supabase, job_id)
    except Exception as exc:  # noqa: BLE001 - capture status should not break ingestion.
        print(f"[CAPTURE] Failed to sync capture item status for job {job_id}: {exc}")


def _assign_indexed_capture_item_to_project(supabase, job_id: str) -> None:
    """Attach a successfully indexed capture item to its source project, if configured."""
    try:
        item_result = (
            supabase.table("youtube_capture_items")
            .select("id, user_id, capture_source_id, youtube_video_id")
            .eq("ingestion_job_id", job_id)
            .limit(1)
            .execute()
        )
        items = item_result.data or []
        item = items[0] if items else {}
        capture_source_id = str(item.get("capture_source_id") or "")
        youtube_video_id = str(item.get("youtube_video_id") or "")
        user_id = str(item.get("user_id") or "")
        if not capture_source_id or not youtube_video_id or not user_id:
            return
        source_result = (
            supabase.table("youtube_capture_sources")
            .select("id, project_id")
            .eq("id", capture_source_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        sources = source_result.data or []
        project_id = str((sources[0] if sources else {}).get("project_id") or "")
        if not project_id:
            return
        add_videos_to_project(
            supabase,
            user_id,
            project_id,
            youtube_video_ids=[youtube_video_id],
            added_source="capture_sync",
            capture_source_id=capture_source_id,
        )
    except Exception as exc:  # noqa: BLE001 - project assignment must not break ingestion.
        print(f"[CAPTURE] Failed to assign indexed item to project for job {job_id}: {exc}")


def _assign_agent_ingestion_to_project(supabase, job: dict, summary: dict) -> None:
    """Attach a successful agent-queued single-video ingestion to its requested project."""
    if int(summary.get("indexed_video_count") or 0) <= 0:
        return

    cost_estimate = job.get("cost_estimate")
    mcp_context = cost_estimate.get("mcp") if isinstance(cost_estimate, dict) else None
    requested_project = (
        mcp_context.get("requestedProject") if isinstance(mcp_context, dict) else None
    )
    project_id = str((requested_project or {}).get("id") or "").strip()
    if not project_id:
        return

    job_id = str(job.get("id") or "").strip()
    user_id = str(job.get("user_id") or "").strip()
    source_url = str(job.get("source_url") or "").strip()
    source_type, youtube_video_id = detect_url_type(source_url)
    if source_type != "video" or not youtube_video_id or not user_id:
        return

    try:
        result = add_videos_to_project(
            supabase,
            user_id,
            project_id,
            youtube_video_ids=[youtube_video_id],
            added_source="agent",
        )
        if job_id and int(result.get("addedCount") or 0) > 0:
            project_name = str((requested_project or {}).get("name") or project_id)
            record_ingestion_job_event(
                supabase,
                job_id,
                "info",
                f"Assigned indexed video to project {project_name}.",
                video_id=youtube_video_id,
            )
    except Exception as exc:  # noqa: BLE001 - project assignment must not break ingestion.
        print(f"[MCP] Failed to assign agent ingestion job {job_id} to project: {exc}")


def _mark_capture_item_failed(supabase, job_id: str, skip_reason: str) -> None:
    try:
        supabase.table("youtube_capture_items").update(
            {
                "status": "failed",
                "skip_reason": skip_reason,
                "updated_at": utc_now(),
            }
        ).eq("ingestion_job_id", job_id).execute()
    except Exception as exc:  # noqa: BLE001 - capture status should not hide job failure.
        print(f"[CAPTURE] Failed to mark capture item failed for job {job_id}: {exc}")


def _queue_video_ingested_event(
    supabase,
    user_id: str,
    job: dict,
    summary: dict,
    completed_job: dict,
    digest_depth: str,
    used_own_key: bool,
) -> None:
    if int(summary.get("indexed_video_count") or 0) <= 0:
        return

    job_id = str(job.get("id") or completed_job.get("id") or "").strip()
    source_url = str(job.get("source_url") or "").strip()
    source_type = str(job.get("source_type") or "unknown").strip() or "unknown"
    try:
        queue_brain_sync_event(
            supabase,
            user_id,
            "video.ingested",
            payload={
                "jobId": job_id or None,
                "sourceUrl": source_url,
                "sourceType": source_type,
                "status": summary.get("status"),
                "requestedVideoCount": summary.get("requested_video_count", 0),
                "indexedVideoCount": summary.get("indexed_video_count", 0),
                "skippedVideoCount": summary.get("skipped_video_count", 0),
                "failedVideoCount": summary.get("failed_video_count", 0),
                "digestDepth": digest_depth,
            },
            source_ref={
                "type": "ingestion_job",
                "id": job_id or None,
                "source_url": source_url,
                "source_type": source_type,
            },
            metadata={"trigger": "ingestion.job.completed", "usedOwnKey": used_own_key},
            idempotency_key=f"video.ingested:{job_id}" if job_id else None,
        )
    except Exception as exc:  # noqa: BLE001 - outbound sync must not break ingestion jobs.
        print(f"[BRAIN_SYNC] Failed to queue video ingested event: {exc}")
