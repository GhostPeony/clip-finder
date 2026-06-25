from fastapi.testclient import TestClient

from backend import server


class Result:
    def __init__(self, data=None):
        self.data = data


class Query:
    def __init__(self, table_name, supabase):
        self.table_name = table_name
        self.supabase = supabase
        self.action = "select"
        self.payload = None
        self.filters = []
        self.row_limit = None
        self.expect_single = False

    def select(self, *_args, **_kwargs):
        self.action = "select"
        return self

    def update(self, payload):
        self.action = "update"
        self.payload = payload
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def limit(self, value):
        self.row_limit = value
        return self

    def single(self):
        self.expect_single = True
        return self

    def execute(self):
        rows = self._matching_rows()
        if self.action == "update":
            for row in rows:
                row.update(self.payload)
            return Result(rows)
        if self.expect_single:
            return Result(rows[0] if rows else None)
        if self.row_limit is not None:
            rows = rows[: self.row_limit]
        return Result(rows)

    def _matching_rows(self):
        rows = list(self.supabase.tables.get(self.table_name, []))
        for column, value in self.filters:
            rows = [row for row in rows if row.get(column) == value]
        return rows


class Supabase:
    def __init__(self, tables):
        self.tables = tables

    def table(self, table_name):
        return Query(table_name, self)


def test_onboarding_status_returns_resumable_next_steps(monkeypatch):
    supabase = Supabase(
        {
            "profiles": [
                {
                    "id": server.LOCAL_USER_ID,
                    "onboarding_step": "youtube",
                    "onboarding_state": {"dismissedIntro": True},
                    "onboarding_completed_at": None,
                    "onboarding_skipped_at": None,
                    "last_search_reset": "2026-06-23",
                    "last_search_month_reset": "2026-06-01",
                    "last_index_reset": "2026-06-01",
                }
            ],
            "youtube_oauth_connections": [
                {"id": "yt-1", "user_id": server.LOCAL_USER_ID, "status": "active"}
            ],
            "youtube_capture_sources": [],
            "user_videos": [],
            "ingestion_jobs": [],
            "mcp_tokens": [],
            "usage_logs": [],
        }
    )
    monkeypatch.setattr(server, "get_auth_mode", lambda: server.NO_AUTH)
    monkeypatch.setattr(server, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(server, "get_supabase", lambda: supabase)

    response = TestClient(server.app).get("/api/onboarding/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["step"] == "youtube"
    assert payload["state"] == {"dismissedIntro": True}
    assert payload["derived"]["youtubeConnected"] is True
    assert payload["derived"]["activationComplete"] is False
    assert [step["id"] for step in payload["nextSteps"]] == [
        "choose_playlist",
        "import_first_video",
        "connect_agent",
    ]


def test_onboarding_status_patch_can_mark_complete(monkeypatch):
    profile = {
        "id": server.LOCAL_USER_ID,
        "onboarding_step": "agent",
        "onboarding_state": {},
        "onboarding_completed_at": None,
        "onboarding_skipped_at": None,
        "last_search_reset": "2026-06-23",
        "last_search_month_reset": "2026-06-01",
        "last_index_reset": "2026-06-01",
    }
    supabase = Supabase(
        {
            "profiles": [profile],
            "youtube_oauth_connections": [],
            "youtube_capture_sources": [],
            "user_videos": [{"id": "grant-1", "user_id": server.LOCAL_USER_ID}],
            "ingestion_jobs": [],
            "mcp_tokens": [{"id": "token-1", "user_id": server.LOCAL_USER_ID}],
            "usage_logs": [],
        }
    )
    monkeypatch.setattr(server, "get_auth_mode", lambda: server.NO_AUTH)
    monkeypatch.setattr(server, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(server, "get_supabase", lambda: supabase)

    response = TestClient(server.app).patch(
        "/api/onboarding/status",
        json={"complete": True, "onboarding_state": {"agent": "codex"}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["step"] == "done"
    assert payload["explicitCompleted"] is True
    assert payload["derived"]["activationComplete"] is True
    assert profile["onboarding_step"] == "done"
    assert profile["onboarding_state"] == {"agent": "codex"}
