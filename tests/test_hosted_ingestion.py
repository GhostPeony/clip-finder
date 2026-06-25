from backend import hosted_ingestion


class Result:
    def __init__(self, data):
        self.data = data


class Query:
    def __init__(self, supabase, table_name):
        self.supabase = supabase
        self.table_name = table_name
        self.filters = []
        self.action = None
        self.payload = None

    def select(self, payload):
        self.action = "select"
        self.payload = payload
        self.supabase.calls.append((self.table_name, "select", payload))
        return self

    def update(self, payload):
        self.action = "update"
        self.payload = payload
        self.supabase.calls.append((self.table_name, "update", payload))
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        self.supabase.calls.append((self.table_name, "eq", column, value))
        return self

    def order(self, column, desc=False):
        self.supabase.calls.append((self.table_name, "order", column, desc))
        return self

    def limit(self, value):
        self.supabase.calls.append((self.table_name, "limit", value))
        return self

    def execute(self):
        if self.action == "update":
            return Result([{**(self.payload or {}), "id": self._filter_value("id")}])
        if self.table_name == "ingestion_jobs":
            job_id = self._filter_value("id")
            if job_id:
                return Result(
                    [row for row in self.supabase.ingestion_jobs if row.get("id") == job_id]
                )
            user_id = self._filter_value("user_id")
            status = self._filter_value("status")
            rows = [
                row
                for row in self.supabase.ingestion_jobs
                if row.get("user_id") == user_id and row.get("status") == status
            ]
            return Result(rows)
        return Result([])

    def _filter_value(self, column):
        return next((value for key, value in self.filters if key == column), None)


class Supabase:
    def __init__(self, ingestion_jobs=None):
        self.calls = []
        self.ingestion_jobs = ingestion_jobs or []

    def table(self, table_name):
        self.calls.append(("table", table_name))
        return Query(self, table_name)


def test_process_hosted_ingestion_job_drains_user_queue_sequentially(monkeypatch):
    supabase = Supabase(
        [
            {"id": "job-2", "user_id": "user-1", "status": "queued"},
            {"id": "job-3", "user_id": "user-1", "status": "queued"},
        ]
    )
    processed_job_ids = []

    monkeypatch.setattr(hosted_ingestion, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(hosted_ingestion, "get_supabase", lambda: supabase)
    monkeypatch.setattr(hosted_ingestion, "get_user_profile", lambda *_args: {})
    monkeypatch.setattr(hosted_ingestion, "resolve_api_key", lambda *_args: ("key", False))
    monkeypatch.setattr(
        hosted_ingestion,
        "process_ingestion_job",
        lambda _supabase, job, *_args: (
            processed_job_ids.append(job["id"]) or {"status": "completed"}
        ),
    )

    result = hosted_ingestion.process_hosted_ingestion_job(
        {"id": "job-1", "user_id": "user-1", "status": "queued"}
    )

    assert result == {"status": "completed"}
    assert processed_job_ids == ["job-1", "job-2", "job-3"]


def test_rate_limit_retry_requeues_without_terminal_failure_fields(monkeypatch):
    supabase = object()
    updates = []
    events = []
    sleeps = []
    attempts = []
    retrying_capture_items = []

    def fake_process(_supabase, job, *_args):
        attempts.append(job["id"])
        if len(attempts) == 1:
            raise RuntimeError("429 RESOURCE_EXHAUSTED; retry in 0.1s")
        return {"status": "completed"}

    monkeypatch.setattr(hosted_ingestion, "process_ingestion_job", fake_process)
    monkeypatch.setattr(
        hosted_ingestion,
        "update_ingestion_job",
        lambda _supabase, job_id, **fields: updates.append((job_id, fields)) or fields,
    )
    monkeypatch.setattr(
        hosted_ingestion,
        "record_ingestion_job_event",
        lambda *_args, **kwargs: events.append((_args, kwargs)),
    )
    monkeypatch.setattr(
        hosted_ingestion,
        "_mark_capture_item_retrying",
        lambda _supabase, job_id: retrying_capture_items.append(job_id),
    )
    monkeypatch.setattr(hosted_ingestion.time, "sleep", lambda seconds: sleeps.append(seconds))

    result = hosted_ingestion._process_with_rate_limit_retries(
        supabase,
        {"id": "job-1", "user_id": "user-1", "status": "queued"},
        "key",
        False,
    )

    assert result == {"status": "completed"}
    assert attempts == ["job-1", "job-1"]
    assert sleeps == [5]
    assert retrying_capture_items == ["job-1"]
    assert updates == [
        (
            "job-1",
            {
                "status": "queued",
                "error": None,
                "completed_at": None,
                "failed_video_count": 0,
                "last_message": "Rate limited by model provider. Retrying in 5s.",
            },
        )
    ]
    assert events[0][0][2:] == ("warning", "Rate limited by model provider. Retrying in 5s.")
    assert events[0][1] == {"reason": "rate_limited"}


def test_rate_limit_failed_summary_requeues_and_retries(monkeypatch):
    supabase = Supabase(
        [
            {
                "id": "job-1",
                "user_id": "user-1",
                "status": "failed",
                "last_message": "Error indexing: 429 RESOURCE_EXHAUSTED. Please retry in 0.1s.",
                "error": None,
            }
        ]
    )
    attempts = []
    updates = []
    sleeps = []

    def fake_process(_supabase, job, *_args):
        attempts.append(job["id"])
        if len(attempts) == 1:
            return {"status": "failed", "failed_video_count": 1, "indexed_video_count": 0}
        return {"status": "completed", "failed_video_count": 0, "indexed_video_count": 1}

    monkeypatch.setattr(hosted_ingestion, "process_ingestion_job", fake_process)
    monkeypatch.setattr(
        hosted_ingestion,
        "update_ingestion_job",
        lambda _supabase, job_id, **fields: updates.append((job_id, fields)) or fields,
    )
    monkeypatch.setattr(hosted_ingestion, "record_ingestion_job_event", lambda *_args, **_kw: None)
    monkeypatch.setattr(hosted_ingestion, "_mark_capture_item_retrying", lambda *_args: None)
    monkeypatch.setattr(hosted_ingestion.time, "sleep", lambda seconds: sleeps.append(seconds))

    result = hosted_ingestion._process_with_rate_limit_retries(
        supabase,
        {"id": "job-1", "user_id": "user-1", "status": "queued"},
        "key",
        False,
    )

    assert result == {"status": "completed", "failed_video_count": 0, "indexed_video_count": 1}
    assert attempts == ["job-1", "job-1"]
    assert sleeps == [5]
    assert updates[0] == (
        "job-1",
        {
            "status": "queued",
            "error": None,
            "completed_at": None,
            "failed_video_count": 0,
            "last_message": "Rate limited by model provider. Retrying in 5s.",
        },
    )
