import re
from pathlib import Path

import pytest

from backend.jobs import (
    INGESTION_EVENT_LEVELS,
    INGESTION_JOB_SOURCE_TYPES,
    INGESTION_JOB_STATUSES,
    classify_ingestion_event_level,
    clear_ingestion_job_history,
    create_ingestion_job,
    extract_ingestion_event_reason,
    failed_ingestion_fields,
    format_ingestion_error,
    get_ingestion_job,
    list_ingestion_jobs,
    normalize_ingestion_source_type,
    record_ingestion_job_event,
    summarize_ingestion_messages,
    update_ingestion_job,
)


class Result:
    def __init__(self, data):
        self.data = data


class Query:
    def __init__(self, table_name, response, calls):
        self.table_name = table_name
        self.response = response
        self.calls = calls

    def insert(self, payload):
        self.calls.append((self.table_name, "insert", payload))
        return self

    def update(self, payload):
        self.calls.append((self.table_name, "update", payload))
        return self

    def delete(self):
        self.calls.append((self.table_name, "delete"))
        return self

    def select(self, payload):
        self.calls.append((self.table_name, "select", payload))
        return self

    def eq(self, column, value):
        self.calls.append((self.table_name, "eq", column, value))
        return self

    def in_(self, column, values):
        self.calls.append((self.table_name, "in", column, values))
        return self

    def order(self, column, desc=False):
        self.calls.append((self.table_name, "order", column, desc))
        return self

    def limit(self, value):
        self.calls.append((self.table_name, "limit", value))
        return self

    def maybe_single(self):
        self.calls.append((self.table_name, "maybe_single"))
        return self

    def execute(self):
        return Result(self.response)


class Supabase:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def table(self, table_name):
        self.calls.append(("table", table_name))
        return Query(table_name, self.response, self.calls)


def test_create_ingestion_job_inserts_queued_job():
    supabase = Supabase([{"id": "job-1", "status": "queued"}])

    job = create_ingestion_job(supabase, "user-1", "https://youtube.com/@x", "channel")

    assert job == {"id": "job-1", "status": "queued"}
    assert (
        "ingestion_jobs",
        "insert",
        {
            "user_id": "user-1",
            "source_url": "https://youtube.com/@x",
            "source_type": "channel",
            "status": "queued",
        },
    ) in supabase.calls


def test_create_ingestion_job_stores_cost_estimate_when_provided():
    supabase = Supabase([{"id": "job-1", "status": "queued"}])
    cost_estimate = {"videosToEmbed": 2, "estimatedEmbeddingTokens": 7200}

    create_ingestion_job(
        supabase,
        "user-1",
        "https://youtube.com/playlist?list=PL12345678901",
        "playlist",
        cost_estimate,
    )

    inserted = [call[2] for call in supabase.calls if call[0] == "ingestion_jobs"][0]
    assert inserted["cost_estimate"] == cost_estimate


def test_create_ingestion_job_normalizes_unknown_source_type():
    supabase = Supabase([{"id": "job-1", "status": "queued"}])

    create_ingestion_job(supabase, "user-1", "https://example.com", "clip")

    inserted = [call[2] for call in supabase.calls if call[0] == "ingestion_jobs"][0]
    assert inserted["source_type"] == "unknown"


def test_ingestion_job_constants_match_database_constraints():
    migration_sql = Path("backend/supabase/migrations/002_ingestion_jobs.sql").read_text()

    assert INGESTION_JOB_SOURCE_TYPES == _check_values(migration_sql, "source_type")
    assert INGESTION_JOB_STATUSES == _check_values(migration_sql, "status")
    assert INGESTION_EVENT_LEVELS == _check_values(migration_sql, "level")


def test_playlist_sync_migration_removes_single_active_job_constraint():
    migration_sql = Path(
        "backend/supabase/migrations/023_allow_multiple_queued_ingestion_jobs.sql"
    ).read_text()

    assert "DROP INDEX IF EXISTS ingestion_jobs_one_active_per_user_idx" in migration_sql


def test_list_ingestion_jobs_scopes_to_user():
    supabase = Supabase([{"id": "job-1"}])

    jobs = list_ingestion_jobs(supabase, "user-1", limit=5)

    assert jobs == [{"id": "job-1"}]
    assert ("ingestion_jobs", "eq", "user_id", "user-1") in supabase.calls
    assert ("ingestion_jobs", "limit", 5) in supabase.calls


def test_get_ingestion_job_scopes_job_and_user():
    supabase = Supabase({"id": "job-1"})

    job = get_ingestion_job(supabase, "user-1", "job-1")

    assert job == {"id": "job-1"}
    assert ("ingestion_jobs", "eq", "id", "job-1") in supabase.calls
    assert ("ingestion_jobs", "eq", "user_id", "user-1") in supabase.calls


def test_clear_ingestion_job_history_deletes_only_settled_user_jobs():
    supabase = Supabase([{"id": "job-1"}, {"id": "job-2"}])

    deleted_count = clear_ingestion_job_history(supabase, "user-1")

    assert deleted_count == 2
    assert ("ingestion_jobs", "delete") in supabase.calls
    assert ("ingestion_jobs", "eq", "user_id", "user-1") in supabase.calls
    assert (
        "ingestion_jobs",
        "in",
        "status",
        ["cancelled", "completed", "failed", "partial"],
    ) in supabase.calls


def test_update_terminal_ingestion_job_sets_completed_at():
    supabase = Supabase([{"id": "job-1", "status": "completed"}])

    update_ingestion_job(supabase, "job-1", status="completed")

    update_calls = [call for call in supabase.calls if call[1] == "update"]
    assert update_calls
    assert update_calls[0][2]["status"] == "completed"
    assert "completed_at" in update_calls[0][2]


def test_update_ingestion_job_rejects_unknown_status_before_db_write():
    supabase = Supabase([{"id": "job-1"}])

    with pytest.raises(ValueError, match="Unsupported ingestion job status"):
        update_ingestion_job(supabase, "job-1", status="done")

    assert not [call for call in supabase.calls if len(call) > 1 and call[1] == "update"]


def test_record_ingestion_event_rejects_unknown_level_before_db_write():
    supabase = Supabase([{"id": "event-1"}])

    with pytest.raises(ValueError, match="Unsupported ingestion event level"):
        record_ingestion_job_event(supabase, "job-1", "debug", "hello")

    assert not [call for call in supabase.calls if len(call) > 1 and call[1] == "insert"]


def test_normalize_ingestion_source_type():
    assert normalize_ingestion_source_type("VIDEO") == "video"
    assert normalize_ingestion_source_type("clip") == "unknown"


def test_format_ingestion_error_sanitizes_check_constraint_payload():
    message = format_ingestion_error(
        {
            "message": 'new row for relation "user_videos" violates check constraint',
            "details": "Failing row contains unsupported metadata.",
        }
    )

    assert "Database schema rejected" in message
    assert "new row for relation" not in message


def test_ingestion_message_summary_counts_progress():
    summary = summarize_ingestion_messages(
        [
            "Found 3 videos in channel",
            "3 new videos to index",
            "  Indexed 12 clips",
            "  Reused existing indexed video (no embedding compute)",
            "  Skipped: transcript unavailable",
            "  Error indexing: quota",
        ]
    )

    assert summary == {
        "requested_video_count": 3,
        "indexed_video_count": 2,
        "skipped_video_count": 1,
        "failed_video_count": 1,
        "status": "partial",
    }


def test_failed_ingestion_fields_counts_single_video_pre_progress_failure():
    assert failed_ingestion_fields({"source_type": "video"}) == {
        "requested_video_count": 1,
        "failed_video_count": 1,
    }


def test_failed_ingestion_fields_preserves_existing_failure_count():
    assert failed_ingestion_fields({"source_type": "channel", "failed_video_count": 3}) == {
        "failed_video_count": 3,
    }


def test_ingestion_message_level_classification():
    assert classify_ingestion_event_level("Scanning channel") == "info"
    assert classify_ingestion_event_level("  Skipped: transcript unavailable") == "warning"
    assert classify_ingestion_event_level("  Error indexing: failed") == "error"


def test_extract_ingestion_event_reason():
    assert (
        extract_ingestion_event_reason(
            "  Skipped: captions_unavailable | captions are unavailable for abc"
        )
        == "captions_unavailable"
    )
    assert (
        extract_ingestion_event_reason("  Error indexing: vector insert failed")
        == "vector_insert_failed"
    )
    assert extract_ingestion_event_reason("Scanning channel") is None


def test_worker_processes_job_and_records_events(monkeypatch):
    from backend import worker

    supabase = Supabase([{"id": "job-1"}])
    sync_events = []
    monkeypatch.setattr(
        worker,
        "ingest_url",
        lambda source_url, user_id, api_key=None, used_own_key=False, digest_depth="standard": iter(
            [
                "Found 1 videos in channel",
                "1 new videos to index",
                "  Indexed 8 clips",
                "  Skipped: captions_unavailable | captions are unavailable for abc",
            ]
        ),
    )
    monkeypatch.setattr(
        worker,
        "queue_brain_sync_event",
        lambda *args, **kwargs: sync_events.append((args, kwargs)) or {"queuedCount": 1},
    )

    summary = worker.process_ingestion_job(
        supabase,
        {"id": "job-1", "user_id": "user-1", "source_url": "https://youtube.com/@x"},
        api_key="key",
        used_own_key=True,
    )

    assert summary["status"] == "partial"
    assert summary["indexed_video_count"] == 1
    assert summary["skipped_video_count"] == 1
    assert any(call[0] == "ingestion_job_events" and call[1] == "insert" for call in supabase.calls)
    assert any(call[0] == "ingestion_jobs" and call[1] == "update" for call in supabase.calls)
    capture_item_updates = [
        call[2]
        for call in supabase.calls
        if call[0] == "youtube_capture_items" and call[1] == "update"
    ]
    assert capture_item_updates
    assert capture_item_updates[0]["status"] == "indexed"
    assert capture_item_updates[0]["skip_reason"] is None
    event_inserts = [
        call[2]
        for call in supabase.calls
        if call[0] == "ingestion_job_events" and call[1] == "insert"
    ]
    assert any(event.get("reason") == "captions_unavailable" for event in event_inserts)
    event_args, event_kwargs = sync_events[0]
    assert event_args[:3] == (supabase, "user-1", "video.ingested")
    assert event_kwargs["payload"]["jobId"] == "job-1"
    assert event_kwargs["payload"]["indexedVideoCount"] == 1
    assert event_kwargs["payload"]["digestDepth"] == "standard"
    assert event_kwargs["source_ref"]["source_url"] == "https://youtube.com/@x"
    assert event_kwargs["idempotency_key"] == "video.ingested:job-1"


def test_worker_failure_marks_job_with_failed_video_count(monkeypatch):
    from backend import worker

    supabase = Supabase([{"id": "job-1"}])

    def fail_ingest(*args, **kwargs):
        raise RuntimeError("boom")
        yield  # pragma: no cover

    monkeypatch.setattr(worker, "ingest_url", fail_ingest)

    with pytest.raises(RuntimeError, match="boom"):
        worker.process_ingestion_job(
            supabase,
            {
                "id": "job-1",
                "user_id": "user-1",
                "source_url": "https://youtu.be/6nyJ8y8ghsE",
                "source_type": "video",
            },
            api_key="key",
        )

    failed_updates = [
        call[2]
        for call in supabase.calls
        if call[0] == "ingestion_jobs" and call[1] == "update" and call[2].get("status") == "failed"
    ]
    assert failed_updates
    assert failed_updates[0]["failed_video_count"] == 1
    assert failed_updates[0]["requested_video_count"] == 1
    capture_item_updates = [
        call[2]
        for call in supabase.calls
        if call[0] == "youtube_capture_items" and call[1] == "update"
    ]
    assert capture_item_updates
    assert capture_item_updates[0]["status"] == "failed"
    assert capture_item_updates[0]["skip_reason"] == "ingestion_failed"


def _check_values(sql: str, column: str) -> frozenset[str]:
    match = re.search(
        rf"CHECK\s*\(\s*{column}\s+IN\s*\((.*?)\)\s*\)",
        sql,
        flags=re.DOTALL,
    )
    assert match is not None
    return frozenset(re.findall(r"'([^']+)'", match.group(1)))
