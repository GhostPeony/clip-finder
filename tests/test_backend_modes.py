import importlib

from fastapi.testclient import TestClient


def test_backend_server_importable_from_package():
    module = importlib.import_module("backend.server")

    assert module.app.title == "Memexai API"


def test_storage_import_uses_supabase_only(monkeypatch):
    monkeypatch.setenv("SEARCHTUBE_STORAGE", "supabase")

    module = importlib.import_module("backend.storage")

    assert module.is_supabase_mode()


def test_local_chroma_storage_mode_is_removed(monkeypatch):
    monkeypatch.setenv("SEARCHTUBE_STORAGE", "local")

    from backend.config import get_storage_mode

    try:
        get_storage_mode()
    except ValueError as exc:
        assert "local Chroma mode was removed" in str(exc)
    else:
        raise AssertionError("SEARCHTUBE_STORAGE=local should be rejected")


def test_validate_embedding_dimensions_accepts_schema_default(monkeypatch):
    monkeypatch.delenv("EMBEDDING_DIMENSIONS", raising=False)

    from backend.config import validate_embedding_dimensions

    assert validate_embedding_dimensions() == 768


def test_validate_embedding_dimensions_rejects_schema_mismatch(monkeypatch):
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "1536")

    from backend.config import validate_embedding_dimensions

    try:
        validate_embedding_dimensions()
    except ValueError as exc:
        assert "VECTOR(768)" in str(exc)
    else:
        raise AssertionError("mismatched embedding dimensions should fail fast")


def test_config_endpoint_defaults_to_hosted_mode(monkeypatch):
    monkeypatch.delenv("SEARCHTUBE_STORAGE", raising=False)
    monkeypatch.delenv("SEARCHTUBE_AUTH_MODE", raising=False)

    from backend.server import app

    client = TestClient(app)
    response = client.get("/api/config")

    assert response.status_code == 200
    assert response.json()["storage"] == "supabase"
    assert response.json()["authMode"] == "supabase"
    assert response.json()["apiKeyMode"] == "server"
    assert response.json()["allowUserKeys"] is False


def test_public_agent_docs_expose_mcp_and_repo_context_guidance(monkeypatch):
    monkeypatch.setenv("SEARCHTUBE_AUTH_MODE", "supabase")

    from backend.server import app

    client = TestClient(app)
    response = client.get("/llms.txt")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    text = response.text
    assert "MCP endpoint: http://testserver/mcp" in text
    assert "Use your own repo, filesystem, GitHub, or code-index MCP tools" in text
    assert "build_agent_brief" in text
    assert "Source video context is read-only" in text
    assert "accessScope, accessSource, and accessReason" in text
    assert "library videos, and video context" in text
    assert "get_mcp_session" in text
    assert "context://brain-sync-contract" in text
    assert "repoFit.targetMap" in text
    assert "Claude custom connector URL: http://testserver/mcp" in text
    assert "Fallback path: create a bearer MCP token" in text


def test_public_full_agent_docs_include_ingestion_guardrails(monkeypatch):
    monkeypatch.setenv("SEARCHTUBE_AUTH_MODE", "supabase")

    from backend.server import app

    client = TestClient(app)
    response = client.get("/llms-full.txt")

    assert response.status_code == 200
    assert "Playlist and channel URLs require allow_bulk=true" in response.text
    assert "Recommended repo_context shape" in response.text
    assert "- locations: compact path" in response.text
    assert "- symbols: relevant functions" in response.text
    assert "get_repo_context_workflow" in response.text
    assert "context://repo-context-workflow" in response.text
    assert "prompts/get collect_repo_context" in response.text
    assert "validate_repo_context" in response.text
    assert "readiness.suggestedAgentNextSteps" in response.text
    assert "get_ingestion_job" in response.text


def test_public_mcp_manifest_has_agent_setup_metadata(monkeypatch):
    monkeypatch.setenv("SEARCHTUBE_AUTH_MODE", "supabase")

    from backend.server import app

    client = TestClient(app)
    response = client.get("/mcp.json")

    assert response.status_code == 200
    manifest = response.json()
    assert manifest["transport"]["url"] == "http://testserver/mcp"
    assert manifest["auth"]["type"] == "oauth_or_bearer"
    assert manifest["auth"]["preferred"] == "oauth_custom_connector"
    assert manifest["auth"]["setupBundle"]["mcpEndpoint"] == "http://testserver/mcp"
    assert manifest["auth"]["setupBundle"]["manifestUrl"] == "http://testserver/mcp.json"
    assert manifest["auth"]["setupBundle"]["claudeCustomConnector"]["url"] == (
        "http://testserver/mcp"
    )
    assert (
        "Customize > Connectors"
        in manifest["auth"]["setupBundle"]["claudeCustomConnector"]["setupSteps"][0]
    )
    assert (
        "get_mcp_session"
        in manifest["auth"]["setupBundle"]["claudeCustomConnector"]["initialPrompt"]
    )
    assert manifest["auth"]["setupBundle"]["accessModel"]["searchScope"] == "current_user_grants"
    assert manifest["auth"]["setupBundle"]["accessModel"]["globalSearch"] == "not_exposed"
    assert manifest["auth"]["setupBundle"]["accessModel"]["visibilityGrants"] == [
        "user_videos",
        "user_channels",
    ]
    assert "Bearer ${MEMEXAI_MCP_TOKEN}" in manifest["auth"]["setupBundle"]["hermesConfig"]
    assert "[mcp_servers.memexai]" in manifest["auth"]["setupBundle"]["codexConfig"]
    assert (
        'bearer_token_env_var = "MEMEXAI_MCP_TOKEN"'
        in manifest["auth"]["setupBundle"]["codexConfig"]
    )
    assert "does not spend" in manifest["auth"]["setupBundle"]["codexSetupNote"]
    assert "oneTimeCredential" not in manifest["auth"]["setupBundle"]
    assert manifest["auth"]["oauth"]["mcpEndpoint"] == "http://testserver/mcp"
    assert manifest["auth"]["oauth"]["clientRegistration"] == "http://testserver/oauth/register"
    assert {scope["name"] for scope in manifest["auth"]["scopes"]} == {
        "context:read",
        "overlay:write",
        "ingest:write",
        "capture:write",
        "project:write",
    }
    assert manifest["accessModel"]["visibilityGrants"] == ["user_videos", "user_channels"]
    assert "current user" in manifest["accessModel"]["searchScope"]
    assert manifest["accessModel"]["searchProvenanceFields"] == [
        "accessScope",
        "accessSource",
        "accessReason",
    ]
    assert manifest["accessModel"]["searchModes"]["default"] == "current_user_grants"
    assert manifest["accessModel"]["searchModes"]["globalSearch"] == "not_exposed"
    assert "context://repo-context-contract" in manifest["resources"]
    assert "context://repo-context-workflow" in manifest["resources"]
    assert "context://agent-quickstart" in manifest["resources"]
    assert "context://brain-sync-contract" in manifest["resources"]
    assert "context://brain-digest" in manifest["resources"]
    assert "category_filters" in manifest["retrievalCapabilities"]["categoryFilterSyntax"]["shape"]
    assert (
        "hybrid vector plus keyword/title retrieval over transcript chunks"
        in manifest["retrievalCapabilities"]["current"]
    )
    assert manifest["storageDecision"]["hostedDefault"] == "supabase_postgres_pgvector"
    assert (
        manifest["storageDecision"]["userSelectableDatabase"] == "not_for_normal_hosted_onboarding"
    )
    assert manifest["repoContextWorkflow"]["preferred"] == "caller_supplied_repo_context"
    assert manifest["repoContextWorkflow"]["contractResource"] == "context://repo-context-contract"
    assert manifest["repoContextWorkflow"]["contractTool"] == "get_repo_context_contract"
    assert manifest["repoContextWorkflow"]["collectionPrompt"] == "collect_repo_context"
    assert manifest["repoContextWorkflow"]["validationTool"] == "validate_repo_context"
    assert manifest["repoContextWorkflow"]["readinessField"] == "readiness"
    assert manifest["repoContextWorkflow"]["readinessGate"]["preferredForImplementation"] == (
        "implementation_ready"
    )
    assert manifest["repoContextWorkflow"]["readinessGate"]["retryWhen"] == [
        "missing",
        "partial",
    ]
    assert manifest["repoContextWorkflow"]["collectPromptExpectedOutput"]["readiness"][
        "missingSignals"
    ]["repoMap"]
    assert "next_mcp_call" in manifest["repoContextWorkflow"]["collectPromptExpectedOutput"]
    assert "implementation_ready" in manifest["repoContextWorkflow"]["readinessLevels"]
    assert manifest["repoContextWorkflow"]["jsonSchema"]["properties"]["commands"]
    assert manifest["repoContextWorkflow"]["jsonSchema"]["recommended"] == [
        "source",
        "repo",
        "features",
        "constraints",
    ]
    assert manifest["repoContextWorkflow"]["schema"]["source"] == "agent-mcp"
    assert any(
        "validate_repo_context" in step and "readiness.suggestedAgentNextSteps" in step
        for step in manifest["repoContextWorkflow"]["steps"]
    )
    assert any("collect_repo_context" in step for step in manifest["repoContextWorkflow"]["steps"])
    assert "entrypoints" in manifest["repoContextWorkflow"]["schema"]
    assert "locations" in manifest["repoContextWorkflow"]["schema"]
    assert "symbols" in manifest["repoContextWorkflow"]["schema"]
    assert "commands" in manifest["repoContextWorkflow"]["schema"]
    assert "tests" in manifest["repoContextWorkflow"]["schema"]
    assert "active_changes" in manifest["repoContextWorkflow"]["schema"]
    assert manifest["agentOnboarding"]["preferred"] == "oauth_custom_connector"
    assert manifest["agentOnboarding"]["sessionTool"] == "get_mcp_session"
    assert manifest["agentOnboarding"]["quickstartResource"] == "context://agent-quickstart"
    assert manifest["agentOnboarding"]["quickstartTool"] == "get_agent_quickstart"
    assert "fallbackFlow" in manifest["agentOnboarding"]
    assert manifest["brainSync"]["version"] == "memexai-brain-sync-v1"
    assert manifest["brainSync"]["sourceTruth"]["readOnly"] is True
    assert any(
        surface["name"] == "incremental_digest_export" and "export_brain_digest" in surface["use"]
        for surface in manifest["brainSync"]["currentPullSurfaces"]
    )
    tool_names = {tool["name"] for tool in manifest["tools"]}
    prompt_names = {prompt["name"] for prompt in manifest["prompts"]}
    assert "get_mcp_session" in tool_names
    assert "build_agent_brief" in tool_names
    assert "search_video_concepts" in tool_names
    assert "get_video_knowledge_map" in tool_names
    assert "get_agent_quickstart" in tool_names
    assert "get_brain_sync_contract" in tool_names
    assert "export_brain_digest" in tool_names
    assert "get_repo_context_contract" in tool_names
    assert "get_repo_context_workflow" in tool_names
    assert "collect_repo_context" in prompt_names


def test_public_mcp_manifest_uses_forwarded_https_for_cloudflare_hosts(monkeypatch):
    monkeypatch.setenv("SEARCHTUBE_AUTH_MODE", "supabase")

    from backend.server import app

    client = TestClient(app)
    response = client.get(
        "/mcp.json",
        headers={
            "host": "memexai-api.cadecr.workers.dev",
            "x-forwarded-proto": "https",
        },
    )

    assert response.status_code == 200
    manifest = response.json()
    assert manifest["transport"]["url"] == "https://memexai-api.cadecr.workers.dev/mcp"
    assert (
        manifest["auth"]["setupBundle"]["manifestUrl"]
        == "https://memexai-api.cadecr.workers.dev/mcp.json"
    )


def test_well_known_mcp_manifest_alias_matches_public_manifest(monkeypatch):
    monkeypatch.setenv("SEARCHTUBE_AUTH_MODE", "supabase")

    from backend.server import app

    client = TestClient(app)
    assert client.get("/.well-known/mcp.json").json() == client.get("/mcp.json").json()


def test_ingestion_jobs_endpoint_is_empty_when_hosted_storage_unavailable(monkeypatch):
    monkeypatch.setenv("SEARCHTUBE_STORAGE", "supabase")
    monkeypatch.setenv("SEARCHTUBE_AUTH_MODE", "none")

    from backend import server

    monkeypatch.setattr(server, "is_supabase_mode", lambda: False)

    client = TestClient(server.app)
    response = client.get("/api/ingestion-jobs")

    assert response.status_code == 200
    assert response.json() == {"jobs": []}


def test_allowed_origins_default_to_local_dev(monkeypatch):
    monkeypatch.delenv("SEARCHTUBE_ALLOWED_ORIGINS", raising=False)

    from backend.config import get_allowed_origins

    assert get_allowed_origins() == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]


def test_allowed_origins_reads_comma_separated_production_values(monkeypatch):
    monkeypatch.setenv(
        "SEARCHTUBE_ALLOWED_ORIGINS",
        "https://app.example.com/, https://preview.example.pages.dev",
    )

    from backend.config import get_allowed_origins

    assert get_allowed_origins() == [
        "https://app.example.com",
        "https://preview.example.pages.dev",
    ]


def test_server_key_mode_resolves_server_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "server-key")
    monkeypatch.setenv("SEARCHTUBE_API_KEY_MODE", "server")

    from backend.server import resolve_api_key

    assert resolve_api_key() == ("server-key", False)


def test_storage_dispatch_uses_supabase_ingestion(monkeypatch):
    from backend import storage

    monkeypatch.setenv("SEARCHTUBE_STORAGE", "supabase")
    monkeypatch.setattr(
        storage,
        "ingest_url_pg",
        lambda url, user_id, api_key=None, used_own_key=False, digest_depth="standard": iter(
            [f"supabase:{url}:{user_id}:{api_key}:{used_own_key}:{digest_depth}"]
        ),
    )

    assert list(
        storage.ingest_url(
            "https://youtu.be/dQw4w9WgXcQ",
            user_id="user-1",
            api_key="key",
            used_own_key=True,
        )
    ) == ["supabase:https://youtu.be/dQw4w9WgXcQ:user-1:key:True:standard"]


def test_supabase_search_groups_nearby_duplicate_chunks():
    # Dedupe logic stays isolated in clip_selection for Supabase search.
    from backend.clip_selection import _is_near_existing

    existing = [
        {
            "videoId": "abc123",
            "startSeconds": 180,
            "endSeconds": 240,
        }
    ]

    assert _is_near_existing(
        {
            "videoId": "abc123",
            "startSeconds": 220,
            "endSeconds": 280,
        },
        existing,
    )
    assert not _is_near_existing(
        {
            "videoId": "abc123",
            "startSeconds": 420,
            "endSeconds": 480,
        },
        existing,
    )
