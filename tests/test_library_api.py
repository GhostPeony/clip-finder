from backend import rag


class Result:
    def __init__(self, data=None, count=None):
        self.data = [] if data is None else data
        self.count = count


class RpcQuery:
    def __init__(self, result):
        self.result = result

    def execute(self):
        return self.result


class Query:
    def __init__(self, supabase, table_name):
        self.supabase = supabase
        self.table_name = table_name
        self.filters = []
        self.count_mode = None

    def select(self, *_args, **kwargs):
        self.count_mode = kwargs.get("count")
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def in_(self, column, values):
        self.filters.append(("in", column, values))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def execute(self):
        return self.supabase.execute(self)


class Supabase:
    def __init__(self):
        self.rpc_calls = []
        self.table_calls = []

    def table(self, table_name):
        self.table_calls.append(table_name)
        return Query(self, table_name)

    def rpc(self, name, payload):
        self.rpc_calls.append((name, payload))
        raise RuntimeError("function count_chunks_for_video is missing")

    def execute(self, query):
        if query.table_name == "user_channels":
            return Result([])
        if query.table_name == "user_videos":
            return Result([{"video_id": "video-db-id"}])
        if query.table_name == "videos":
            return Result(
                [
                    {
                        "id": "video-db-id",
                        "channel_id": "channel-db-id",
                        "youtube_video_id": "yt123",
                        "title": "A useful video",
                        "thumbnail_url": "thumb.jpg",
                        "indexed_at": "2026-06-24T14:31:29.223065+00:00",
                        "channels": {"id": "channel-db-id", "name": "Research Channel"},
                    }
                ]
            )
        if query.table_name == "chunks":
            return Result([], count=12)
        raise AssertionError(f"Unexpected table query: {query.table_name}")


def test_get_library_pg_returns_explicit_video_when_chunk_count_rpc_is_missing(monkeypatch):
    supabase = Supabase()
    monkeypatch.setattr(rag, "get_supabase", lambda: supabase)

    library = rag.get_library_pg("user-1")

    assert library["totalVideos"] == 1
    assert library["totalClips"] == 12
    assert library["channels"][0]["name"] == "Research Channel"
    assert library["channels"][0]["videos"][0]["videoId"] == "yt123"
    assert library["channels"][0]["videos"][0]["clipCount"] == 12
    assert supabase.rpc_calls == [("count_chunks_for_videos", {"video_ids": ["video-db-id"]})]
    assert "chunks" in supabase.table_calls


class BulkSupabase(Supabase):
    def rpc(self, name, payload):
        self.rpc_calls.append((name, payload))
        assert name == "count_chunks_for_videos"
        return RpcQuery(
            Result(
                [
                    {"video_id": "video-db-id-1", "chunk_count": 8},
                    {"video_id": "video-db-id-2", "chunk_count": 5},
                ]
            )
        )

    def execute(self, query):
        if query.table_name == "user_channels":
            return Result(
                [
                    {
                        "channel_id": "channel-db-id",
                        "channels": {"id": "channel-db-id", "name": "Research Channel"},
                    }
                ]
            )
        if query.table_name == "user_videos":
            return Result([])
        if query.table_name == "videos":
            return Result(
                [
                    {
                        "id": "video-db-id-1",
                        "channel_id": "channel-db-id",
                        "youtube_video_id": "yt123",
                        "title": "A useful video",
                        "thumbnail_url": "thumb.jpg",
                        "indexed_at": "2026-06-24T14:31:29.223065+00:00",
                    },
                    {
                        "id": "video-db-id-2",
                        "channel_id": "channel-db-id",
                        "youtube_video_id": "yt456",
                        "title": "Another useful video",
                        "thumbnail_url": "thumb2.jpg",
                        "indexed_at": "2026-06-23T14:31:29.223065+00:00",
                    },
                ]
            )
        raise AssertionError(f"Unexpected table query: {query.table_name}")


def test_get_library_pg_counts_chunks_with_one_bulk_rpc(monkeypatch):
    supabase = BulkSupabase()
    monkeypatch.setattr(rag, "get_supabase", lambda: supabase)

    library = rag.get_library_pg("user-1")

    assert library["totalVideos"] == 2
    assert library["totalClips"] == 13
    assert [video["clipCount"] for video in library["channels"][0]["videos"]] == [8, 5]
    assert supabase.rpc_calls == [
        (
            "count_chunks_for_videos",
            {"video_ids": ["video-db-id-1", "video-db-id-2"]},
        )
    ]
    assert "chunks" not in supabase.table_calls
