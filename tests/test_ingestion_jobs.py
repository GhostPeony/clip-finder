from backend.jobs import (
    classify_ingestion_event_level,
    create_ingestion_job,
    extract_ingestion_event_reason,
    get_ingestion_job,
    list_ingestion_jobs,
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

    def select(self, payload):
        self.calls.append((self.table_name, "select", payload))
        return self

    def eq(self, column, value):
        self.calls.append((self.table_name, "eq", column, value))
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


def test_update_terminal_ingestion_job_sets_completed_at():
    supabase = Supabase([{"id": "job-1", "status": "completed"}])

    update_ingestion_job(supabase, "job-1", status="completed")

    update_calls = [call for call in supabase.calls if call[1] == "update"]
    assert update_calls
    assert update_calls[0][2]["status"] == "completed"
    assert "completed_at" in update_calls[0][2]


def test_ingestion_message_summary_counts_progress():
    summary = summarize_ingestion_messages(
        [
            "Found 3 videos in channel",
            "3 new videos to index",
            "  Indexed 12 clips",
            "  Skipped: transcript unavailable",
            "  Error indexing: quota",
        ]
    )

    assert summary == {
        "requested_video_count": 3,
        "indexed_video_count": 1,
        "skipped_video_count": 1,
        "failed_video_count": 1,
        "status": "partial",
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
    monkeypatch.setattr(
        worker,
        "ingest_url",
        lambda source_url, user_id, api_key=None: iter(
            [
                "Found 1 videos in channel",
                "1 new videos to index",
                "  Indexed 8 clips",
                "  Skipped: captions_unavailable | captions are unavailable for abc",
            ]
        ),
    )

    summary = worker.process_ingestion_job(
        supabase,
        {"id": "job-1", "user_id": "user-1", "source_url": "https://youtube.com/@x"},
        api_key="key",
    )

    assert summary["status"] == "partial"
    assert summary["indexed_video_count"] == 1
    assert summary["skipped_video_count"] == 1
    assert any(call[0] == "ingestion_job_events" and call[1] == "insert" for call in supabase.calls)
    assert any(call[0] == "ingestion_jobs" and call[1] == "update" for call in supabase.calls)
    event_inserts = [
        call[2]
        for call in supabase.calls
        if call[0] == "ingestion_job_events" and call[1] == "insert"
    ]
    assert any(event.get("reason") == "captions_unavailable" for event in event_inserts)
