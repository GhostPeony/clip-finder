from backend import brain_sync


class Result:
    def __init__(self, data=None):
        self.data = data if data is not None else []


class Query:
    def __init__(self, table_name, supabase):
        self.table_name = table_name
        self.supabase = supabase
        self.action = None
        self.payload = None
        self.filters = []
        self.limit_value = None

    def select(self, *args, **kwargs):
        self.action = "select"
        self.supabase.calls.append((self.table_name, "select", args, kwargs))
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        self.supabase.calls.append((self.table_name, "eq", column, value))
        return self

    def order(self, column, desc=False):
        self.supabase.calls.append((self.table_name, "order", column, desc))
        return self

    def limit(self, value):
        self.limit_value = value
        self.supabase.calls.append((self.table_name, "limit", value))
        return self

    def insert(self, payload):
        self.action = "insert"
        self.payload = payload
        self.supabase.calls.append((self.table_name, "insert", payload))
        return self

    def execute(self):
        if self.table_name in self.supabase.raise_on_tables:
            raise RuntimeError(f"{self.table_name} unavailable")

        if self.action == "insert":
            rows = self.payload if isinstance(self.payload, list) else [self.payload]
            self.supabase.inserts.append((self.table_name, self.payload))
            return Result([{**row, "id": f"event-{index + 1}"} for index, row in enumerate(rows)])

        rows = self.supabase.responses.get(self.table_name, [])
        if isinstance(rows, dict):
            rows = [rows]
        rows = [row for row in rows if isinstance(row, dict)]
        for column, value in self.filters:
            rows = [row for row in rows if row.get(column) == value]
        if self.limit_value is not None:
            rows = rows[: self.limit_value]
        return Result(rows)


class Supabase:
    def __init__(self, responses=None, raise_on_tables=None):
        self.responses = responses or {}
        self.raise_on_tables = set(raise_on_tables or [])
        self.calls = []
        self.inserts = []

    def table(self, table_name):
        self.calls.append(("table", table_name))
        return Query(table_name, self)


SOURCE_CONTEXT_TABLES = {
    "videos",
    "chunks",
    "transcript_lines",
    "source_concepts",
    "source_edges",
    "source_labels",
    "knowledge_artifacts",
    "agent_notes",
    "personal_concepts",
}


def test_list_active_brain_connections_scopes_user_and_event_type():
    supabase = Supabase(
        {
            "external_brain_connections": [
                {
                    "id": "conn-all",
                    "user_id": "user-1",
                    "status": "active",
                    "event_types": [],
                },
                {
                    "id": "conn-video",
                    "user_id": "user-1",
                    "status": "active",
                    "event_types": ["video.ingested"],
                },
                {
                    "id": "conn-note",
                    "user_id": "user-1",
                    "status": "active",
                    "event_types": ["overlay.note.created"],
                },
                {
                    "id": "conn-paused",
                    "user_id": "user-1",
                    "status": "paused",
                    "event_types": [],
                },
                {
                    "id": "conn-other-user",
                    "user_id": "user-2",
                    "status": "active",
                    "event_types": [],
                },
            ]
        }
    )

    connections = brain_sync.list_active_brain_connections(
        supabase,
        "user-1",
        event_type="video.ingested",
        limit=999,
    )

    assert [connection["id"] for connection in connections] == ["conn-all", "conn-video"]
    assert ("external_brain_connections", "eq", "user_id", "user-1") in supabase.calls
    assert ("external_brain_connections", "eq", "status", "active") in supabase.calls
    assert ("external_brain_connections", "limit", brain_sync.MAX_CONNECTIONS_PER_EVENT) in (
        supabase.calls
    )


def test_queue_brain_sync_event_creates_user_scoped_outbox_rows_per_connection():
    supabase = Supabase(
        {
            "external_brain_connections": [
                {
                    "id": "conn-all",
                    "user_id": "user-1",
                    "status": "active",
                    "event_types": [],
                },
                {
                    "id": "conn-video",
                    "user_id": "user-1",
                    "status": "active",
                    "event_types": ["video.ingested"],
                },
                {
                    "id": "conn-note",
                    "user_id": "user-1",
                    "status": "active",
                    "event_types": ["overlay.note.created"],
                },
                {
                    "id": "conn-other-user",
                    "user_id": "user-2",
                    "status": "active",
                    "event_types": [],
                },
            ]
        }
    )

    result = brain_sync.queue_brain_sync_event(
        supabase,
        "user-1",
        "video.ingested",
        payload={"videoId": "yt-123", "title": "A saved video"},
        source_ref={"type": "youtube_video", "video_id": "yt-123"},
        metadata={"trigger": "ingest"},
    )

    assert result["queuedCount"] == 2
    assert result["failedCount"] == 0
    assert len(supabase.inserts) == 1
    table_name, inserted_rows = supabase.inserts[0]
    assert table_name == "external_brain_sync_events"
    assert {row["connection_id"] for row in inserted_rows} == {"conn-all", "conn-video"}
    assert {row["user_id"] for row in inserted_rows} == {"user-1"}

    for row in inserted_rows:
        assert row["event_type"] == "video.ingested"
        assert row["status"] == "queued"
        assert row["source_ref"] == {"type": "youtube_video", "video_id": "yt-123"}
        assert row["payload"]["version"] == brain_sync.BRAIN_SYNC_OUTBOX_VERSION
        assert row["payload"]["data"]["videoId"] == "yt-123"
        assert row["metadata"] == {"trigger": "ingest"}
        assert row["idempotency_key"].startswith("video.ingested:")

    touched_tables = {call[1] for call in supabase.calls if call[0] == "table"}
    assert touched_tables.isdisjoint(SOURCE_CONTEXT_TABLES)


def test_queue_brain_sync_event_noops_without_active_connections():
    supabase = Supabase(
        {
            "external_brain_connections": [
                {
                    "id": "conn-paused",
                    "user_id": "user-1",
                    "status": "paused",
                    "event_types": [],
                }
            ]
        }
    )

    result = brain_sync.queue_brain_sync_event(
        supabase,
        "user-1",
        "overlay.note.created",
        payload={"noteId": "note-1"},
        source_ref={"type": "agent_note", "id": "note-1"},
    )

    assert result["connectionCount"] == 0
    assert result["queuedCount"] == 0
    assert supabase.inserts == []
    assert all(call[0] != "external_brain_sync_events" for call in supabase.calls)


def test_queue_brain_sync_event_treats_missing_connection_table_as_no_connections():
    supabase = Supabase(raise_on_tables={"external_brain_connections"})

    result = brain_sync.queue_brain_sync_event(
        supabase,
        "user-1",
        "capture_source.synced",
        payload={"captureSourceId": "capture-1"},
    )

    assert result["queuedCount"] == 0
    assert result["events"] == []
    assert supabase.inserts == []


def test_queue_brain_sync_event_rejects_unknown_event_type_before_writes():
    supabase = Supabase()

    try:
        brain_sync.queue_brain_sync_event(
            supabase,
            "user-1",
            "source_context.rewritten",
            payload={},
        )
    except ValueError as exc:
        assert "Unsupported brain sync event type" in str(exc)
    else:
        raise AssertionError("expected unsupported event type to fail")

    assert supabase.calls == []
