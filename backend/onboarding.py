"""First-time setup state helpers for Memexai."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

ONBOARDING_STEPS = {
    "intro",
    "youtube",
    "playlist",
    "first_import",
    "agent",
    "done",
    "skipped",
}
DEFAULT_ONBOARDING_STEP = "intro"


def normalize_onboarding_step(step: str | None) -> str:
    """Return a known onboarding step name."""
    cleaned = str(step or "").strip().lower()
    if not cleaned:
        return DEFAULT_ONBOARDING_STEP
    if cleaned not in ONBOARDING_STEPS:
        raise ValueError("Invalid onboarding_step")
    return cleaned


def build_onboarding_status(supabase: Any, user_id: str, profile: dict) -> dict:
    """Build token-safe first-time setup state with derived activation signals."""
    signals = collect_onboarding_signals(supabase, user_id)
    explicit_completed = bool(profile.get("onboarding_completed_at"))
    explicit_skipped = bool(profile.get("onboarding_skipped_at"))
    activation_complete = bool(
        signals["hasGrantedVideo"] and (signals["hasMcpToken"] or signals["hasSearchUsage"])
    )
    step = normalize_onboarding_step(profile.get("onboarding_step"))
    if explicit_completed or activation_complete:
        step = "done"
    elif explicit_skipped:
        step = "skipped"

    return {
        "step": step,
        "state": profile.get("onboarding_state") or {},
        "completedAt": profile.get("onboarding_completed_at"),
        "skippedAt": profile.get("onboarding_skipped_at"),
        "explicitCompleted": explicit_completed,
        "explicitSkipped": explicit_skipped,
        "derived": {**signals, "activationComplete": activation_complete},
        "nextSteps": build_onboarding_next_steps(step, signals),
    }


def collect_onboarding_signals(supabase: Any, user_id: str) -> dict:
    """Return minimal activation signals without exposing source rows."""
    return {
        "youtubeConnected": _has_any(
            supabase,
            "youtube_oauth_connections",
            [("user_id", user_id), ("status", "active")],
        ),
        "hasCaptureSource": _has_any(
            supabase,
            "youtube_capture_sources",
            [("user_id", user_id), ("status", "active")],
        ),
        "hasGrantedVideo": _has_any(supabase, "user_videos", [("user_id", user_id)]),
        "hasQueuedOrIndexedJob": _has_any(supabase, "ingestion_jobs", [("user_id", user_id)]),
        "hasMcpToken": _has_any(supabase, "mcp_tokens", [("user_id", user_id)]),
        "hasSearchUsage": _has_any(
            supabase,
            "usage_logs",
            [("user_id", user_id), ("action", "search")],
        ),
    }


def build_onboarding_next_steps(step: str, signals: dict) -> list[dict]:
    """Return a compact checklist for the app or agent to render."""
    if step in {"done", "skipped"}:
        return []

    steps = []
    if not signals["youtubeConnected"]:
        steps.append(
            {
                "id": "connect_youtube",
                "label": "Connect YouTube",
                "reason": "Read-only playlist access lets Memexai sync the user's save inbox.",
            }
        )
    if not signals["hasCaptureSource"]:
        steps.append(
            {
                "id": "choose_playlist",
                "label": "Choose a capture playlist",
                "reason": "A standing playlist avoids repeated copy/paste when saving videos.",
            }
        )
    if not (signals["hasGrantedVideo"] or signals["hasQueuedOrIndexedJob"]):
        steps.append(
            {
                "id": "import_first_video",
                "label": "Import the first video",
                "reason": "Search and agents become useful only after at least one granted source exists.",
            }
        )
    if not signals["hasMcpToken"]:
        steps.append(
            {
                "id": "connect_agent",
                "label": "Connect an agent",
                "reason": "MCP access lets Codex, Claude, Hermes, or another client use saved-video context.",
            }
        )
    return steps


def build_onboarding_update(fields: dict) -> dict:
    """Normalize a partial onboarding update for the profiles table."""
    updates: dict[str, Any] = {}
    if "onboarding_step" in fields and fields["onboarding_step"] is not None:
        updates["onboarding_step"] = normalize_onboarding_step(fields["onboarding_step"])
    if "onboarding_state" in fields and fields["onboarding_state"] is not None:
        if not isinstance(fields["onboarding_state"], dict):
            raise ValueError("onboarding_state must be an object")
        updates["onboarding_state"] = fields["onboarding_state"]

    now = datetime.now(timezone.utc).isoformat()
    if fields.get("complete"):
        updates["onboarding_completed_at"] = now
        updates["onboarding_step"] = "done"
    if fields.get("skip"):
        updates["onboarding_skipped_at"] = now
        updates.setdefault("onboarding_step", "skipped")
    return updates


def _has_any(supabase: Any, table_name: str, filters: list[tuple[str, Any]]) -> bool:
    query = supabase.table(table_name).select("id")
    for column, value in filters:
        query = query.eq(column, value)
    result = query.limit(1).execute()
    data = getattr(result, "data", None)
    if data is None:
        return False
    if isinstance(data, list):
        return bool(data)
    return bool(data)
