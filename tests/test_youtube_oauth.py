from fastapi.testclient import TestClient

from backend import youtube_oauth


class Result:
    def __init__(self, data=None):
        self.data = data


class Query:
    def __init__(self, table_name, supabase):
        self.table_name = table_name
        self.supabase = supabase
        self.action = None
        self.payload = None
        self.filters = []

    def select(self, *args, **kwargs):
        self.action = "select"
        self.supabase.calls.append((self.table_name, "select", args, kwargs))
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        self.supabase.calls.append((self.table_name, "eq", column, value))
        return self

    def maybe_single(self):
        self.supabase.calls.append((self.table_name, "maybe_single"))
        return self

    def upsert(self, payload, on_conflict=None):
        self.action = "upsert"
        self.payload = payload
        self.supabase.upserts.append((self.table_name, payload, on_conflict))
        return self

    def delete(self):
        self.action = "delete"
        self.supabase.deletes.append((self.table_name, tuple(self.filters)))
        return self

    def execute(self):
        if self.action == "upsert":
            self.supabase.row = {
                **(self.supabase.row or {}),
                **self.payload,
                "connected_at": "2026-06-22T00:00:00Z",
                "updated_at": "2026-06-22T00:00:00Z",
            }
            return Result([self.supabase.row])
        if self.action == "delete":
            self.supabase.row = None
            return Result([])
        return Result(self.supabase.row)


class Supabase:
    def __init__(self, row=None):
        self.row = row
        self.calls = []
        self.upserts = []
        self.deletes = []

    def table(self, table_name):
        self.calls.append(("table", table_name))
        return Query(table_name, self)


def test_youtube_oauth_status_is_token_safe():
    status = youtube_oauth.format_youtube_oauth_status(
        {
            "scopes": ["openid", youtube_oauth.YOUTUBE_READONLY_SCOPE],
            "access_token_enc": "encrypted-access",
            "refresh_token_enc": "encrypted-refresh",
            "expires_at": "2026-06-22T01:00:00Z",
            "connected_at": "2026-06-22T00:00:00Z",
            "updated_at": "2026-06-22T00:00:00Z",
            "last_error": None,
        }
    )

    assert status == {
        "connected": True,
        "needsReconnect": False,
        "youtubeReadonlyGranted": True,
        "hasRefreshToken": True,
        "scopes": ["openid", youtube_oauth.YOUTUBE_READONLY_SCOPE],
        "expiresAt": "2026-06-22T01:00:00Z",
        "connectedAt": "2026-06-22T00:00:00Z",
        "updatedAt": "2026-06-22T00:00:00Z",
        "lastError": None,
    }
    assert "encrypted-access" not in status.values()


def test_get_youtube_oauth_access_token_requires_active_readonly_grant(monkeypatch):
    monkeypatch.setattr(youtube_oauth, "decrypt_api_key", lambda value: f"dec:{value}")
    supabase = Supabase(
        {
            "scopes": ["openid", youtube_oauth.YOUTUBE_READONLY_SCOPE],
            "status": "active",
            "access_token_enc": "encrypted-access",
            "refresh_token_enc": "encrypted-refresh",
        }
    )

    token = youtube_oauth.get_youtube_oauth_access_token(supabase, "user-1")

    assert token == "dec:encrypted-access"  # noqa: S105 - synthetic test credential.
    assert ("youtube_oauth_connections", "eq", "user_id", "user-1") in supabase.calls


def test_get_youtube_oauth_access_token_rejects_missing_readonly_scope(monkeypatch):
    monkeypatch.setattr(youtube_oauth, "decrypt_api_key", lambda value: f"dec:{value}")
    supabase = Supabase(
        {
            "scopes": ["openid", "email"],
            "status": "active",
            "access_token_enc": "encrypted-access",
        }
    )

    assert youtube_oauth.get_youtube_oauth_access_token(supabase, "user-1") is None


def test_upsert_youtube_oauth_connection_encrypts_and_preserves_refresh(monkeypatch):
    monkeypatch.setattr(youtube_oauth, "encrypt_api_key", lambda value: f"enc:{value}")
    sample_access_value = "sample-access-value"
    existing_refresh_value = "enc:existing-refresh"
    supabase = Supabase(
        {
            "user_id": "user-1",
            "refresh_token_enc": existing_refresh_value,
            "scopes": ["openid"],
        }
    )

    status = youtube_oauth.upsert_youtube_oauth_connection(
        supabase,
        "user-1",
        access_token=sample_access_value,  # noqa: S106 - synthetic test credential.
        refresh_token=None,
        scopes=f"openid email {youtube_oauth.YOUTUBE_READONLY_SCOPE}",
    )

    inserted = supabase.upserts[0][1]
    assert inserted["access_token_enc"] == f"enc:{sample_access_value}"
    assert inserted["refresh_token_enc"] == existing_refresh_value
    assert inserted["scopes"] == ["openid", "email", youtube_oauth.YOUTUBE_READONLY_SCOPE]
    assert supabase.upserts[0][2] == "user_id"
    assert status["connected"] is True
    assert status["hasRefreshToken"] is True
    assert status["youtubeReadonlyGranted"] is True


def test_youtube_oauth_endpoint_saves_connection(monkeypatch):
    from backend import server

    monkeypatch.setenv("SEARCHTUBE_AUTH_MODE", "none")
    monkeypatch.setattr(server, "get_auth_mode", lambda: server.NO_AUTH)
    monkeypatch.setattr(server, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(youtube_oauth, "encrypt_api_key", lambda value: f"enc:{value}")
    sample_access_value = "sample-provider-access"
    sample_refresh_value = "sample-provider-refresh"

    supabase = Supabase()
    monkeypatch.setattr(server, "get_supabase", lambda: supabase)
    monkeypatch.setattr(
        server, "upsert_youtube_oauth_connection", youtube_oauth.upsert_youtube_oauth_connection
    )

    response = TestClient(server.app).post(
        "/api/youtube/oauth/connection",
        json={
            "access_token": sample_access_value,
            "refresh_token": sample_refresh_value,
            "scopes": ["openid", youtube_oauth.YOUTUBE_READONLY_SCOPE],
        },
    )

    assert response.status_code == 200
    assert response.json()["connected"] is True
    assert response.json()["hasRefreshToken"] is True
    inserted = supabase.upserts[0][1]
    assert inserted["access_token_enc"] == f"enc:{sample_access_value}"
    assert inserted["refresh_token_enc"] == f"enc:{sample_refresh_value}"
