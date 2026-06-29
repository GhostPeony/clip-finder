from fastapi.testclient import TestClient

from backend import capture


class Result:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


class Query:
    def __init__(self, table_name, supabase):
        self.table_name = table_name
        self.supabase = supabase
        self.action = None
        self.payload = None
        self.filters = []
        self.single = False
        self.count_requested = False

    def select(self, *args, **kwargs):
        self.action = "select"
        self.count_requested = kwargs.get("count") == "exact"
        self.supabase.calls.append((self.table_name, "select", args, kwargs))
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        self.supabase.calls.append((self.table_name, "eq", column, value))
        return self

    def in_(self, column, values):
        self.supabase.calls.append((self.table_name, "in", column, values))
        return self

    def order(self, column, desc=False):
        self.supabase.calls.append((self.table_name, "order", column, desc))
        return self

    def limit(self, value):
        self.supabase.calls.append((self.table_name, "limit", value))
        return self

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

    def delete(self):
        self.action = "delete"
        self.supabase.calls.append((self.table_name, "delete"))
        return self

    def maybe_single(self):
        self.single = True
        self.supabase.calls.append((self.table_name, "maybe_single"))
        return self

    def execute(self):
        if self.action == "insert":
            prefix = {
                "ingestion_jobs": "job",
                "youtube_capture_items": "item",
                "youtube_capture_sources": "capture",
            }.get(self.table_name, "row")
            self.supabase.insert_counts[self.table_name] = (
                self.supabase.insert_counts.get(self.table_name, 0) + 1
            )
            row = {
                **self.payload,
                "id": f"{prefix}-{self.supabase.insert_counts[self.table_name]}",
            }
            return Result([row])
        if self.action == "update":
            row_id = next((value for column, value in self.filters if column == "id"), "row-1")
            return Result([{**self.payload, "id": row_id}])
        if self.action == "delete":
            return Result([])
        if self.count_requested:
            return Result([], self.supabase.active_count)
        data = self.supabase.responses.get(self.table_name, [])
        if self.single and isinstance(data, list):
            return Result(data[0] if data else None)
        return Result(data)


class Supabase:
    def __init__(self, responses=None, active_count=0):
        self.responses = responses or {}
        self.active_count = active_count
        self.insert_counts = {}
        self.calls = []

    def table(self, table_name):
        self.calls.append(("table", table_name))
        return Query(table_name, self)


def test_create_playlist_capture_source_extracts_playlist_id():
    supabase = Supabase()

    source = capture.create_playlist_capture_source(
        supabase,
        "user-1",
        "https://www.youtube.com/playlist?list=PLabcdef123456",
        title="Memexai Inbox",
        created_by="agent",
        created_by_client="hermes",
    )

    assert source["id"] == "capture-1"
    assert source["source_type"] == "playlist"
    assert source["external_id"] == "PLabcdef123456"
    assert source["title"] == "Memexai Inbox"
    assert source["created_by"] == "agent"
    assert source["created_by_client"] == "hermes"
    inserted = [call[2] for call in supabase.calls if call[0] == "youtube_capture_sources"][0]
    assert inserted["user_id"] == "user-1"


def test_create_playlist_capture_source_rejects_video_url():
    supabase = Supabase()

    try:
        capture.create_playlist_capture_source(
            supabase,
            "user-1",
            "https://www.youtube.com/watch?v=uCKhOmth2ms",
        )
    except ValueError as exc:
        assert "playlist_url" in str(exc)
    else:
        raise AssertionError("expected playlist validation to fail")

    assert ("table", "youtube_capture_sources") not in supabase.calls


def test_list_capture_sources_scopes_to_user():
    supabase = Supabase({"youtube_capture_sources": [{"id": "capture-1", "title": "Inbox"}]})

    sources = capture.list_capture_sources(supabase, "user-1", limit=999)

    assert sources == [{"id": "capture-1", "title": "Inbox"}]
    assert ("youtube_capture_sources", "eq", "user_id", "user-1") in supabase.calls
    assert ("youtube_capture_sources", "limit", 100) in supabase.calls


def test_delete_capture_source_scopes_to_user_and_leaves_videos_untouched():
    supabase = Supabase({"youtube_capture_sources": [{"id": "capture-1", "title": "Inbox"}]})

    deleted = capture.delete_capture_source(supabase, "user-1", "capture-1")

    assert deleted is True
    assert ("youtube_capture_sources", "eq", "user_id", "user-1") in supabase.calls
    assert ("youtube_capture_sources", "eq", "id", "capture-1") in supabase.calls
    assert ("youtube_capture_sources", "delete") in supabase.calls
    assert all(call[0] != "videos" for call in supabase.calls)


def test_delete_capture_source_returns_false_when_source_missing():
    supabase = Supabase({"youtube_capture_sources": []})

    deleted = capture.delete_capture_source(supabase, "user-1", "capture-404")

    assert deleted is False
    assert ("youtube_capture_sources", "delete") not in supabase.calls


def test_build_capture_sources_context_includes_recent_items():
    supabase = Supabase(
        {
            "youtube_capture_sources": [{"id": "capture-1", "title": "Inbox"}],
            "youtube_capture_items": [
                {
                    "id": "item-1",
                    "youtube_video_id": "uCKhOmth2ms",
                    "status": "queued",
                    "ingestion_job_id": "job-1",
                }
            ],
        }
    )

    context = capture.build_capture_sources_context(supabase, "user-1", limit=10)

    assert context["captureSources"][0]["recentItems"] == [
        {
            "id": "item-1",
            "youtube_video_id": "uCKhOmth2ms",
            "status": "queued",
            "ingestion_job_id": "job-1",
        }
    ]
    assert ("youtube_capture_items", "eq", "user_id", "user-1") in supabase.calls
    assert ("youtube_capture_items", "eq", "capture_source_id", "capture-1") in supabase.calls


def test_fetch_playlist_video_items_uses_youtube_api_when_token_present(monkeypatch):
    requests = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return (
                b'{"items":[{"id":"playlist-item-1","snippet":{"title":"First video",'
                b'"publishedAt":"2026-06-24T00:00:00Z","resourceId":{"videoId":"video-one"},'
                b'"channelTitle":"Course Channel","position":0},"contentDetails":'
                b'{"videoId":"video-one"}}]}'
            )

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return Response()

    monkeypatch.setattr(capture, "urlopen", fake_urlopen)

    items = capture.fetch_playlist_video_items(
        "PLabcdef123456",
        access_token="oauth-access",  # noqa: S106 - synthetic test credential.
    )

    assert items == [
        {
            "youtube_video_id": "video-one",
            "playlist_item_id": "playlist-item-1",
            "title": "First video",
            "source_added_at": "2026-06-24T00:00:00Z",
            "metadata": {
                "title": "First video",
                "channelTitle": "Course Channel",
                "position": 0,
            },
        }
    ]
    request, timeout = requests[0]
    assert timeout == 15
    assert "playlistId=PLabcdef123456" in request.full_url
    assert request.get_header("Authorization") == "Bearer oauth-access"


def test_fetch_playlist_video_items_falls_back_to_ytdlp_when_scrapetube_is_empty(monkeypatch):
    monkeypatch.setattr(capture, "_fetch_playlist_video_items_with_scrapetube", lambda _: [])
    monkeypatch.setattr(
        capture,
        "_fetch_playlist_video_items_with_ytdlp",
        lambda _: [
            {
                "youtube_video_id": "SupFHGbytvA",
                "playlist_item_id": None,
                "title": "CS 285: Lecture 1",
                "source_added_at": None,
                "metadata": {"title": "CS 285: Lecture 1"},
            },
            {
                "youtube_video_id": "x-MqKBzoxkI",
                "playlist_item_id": None,
                "title": "Q&A 1",
                "source_added_at": None,
                "metadata": {"title": "Q&A 1"},
            },
        ],
    )

    items = capture.fetch_playlist_video_items("PLDHB-33bMSPDnjNZSuaMjL0iBAXfI_-QH")

    assert [item["youtube_video_id"] for item in items] == ["SupFHGbytvA", "x-MqKBzoxkI"]


def test_sync_playlist_capture_source_discovers_and_queues_one_job():
    supabase = Supabase(
        {
            "youtube_capture_sources": [
                {
                    "id": "capture-1",
                    "user_id": "user-1",
                    "source_type": "playlist",
                    "external_id": "PLabcdef123456",
                    "status": "active",
                }
            ],
            "youtube_capture_items": [],
        }
    )

    result = capture.sync_playlist_capture_source(
        supabase,
        "user-1",
        "capture-1",
        max_jobs=1,
        playlist_items=[
            {"youtube_video_id": "uCKhOmth2ms", "title": "Sierra product harness"},
            {"youtube_video_id": "abcdefghijk", "title": "Second video"},
        ],
    )

    assert result["discoveredCount"] == 2
    assert result["newItemCount"] == 2
    assert result["queueCandidateCount"] == 2
    assert result["queuedJobCount"] == 1
    assert result["requestedJobCount"] == 1
    assert result["remainingQueueCount"] == 1
    assert result["costEstimate"]["discoveredVideos"] == 2
    assert result["costEstimate"]["videosToEmbed"] == 2
    assert result["queuedJobs"][0]["source_url"] == "https://www.youtube.com/watch?v=uCKhOmth2ms"
    assert result["queuedJobs"][0]["cost_estimate"]["videosToEmbed"] == 1
    assert any(
        call[0] == "ingestion_jobs"
        and call[1] == "insert"
        and call[2]["source_url"] == "https://www.youtube.com/watch?v=uCKhOmth2ms"
        and call[2]["cost_estimate"]["videosToEmbed"] == 1
        for call in supabase.calls
    )
    assert any(
        call[0] == "youtube_capture_items"
        and call[1] == "update"
        and call[2]["status"] == "queued"
        and call[2]["ingestion_job_id"] == "job-1"
        for call in supabase.calls
    )
    assert any(
        call[0] == "youtube_capture_sources"
        and call[1] == "update"
        and call[2]["last_error"] is None
        for call in supabase.calls
    )


def test_sync_playlist_capture_source_queues_all_confirmed_jobs_without_five_job_cap():
    supabase = Supabase(
        {
            "youtube_capture_sources": [
                {
                    "id": "capture-1",
                    "user_id": "user-1",
                    "source_type": "playlist",
                    "external_id": "PLabcdef123456",
                    "status": "active",
                }
            ],
            "youtube_capture_items": [],
        }
    )
    playlist_items = [
        {"youtube_video_id": f"video-{index}", "title": f"Video {index}"} for index in range(6)
    ]

    result = capture.sync_playlist_capture_source(
        supabase,
        "user-1",
        "capture-1",
        max_jobs=6,
        playlist_items=playlist_items,
    )

    assert result["queueCandidateCount"] == 6
    assert result["queuedJobCount"] == 6
    assert result["remainingQueueCount"] == 0
    assert result["activeJobLimitReached"] is False
    queued_job_inserts = [
        call for call in supabase.calls if call[0] == "ingestion_jobs" and call[1] == "insert"
    ]
    assert len(queued_job_inserts) == 6


def test_sync_playlist_capture_source_passes_oauth_token_to_discovery(monkeypatch):
    supabase = Supabase(
        {
            "youtube_capture_sources": [
                {
                    "id": "capture-1",
                    "user_id": "user-1",
                    "source_type": "playlist",
                    "external_id": "PLabcdef123456",
                    "status": "active",
                }
            ],
            "youtube_capture_items": [],
        }
    )

    seen = {}

    def fake_fetch_playlist_video_items(playlist_id, access_token=None):
        seen["playlist_id"] = playlist_id
        seen["access_token"] = access_token
        return [{"youtube_video_id": "uCKhOmth2ms", "title": "Sierra product harness"}]

    monkeypatch.setattr(capture, "get_youtube_oauth_access_token", lambda *_: "oauth-access")
    monkeypatch.setattr(capture, "fetch_playlist_video_items", fake_fetch_playlist_video_items)

    result = capture.sync_playlist_capture_source(
        supabase,
        "user-1",
        "capture-1",
        max_jobs=0,
    )

    assert result["discoveredCount"] == 1
    assert seen == {"playlist_id": "PLabcdef123456", "access_token": "oauth-access"}


def test_sync_playlist_capture_source_dedupes_existing_items_without_queueing():
    supabase = Supabase(
        {
            "youtube_capture_sources": [
                {
                    "id": "capture-1",
                    "user_id": "user-1",
                    "source_type": "playlist",
                    "external_id": "PLabcdef123456",
                    "status": "active",
                }
            ],
            "youtube_capture_items": [
                {
                    "id": "item-existing",
                    "youtube_video_id": "uCKhOmth2ms",
                    "status": "queued",
                    "ingestion_job_id": "job-existing",
                }
            ],
        }
    )

    result = capture.sync_playlist_capture_source(
        supabase,
        "user-1",
        "capture-1",
        max_jobs=0,
        playlist_items=[
            {"youtube_video_id": "uCKhOmth2ms", "title": "Existing"},
            {"youtube_video_id": "abcdefghijk", "title": "New"},
        ],
    )

    assert result["discoveredCount"] == 2
    assert result["newItemCount"] == 1
    assert result["queueCandidateCount"] == 1
    assert result["skippedExistingCount"] == 1
    assert result["queuedJobCount"] == 0
    assert result["remainingQueueCount"] == 1
    item_inserts = [
        call
        for call in supabase.calls
        if call[0] == "youtube_capture_items" and call[1] == "insert"
    ]
    assert len(item_inserts) == 1
    assert item_inserts[0][2]["youtube_video_id"] == "abcdefghijk"


def test_capture_sources_endpoint_lists_sources(monkeypatch):
    from backend import server

    monkeypatch.setenv("SEARCHTUBE_AUTH_MODE", "none")
    monkeypatch.setattr(server, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(server, "get_supabase", lambda: object())
    monkeypatch.setattr(
        server,
        "build_capture_sources_context",
        lambda supabase, user_id, limit: {
            "captureSources": [{"id": "capture-1", "user_id": user_id, "limit": limit}]
        },
    )

    response = TestClient(server.app).get("/api/capture/sources?limit=999")

    assert response.status_code == 200
    assert response.json()["captureSources"] == [
        {"id": "capture-1", "user_id": "local", "limit": 100}
    ]


def test_create_capture_source_endpoint_validates_playlist(monkeypatch):
    from backend import server

    monkeypatch.setenv("SEARCHTUBE_AUTH_MODE", "none")
    monkeypatch.setattr(server, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(server, "get_supabase", lambda: object())
    monkeypatch.setattr(
        server,
        "create_playlist_capture_source",
        lambda supabase, user_id, playlist_url, title, project_id, created_by, created_by_client: {
            "id": "capture-1",
            "user_id": user_id,
            "source_url": playlist_url,
            "title": title,
            "project_id": project_id,
            "created_by": created_by,
            "created_by_client": created_by_client,
        },
    )

    response = TestClient(server.app).post(
        "/api/capture/sources",
        json={
            "playlist_url": "https://www.youtube.com/playlist?list=PLabcdef123456",
            "title": "Memexai Inbox",
            "created_by": "user",
        },
    )

    assert response.status_code == 200
    assert response.json()["captureSource"]["title"] == "Memexai Inbox"


def test_sync_capture_source_endpoint_schedules_queued_jobs(monkeypatch):
    from backend import server

    dispatched = []

    monkeypatch.setenv("SEARCHTUBE_AUTH_MODE", "none")
    monkeypatch.setattr(server, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(server, "get_supabase", lambda: object())

    def fake_capture_sync_workflow(
        supabase,
        user_id,
        source_id,
        max_jobs,
        dispatch_job,
        trigger,
        created_by,
    ):
        job = {
            "id": "job-1",
            "user_id": user_id,
            "source_url": "https://www.youtube.com/watch?v=uCKhOmth2ms",
            "source_type": "video",
            "max_jobs": max_jobs,
        }
        dispatched.append(dispatch_job(job))
        return {
            "captureSource": {"id": source_id, "user_id": user_id},
            "discoveredCount": 1,
            "newItemCount": 1,
            "queuedJobCount": 1,
            "workflow_instance_id": "workflow-1",
            "workflowInstance": {
                "id": "workflow-1",
                "trigger": trigger,
                "created_by": created_by,
                "status": "completed",
            },
        }

    monkeypatch.setattr(server, "run_capture_sync_workflow", fake_capture_sync_workflow)
    monkeypatch.setattr(
        server,
        "schedule_hosted_ingestion_job",
        lambda background_tasks, job, source: {"source": source, "job_id": job["id"]},
    )

    response = TestClient(server.app).post(
        "/api/capture/sources/capture-1/sync",
        json={"max_jobs": 1},
    )

    assert response.status_code == 200
    assert response.json()["queuedJobCount"] == 1
    assert response.json()["workflow_instance_id"] == "workflow-1"
    assert dispatched == [{"source": "capture-sync", "job_id": "job-1"}]
