from backend import rag


class Result:
    def __init__(self, data=None, count=0):
        self.data = data
        self.count = count


class Query:
    def __init__(self, supabase, table_name):
        self.supabase = supabase
        self.table_name = table_name
        self.action = None
        self.filters = []

    def select(self, *args, **kwargs):
        self.action = "select"
        self.supabase.calls.append((self.table_name, "select", args, kwargs))
        return self

    def delete(self):
        self.action = "delete"
        self.supabase.calls.append((self.table_name, "delete"))
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        self.supabase.calls.append((self.table_name, "eq", column, value))
        return self

    def match(self, payload):
        self.filters.append(("match", payload))
        self.supabase.calls.append((self.table_name, "match", payload))
        return self

    def maybe_single(self):
        self.supabase.calls.append((self.table_name, "maybe_single"))
        return self

    def execute(self):
        return self.supabase.execute(self)


class Supabase:
    def __init__(self, explicit_video_access=False, channel_access=False):
        self.explicit_video_access = explicit_video_access
        self.channel_access = channel_access
        self.calls = []

    def table(self, table_name):
        self.calls.append(("table", table_name))
        return Query(self, table_name)

    def execute(self, query):
        if query.table_name == "videos" and query.action == "select":
            return Result({"id": "video-db-id", "channel_id": "channel-db-id"})
        if query.table_name == "user_videos" and query.action == "select":
            return Result({"user_id": "user-1"} if self.explicit_video_access else None)
        if query.table_name == "user_channels" and query.action == "select":
            return Result({"user_id": "user-1"} if self.channel_access else None)
        return Result([])


def test_delete_video_removes_explicit_user_grant_without_deleting_canonical_video(monkeypatch):
    supabase = Supabase(explicit_video_access=True)
    monkeypatch.setattr(rag, "get_supabase", lambda: supabase)

    result = rag.delete_video_pg("yt123", "user-1")

    assert result == {"deleted": True, "deletedClips": 0, "reason": "Removed from your library"}
    assert ("user_videos", "delete") in supabase.calls
    assert ("videos", "delete") not in supabase.calls
    assert ("chunks", "delete") not in supabase.calls


def test_delete_video_does_not_delete_canonical_video_for_channel_grant(monkeypatch):
    supabase = Supabase(explicit_video_access=False, channel_access=True)
    monkeypatch.setattr(rag, "get_supabase", lambda: supabase)

    result = rag.delete_video_pg("yt123", "user-1")

    assert result["deleted"] is False
    assert "Per-video hiding" in result["reason"]
    assert ("videos", "delete") not in supabase.calls
    assert ("chunks", "delete") not in supabase.calls
    assert ("channels", "delete") not in supabase.calls
