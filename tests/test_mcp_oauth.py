import base64
import hashlib
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from backend import mcp_oauth


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

    def insert(self, payload):
        self.action = "insert"
        self.payload = payload
        return self

    def select(self, *args, **kwargs):
        self.action = "select"
        return self

    def update(self, payload):
        self.action = "update"
        self.payload = payload
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def maybe_single(self):
        return self

    def execute(self):
        if self.action == "insert":
            self.supabase.tables.setdefault(self.table_name, []).append(self.payload)
            return Result([self.payload])
        if self.action == "update":
            row = self._find_row()
            if row:
                row.update(self.payload)
                return Result([row])
            return Result([])
        if self.action == "select":
            row = self._find_row()
            return Result(row)
        return Result([])

    def _find_row(self):
        rows = self.supabase.tables.get(self.table_name, [])
        for row in rows:
            if all(row.get(column) == value for column, value in self.filters):
                return row
        return rows[0] if rows else None


class Supabase:
    def __init__(self):
        self.tables = {}

    def table(self, table_name):
        return Query(table_name, self)


def test_register_oauth_client_accepts_loopback_redirect():
    supabase = Supabase()

    result = mcp_oauth.register_oauth_client(
        supabase,
        {
            "client_name": "Codex",
            "redirect_uris": ["http://127.0.0.1:1455/callback"],
        },
    )

    assert result["client_id"].startswith("memexai_mcp_")
    assert result["token_endpoint_auth_method"] == "none"  # noqa: S105 - OAuth spec value.
    assert supabase.tables[mcp_oauth.CLIENT_TABLE][0]["client_name"] == "Codex"


def test_register_oauth_client_rejects_non_loopback_http_redirect():
    supabase = Supabase()

    try:
        mcp_oauth.register_oauth_client(
            supabase,
            {
                "client_name": "Bad client",
                "redirect_uris": ["http://example.com/callback"],
            },
        )
    except ValueError as exc:
        assert "https or localhost" in str(exc)
    else:
        raise AssertionError("expected redirect URI validation to fail")


def test_oauth_authorization_code_exchange_issues_mcp_token(monkeypatch):
    supabase = Supabase()
    client = mcp_oauth.register_oauth_client(
        supabase,
        {
            "client_name": "Claude Code",
            "redirect_uris": ["http://localhost:31337/oauth/callback"],
        },
    )
    verifier = "sample-code-verifier-for-pkce"
    challenge = _pkce_s256(verifier)
    monkeypatch.setattr(
        mcp_oauth,
        "create_mcp_token",
        lambda supabase, user_id, name, scopes, expires_at: {
            "token": "emt_oauth_sample",
            "record": {"scopes": scopes, "expiresAt": expires_at},
        },
    )

    redirect_url = mcp_oauth.create_authorization_redirect(
        supabase,
        "user-1",
        {
            "response_type": "code",
            "client_id": client["client_id"],
            "redirect_uri": "http://localhost:31337/oauth/callback",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "scope": "context:read overlay:write ingest:write admin",
            "state": "state-1",
        },
    )
    parsed = urlparse(redirect_url)
    code = parse_qs(parsed.query)["code"][0]

    expected_access_token = "emt_oauth_sample"  # noqa: S105 - synthetic test token.
    token = mcp_oauth.exchange_authorization_code(
        supabase,
        {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client["client_id"],
            "redirect_uri": "http://localhost:31337/oauth/callback",
            "code_verifier": verifier,
        },
    )

    assert token["access_token"] == expected_access_token
    assert token["token_type"] == "Bearer"  # noqa: S105 - OAuth token type, not a secret.
    assert token["scope"] == "context:read overlay:write ingest:write"
    assert supabase.tables[mcp_oauth.CODE_TABLE][0]["consumed_at"] is not None


def test_oauth_metadata_and_mcp_challenge_routes(monkeypatch):
    from backend import server

    monkeypatch.setenv("SEARCHTUBE_AUTH_MODE", "supabase")
    monkeypatch.setattr(server, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(server, "get_auth_mode", lambda: server.SUPABASE_AUTH)

    client = TestClient(server.app)

    metadata = client.get("/.well-known/oauth-protected-resource/mcp").json()
    assert metadata["resource"] == "http://testserver/mcp"
    assert metadata["authorization_servers"] == ["http://testserver"]

    response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})

    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers
    assert "oauth-protected-resource/mcp" in response.headers["WWW-Authenticate"]


def _pkce_s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
