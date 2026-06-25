"""External brain connection and outbound sync outbox helpers."""

from __future__ import annotations

import hashlib
import json
from typing import Any

BRAIN_SYNC_OUTBOX_VERSION = "memexai-brain-sync-outbox-v1"

BRAIN_SYNC_EVENT_TYPES = frozenset(
    {
        "video.ingested",
        "knowledge.published",
        "overlay.note.created",
        "capture_source.synced",
    }
)

MAX_CONNECTIONS_PER_EVENT = 25
MAX_PAYLOAD_BYTES = 32_000
MAX_SOURCE_REF_BYTES = 8_000
MAX_METADATA_BYTES = 8_000

CONNECTION_SELECT = (
    "id, user_id, provider, display_name, external_id, status, event_types, "
    "settings, last_synced_at, created_at"
)


def _rows(result: Any) -> list[dict]:
    data = getattr(result, "data", None)
    if data is None:
        return []
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return [data] if isinstance(data, dict) else []


def normalize_brain_sync_event_type(event_type: Any) -> str:
    """Return a supported outbound brain-sync event type."""
    normalized = str(event_type or "").strip()
    if normalized not in BRAIN_SYNC_EVENT_TYPES:
        allowed = ", ".join(sorted(BRAIN_SYNC_EVENT_TYPES))
        raise ValueError(f"Unsupported brain sync event type: {normalized}. Allowed: {allowed}")
    return normalized


def list_active_brain_connections(
    supabase: Any,
    user_id: str,
    event_type: str | None = None,
    limit: int = MAX_CONNECTIONS_PER_EVENT,
) -> list[dict]:
    """List active external brain connections for a user and optional event type.

    Empty connection tables, unapplied migrations, or transient read errors are
    treated as no active connections so feature call sites can remain optional.
    """
    normalized_event_type = (
        normalize_brain_sync_event_type(event_type) if event_type is not None else None
    )
    bounded_limit = max(1, min(int(limit or MAX_CONNECTIONS_PER_EVENT), MAX_CONNECTIONS_PER_EVENT))
    try:
        result = (
            supabase.table("external_brain_connections")
            .select(CONNECTION_SELECT)
            .eq("user_id", user_id)
            .eq("status", "active")
            .order("created_at", desc=False)
            .limit(bounded_limit)
            .execute()
        )
    except Exception:  # noqa: BLE001 - optional sync should not break core flows.
        return []

    connections = []
    for row in _rows(result):
        if row.get("user_id") != user_id or row.get("status") != "active":
            continue
        if normalized_event_type and not _connection_allows_event(row, normalized_event_type):
            continue
        connections.append(row)
    return connections[:bounded_limit]


def queue_brain_sync_event(
    supabase: Any,
    user_id: str,
    event_type: str,
    payload: dict | None = None,
    source_ref: dict | None = None,
    metadata: dict | None = None,
    idempotency_key: str | None = None,
    occurred_at: str | None = None,
    connection_limit: int = MAX_CONNECTIONS_PER_EVENT,
) -> dict:
    """Queue one outbound sync event per active eligible external brain connection."""
    normalized_event_type = normalize_brain_sync_event_type(event_type)
    connections = list_active_brain_connections(
        supabase,
        user_id,
        event_type=normalized_event_type,
        limit=connection_limit,
    )
    if not connections:
        return {
            "version": BRAIN_SYNC_OUTBOX_VERSION,
            "eventType": normalized_event_type,
            "connectionCount": 0,
            "queuedCount": 0,
            "failedCount": 0,
            "events": [],
        }

    safe_source_ref = _bounded_json_object("source_ref", source_ref or {}, MAX_SOURCE_REF_BYTES)
    safe_payload = _bounded_json_object("payload", payload or {}, MAX_PAYLOAD_BYTES)
    safe_metadata = _bounded_json_object("metadata", metadata or {}, MAX_METADATA_BYTES)
    base_idempotency_key = _clean_idempotency_key(idempotency_key) or _build_idempotency_key(
        normalized_event_type,
        safe_source_ref,
        safe_payload,
    )

    event_payload = {
        "version": BRAIN_SYNC_OUTBOX_VERSION,
        "eventType": normalized_event_type,
        "sourceRef": safe_source_ref,
        "data": safe_payload,
    }
    rows = []
    for connection in connections:
        connection_id = str(connection.get("id") or "").strip()
        if not connection_id:
            continue
        row = {
            "connection_id": connection_id,
            "user_id": user_id,
            "event_type": normalized_event_type,
            "source_ref": safe_source_ref,
            "payload": event_payload,
            "metadata": safe_metadata,
            "status": "queued",
            "idempotency_key": base_idempotency_key,
        }
        if occurred_at:
            row["occurred_at"] = occurred_at
        rows.append(row)

    if not rows:
        return {
            "version": BRAIN_SYNC_OUTBOX_VERSION,
            "eventType": normalized_event_type,
            "connectionCount": len(connections),
            "queuedCount": 0,
            "failedCount": 0,
            "events": [],
        }

    try:
        result = supabase.table("external_brain_sync_events").insert(rows).execute()
    except Exception as exc:  # noqa: BLE001 - optional outbox should not break core flows.
        return {
            "version": BRAIN_SYNC_OUTBOX_VERSION,
            "eventType": normalized_event_type,
            "connectionCount": len(connections),
            "queuedCount": 0,
            "failedCount": len(rows),
            "events": [],
            "error": str(exc),
        }

    inserted_rows = _rows(result)
    return {
        "version": BRAIN_SYNC_OUTBOX_VERSION,
        "eventType": normalized_event_type,
        "connectionCount": len(connections),
        "queuedCount": len(inserted_rows) if inserted_rows else len(rows),
        "failedCount": 0,
        "events": inserted_rows or rows,
    }


def _connection_allows_event(connection: dict, event_type: str) -> bool:
    event_types = connection.get("event_types")
    if not event_types:
        return True
    if isinstance(event_types, str):
        configured = [item.strip() for item in event_types.split(",")]
    elif isinstance(event_types, (list, tuple, set)):
        configured = [str(item).strip() for item in event_types]
    else:
        return True
    configured = [item for item in configured if item]
    return not configured or event_type in configured


def _bounded_json_object(name: str, value: dict, max_bytes: int) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    if len(raw.encode("utf-8")) > max_bytes:
        raise ValueError(f"{name} exceeds {max_bytes} bytes")
    return json.loads(raw)


def _build_idempotency_key(event_type: str, source_ref: dict, payload: dict) -> str:
    raw = json.dumps(
        {
            "event_type": event_type,
            "source_ref": source_ref,
            "payload": payload,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    return f"{event_type}:{digest}"


def _clean_idempotency_key(value: str | None) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:200]
