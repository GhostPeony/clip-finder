"""Durable platform workflow state helpers."""

from __future__ import annotations

from typing import Any

try:
    from .jobs import utc_now
except ImportError:
    from jobs import utc_now

TERMINAL_WORKFLOW_STATUSES = {"completed", "failed", "cancelled"}
ACTIVE_WORKFLOW_STATUSES = {"queued", "running", "waiting"}


def _rows(result: Any) -> list[dict]:
    data = getattr(result, "data", None)
    if data is None:
        return []
    if isinstance(data, list):
        return data
    return [data]


def _first(result: Any) -> dict | None:
    rows = _rows(result)
    return rows[0] if rows else None


def list_workflow_definitions(supabase: Any, user_id: str, limit: int = 50) -> list[dict]:
    """List workflow definitions visible to a user."""
    bounded_limit = max(1, min(limit, 100))
    return _rows(
        supabase.table("workflow_definitions")
        .select("*")
        .or_(f"user_id.is.null,user_id.eq.{user_id}")
        .order("key", desc=False)
        .order("version", desc=True)
        .limit(bounded_limit)
        .execute()
    )


def create_workflow_instance(
    supabase: Any,
    user_id: str,
    workflow_key: str,
    workflow_version: int,
    input_payload: dict | None = None,
    status: str = "queued",
    trigger: str = "",
    created_by: str = "system",
    created_by_client: str | None = None,
    metadata: dict | None = None,
) -> dict:
    """Create a user-scoped workflow instance."""
    if status not in ACTIVE_WORKFLOW_STATUSES | TERMINAL_WORKFLOW_STATUSES:
        raise ValueError("Invalid workflow status")
    if created_by not in {"system", "user", "agent"}:
        raise ValueError("created_by must be 'system', 'user', or 'agent'")

    payload = {
        "user_id": user_id,
        "workflow_key": workflow_key,
        "workflow_version": int(workflow_version),
        "trigger": trigger,
        "status": status,
        "input": input_payload or {},
        "metadata": metadata or {},
        "created_by": created_by,
    }
    if created_by_client:
        payload["created_by_client"] = created_by_client
    if status == "running":
        payload["started_at"] = utc_now()
    if status in TERMINAL_WORKFLOW_STATUSES:
        payload["completed_at"] = utc_now()

    return _first(supabase.table("workflow_instances").insert(payload).execute()) or payload


def list_workflow_instances(supabase: Any, user_id: str, limit: int = 20) -> list[dict]:
    """List recent workflow instances scoped to a user."""
    bounded_limit = max(1, min(limit, 50))
    return _rows(
        supabase.table("workflow_instances")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(bounded_limit)
        .execute()
    )


def get_workflow_instance(supabase: Any, user_id: str, instance_id: str) -> dict | None:
    """Fetch one workflow instance with step and artifact details."""
    return _first(
        supabase.table("workflow_instances")
        .select("*, workflow_steps(*), workflow_artifacts(*)")
        .eq("id", instance_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )


def update_workflow_instance(supabase: Any, instance_id: str, **fields: Any) -> dict:
    """Patch a workflow instance and return the updated row."""
    if "status" in fields:
        status = fields["status"]
        if status not in ACTIVE_WORKFLOW_STATUSES | TERMINAL_WORKFLOW_STATUSES:
            raise ValueError("Invalid workflow status")
        if status == "running":
            fields.setdefault("started_at", utc_now())
        if status in TERMINAL_WORKFLOW_STATUSES:
            fields.setdefault("completed_at", utc_now())

    result = supabase.table("workflow_instances").update(fields).eq("id", instance_id).execute()
    return (result.data or [{}])[0]


def record_workflow_step(
    supabase: Any,
    workflow_instance_id: str,
    step_key: str,
    status: str,
    attempt: int = 1,
    input_ref: dict | None = None,
    output_ref: dict | None = None,
    error: str | None = None,
    metrics: dict | None = None,
) -> dict:
    """Record one durable workflow step event."""
    payload = {
        "workflow_instance_id": workflow_instance_id,
        "step_key": step_key,
        "status": status,
        "attempt": max(1, int(attempt)),
        "input_ref": input_ref or {},
        "output_ref": output_ref or {},
        "metrics": metrics or {},
    }
    if error:
        payload["error"] = error
    if status in {"running"}:
        payload["started_at"] = utc_now()
    if status in TERMINAL_WORKFLOW_STATUSES | {"skipped"}:
        payload["completed_at"] = utc_now()

    return _first(supabase.table("workflow_steps").insert(payload).execute()) or payload


def record_workflow_artifact(
    supabase: Any,
    workflow_instance_id: str,
    artifact_type: str,
    title: str,
    payload: dict,
    source_refs: list[dict] | None = None,
    status: str = "draft",
    metadata: dict | None = None,
) -> dict:
    """Record an artifact produced by a workflow instance."""
    artifact = {
        "workflow_instance_id": workflow_instance_id,
        "artifact_type": artifact_type,
        "title": title,
        "payload": payload,
        "source_refs": source_refs or [],
        "status": status,
        "metadata": metadata or {},
    }
    return _first(supabase.table("workflow_artifacts").insert(artifact).execute()) or artifact


def build_workflow_status_context(supabase: Any, user_id: str, limit: int = 20) -> dict:
    """Return agent-readable workflow status context."""
    return {
        "workflowInstances": list_workflow_instances(supabase, user_id, limit),
        "guidance": (
            "Workflow instances are durable platform runs such as capture sync, video "
            "ingestion, knowledge release, eval, and agent brief generation. Agents should "
            "poll workflow status handles instead of blocking on long-running work."
        ),
    }
