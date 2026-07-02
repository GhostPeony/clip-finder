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

    def is_(self, column, value):
        self.filters.append((column, None if value == "null" else value))
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
        if self.filters:
            return None
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
    mint_calls = []

    def fake_create_mcp_token(supabase, user_id, name, scopes, expires_at, oauth_client_id=None):
        mint_calls.append({"name": name, "oauthClientId": oauth_client_id})
        return {
            "token": "emt_oauth_sample",
            "record": {"scopes": scopes, "expiresAt": expires_at},
        }

    monkeypatch.setattr(mcp_oauth, "create_mcp_token", fake_create_mcp_token)

    redirect_url = mcp_oauth.create_authorization_redirect(
        supabase,
        "user-1",
        {
            "response_type": "code",
            "client_id": client["client_id"],
            "redirect_uri": "http://localhost:31337/oauth/callback",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "scope": "context:read overlay:write ingest:write capture:write project:write admin",
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
    assert token["scope"] == ("context:read overlay:write ingest:write capture:write project:write")
    assert supabase.tables[mcp_oauth.CODE_TABLE][0]["consumed_at"] is not None
    assert mint_calls == [{"name": "Claude Code", "oauthClientId": client["client_id"]}]


def _register_test_client(supabase):
    return mcp_oauth.register_oauth_client(
        supabase,
        {
            "client_name": "Claude Code",
            "redirect_uris": ["http://localhost:31337/oauth/callback"],
        },
    )


def _issue_authorization_code(supabase, client_id, verifier):
    redirect_url = mcp_oauth.create_authorization_redirect(
        supabase,
        "user-1",
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": "http://localhost:31337/oauth/callback",
            "code_challenge": _pkce_s256(verifier),
            "code_challenge_method": "S256",
            "scope": "context:read overlay:write",
        },
    )
    return parse_qs(urlparse(redirect_url).query)["code"][0]


def test_oauth_authorization_code_cannot_be_exchanged_twice(monkeypatch):
    supabase = Supabase()
    client = _register_test_client(supabase)
    verifier = "sample-code-verifier-for-pkce"
    mint_calls = []

    def fake_create_mcp_token(supabase, user_id, name, scopes, expires_at, oauth_client_id=None):
        mint_calls.append((user_id, name, oauth_client_id))
        return {"token": "emt_oauth_sample", "record": {"scopes": scopes, "expiresAt": expires_at}}

    monkeypatch.setattr(mcp_oauth, "create_mcp_token", fake_create_mcp_token)
    code = _issue_authorization_code(supabase, client["client_id"], verifier)
    exchange_payload = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client["client_id"],
        "redirect_uri": "http://localhost:31337/oauth/callback",
        "code_verifier": verifier,
    }

    first = mcp_oauth.exchange_authorization_code(supabase, exchange_payload)
    assert first["access_token"] == "emt_oauth_sample"  # noqa: S105 - synthetic test token.

    try:
        mcp_oauth.exchange_authorization_code(supabase, exchange_payload)
    except ValueError as exc:
        assert "already consumed" in str(exc)
    else:
        raise AssertionError("expected the second exchange to fail")

    assert len(mint_calls) == 1


def test_oauth_exchange_consumes_code_before_minting(monkeypatch):
    supabase = Supabase()
    client = _register_test_client(supabase)
    verifier = "sample-code-verifier-for-pkce"
    mint_calls = []

    def fake_create_mcp_token(supabase, user_id, name, scopes, expires_at, oauth_client_id=None):
        mint_calls.append((user_id, name, oauth_client_id))
        return {"token": "emt_oauth_sample", "record": {"scopes": scopes, "expiresAt": expires_at}}

    monkeypatch.setattr(mcp_oauth, "create_mcp_token", fake_create_mcp_token)
    code = _issue_authorization_code(supabase, client["client_id"], verifier)

    try:
        mcp_oauth.exchange_authorization_code(
            supabase,
            {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client["client_id"],
                "redirect_uri": "http://localhost:31337/oauth/callback",
                "code_verifier": "wrong-code-verifier",
            },
        )
    except ValueError as exc:
        assert "code_verifier" in str(exc)
    else:
        raise AssertionError("expected an invalid code_verifier to fail")

    # The failed attempt consumed the code without minting, so a replay with the
    # correct verifier cannot mint either.
    assert mint_calls == []
    assert supabase.tables[mcp_oauth.CODE_TABLE][0]["consumed_at"] is not None
    try:
        mcp_oauth.exchange_authorization_code(
            supabase,
            {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client["client_id"],
                "redirect_uri": "http://localhost:31337/oauth/callback",
                "code_verifier": verifier,
            },
        )
    except ValueError as exc:
        assert "already consumed" in str(exc)
    else:
        raise AssertionError("expected the replayed exchange to fail")

    assert mint_calls == []


def test_authorization_request_with_only_unknown_scopes_raises_invalid_scope():
    supabase = Supabase()
    client = _register_test_client(supabase)

    try:
        mcp_oauth.validate_authorization_request(
            supabase,
            {
                "response_type": "code",
                "client_id": client["client_id"],
                "redirect_uri": "http://localhost:31337/oauth/callback",
                "code_challenge": _pkce_s256("sample-code-verifier-for-pkce"),
                "code_challenge_method": "S256",
                "scope": "admin superuser",
            },
        )
    except ValueError as exc:
        assert "invalid_scope" in str(exc)
    else:
        raise AssertionError("expected unknown-only scopes to be rejected")


def test_authorization_request_without_scope_falls_back_to_defaults():
    supabase = Supabase()
    client = _register_test_client(supabase)

    request = mcp_oauth.validate_authorization_request(
        supabase,
        {
            "response_type": "code",
            "client_id": client["client_id"],
            "redirect_uri": "http://localhost:31337/oauth/callback",
            "code_challenge": _pkce_s256("sample-code-verifier-for-pkce"),
            "code_challenge_method": "S256",
        },
    )

    assert request["scope"] == mcp_oauth.DEFAULT_MCP_SCOPES


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


def test_mcp_oauth_client_info_endpoint_returns_only_safe_fields(monkeypatch):
    from backend import server

    supabase = Supabase()
    registered = mcp_oauth.register_oauth_client(
        supabase,
        {
            "client_name": "Claude Code",
            "redirect_uris": [
                "https://claude.ai/api/mcp/auth_callback",
                "http://localhost:31337/oauth/callback",
            ],
            "logo_uri": "https://claude.ai/logo.png",
        },
    )
    monkeypatch.setattr(server, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(server, "get_supabase", lambda: supabase)

    response = TestClient(server.app).get(
        "/api/mcp/oauth/client-info",
        params={"client_id": registered["client_id"]},
    )

    assert response.status_code == 200
    assert response.json() == {
        "clientName": "Claude Code",
        "redirectHosts": ["claude.ai", "localhost"],
    }


def test_mcp_oauth_client_info_endpoint_returns_404_for_unknown_client(monkeypatch):
    from backend import server

    monkeypatch.setattr(server, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(server, "get_supabase", lambda: Supabase())

    response = TestClient(server.app).get(
        "/api/mcp/oauth/client-info",
        params={"client_id": "memexai_mcp_unknown"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown OAuth client"


def test_mcp_oauth_client_info_endpoint_requires_hosted_mode(monkeypatch):
    from backend import server

    monkeypatch.setattr(server, "is_supabase_mode", lambda: False)

    response = TestClient(server.app).get(
        "/api/mcp/oauth/client-info",
        params={"client_id": "memexai_mcp_anything"},
    )

    assert response.status_code == 404


def _pkce_s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
