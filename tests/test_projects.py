from backend import projects


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
        self.in_filters = []
        self.single = False

    def select(self, *args, **kwargs):
        self.supabase.calls.append((self.table_name, "select", args, kwargs))
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        self.supabase.calls.append((self.table_name, "eq", column, value))
        return self

    def in_(self, column, values):
        self.in_filters.append((column, set(values)))
        self.supabase.calls.append((self.table_name, "in", column, values))
        return self

    def order(self, column, desc=False):
        self.supabase.calls.append((self.table_name, "order", column, desc))
        return self

    def limit(self, value):
        self.supabase.calls.append((self.table_name, "limit", value))
        return self

    def maybe_single(self):
        self.single = True
        self.supabase.calls.append((self.table_name, "maybe_single"))
        return self

    def insert(self, payload):
        self.action = "insert"
        self.payload = payload
        self.supabase.calls.append((self.table_name, "insert", payload))
        return self

    def upsert(self, payload, **kwargs):
        self.action = "upsert"
        self.payload = payload
        self.supabase.calls.append((self.table_name, "upsert", payload, kwargs))
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

    def execute(self):
        if self.action == "insert":
            row = {**self.payload, "id": "project-1"}
            self.supabase.rows.setdefault(self.table_name, []).append(row)
            return Result([row])
        if self.action == "upsert":
            return Result(self.payload)
        if self.action == "update":
            return Result([{**self.payload, "id": self._filter_value("id", "project-1")}])
        data = list(self.supabase.rows.get(self.table_name, []))
        data = [row for row in data if self._matches(row)]
        if self.single:
            return Result(data[0] if data else None)
        return Result(data)

    def _filter_value(self, column, default=None):
        return next((value for key, value in self.filters if key == column), default)

    def _matches(self, row):
        for column, value in self.filters:
            if row.get(column) != value:
                return False
        for column, values in self.in_filters:
            if row.get(column) not in values:
                return False
        return True


class Supabase:
    def __init__(self, rows=None):
        self.rows = rows or {}
        self.calls = []

    def table(self, table_name):
        self.calls.append(("table", table_name))
        return Query(table_name, self)


def test_create_project_slugifies_name_and_lists_counts():
    supabase = Supabase(
        {
            "user_project_videos": [
                {"user_id": "user-1", "project_id": "project-1", "video_id": "video-db"}
            ],
            "youtube_capture_sources": [
                {
                    "user_id": "user-1",
                    "project_id": "project-1",
                    "id": "capture-1",
                    "title": "Inbox",
                }
            ],
        }
    )

    project = projects.create_project(supabase, "user-1", "Agent Harness Research")
    listed = projects.list_projects(supabase, "user-1")

    assert project["slug"] == "agent-harness-research"
    assert listed["projects"][0]["videoCount"] == 1
    assert listed["projects"][0]["linkedCaptureSourceCount"] == 1


def test_add_videos_to_project_requires_existing_user_access():
    supabase = Supabase(
        {
            "user_projects": [
                {"id": "project-1", "user_id": "user-1", "name": "Agent Harness", "slug": "agent"}
            ],
            "videos": [
                {
                    "id": "video-db-1",
                    "youtube_video_id": "yt-1",
                    "channel_id": "channel-1",
                    "title": "Visible",
                },
                {
                    "id": "video-db-2",
                    "youtube_video_id": "yt-2",
                    "channel_id": "channel-2",
                    "title": "Hidden",
                },
            ],
            "user_channels": [{"user_id": "user-1", "channel_id": "channel-1"}],
            "user_videos": [],
        }
    )

    result = projects.add_videos_to_project(
        supabase,
        "user-1",
        "project-1",
        youtube_video_ids=["yt-1", "yt-2"],
    )

    assert result["addedVideos"] == ["yt-1"]
    upserts = [
        call for call in supabase.calls if call[0] == "user_project_videos" and call[1] == "upsert"
    ]
    assert upserts[0][2] == [
        {
            "project_id": "project-1",
            "user_id": "user-1",
            "video_id": "video-db-1",
            "added_source": "manual",
            "capture_source_id": None,
            "metadata": {},
        }
    ]


def test_resolve_project_scope_returns_project_video_ids_and_sources():
    supabase = Supabase(
        {
            "user_projects": [
                {"id": "project-1", "user_id": "user-1", "name": "Agent Harness", "slug": "agent"}
            ],
            "user_project_videos": [
                {"user_id": "user-1", "project_id": "project-1", "video_id": "video-db"}
            ],
            "youtube_capture_sources": [
                {
                    "user_id": "user-1",
                    "project_id": "project-1",
                    "id": "capture-1",
                    "title": "Inbox",
                }
            ],
        }
    )

    scope = projects.resolve_project_scope(supabase, "user-1", project_slug="agent")

    assert scope["id"] == "project-1"
    assert scope["videoIds"] == ["video-db"]
    assert scope["captureSources"][0]["id"] == "capture-1"
