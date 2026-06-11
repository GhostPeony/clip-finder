import asyncio

from backend import db


def test_api_key_encryption_round_trips(monkeypatch):
    monkeypatch.setattr(db, "API_KEY_ENCRYPTION_KEY", "test-secret")

    encrypted = db.encrypt_api_key("AIza-test")

    assert encrypted != "AIza-test"
    assert db.decrypt_api_key(encrypted) == "AIza-test"


def test_ingest_single_video_pg_stops_when_index_quota_is_exhausted(monkeypatch):
    from backend import ingest

    monkeypatch.setattr(ingest, "get_supabase", lambda: object())
    monkeypatch.setattr(ingest, "fetch_video_metadata", lambda video_id: ("Title", "Channel"))
    monkeypatch.setattr(
        ingest,
        "get_or_create_channel",
        lambda supabase, youtube_handle, channel_name, user_id: {"id": "channel-id"},
    )
    monkeypatch.setattr(ingest, "get_indexed_video_ids_pg", lambda supabase, channel_id: set())
    monkeypatch.setattr(ingest, "get_user_profile", lambda supabase, user_id: {"api_key_enc": None})
    monkeypatch.setattr(ingest, "check_index_quota", lambda profile, count, seconds=0: False)
    monkeypatch.setattr(ingest, "ensure_user_channel_subscription", lambda *_args: None)
    monkeypatch.setattr(
        ingest,
        "fetch_transcript_chunks",
        lambda video_id: (_ for _ in ()).throw(AssertionError("transcripts should not be fetched")),
    )

    messages = list(ingest.ingest_single_video_pg("video123", "user123"))

    assert messages[-1].startswith("Free indexing limit reached")


def test_transcript_export_requires_channel_subscription(monkeypatch):
    from backend import rag

    calls = []

    class Result:
        def __init__(self, data=None, count=None):
            self.data = data
            self.count = count

    class Query:
        def __init__(self, table):
            self.table = table

        def select(self, *args, **kwargs):
            return self

        def eq(self, *args, **kwargs):
            return self

        def match(self, *args, **kwargs):
            return self

        def maybe_single(self):
            return self

        def execute(self):
            if self.table == "videos":
                return Result({"id": "video-db-id", "channel_id": "channel-id"})
            if self.table == "user_channels":
                return Result(None)
            raise AssertionError("chunks should not be queried for unsubscribed users")

    class Supabase:
        def table(self, table):
            calls.append(table)
            return Query(table)

    monkeypatch.setattr(rag, "get_supabase", lambda: Supabase())

    assert rag.get_video_transcript_pg("yt-id", "other-user") == []
    assert calls == ["videos", "user_channels"]


def test_get_current_user_prefers_supabase_auth_server(monkeypatch):
    monkeypatch.setattr(
        db,
        "_get_user_from_auth_server",
        lambda token: {"sub": "user-from-auth-server", "email": "creator@example.com"},
    )
    monkeypatch.setattr(
        db,
        "_get_user_from_jwt_secret",
        lambda token: (_ for _ in ()).throw(AssertionError("JWT fallback should not run")),
    )

    user = asyncio.run(db.get_current_user("Bearer test-token"))

    assert user["sub"] == "user-from-auth-server"
    assert user["email"] == "creator@example.com"


def test_get_current_user_falls_back_to_jwt_secret_when_auth_server_unavailable(monkeypatch):
    monkeypatch.setattr(db, "_get_user_from_auth_server", lambda token: None)
    monkeypatch.setattr(
        db,
        "_get_user_from_jwt_secret",
        lambda token: {"sub": "user-from-jwt"},
    )

    user = asyncio.run(db.get_current_user("Bearer test-token"))

    assert user["sub"] == "user-from-jwt"
