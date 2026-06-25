import pytest

from backend import capture_workflows


class Result:
    def __init__(self, data):
        self.data = data


class Query:
    def __init__(self, table_name, supabase):
        self.table_name = table_name
        self.supabase = supabase
        self.action = None
        self.payload = None
        self.filters = []

    def insert(self, payload):
        self.action = "insert"
        self.payload = payload
        self.supabase.calls.append((self.table_name, "insert", payload))
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

    def execute(self):
        if self.action == "insert":
            prefix = self.table_name.removeprefix("workflow_").removesuffix("s")
            self.supabase.insert_counts[self.table_name] = (
                self.supabase.insert_counts.get(self.table_name, 0) + 1
            )
            return Result(
                [
                    {
                        **self.payload,
                        "id": f"{prefix}-{self.supabase.insert_counts[self.table_name]}",
                    }
                ]
            )
        if self.action == "update":
            row_id = next((value for column, value in self.filters if column == "id"), "row-1")
            return Result([{**self.payload, "id": row_id}])
        return Result([])


class Supabase:
    def __init__(self):
        self.calls = []
        self.insert_counts = {}

    def table(self, table_name):
        self.calls.append(("table", table_name))
        return Query(table_name, self)


def test_run_capture_sync_workflow_records_steps_artifact_and_dispatch(monkeypatch):
    supabase = Supabase()
    dispatched_jobs = []
    sync_events = []

    def fake_sync(source_supabase, user_id, source_id, max_jobs):
        assert source_supabase is supabase
        assert user_id == "user-1"
        assert source_id == "capture-1"
        assert max_jobs == 1
        return {
            "captureSource": {
                "id": "capture-1",
                "source_url": "https://www.youtube.com/playlist?list=PLabcdef123456",
                "external_id": "PLabcdef123456",
            },
            "discoveredCount": 2,
            "newItemCount": 1,
            "queuedJobCount": 1,
            "skippedExistingCount": 1,
            "activeJobLimitReached": False,
            "newItems": [{"id": "item-1", "youtube_video_id": "uCKhOmth2ms"}],
            "queuedItems": [{"id": "item-1", "youtube_video_id": "uCKhOmth2ms"}],
            "queuedJobs": [{"id": "job-1", "source_url": "https://youtu.be/uCKhOmth2ms"}],
        }

    monkeypatch.setattr(capture_workflows, "sync_playlist_capture_source", fake_sync)
    monkeypatch.setattr(
        capture_workflows,
        "queue_brain_sync_event",
        lambda *args, **kwargs: sync_events.append((args, kwargs)) or {"queuedCount": 1},
    )

    result = capture_workflows.run_capture_sync_workflow(
        supabase,
        "user-1",
        "capture-1",
        max_jobs=1,
        dispatch_job=lambda job: dispatched_jobs.append(job) or {"mode": "background"},
        trigger="test.capture.sync",
    )

    assert result["workflow_instance_id"] == "instance-1"
    assert result["workflowInstance"]["status"] == "completed"
    assert result["workflowInstance"]["result"]["queued_job_ids"] == ["job-1"]
    assert result["dispatchResults"][0]["dispatch"] == {"mode": "background"}
    assert dispatched_jobs == [{"id": "job-1", "source_url": "https://youtu.be/uCKhOmth2ms"}]

    step_keys = [call[2]["step_key"] for call in supabase.calls if call[0] == "workflow_steps"]
    assert step_keys == [
        "sync_capture_source",
        "sync_capture_source",
        "dispatch_ingestion_jobs",
        "dispatch_ingestion_jobs",
    ]
    artifact_payloads = [call[2] for call in supabase.calls if call[0] == "workflow_artifacts"]
    assert artifact_payloads[0]["artifact_type"] == "capture_sync_result"
    assert artifact_payloads[0]["payload"]["new_item_count"] == 1
    event_args, event_kwargs = sync_events[0]
    assert event_args[:3] == (supabase, "user-1", "capture_source.synced")
    assert event_kwargs["payload"]["workflowInstanceId"] == "instance-1"
    assert event_kwargs["payload"]["artifactId"] == "artifact-1"
    assert event_kwargs["payload"]["queuedVideoIds"] == ["uCKhOmth2ms"]
    assert event_kwargs["source_ref"]["id"] == "capture-1"
    assert event_kwargs["idempotency_key"] == "capture_source.synced:instance-1"


def test_capture_sync_workflow_defers_extra_background_jobs(monkeypatch):
    supabase = Supabase()
    dispatched_jobs = []

    def fake_sync(source_supabase, user_id, source_id, max_jobs):
        assert source_supabase is supabase
        assert user_id == "user-1"
        assert source_id == "capture-1"
        return {
            "captureSource": {
                "id": source_id,
                "source_url": "https://www.youtube.com/playlist?list=PLabcdef123456",
                "external_id": "PLabcdef123456",
            },
            "discoveredCount": 3,
            "newItemCount": 3,
            "queueCandidateCount": 3,
            "queuedJobCount": 3,
            "requestedJobCount": max_jobs,
            "remainingQueueCount": 0,
            "skippedExistingCount": 0,
            "activeJobLimitReached": False,
            "newItems": [],
            "queuedItems": [],
            "queuedJobs": [
                {"id": "job-1", "source_url": "https://youtu.be/one"},
                {"id": "job-2", "source_url": "https://youtu.be/two"},
                {"id": "job-3", "source_url": "https://youtu.be/three"},
            ],
        }

    monkeypatch.setattr(capture_workflows, "sync_playlist_capture_source", fake_sync)
    monkeypatch.setattr(capture_workflows, "get_ingestion_dispatch_mode", lambda: "background")
    monkeypatch.setattr(capture_workflows, "queue_brain_sync_event", lambda *args, **kwargs: None)

    result = capture_workflows.run_capture_sync_workflow(
        supabase,
        "user-1",
        "capture-1",
        max_jobs=3,
        dispatch_job=lambda job: dispatched_jobs.append(job) or {"mode": "background"},
    )

    assert dispatched_jobs == [{"id": "job-1", "source_url": "https://youtu.be/one"}]
    assert result["dispatchResults"] == [
        {"ingestion_job_id": "job-1", "dispatch": {"mode": "background"}},
        {
            "ingestion_job_id": "job-2",
            "dispatch": {
                "mode": "background",
                "scheduled": False,
                "reason": "queued_for_sequential_processing",
            },
        },
        {
            "ingestion_job_id": "job-3",
            "dispatch": {
                "mode": "background",
                "scheduled": False,
                "reason": "queued_for_sequential_processing",
            },
        },
    ]


def test_run_capture_sync_workflow_marks_instance_failed(monkeypatch):
    supabase = Supabase()

    def broken_sync(*args, **kwargs):
        raise ValueError("playlist unavailable")

    monkeypatch.setattr(capture_workflows, "sync_playlist_capture_source", broken_sync)

    with pytest.raises(ValueError, match="playlist unavailable"):
        capture_workflows.run_capture_sync_workflow(
            supabase,
            "user-1",
            "capture-1",
        )

    step_payloads = [call[2] for call in supabase.calls if call[0] == "workflow_steps"]
    assert step_payloads[-1]["step_key"] == "workflow_failed"
    assert step_payloads[-1]["status"] == "failed"
    instance_updates = [
        call[2]
        for call in supabase.calls
        if call[0] == "workflow_instances" and call[1] == "update"
    ]
    assert instance_updates[-1]["status"] == "failed"
    assert instance_updates[-1]["error"] == "playlist unavailable"
