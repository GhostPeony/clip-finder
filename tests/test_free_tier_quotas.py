from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend import config, db, ingest, jobs, server


def free_billing_context(searches=0, indexed_seconds=0, indexed_videos=0):
    return {
        "entitlements": {
            "planKey": "free",
            "billingStatus": "free",
            "monthlyIndexedTranscriptSeconds": 18000,
            "libraryTranscriptSeconds": 18000,
            "indexedVideosTotal": 15,
            "monthlyRetrievalCalls": 100,
            "maxImportVideos": 10,
            "maxSearchResults": 5,
            "maxActiveIngestionJobs": 1,
            "deepTranscriptSeconds": 0,
            "priorityQueue": False,
            "usagePackSecondsBalance": 0,
            "periodStart": "2026-06-01T00:00:00+00:00",
            "periodEnd": "2026-07-01T00:00:00+00:00",
        },
        "usage": {
            "retrievalCalls": searches,
            "indexedTranscriptSeconds": indexed_seconds,
            "deepIndexedTranscriptSeconds": 0,
            "ingestionJobsStarted": 0,
            "indexedVideosAdded": indexed_videos,
        },
        "billingProfile": None,
    }


def test_free_tier_config_defaults_and_env(monkeypatch):
    monkeypatch.delenv("FREE_SEARCHES_PER_MONTH", raising=False)
    monkeypatch.setenv("FREE_INDEXED_VIDEOS_TOTAL", "7")

    assert config.get_free_searches_per_month() == 100
    assert config.get_free_indexed_videos_total() == 7

    monkeypatch.setenv("FREE_MAX_SEARCH_RESULTS", "0")
    try:
        config.get_free_max_search_results()
    except ValueError as exc:
        assert "FREE_MAX_SEARCH_RESULTS must be positive" in str(exc)
    else:
        raise AssertionError("invalid free-tier config should fail")


def test_quota_helpers_do_not_let_byok_bypass_hosted_plan_quotas(monkeypatch):
    monkeypatch.setenv("FREE_SEARCHES_PER_MONTH", "100")
    monkeypatch.setenv("FREE_INDEXED_VIDEOS_TOTAL", "15")
    monkeypatch.setenv("FREE_INDEXED_TRANSCRIPT_SECONDS_TOTAL", "18000")

    exhausted = {
        "api_key_enc": "encrypted-key",
        "free_searches_this_month": 100,
        "free_indexed_videos_total": 15,
        "free_indexed_seconds_total": 0,
    }

    assert not db.check_search_quota(exhausted, used_own_key=True)
    assert not db.check_search_quota(exhausted, used_own_key=False)
    assert not db.check_index_quota(exhausted, 1, 0)


def test_get_user_profile_resets_monthly_search_counter():
    class Result:
        def __init__(self, data):
            self.data = data

    class Query:
        def __init__(self, supabase, table_name):
            self.supabase = supabase
            self.table_name = table_name

        def select(self, *_args, **_kwargs):
            return self

        def update(self, payload):
            self.supabase.updates.append(payload)
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def single(self):
            return self

        def execute(self):
            return Result(self.supabase.profile)

    class Supabase:
        def __init__(self):
            self.profile = {
                "id": "user-1",
                "free_searches_today": 3,
                "last_search_reset": "1900-01-01",
                "free_searches_this_month": 88,
                "last_search_month_reset": "1900-01-01",
                "free_indexes_this_month": 1,
                "last_index_reset": "1900-01-01",
            }
            self.updates = []

        def table(self, table_name):
            return Query(self, table_name)

    supabase = Supabase()

    profile = db.get_user_profile(supabase, "user-1")

    assert profile["free_searches_this_month"] == 0
    assert any(update.get("free_searches_this_month") == 0 for update in supabase.updates)


def test_single_video_stops_when_transcript_hour_quota_is_exhausted(monkeypatch):
    monkeypatch.setenv("FREE_INDEXED_TRANSCRIPT_SECONDS_TOTAL", "18000")

    monkeypatch.setattr(ingest, "get_supabase", lambda: object())
    monkeypatch.setattr(ingest, "fetch_video_metadata", lambda video_id: ("Title", "Channel"))
    monkeypatch.setattr(
        ingest,
        "get_or_create_channel",
        lambda supabase, youtube_handle, channel_name, user_id: {"id": "channel-id"},
    )
    monkeypatch.setattr(ingest, "ensure_user_channel_subscription", lambda *_args: None)
    monkeypatch.setattr(ingest, "get_indexed_video_ids_pg", lambda supabase, channel_id: set())
    monkeypatch.setattr(ingest, "get_indexed_video_pg", lambda supabase, video_id: None)
    monkeypatch.setattr(
        ingest,
        "get_user_profile",
        lambda supabase, user_id: {
            "free_indexed_videos_total": 0,
            "free_indexed_seconds_total": 17_900,
        },
    )
    monkeypatch.setattr(
        ingest,
        "fetch_transcript_chunks",
        lambda video_id: SimpleNamespace(
            chunks=[{"text": "hello", "start_seconds": 0, "end_seconds": 200}],
            skip_reason=None,
        ),
    )
    monkeypatch.setattr(
        ingest,
        "index_video_to_pg",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("video should not be embedded")
        ),
    )

    messages = list(ingest.ingest_single_video_pg("video123", "user123"))

    assert messages[-1].startswith("Free total library limit reached")


def test_channel_import_truncates_to_free_import_cap(monkeypatch):
    monkeypatch.setenv("FREE_MAX_IMPORT_VIDEOS", "10")
    monkeypatch.setenv("FREE_INDEXED_VIDEOS_TOTAL", "15")

    fake_scrapetube = SimpleNamespace(
        get_channel=lambda **_kwargs: [{"videoId": f"video-{index}"} for index in range(12)]
    )
    monkeypatch.setitem(__import__("sys").modules, "scrapetube", fake_scrapetube)
    monkeypatch.setattr(ingest, "get_supabase", lambda: object())
    monkeypatch.setattr(ingest, "fetch_video_metadata", lambda video_id: ("Title", "Channel"))
    monkeypatch.setattr(
        ingest,
        "get_or_create_channel",
        lambda supabase, youtube_handle, channel_name, user_id: {"id": "channel-id"},
    )
    monkeypatch.setattr(ingest, "ensure_user_channel_subscription", lambda *_args: None)
    monkeypatch.setattr(ingest, "get_indexed_video_ids_pg", lambda supabase, channel_id: set())
    monkeypatch.setattr(ingest, "get_indexed_video_pg", lambda supabase, video_id: None)
    monkeypatch.setattr(
        ingest,
        "get_user_profile",
        lambda supabase, user_id: {
            "free_indexed_videos_total": 0,
            "free_indexed_seconds_total": 0,
        },
    )
    monkeypatch.setattr(
        ingest,
        "fetch_transcript_chunks",
        lambda video_id: SimpleNamespace(
            chunks=[{"text": "hello", "start_seconds": 0, "end_seconds": 60}],
            skip_reason=None,
        ),
    )
    indexed = []
    monkeypatch.setattr(
        ingest,
        "index_video_to_pg",
        lambda supabase, video_id, *_args, **_kwargs: indexed.append(video_id) or 1,
    )
    monkeypatch.setattr(ingest, "increment_index_usage", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ingest.time, "sleep", lambda _seconds: None)

    messages = list(ingest.ingest_channel_pg("https://youtube.com/@channel", "user123"))

    assert len(indexed) == 10
    assert any("first 10 eligible videos" in message for message in messages)


def test_existing_channel_subscription_claims_quota_before_insert(monkeypatch):
    monkeypatch.setattr(
        ingest,
        "get_channel_index_usage_pg",
        lambda supabase, channel_id: {"video_count": 16, "transcript_seconds": 0},
    )
    monkeypatch.setattr(
        ingest,
        "get_user_profile",
        lambda supabase, user_id: {
            "free_indexed_videos_total": 0,
            "free_indexed_seconds_total": 0,
        },
    )

    class Result:
        data = None

    class Query:
        def __init__(self, supabase):
            self.supabase = supabase

        def select(self, *_args, **_kwargs):
            return self

        def match(self, *_args, **_kwargs):
            return self

        def maybe_single(self):
            return self

        def insert(self, payload):
            self.supabase.inserts.append(payload)
            return self

        def execute(self):
            return Result()

    class Supabase:
        def __init__(self):
            self.inserts = []

        def table(self, _table_name):
            return Query(self)

    supabase = Supabase()

    message = ingest.ensure_user_channel_subscription(supabase, {"id": "channel-id"}, "user123")

    assert message.startswith("Free video limit reached")
    assert supabase.inserts == []


def test_usage_endpoint_returns_new_free_tier_shape(monkeypatch):
    app = server.app
    app.dependency_overrides[server.get_request_user] = lambda: {"sub": "user-1"}
    monkeypatch.setattr(server, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(server, "get_supabase", lambda: object())
    monkeypatch.setattr(
        server,
        "get_user_profile",
        lambda supabase, user_id: {
            "api_key_enc": None,
            "free_searches_this_month": 4,
            "free_indexed_videos_total": 2,
            "free_indexed_seconds_total": 7200,
        },
    )
    monkeypatch.setattr(
        server,
        "resolve_user_entitlements",
        lambda supabase, user_id, profile=None: free_billing_context(
            searches=4,
            indexed_seconds=7200,
            indexed_videos=2,
        ),
    )

    try:
        response = TestClient(app).get("/api/usage")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["plan"] == "free"
    assert body["searchesUsedThisMonth"] == 4
    assert body["indexedVideosUsed"] == 2
    assert body["indexedSecondsUsed"] == 7200
    assert body["maxSearchResults"] == 5


def test_search_endpoint_rejects_free_result_limit(monkeypatch):
    app = server.app
    app.dependency_overrides[server.get_request_user] = lambda: {"sub": "user-1"}
    monkeypatch.setattr(server, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(server, "get_supabase", lambda: object())
    monkeypatch.setattr(
        server,
        "get_user_profile",
        lambda supabase, user_id: {"api_key_enc": None, "free_searches_this_month": 0},
    )
    monkeypatch.setattr(
        server, "resolve_api_key", lambda profile=None, x_api_key=None: ("key", False)
    )
    monkeypatch.setattr(
        server,
        "resolve_user_entitlements",
        lambda supabase, user_id, profile=None: free_billing_context(searches=0),
    )
    monkeypatch.setattr(
        server,
        "search",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("search should not run")),
    )

    try:
        response = TestClient(app).post("/api/search", json={"query": "pricing", "limit": 10})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "Free searches can return up to 5 clips."


def test_search_endpoint_returns_monthly_quota_429(monkeypatch):
    app = server.app
    app.dependency_overrides[server.get_request_user] = lambda: {"sub": "user-1"}
    monkeypatch.setattr(server, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(server, "get_supabase", lambda: object())
    monkeypatch.setattr(
        server,
        "get_user_profile",
        lambda supabase, user_id: {"api_key_enc": None, "free_searches_this_month": 100},
    )
    monkeypatch.setattr(
        server, "resolve_api_key", lambda profile=None, x_api_key=None: ("key", False)
    )
    monkeypatch.setattr(
        server,
        "resolve_user_entitlements",
        lambda supabase, user_id, profile=None: free_billing_context(searches=100),
    )
    monkeypatch.setattr(
        server,
        "search",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("search should not run")),
    )

    try:
        response = TestClient(app).post("/api/search", json={"query": "pricing", "limit": 5})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 429
    assert response.json()["detail"].startswith("Free monthly search limit reached")


def test_ingest_endpoint_rejects_active_job_conflict(monkeypatch):
    app = server.app
    app.dependency_overrides[server.get_request_user] = lambda: {"sub": "user-1"}
    monkeypatch.setattr(server, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(server, "get_supabase", lambda: object())
    monkeypatch.setattr(server, "get_user_profile", lambda supabase, user_id: {})
    monkeypatch.setattr(
        server, "resolve_api_key", lambda profile=None, x_api_key=None: ("key", False)
    )
    monkeypatch.setattr(
        server,
        "resolve_user_entitlements",
        lambda supabase, user_id, profile=None: free_billing_context(),
    )
    monkeypatch.setattr(server, "count_active_ingestion_jobs", lambda supabase, user_id: 1)

    try:
        response = TestClient(app).post("/api/ingest", json={"url": "https://youtu.be/video"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["detail"].startswith("You already have the maximum number of imports")


def test_ingest_endpoint_treats_watch_url_with_playlist_context_as_video(monkeypatch):
    app = server.app
    app.dependency_overrides[server.get_request_user] = lambda: {"sub": "user-1"}
    created_jobs = []

    monkeypatch.setattr(server, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(server, "get_supabase", lambda: object())
    monkeypatch.setattr(server, "get_user_profile", lambda supabase, user_id: {})
    monkeypatch.setattr(
        server, "resolve_api_key", lambda profile=None, x_api_key=None: ("key", False)
    )
    monkeypatch.setattr(
        server,
        "resolve_user_entitlements",
        lambda supabase, user_id, profile=None: free_billing_context(),
    )
    monkeypatch.setattr(server, "count_active_ingestion_jobs", lambda supabase, user_id: 0)
    monkeypatch.setattr(
        server,
        "build_ingestion_cost_estimate",
        lambda supabase, user_id, source_url, source_type, digest_depth="standard": {
            "sourceType": source_type
        },
    )

    def fake_create_job(supabase, user_id, source_url, source_type, cost_estimate=None):
        job = {
            "id": "job-1",
            "user_id": user_id,
            "source_url": source_url,
            "source_type": source_type,
            "cost_estimate": cost_estimate,
        }
        created_jobs.append(job)
        return job

    monkeypatch.setattr(server, "create_ingestion_job", fake_create_job)
    monkeypatch.setattr(server, "update_ingestion_job", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(server, "record_ingestion_job_event", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        server,
        "ingest_url",
        lambda *_args, **_kwargs: iter(["Detected URL type: VIDEO", "Complete!"]),
    )

    try:
        response = TestClient(app).post(
            "/api/ingest",
            json={
                "url": (
                    "https://www.youtube.com/watch?v=6nyJ8y8ghsE"
                    "&list=PLL1tdVxB1CpVpEtMHxwuR4ul4Lxjw0O_y"
                )
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert created_jobs[0]["source_type"] == "video"
    assert created_jobs[0]["cost_estimate"] == {"sourceType": "video"}


def test_count_active_ingestion_jobs_uses_queued_and_running_statuses():
    class Result:
        count = 1

    class Query:
        def __init__(self):
            self.calls = []

        def select(self, *args, **kwargs):
            self.calls.append(("select", args, kwargs))
            return self

        def eq(self, *args):
            self.calls.append(("eq", args))
            return self

        def in_(self, *args):
            self.calls.append(("in_", args))
            return self

        def execute(self):
            return Result()

    class Supabase:
        def __init__(self):
            self.query = Query()

        def table(self, table_name):
            assert table_name == "ingestion_jobs"
            return self.query

    supabase = Supabase()

    assert jobs.count_active_ingestion_jobs(supabase, "user-1") == 1
    assert ("in_", ("status", ["queued", "running"])) in supabase.query.calls
