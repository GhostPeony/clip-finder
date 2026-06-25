from fastapi.testclient import TestClient

from backend import mcp_tokens


class Result:
    def __init__(self, data=None):
        self.data = data


class Query:
    def __init__(self, table_name, supabase):
        self.table_name = table_name
        self.supabase = supabase
        self.action = None
        self.payload = None

    def insert(self, payload):
        self.action = "insert"
        self.payload = payload
        self.supabase.inserts.append((self.table_name, payload))
        return self

    def update(self, payload):
        self.action = "update"
        self.payload = payload
        self.supabase.updates.append((self.table_name, payload))
        return self

    def select(self, *args, **kwargs):
        self.action = "select"
        self.supabase.calls.append((self.table_name, "select", args, kwargs))
        return self

    def eq(self, column, value):
        self.supabase.calls.append((self.table_name, "eq", column, value))
        return self

    def is_(self, column, value):
        self.supabase.calls.append((self.table_name, "is", column, value))
        return self

    def maybe_single(self):
        self.supabase.calls.append((self.table_name, "maybe_single"))
        return self

    def order(self, column, desc=False):
        self.supabase.calls.append((self.table_name, "order", column, desc))
        return self

    def execute(self):
        if self.action == "insert":
            return Result(
                [
                    {
                        **self.payload,
                        "id": "token-1",
                        "created_at": "2026-06-22T00:00:00Z",
                    }
                ]
            )
        if self.action == "update":
            return Result(self.supabase.update_response)
        return Result(self.supabase.select_response)


class Supabase:
    def __init__(self, select_response=None, update_response=None):
        self.select_response = select_response
        self.update_response = update_response if update_response is not None else []
        self.inserts = []
        self.updates = []
        self.calls = []

    def table(self, table_name):
        self.calls.append(("table", table_name))
        return Query(table_name, self)


def test_create_mcp_token_returns_raw_token_once_and_stores_hash(monkeypatch):
    supabase = Supabase()
    sample_bearer = "_".join([mcp_tokens.MCP_AUTH_PREFIX, "display", "secret"])
    monkeypatch.setattr(mcp_tokens, "_new_token", lambda: sample_bearer)

    result = mcp_tokens.create_mcp_token(
        supabase,
        "user-1",
        "Hermes on ponyo",
        ["context:read", "overlay:write", "admin"],
    )

    inserted = supabase.inserts[0][1]
    assert result["token"] == sample_bearer
    assert result["record"]["tokenPrefix"] == "emt_display"
    assert inserted["token_hash"] != sample_bearer
    assert inserted["token_hash"] == mcp_tokens._hash_token(sample_bearer)
    assert inserted["scopes"] == ["context:read", "overlay:write"]
    assert "token_hash" not in result["record"]


def test_create_mcp_token_allows_explicit_ingestion_scope(monkeypatch):
    supabase = Supabase()
    sample_bearer = "_".join([mcp_tokens.MCP_AUTH_PREFIX, "display", "secret"])
    monkeypatch.setattr(mcp_tokens, "_new_token", lambda: sample_bearer)

    mcp_tokens.create_mcp_token(
        supabase,
        "user-1",
        "Agent ingest token",
        ["context:read", "overlay:write", "ingest:write", "admin"],
    )

    inserted = supabase.inserts[0][1]
    assert inserted["scopes"] == ["context:read", "overlay:write", "ingest:write"]


def test_authenticate_mcp_token_updates_last_used_for_valid_token():
    sample_bearer = "_".join([mcp_tokens.MCP_AUTH_PREFIX, "display", "secret"])
    supabase = Supabase(
        select_response={
            "id": "token-1",
            "user_id": "user-1",
            "scopes": ["context:read"],
            "expires_at": None,
            "revoked_at": None,
        }
    )

    user = mcp_tokens.authenticate_mcp_token(supabase, f"Bearer {sample_bearer}")

    assert user["sub"] == "user-1"
    assert user["auth"] == "mcp_token"
    assert user["scopes"] == ["context:read"]
    assert (
        "mcp_tokens",
        "eq",
        "token_hash",
        mcp_tokens._hash_token(sample_bearer),
    ) in supabase.calls
    assert supabase.updates[0][0] == "mcp_tokens"
    assert "last_used_at" in supabase.updates[0][1]


def test_authenticate_mcp_token_rejects_revoked_token():
    supabase = Supabase(
        select_response={
            "id": "token-1",
            "user_id": "user-1",
            "scopes": ["context:read"],
            "expires_at": None,
            "revoked_at": "2026-06-22T00:00:00Z",
        }
    )

    sample_bearer = "_".join([mcp_tokens.MCP_AUTH_PREFIX, "display", "secret"])

    assert mcp_tokens.authenticate_mcp_token(supabase, f"Bearer {sample_bearer}") is None
    assert supabase.updates == []


def test_mcp_endpoint_accepts_dedicated_mcp_token(monkeypatch):
    from backend import server

    sample_bearer = "_".join([mcp_tokens.MCP_AUTH_PREFIX, "display", "secret"])
    monkeypatch.setenv("SEARCHTUBE_AUTH_MODE", "supabase")
    monkeypatch.setattr(server, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(server, "get_supabase", lambda: object())
    monkeypatch.setattr(
        server,
        "authenticate_mcp_token",
        lambda supabase, authorization: {
            "sub": "user-1",
            "auth": "mcp_token",
            "scopes": ["context:read", "overlay:write"],
        },
    )

    response = TestClient(server.app).post(
        "/mcp",
        headers={"Authorization": f"Bearer {sample_bearer}"},
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
    )

    assert response.status_code == 200
    assert response.json()["result"]["serverInfo"]["name"] == "memexai-context"


def test_mcp_endpoint_rejects_overlay_write_without_scope(monkeypatch):
    from backend import server

    sample_bearer = "_".join([mcp_tokens.MCP_AUTH_PREFIX, "display", "secret"])
    monkeypatch.setenv("SEARCHTUBE_AUTH_MODE", "supabase")
    monkeypatch.setattr(server, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(server, "get_supabase", lambda: object())
    monkeypatch.setattr(
        server,
        "authenticate_mcp_token",
        lambda supabase, authorization: {
            "sub": "user-1",
            "auth": "mcp_token",
            "scopes": ["context:read"],
        },
    )

    response = TestClient(server.app).post(
        "/mcp",
        headers={"Authorization": f"Bearer {sample_bearer}"},
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "add_context_note",
                "arguments": {"content": "save this"},
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["error"]["code"] == -32002
    assert "overlay:write" in response.json()["error"]["message"]


def test_mcp_endpoint_schedules_queued_ingestion_jobs(monkeypatch):
    from backend import server

    queued_job = {
        "id": "job-1",
        "user_id": "local",
        "source_url": "https://www.youtube.com/watch?v=uCKhOmth2ms",
        "status": "queued",
    }
    processed = []

    def fake_handle(payload, user_id, supabase, scopes, tool_context):
        assert user_id == "local"
        assert supabase == "supabase"
        tool_context["queued_ingestion_jobs"].append(queued_job)
        return {"jsonrpc": "2.0", "id": payload["id"], "result": {"ok": True}}, 200

    monkeypatch.setenv("SEARCHTUBE_AUTH_MODE", "none")
    monkeypatch.setattr(server, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(server, "get_supabase", lambda: "supabase")
    monkeypatch.setattr(server, "mcp_payload_requires_supabase", lambda payload: True)
    monkeypatch.setattr(server, "handle_mcp_request", fake_handle)
    monkeypatch.setattr(server, "process_hosted_ingestion_job", lambda job: processed.append(job))

    response = TestClient(server.app).post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 9, "method": "tools/call"},
    )

    assert response.status_code == 200
    assert response.json()["result"] == {"ok": True}
    assert processed == [queued_job]


def test_create_mcp_token_endpoint_returns_raw_token_once(monkeypatch):
    from backend import server

    sample_bearer = "_".join([mcp_tokens.MCP_AUTH_PREFIX, "display", "secret"])
    app = server.app
    app.dependency_overrides[server.get_request_user] = lambda: {"sub": "user-1"}
    monkeypatch.setattr(server, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(server, "get_supabase", lambda: object())
    monkeypatch.setattr(
        server,
        "create_mcp_token",
        lambda supabase, user_id, name, scopes: {
            "token": sample_bearer,
            "record": {
                "id": "token-1",
                "name": name,
                "tokenPrefix": "emt_display",
                "scopes": scopes,
            },
        },
    )

    try:
        response = TestClient(app).post(
            "/api/mcp/tokens",
            json={"name": "Hermes on ponyo", "scopes": ["context:read"]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["token"] == sample_bearer
    assert body["tokenRecord"]["name"] == "Hermes on ponyo"
    assert body["setup"]["mcpEndpoint"] == "http://testserver/mcp"
    assert body["setup"]["manifestUrl"] == "http://testserver/mcp.json"
    assert body["setup"]["accessModel"]["searchScope"] == "current_user_grants"
    assert body["setup"]["accessModel"]["globalSearch"] == "not_exposed"
    assert body["setup"]["accessModel"]["visibilityGrants"] == [
        "user_videos",
        "user_channels",
    ]
    assert "Bearer ${MEMEXAI_MCP_TOKEN}" in body["setup"]["hermesConfig"]
    assert "[mcp_servers.memexai]" in body["setup"]["codexConfig"]
    assert 'bearer_token_env_var = "MEMEXAI_MCP_TOKEN"' in body["setup"]["codexConfig"]
    assert "does not spend" in body["setup"]["codexSetupNote"]
    assert body["setup"]["oneTimeCredential"]["bearerToken"] == sample_bearer
    assert body["setup"]["oneTimeCredential"]["envLine"] == (f"MEMEXAI_MCP_TOKEN={sample_bearer}")
    assert body["setup"]["oneTimeCredential"]["codexEnvLine"] == (
        f"MEMEXAI_MCP_TOKEN={sample_bearer}"
    )
    assert f"Bearer {sample_bearer}" in body["setup"]["oneTimeCredential"]["hermesConfig"]
