"""Workflow runners for YouTube capture source orchestration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

try:
    from .brain_sync import queue_brain_sync_event
    from .capture import sync_playlist_capture_source
    from .config import INGESTION_DISPATCH_BACKGROUND, get_ingestion_dispatch_mode
    from .workflows import (
        create_workflow_instance,
        record_workflow_artifact,
        record_workflow_step,
        update_workflow_instance,
    )
except ImportError:
    from brain_sync import queue_brain_sync_event
    from capture import sync_playlist_capture_source
    from config import INGESTION_DISPATCH_BACKGROUND, get_ingestion_dispatch_mode
    from workflows import (
        create_workflow_instance,
        record_workflow_artifact,
        record_workflow_step,
        update_workflow_instance,
    )


CAPTURE_SYNC_WORKFLOW_KEY = "capture.playlist.sync"
CAPTURE_SYNC_WORKFLOW_VERSION = 1


def run_capture_sync_workflow(
    supabase: Any,
    user_id: str,
    capture_source_id: str,
    max_jobs: int = 1,
    dispatch_job: Callable[[dict], dict | None] | None = None,
    trigger: str = "api.capture.sync",
    created_by: str = "user",
    created_by_client: str | None = None,
) -> dict:
    """Run a capture-source sync as a durable, inspectable platform workflow."""
    instance = create_workflow_instance(
        supabase,
        user_id,
        CAPTURE_SYNC_WORKFLOW_KEY,
        CAPTURE_SYNC_WORKFLOW_VERSION,
        input_payload={
            "capture_source_id": capture_source_id,
            "max_jobs": max(0, int(max_jobs or 0)),
        },
        status="running",
        trigger=trigger,
        created_by=created_by,
        created_by_client=created_by_client,
        metadata={
            "coordinator": "hosted-python",
            "cloudflare_ready": True,
        },
    )
    instance_id = instance["id"]

    try:
        update_workflow_instance(
            supabase,
            instance_id,
            status="running",
            current_step="sync_capture_source",
        )
        record_workflow_step(
            supabase,
            instance_id,
            "sync_capture_source",
            "running",
            input_ref={"capture_source_id": capture_source_id},
        )
        sync_result = sync_playlist_capture_source(
            supabase,
            user_id,
            capture_source_id,
            max_jobs,
        )
        record_workflow_step(
            supabase,
            instance_id,
            "sync_capture_source",
            "completed",
            output_ref={
                "capture_source_id": capture_source_id,
                "new_item_ids": _ids(sync_result.get("newItems", [])),
                "queued_item_ids": _ids(sync_result.get("queuedItems", [])),
            },
            metrics={
                "discovered_count": sync_result.get("discoveredCount", 0),
                "new_item_count": sync_result.get("newItemCount", 0),
                "queue_candidate_count": sync_result.get("queueCandidateCount", 0),
                "remaining_queue_count": sync_result.get("remainingQueueCount", 0),
                "skipped_existing_count": sync_result.get("skippedExistingCount", 0),
            },
        )

        update_workflow_instance(
            supabase,
            instance_id,
            status="running",
            current_step="dispatch_ingestion_jobs",
        )
        dispatch_results = _dispatch_ingestion_jobs(
            supabase,
            instance_id,
            sync_result.get("queuedJobs", []),
            dispatch_job,
        )

        result_payload = _capture_sync_result_payload(sync_result, dispatch_results)
        artifact = record_workflow_artifact(
            supabase,
            instance_id,
            "capture_sync_result",
            "Playlist capture sync result",
            result_payload,
            source_refs=_capture_source_refs(sync_result),
            status="published",
            metadata={"workflow_key": CAPTURE_SYNC_WORKFLOW_KEY},
        )
        completed_instance = update_workflow_instance(
            supabase,
            instance_id,
            status="completed",
            current_step="complete",
            result={**result_payload, "artifact_id": artifact.get("id")},
        )
        _queue_capture_source_synced_event(
            supabase,
            user_id,
            instance_id,
            sync_result,
            result_payload,
            artifact,
            trigger,
        )

        return {
            **sync_result,
            "workflowInstance": completed_instance,
            "workflow_instance_id": instance_id,
            "dispatchResults": dispatch_results,
        }
    except Exception as exc:
        _record_failure(supabase, instance_id, str(exc))
        raise


def _dispatch_ingestion_jobs(
    supabase: Any,
    workflow_instance_id: str,
    queued_jobs: list[dict],
    dispatch_job: Callable[[dict], dict | None] | None,
) -> list[dict]:
    if not queued_jobs:
        record_workflow_step(
            supabase,
            workflow_instance_id,
            "dispatch_ingestion_jobs",
            "skipped",
            metrics={"queued_job_count": 0},
        )
        return []

    record_workflow_step(
        supabase,
        workflow_instance_id,
        "dispatch_ingestion_jobs",
        "running",
        input_ref={"ingestion_job_ids": _ids(queued_jobs)},
        metrics={"queued_job_count": len(queued_jobs)},
    )

    jobs_to_dispatch = queued_jobs
    deferred_jobs = []
    if get_ingestion_dispatch_mode() == INGESTION_DISPATCH_BACKGROUND:
        jobs_to_dispatch = queued_jobs[:1]
        deferred_jobs = queued_jobs[1:]

    dispatch_results = []
    for job in jobs_to_dispatch:
        dispatch_result = dispatch_job(job) if dispatch_job else None
        dispatch_results.append(
            {
                "ingestion_job_id": job.get("id"),
                "dispatch": dispatch_result or {"status": "not_dispatched"},
            }
        )
    for job in deferred_jobs:
        dispatch_results.append(
            {
                "ingestion_job_id": job.get("id"),
                "dispatch": {
                    "mode": INGESTION_DISPATCH_BACKGROUND,
                    "scheduled": False,
                    "reason": "queued_for_sequential_processing",
                },
            }
        )

    record_workflow_step(
        supabase,
        workflow_instance_id,
        "dispatch_ingestion_jobs",
        "completed",
        output_ref={"ingestion_job_ids": _ids(queued_jobs)},
        metrics={
            "dispatched_job_count": len(jobs_to_dispatch),
            "deferred_job_count": len(deferred_jobs),
        },
    )
    return dispatch_results


def _record_failure(supabase: Any, workflow_instance_id: str, message: str) -> None:
    record_workflow_step(
        supabase,
        workflow_instance_id,
        "workflow_failed",
        "failed",
        error=message,
    )
    update_workflow_instance(
        supabase,
        workflow_instance_id,
        status="failed",
        current_step="failed",
        error=message,
    )


def _capture_sync_result_payload(sync_result: dict, dispatch_results: list[dict]) -> dict:
    return {
        "capture_source_id": sync_result.get("captureSource", {}).get("id"),
        "discovered_count": sync_result.get("discoveredCount", 0),
        "new_item_count": sync_result.get("newItemCount", 0),
        "queue_candidate_count": sync_result.get("queueCandidateCount", 0),
        "queued_job_count": sync_result.get("queuedJobCount", 0),
        "requested_job_count": sync_result.get("requestedJobCount", 0),
        "remaining_queue_count": sync_result.get("remainingQueueCount", 0),
        "skipped_existing_count": sync_result.get("skippedExistingCount", 0),
        "active_job_limit_reached": bool(sync_result.get("activeJobLimitReached")),
        "new_item_ids": _ids(sync_result.get("newItems", [])),
        "queued_item_ids": _ids(sync_result.get("queuedItems", [])),
        "queued_job_ids": _ids(sync_result.get("queuedJobs", [])),
        "dispatch_results": dispatch_results,
    }


def _queue_capture_source_synced_event(
    supabase: Any,
    user_id: str,
    workflow_instance_id: str,
    sync_result: dict,
    result_payload: dict,
    artifact: dict,
    trigger: str,
) -> None:
    source = sync_result.get("captureSource", {})
    capture_source_id = str(source.get("id") or result_payload.get("capture_source_id") or "")
    source_ref = {
        "type": "youtube_capture_source",
        "id": capture_source_id or None,
        "source_url": source.get("source_url"),
        "external_id": source.get("external_id"),
    }
    try:
        queue_brain_sync_event(
            supabase,
            user_id,
            "capture_source.synced",
            payload={
                "captureSourceId": capture_source_id or None,
                "workflowInstanceId": workflow_instance_id,
                "artifactId": artifact.get("id"),
                "discoveredCount": result_payload.get("discovered_count", 0),
                "newItemCount": result_payload.get("new_item_count", 0),
                "queuedJobCount": result_payload.get("queued_job_count", 0),
                "skippedExistingCount": result_payload.get("skipped_existing_count", 0),
                "activeJobLimitReached": result_payload.get("active_job_limit_reached", False),
                "queuedVideoIds": [
                    item.get("youtube_video_id")
                    for item in sync_result.get("queuedItems", [])[:5]
                    if item.get("youtube_video_id")
                ],
            },
            source_ref=source_ref,
            metadata={
                "trigger": trigger,
                "workflowKey": CAPTURE_SYNC_WORKFLOW_KEY,
                "workflowVersion": CAPTURE_SYNC_WORKFLOW_VERSION,
            },
            idempotency_key=f"capture_source.synced:{workflow_instance_id}",
        )
    except Exception as exc:  # noqa: BLE001 - outbound sync must not break capture workflows.
        print(f"[BRAIN_SYNC] Failed to queue capture-source sync event: {exc}")


def _capture_source_refs(sync_result: dict) -> list[dict]:
    source = sync_result.get("captureSource", {})
    source_ref = {
        "type": "youtube_capture_source",
        "id": source.get("id"),
        "source_url": source.get("source_url"),
        "external_id": source.get("external_id"),
    }
    video_refs = [
        {
            "type": "youtube_video",
            "video_id": item.get("youtube_video_id"),
        }
        for item in sync_result.get("queuedItems", [])
        if item.get("youtube_video_id")
    ]
    return [source_ref, *video_refs]


def _ids(rows: list[dict]) -> list[str]:
    return [row["id"] for row in rows if isinstance(row.get("id"), str)]
