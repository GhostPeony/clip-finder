import json

from fastapi.testclient import TestClient


class Result:
    def __init__(self, data):
        self.data = data


class Query:
    def __init__(self, table_name, supabase):
        self.table_name = table_name
        self.supabase = supabase

    def select(self, *args, **kwargs):
        self.supabase.calls.append((self.table_name, "select", args, kwargs))
        return self

    def eq(self, column, value):
        self.supabase.calls.append((self.table_name, "eq", column, value))
        return self

    def match(self, payload):
        self.supabase.calls.append((self.table_name, "match", payload))
        return self

    def maybe_single(self):
        self.supabase.calls.append((self.table_name, "maybe_single"))
        return self

    def in_(self, column, values):
        self.supabase.calls.append((self.table_name, "in", column, values))
        return self

    def order(self, column, desc=False):
        self.supabase.calls.append((self.table_name, "order", column, desc))
        return self

    def limit(self, value):
        self.supabase.calls.append((self.table_name, "limit", value))
        return self

    def or_(self, expression):
        self.supabase.calls.append((self.table_name, "or", expression))
        return self

    def insert(self, payload):
        self.supabase.calls.append((self.table_name, "insert", payload))
        self.supabase.inserted[self.table_name] = payload
        return self

    def execute(self):
        if self.table_name in self.supabase.inserted:
            return Result([{**self.supabase.inserted[self.table_name], "id": "new-row"}])
        return Result(self.supabase.responses.get(self.table_name, []))


class Supabase:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.inserted = {}
        self.calls = []

    def table(self, table_name):
        self.calls.append(("table", table_name))
        return Query(table_name, self)


def _client(monkeypatch, supabase=None):
    from backend import server

    monkeypatch.setenv("SEARCHTUBE_AUTH_MODE", "none")
    monkeypatch.setattr(server, "is_supabase_mode", lambda: supabase is not None)
    if supabase is not None:
        monkeypatch.setattr(server, "get_supabase", lambda: supabase)
    return TestClient(server.app)


def test_tool_response_keeps_large_payload_once_in_structured_content():
    from backend import mcp_adapter

    long_report = "agent harness verification " * 500
    payload = {
        "video": {"videoId": "yt123", "title": "Reliable agent harnesses"},
        "knowledgeArtifacts": [
            {
                "title": "Source Report: Reliable agent harnesses",
                "content": long_report,
            }
        ],
        "sourceConcepts": [{"name": "Verification step", "summary": long_report}],
        "responseBudget": {
            "detailLevel": "deep",
            "estimatedResponseChars": len(long_report),
            "truncatedToBudget": False,
        },
    }

    result = mcp_adapter._tool_response(payload)
    text = result["content"][0]["text"]

    assert result["structuredContent"] == payload
    assert "Read result.structuredContent for the full JSON object." in text
    assert "Reliable agent harnesses" in text
    assert len(text) < 1_000
    assert long_report[:500] not in text


def test_mcp_initialize_negotiates_supported_protocol(monkeypatch):
    client = _client(monkeypatch)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-03-26"},
        },
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["protocolVersion"] == "2025-03-26"
    assert result["capabilities"] == {
        "tools": {"listChanged": False},
        "resources": {"subscribe": False, "listChanged": False},
        "prompts": {"listChanged": False},
    }
    assert result["serverInfo"]["name"] == "memexai-context"


def test_mcp_prompts_list_exposes_agent_workflows(monkeypatch):
    client = _client(monkeypatch)

    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 9, "method": "prompts/list"},
    )

    assert response.status_code == 200
    prompts = response.json()["result"]["prompts"]
    names = {prompt["name"] for prompt in prompts}
    assert "source_report_from_saved_video" in names
    assert "study_guide_from_saved_video" not in names
    assert "repo_implementation_brief" in names
    assert "collect_repo_context" in names
    assert "categorize_saved_video" in names
    assert "capture_personal_context" in names


def test_mcp_prompts_get_returns_repo_implementation_workflow(monkeypatch):
    client = _client(monkeypatch)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 10,
            "method": "prompts/get",
            "params": {
                "name": "repo_implementation_brief",
                "arguments": {
                    "query": "apply Sierra-style eval harness ideas",
                    "repo_context_hint": "agent training gym",
                },
            },
        },
    )

    assert response.status_code == 200
    result = response.json()["result"]
    text = result["messages"][0]["content"]["text"]
    assert (
        result["description"]
        == "Turn saved video knowledge into a repo-aware implementation brief."
    )
    assert "apply Sierra-style eval harness ideas" in text
    assert "agent training gym" in text
    assert "Call build_agent_brief" in text
    assert "Call validate_repo_context" in text
    assert "readiness.level = implementation_ready" in text
    assert "readiness.suggestedAgentNextSteps" in text
    assert "existing repo, filesystem, GitHub, or code-index tools" in text
    assert "commands, tests" in text


def test_mcp_prompts_get_returns_collect_repo_context_workflow(monkeypatch):
    client = _client(monkeypatch)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 12,
            "method": "prompts/get",
            "params": {
                "name": "collect_repo_context",
                "arguments": {
                    "implementation_goal": "wire Sierra ideas into the eval runner",
                    "repo_context_hint": "eval runner and workflow modules",
                },
            },
        },
    )

    assert response.status_code == 200
    result = response.json()["result"]
    text = result["messages"][0]["content"]["text"]
    assert result["description"] == "Collect and validate caller-supplied repo_context."
    assert "wire Sierra ideas into the eval runner" in text
    assert "eval runner and workflow modules" in text
    assert "get_repo_context_contract" in text
    assert "validate_repo_context" in text
    assert "readiness.level is partial" in text
    assert "Expected output shape" in text
    assert "next_mcp_call" in text
    assert "readyForImplementationBrief" in text
    assert "Do not call build_agent_brief" in text
    assert "existing repo, filesystem, GitHub, or code-index tools" in text


def test_mcp_tools_list_exposes_repo_context_contract_tool(monkeypatch):
    client = _client(monkeypatch)

    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 42, "method": "tools/list"},
    )

    assert response.status_code == 200
    tools = response.json()["result"]["tools"]
    session_tool = next(item for item in tools if item["name"] == "get_mcp_session")
    assert session_tool["annotations"]["readOnlyHint"] is True
    assert "effective scopes" in session_tool["description"]
    quickstart_tool = next(item for item in tools if item["name"] == "get_agent_quickstart")
    assert quickstart_tool["annotations"]["readOnlyHint"] is True
    assert "does not require database access" in quickstart_tool["description"]
    graph_tool = next(item for item in tools if item["name"] == "get_library_source_graph")
    assert graph_tool["annotations"]["readOnlyHint"] is True
    assert "review flags" in graph_tool["description"]
    component_tool = next(item for item in tools if item["name"] == "search_library_components")
    assert component_tool["annotations"]["readOnlyHint"] is True
    assert component_tool["inputSchema"]["properties"]["component_types"]["items"]["enum"] == [
        "video",
        "source_label",
        "source_concept",
        "source_edge",
        "knowledge_artifact",
        "transcript_chunk",
        "agent_note",
        "personal_concept",
    ]
    brain_tool = next(item for item in tools if item["name"] == "get_brain_sync_contract")
    assert brain_tool["annotations"]["readOnlyHint"] is True
    assert brain_tool["inputSchema"]["additionalProperties"] is False
    assert "external personal brain" in brain_tool["description"]
    digest_tool = next(item for item in tools if item["name"] == "export_brain_digest")
    assert digest_tool["annotations"]["readOnlyHint"] is True
    digest_schema = digest_tool["inputSchema"]
    assert digest_schema["properties"]["objects"]["items"]["enum"] == [
        "videos",
        "labels",
        "concepts",
        "artifacts",
        "notes",
        "personal_concepts",
    ]
    assert "max_chars" in digest_schema["properties"]
    tool = next(item for item in tools if item["name"] == "get_repo_context_contract")
    assert tool["annotations"]["readOnlyHint"] is True
    assert tool["inputSchema"]["additionalProperties"] is False
    assert "does not read or store repository data" in tool["description"]
    validate_tool = next(item for item in tools if item["name"] == "validate_repo_context")
    validate_schema = validate_tool["inputSchema"]["properties"]["repo_context"]
    assert validate_schema["properties"]["entrypoints"]["oneOf"][0]["maxItems"] == 20
    assert validate_schema["properties"]["locations"]["oneOf"]
    assert validate_schema["properties"]["symbols"]["description"]
    assert validate_schema["properties"]["commands"]["oneOf"][1]["type"] == "string"
    brief_tool = next(item for item in tools if item["name"] == "build_agent_brief")
    brief_schema = brief_tool["inputSchema"]["properties"]["repo_context"]
    assert brief_schema["properties"]["tests"]
    assert brief_schema["recommended"] == ["source", "repo", "features", "constraints"]


def test_mcp_resources_list_exposes_library_notes_and_video_resources(monkeypatch):
    from backend import mcp_adapter

    def fake_library(supabase, user_id, limit):
        return {
            "channels": [
                {
                    "name": "AI Explained",
                    "videos": [
                        {
                            "videoId": "yt-a",
                            "title": "Reward Models",
                        }
                    ],
                }
            ],
            "limit": limit,
        }

    supabase = Supabase()
    monkeypatch.setattr(mcp_adapter, "list_video_library_context", fake_library)
    client = _client(monkeypatch, supabase)

    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 11, "method": "resources/list"},
    )

    assert response.status_code == 200
    resources = response.json()["result"]["resources"]
    uris = {resource["uri"] for resource in resources}
    assert "context://agent-quickstart" in uris
    assert "context://brain-sync-contract" in uris
    assert "context://brain-digest" in uris
    assert "context://library" in uris
    assert "context://library-graph" in uris
    assert "context://repo-context-contract" in uris
    assert "context://repo-context-workflow" in uris
    assert "context://capture-sources" in uris
    assert "context://notes" in uris
    assert "context://workflows" in uris
    assert "context://video/yt-a" in uris
    assert all(resource["mimeType"] == "application/json" for resource in resources)


def test_mcp_resources_read_returns_agent_quickstart_without_supabase(monkeypatch):
    client = _client(monkeypatch)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 46,
            "method": "resources/read",
            "params": {"uri": "context://agent-quickstart"},
        },
    )

    assert response.status_code == 200
    contents = response.json()["result"]["contents"]
    payload = json.loads(contents[0]["text"])
    assert contents[0]["uri"] == "context://agent-quickstart"
    assert payload["version"] == "memexai-agent-quickstart-v1"
    assert any("accessScope" in rule for rule in payload["coreRules"])
    assert any("library videos" in rule for rule in payload["coreRules"])
    assert "get_mcp_session" in payload["recommendedFlow"][0]["use"]
    repo_step = next(
        step for step in payload["recommendedFlow"] if step["step"] == "shape_repo_context"
    )
    assert "get_repo_context_contract" in repo_step["use"]
    assert "get_repo_context_workflow" in repo_step["use"]
    assert "prompts/get: collect_repo_context" in repo_step["use"]
    brain_step = next(
        step for step in payload["recommendedFlow"] if step["step"] == "sync_external_brain"
    )
    assert "get_brain_sync_contract" in brain_step["use"]
    assert "export_brain_digest" in brain_step["use"]
    assert "context://brain-digest" in brain_step["use"]
    assert payload["brainSyncContract"]["sourceTruth"]["readOnly"] is True
    assert payload["jsonRpcExamples"]["getBrainSyncContract"]["params"]["name"] == (
        "get_brain_sync_contract"
    )
    assert payload["repoContextWorkflow"]["readinessGate"]["preferredForImplementation"] == (
        "implementation_ready"
    )
    assert payload["repoContextWorkflow"]["collectPromptExpectedOutput"]["next_mcp_call"]
    assert payload["jsonRpcExamples"]["readRepoContextWorkflow"]["params"]["uri"] == (
        "context://repo-context-workflow"
    )
    assert payload["jsonRpcExamples"]["getRepoContextWorkflow"]["params"]["name"] == (
        "get_repo_context_workflow"
    )
    assert payload["jsonRpcExamples"]["collectRepoContextPrompt"]["params"]["name"] == (
        "collect_repo_context"
    )
    assert payload["jsonRpcExamples"]["validateRepoContext"]["params"]["name"] == (
        "validate_repo_context"
    )


def test_mcp_resources_read_returns_brain_sync_contract_without_supabase(monkeypatch):
    client = _client(monkeypatch)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 48,
            "method": "resources/read",
            "params": {"uri": "context://brain-sync-contract"},
        },
    )

    assert response.status_code == 200
    contents = response.json()["result"]["contents"]
    payload = json.loads(contents[0]["text"])
    assert contents[0]["uri"] == "context://brain-sync-contract"
    assert payload["version"] == "memexai-brain-sync-v1"
    assert payload["sourceTruth"]["readOnly"] is True
    assert payload["personalOverlay"]["tools"] == ["add_context_note", "upsert_personal_concept"]
    assert payload["accessModel"]["scope"] == "current_user_grants"


def test_mcp_resources_read_returns_brain_digest_with_supabase(monkeypatch):
    from backend import mcp_adapter

    def fake_digest(supabase, user_id, limit):
        return {
            "version": "memexai-brain-digest-v1",
            "userId": user_id,
            "limit": limit,
            "digest": {"videos": []},
        }

    supabase = Supabase()
    monkeypatch.setattr(mcp_adapter, "build_brain_digest_export", fake_digest)
    client = _client(monkeypatch, supabase)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 53,
            "method": "resources/read",
            "params": {"uri": "context://brain-digest"},
        },
    )

    assert response.status_code == 200
    contents = response.json()["result"]["contents"]
    payload = json.loads(contents[0]["text"])
    assert contents[0]["uri"] == "context://brain-digest"
    assert payload["version"] == "memexai-brain-digest-v1"
    assert payload["userId"] == "local"
    assert payload["limit"] == 20


def test_mcp_resources_read_returns_library_source_graph(monkeypatch):
    from backend import mcp_adapter

    def fake_graph(supabase, user_id, limit):
        return {
            "version": "memexai-library-source-graph-v1",
            "userId": user_id,
            "limit": limit,
            "graph": {"nodes": [{"id": "concept:1"}], "edges": []},
            "reviewFlags": [{"type": "potential_conflict"}],
        }

    supabase = Supabase()
    monkeypatch.setattr(mcp_adapter, "build_library_source_graph", fake_graph)
    client = _client(monkeypatch, supabase)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 54,
            "method": "resources/read",
            "params": {"uri": "context://library-graph"},
        },
    )

    assert response.status_code == 200
    contents = response.json()["result"]["contents"]
    payload = json.loads(contents[0]["text"])
    assert contents[0]["uri"] == "context://library-graph"
    assert payload["version"] == "memexai-library-source-graph-v1"
    assert payload["userId"] == "local"
    assert payload["limit"] == 50
    assert payload["reviewFlags"][0]["type"] == "potential_conflict"


def test_mcp_resources_read_returns_repo_context_contract_without_supabase(monkeypatch):
    client = _client(monkeypatch)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 43,
            "method": "resources/read",
            "params": {"uri": "context://repo-context-contract"},
        },
    )

    assert response.status_code == 200
    contents = response.json()["result"]["contents"]
    payload = json.loads(contents[0]["text"])
    assert contents[0]["uri"] == "context://repo-context-contract"
    assert payload["version"] == "caller-supplied-repo-context-v1"
    assert payload["recommendedFields"]["repo"]
    assert payload["recommendedFields"]["commands"]
    assert payload["recommendedFields"]["tests"]
    assert payload["recommendedFields"]["active_changes"]
    assert payload["jsonSchema"]["properties"]["entrypoints"]["oneOf"]
    assert payload["jsonSchema"]["properties"]["locations"]["oneOf"]
    assert payload["jsonSchema"]["properties"]["symbols"]["oneOf"]
    assert payload["normalization"]["listFieldsAcceptSingleString"] is True
    assert "agent-mcp" in payload["example"]["source"]


def test_mcp_resources_read_returns_repo_context_workflow_without_supabase(monkeypatch):
    client = _client(monkeypatch)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 48,
            "method": "resources/read",
            "params": {"uri": "context://repo-context-workflow"},
        },
    )

    assert response.status_code == 200
    contents = response.json()["result"]["contents"]
    payload = json.loads(contents[0]["text"])
    assert contents[0]["uri"] == "context://repo-context-workflow"
    assert payload["collectionPrompt"] == "collect_repo_context"
    assert payload["readinessGate"]["preferredForImplementation"] == "implementation_ready"
    assert payload["collectPromptExpectedOutput"]["next_mcp_call"]


def test_mcp_resources_read_returns_video_context(monkeypatch):
    from backend import mcp_adapter

    calls = []

    def fake_video_context(supabase, user_id, video_id):
        calls.append((supabase, user_id, video_id))
        return {
            "video": {"videoId": video_id, "title": "Reward Models"},
            "sourceConcepts": [{"name": "Reward model"}],
        }

    supabase = Supabase()
    monkeypatch.setattr(mcp_adapter, "get_video_context", fake_video_context)
    client = _client(monkeypatch, supabase)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 12,
            "method": "resources/read",
            "params": {"uri": "context://video/yt-a"},
        },
    )

    assert response.status_code == 200
    contents = response.json()["result"]["contents"]
    assert calls == [(supabase, "local", "yt-a")]
    assert contents[0]["uri"] == "context://video/yt-a"
    assert contents[0]["mimeType"] == "application/json"
    assert '"Reward model"' in contents[0]["text"]
    assert '"includeTranscript": false' in contents[0]["text"]


def test_mcp_get_video_context_omits_transcript_until_explicitly_requested(monkeypatch):
    from backend import mcp_adapter

    def fake_video_context(supabase, user_id, video_id):
        del supabase, user_id
        return {
            "video": {"videoId": video_id, "title": "Reward Models"},
            "transcriptLines": [
                {"id": f"line-{index}", "content": f"line content {index}"} for index in range(60)
            ],
            "transcriptChunks": [
                {"id": f"chunk-{index}", "content": f"chunk content {index}"} for index in range(60)
            ],
            "sourceConcepts": [{"name": "Reward model", "summary": "Evaluate responses."}],
            "knowledgeArtifacts": [{"title": "Study Guide", "content": "Reward model " * 100}],
        }

    supabase = Supabase()
    monkeypatch.setattr(mcp_adapter, "get_video_context", fake_video_context)
    client = _client(monkeypatch, supabase)

    compact_response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 13,
            "method": "tools/call",
            "params": {
                "name": "get_video_context",
                "arguments": {"youtube_video_id": "yt-a"},
            },
        },
    )

    assert compact_response.status_code == 200
    compact = compact_response.json()["result"]["structuredContent"]
    assert compact["transcriptLines"] == []
    assert compact["transcriptChunks"] == []
    assert compact["transcriptBudget"]["includeTranscript"] is False
    assert compact["transcriptBudget"]["availableTranscriptLines"] == 60
    assert compact["responseBudget"]["detailLevel"] == "compact"
    assert len(compact["knowledgeArtifacts"][0]["content"]) <= 700

    deep_response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 14,
            "method": "tools/call",
            "params": {
                "name": "get_video_context",
                "arguments": {
                    "youtube_video_id": "yt-a",
                    "include_transcript": True,
                    "detail_level": "standard",
                    "max_chars": 12000,
                },
            },
        },
    )

    assert deep_response.status_code == 200
    deep = deep_response.json()["result"]["structuredContent"]
    assert deep["transcriptBudget"]["includeTranscript"] is True
    assert deep["transcriptBudget"]["returnedTranscriptLines"] == 50
    assert deep["transcriptBudget"]["returnedTranscriptChunks"] == 50
    assert deep["responseBudget"]["detailLevel"] == "standard"


def test_mcp_resources_read_returns_context_categories(monkeypatch):
    from backend import mcp_adapter

    calls = []

    def fake_categories(supabase, user_id, limit):
        calls.append((supabase, user_id, limit))
        return {"facets": {"domain": ["AI product"]}, "categories": []}

    supabase = Supabase()
    monkeypatch.setattr(mcp_adapter, "list_context_categories", fake_categories)
    client = _client(monkeypatch, supabase)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 13,
            "method": "resources/read",
            "params": {"uri": "context://categories"},
        },
    )

    assert response.status_code == 200
    contents = response.json()["result"]["contents"]
    assert calls == [(supabase, "local", 100)]
    assert contents[0]["uri"] == "context://categories"
    assert '"AI product"' in contents[0]["text"]


def test_mcp_resources_read_returns_capture_sources(monkeypatch):
    from backend import mcp_adapter

    calls = []

    def fake_capture_sources(supabase, user_id, limit):
        calls.append((supabase, user_id, limit))
        return {"captureSources": [{"title": "Memexai Inbox"}]}

    supabase = Supabase()
    monkeypatch.setattr(mcp_adapter, "build_capture_sources_context", fake_capture_sources)
    client = _client(monkeypatch, supabase)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 14,
            "method": "resources/read",
            "params": {"uri": "context://capture-sources"},
        },
    )

    assert response.status_code == 200
    contents = response.json()["result"]["contents"]
    assert calls == [(supabase, "local", 100)]
    assert contents[0]["uri"] == "context://capture-sources"
    assert '"Memexai Inbox"' in contents[0]["text"]


def test_mcp_resources_read_returns_workflow_status(monkeypatch):
    from backend import mcp_adapter

    calls = []

    def fake_workflow_status(supabase, user_id, limit):
        calls.append((supabase, user_id, limit))
        return {"workflowInstances": [{"id": "workflow-1", "status": "running"}]}

    supabase = Supabase()
    monkeypatch.setattr(mcp_adapter, "build_workflow_status_context", fake_workflow_status)
    client = _client(monkeypatch, supabase)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 15,
            "method": "resources/read",
            "params": {"uri": "context://workflows"},
        },
    )

    assert response.status_code == 200
    contents = response.json()["result"]["contents"]
    assert calls == [(supabase, "local", 50)]
    assert contents[0]["uri"] == "context://workflows"
    assert '"workflow-1"' in contents[0]["text"]


def test_mcp_resources_read_returns_one_workflow_run(monkeypatch):
    from backend import mcp_adapter

    calls = []

    def fake_workflow(supabase, user_id, instance_id):
        calls.append((supabase, user_id, instance_id))
        return {
            "id": instance_id,
            "status": "completed",
            "workflow_steps": [{"step_key": "publish_context"}],
        }

    supabase = Supabase()
    monkeypatch.setattr(mcp_adapter, "get_workflow_instance", fake_workflow)
    client = _client(monkeypatch, supabase)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 16,
            "method": "resources/read",
            "params": {"uri": "context://workflow/workflow-1"},
        },
    )

    assert response.status_code == 200
    contents = response.json()["result"]["contents"]
    assert calls == [(supabase, "local", "workflow-1")]
    assert contents[0]["uri"] == "context://workflow/workflow-1"
    assert '"publish_context"' in contents[0]["text"]


def test_mcp_tools_list_exposes_context_tools_only(monkeypatch):
    client = _client(monkeypatch)

    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    )

    assert response.status_code == 200
    tools = response.json()["result"]["tools"]
    names = {tool["name"] for tool in tools}
    assert "get_mcp_session" in names
    assert "get_brain_sync_contract" in names
    assert "list_video_library" in names
    assert "list_capture_sources" in names
    assert "list_context_categories" in names
    assert "list_ingestion_jobs" in names
    assert "get_ingestion_job" in names
    assert "list_workflow_runs" in names
    assert "get_workflow_run" in names
    assert "get_repo_context_contract" in names
    assert "get_repo_context_workflow" in names
    assert "validate_repo_context" in names
    assert "search_video_concepts" in names
    assert "get_video_knowledge_map" in names
    assert "search_video_moments" in names
    assert "get_video_context" in names
    assert "build_context_bundle" in names
    assert "build_agent_brief" in names
    assert "queue_youtube_ingestion" in names
    assert "add_context_note" in names
    assert "ingest_youtube_url" not in names
    assert "update_source_concept" not in names
    search_tool = next(tool for tool in tools if tool["name"] == "search_video_concepts")
    assert search_tool["inputSchema"]["properties"]["retrieval_mode"]["default"] == "hybrid"


def test_mcp_list_video_library_returns_user_library(monkeypatch):
    from backend import mcp_adapter

    calls = []

    def fake_library(supabase, user_id, limit):
        calls.append((supabase, user_id, limit))
        return {
            "channels": [
                {
                    "id": "channel-a",
                    "name": "AI Explained",
                    "youtubeHandle": "@ai",
                    "returnedVideoCount": 1,
                    "videos": [
                        {
                            "videoId": "yt-a",
                            "title": "Reward Models",
                            "accessScope": "video",
                            "accessSource": "shared_existing",
                            "accessReason": "Visible through an explicit saved-video grant.",
                        }
                    ],
                }
            ],
            "totalChannels": 1,
            "returnedVideos": 1,
            "limit": limit,
        }

    supabase = Supabase()
    monkeypatch.setattr(mcp_adapter, "list_video_library_context", fake_library)
    client = _client(monkeypatch, supabase)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 22,
            "method": "tools/call",
            "params": {
                "name": "list_video_library",
                "arguments": {"limit": 999},
            },
        },
    )

    assert response.status_code == 200
    structured = response.json()["result"]["structuredContent"]
    assert calls == [(supabase, "local", 100)]
    assert structured["channels"][0]["videos"][0]["videoId"] == "yt-a"
    assert structured["channels"][0]["videos"][0]["accessScope"] == "video"
    assert structured["channels"][0]["videos"][0]["accessSource"] == "shared_existing"
    assert structured["limit"] == 100


def test_mcp_list_capture_sources_returns_user_sources(monkeypatch):
    from backend import mcp_adapter

    calls = []

    def fake_capture_sources(supabase, user_id, limit):
        calls.append((supabase, user_id, limit))
        return {
            "captureSources": [
                {
                    "id": "capture-1",
                    "title": "Memexai Inbox",
                    "source_type": "playlist",
                }
            ]
        }

    supabase = Supabase()
    monkeypatch.setattr(mcp_adapter, "build_capture_sources_context", fake_capture_sources)
    client = _client(monkeypatch, supabase)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 31,
            "method": "tools/call",
            "params": {
                "name": "list_capture_sources",
                "arguments": {"limit": 999},
            },
        },
    )

    assert response.status_code == 200
    structured = response.json()["result"]["structuredContent"]
    assert calls == [(supabase, "local", 100)]
    assert structured["captureSources"][0]["title"] == "Memexai Inbox"


def test_mcp_build_context_bundle_accepts_agent_repo_context(monkeypatch):
    supabase = Supabase(
        {
            "agent_notes": [{"id": "note-1", "content": "Use for eval harness"}],
            "personal_concepts": [{"id": "concept-1", "name": "Model training gym"}],
        }
    )
    client = _client(monkeypatch, supabase)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "build_context_bundle",
                "arguments": {
                    "query": "apply this RLHF lesson",
                    "repo_context": {
                        "source": "agent-mcp",
                        "repo": "GhostPeony/open-model-gym",
                        "features": ["evaluation harness"],
                    },
                    "category_filters": {"task_fit": ["product spec"]},
                    "limit": 999,
                },
            },
        },
    )

    assert response.status_code == 200
    result = response.json()["result"]
    structured = result["structuredContent"]
    assert structured["repoContext"]["source"] == "agent-mcp"
    assert structured["categoryFilters"] == {"task_fit": ["product spec"]}
    assert structured["personalConcepts"][0]["name"] == "Model training gym"
    assert ("agent_notes", "limit", 20) in supabase.calls
    assert ("personal_concepts", "limit", 20) in supabase.calls
    assert "open-model-gym" in result["content"][0]["text"]


def test_mcp_list_context_categories_returns_agent_discovery_facets(monkeypatch):
    from backend import mcp_adapter

    calls = []

    def fake_categories(supabase, user_id, limit):
        calls.append((supabase, user_id, limit))
        return {
            "categories": [
                {
                    "labelType": "task_fit",
                    "label": "eval harness",
                    "count": 1,
                }
            ],
            "facets": {"task_fit": ["eval harness"]},
            "personalConcepts": [],
        }

    supabase = Supabase()
    monkeypatch.setattr(mcp_adapter, "list_context_categories", fake_categories)
    client = _client(monkeypatch, supabase)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 32,
            "method": "tools/call",
            "params": {
                "name": "list_context_categories",
                "arguments": {"limit": 999},
            },
        },
    )

    assert response.status_code == 200
    structured = response.json()["result"]["structuredContent"]
    assert calls == [(supabase, "local", 200)]
    assert structured["facets"]["task_fit"] == ["eval harness"]


def test_mcp_list_ingestion_jobs_returns_recent_agent_submissions(monkeypatch):
    from backend import mcp_adapter

    calls = []

    def fake_jobs(supabase, user_id, limit):
        calls.append((supabase, user_id, limit))
        return [{"id": "job-1", "status": "completed"}]

    supabase = Supabase()
    monkeypatch.setattr(mcp_adapter, "list_ingestion_jobs", fake_jobs)
    client = _client(monkeypatch, supabase)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 37,
            "method": "tools/call",
            "params": {
                "name": "list_ingestion_jobs",
                "arguments": {"limit": 999},
            },
        },
    )

    assert response.status_code == 200
    structured = response.json()["result"]["structuredContent"]
    assert calls == [(supabase, "local", 50)]
    assert structured["jobs"][0]["id"] == "job-1"


def test_mcp_validate_repo_context_returns_contract(monkeypatch):
    client = _client(monkeypatch, Supabase())

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 41,
            "method": "tools/call",
            "params": {
                "name": "validate_repo_context",
                "arguments": {
                    "repo_context": {
                        "source": "agent-mcp",
                        "repo": "GhostPeony/memexai",
                        "files": ["backend/context.py"],
                    }
                },
            },
        },
    )

    assert response.status_code == 200
    structured = response.json()["result"]["structuredContent"]
    assert structured["valid"] is True
    assert structured["normalized"]["repo"] == "GhostPeony/memexai"
    assert structured["contract"]["recommendedFields"]["features"]
    assert structured["readiness"]["level"] == "partial"
    assert structured["readiness"]["readyForImplementationBrief"] is False
    assert structured["next_mcp_call"]["name"] == "validate_repo_context"
    assert any(
        "commands or tests" in step for step in structured["readiness"]["suggestedAgentNextSteps"]
    )


def test_mcp_get_repo_context_contract_does_not_require_supabase(monkeypatch):
    client = _client(monkeypatch)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 44,
            "method": "tools/call",
            "params": {"name": "get_repo_context_contract", "arguments": {}},
        },
    )

    assert response.status_code == 200
    structured = response.json()["result"]["structuredContent"]
    assert structured["version"] == "caller-supplied-repo-context-v1"
    assert "filesystem, GitHub" in structured["purpose"]
    assert structured["readinessLevels"]["implementation_ready"]
    assert structured["example"]["repo"] == "GhostPeony/open-model-gym"


def test_mcp_get_repo_context_workflow_does_not_require_supabase(monkeypatch):
    client = _client(monkeypatch)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 49,
            "method": "tools/call",
            "params": {"name": "get_repo_context_workflow", "arguments": {}},
        },
    )

    assert response.status_code == 200
    structured = response.json()["result"]["structuredContent"]
    assert structured["preferred"] == "caller_supplied_repo_context"
    assert structured["contractResource"] == "context://repo-context-contract"
    assert structured["readinessGate"]["minimumForBrief"] == "brief_ready"
    assert structured["collectPromptExpectedOutput"]["repo_context"].startswith(
        "normalized repo_context"
    )


def test_mcp_get_brain_sync_contract_does_not_require_supabase(monkeypatch):
    client = _client(monkeypatch)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 45,
            "method": "tools/call",
            "params": {"name": "get_brain_sync_contract", "arguments": {}},
        },
    )

    assert response.status_code == 200
    structured = response.json()["result"]["structuredContent"]
    assert structured["version"] == "memexai-brain-sync-v1"
    assert structured["role"]["embedMoments"].startswith("Canonical saved-video source system")
    assert structured["sourceTruth"]["readOnly"] is True
    assert "search_video_concepts" in structured["currentPullSurfaces"][2]["use"]
    assert "get_video_knowledge_map" in structured["currentPullSurfaces"][2]["use"]
    assert "search_transcript_text" in structured["currentPullSurfaces"][2]["use"]
    digest_surface = next(
        surface
        for surface in structured["currentPullSurfaces"]
        if surface["name"] == "incremental_digest_export"
    )
    assert digest_surface["status"] == "available"
    assert "export_brain_digest" in digest_surface["use"]
    assert structured["currentPushSurfaces"][0]["name"] == "outbound_sync_outbox"
    assert structured["currentPushSurfaces"][0]["status"] == "available"
    assert structured["plannedSyncSurfaces"][0]["name"] == "webhook_delivery_worker"
    assert structured["budgetControls"]["defaultMode"] == "compact"


def test_mcp_export_brain_digest_uses_budget_and_filters(monkeypatch):
    from backend import mcp_adapter

    captured = {}

    def fake_digest(
        supabase,
        user_id,
        cursor=None,
        since=None,
        objects=None,
        limit=20,
        detail_level="compact",
        max_chars=None,
        max_context_tokens=None,
    ):
        captured.update(
            {
                "supabase": supabase,
                "user_id": user_id,
                "cursor": cursor,
                "since": since,
                "objects": objects,
                "limit": limit,
                "detail_level": detail_level,
                "max_chars": max_chars,
                "max_context_tokens": max_context_tokens,
            }
        )
        return {
            "version": "memexai-brain-digest-v1",
            "sync": {"nextCursor": "cursor-2"},
            "digest": {"agentNotes": [{"id": "note-1"}]},
        }

    supabase = Supabase()
    monkeypatch.setattr(mcp_adapter, "build_brain_digest_export", fake_digest)
    client = _client(monkeypatch, supabase)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 54,
            "method": "tools/call",
            "params": {
                "name": "export_brain_digest",
                "arguments": {
                    "cursor": "cursor-1",
                    "since": "2026-06-20T12:30:00Z",
                    "objects": ["notes", "personal_concepts"],
                    "limit": 7,
                    "detail_level": "standard",
                    "max_chars": 4000,
                    "max_context_tokens": 1000,
                },
            },
        },
    )

    assert response.status_code == 200
    structured = response.json()["result"]["structuredContent"]
    assert structured["version"] == "memexai-brain-digest-v1"
    assert structured["sync"]["nextCursor"] == "cursor-2"
    assert captured == {
        "supabase": supabase,
        "user_id": "local",
        "cursor": "cursor-1",
        "since": "2026-06-20T12:30:00Z",
        "objects": ["notes", "personal_concepts"],
        "limit": 7,
        "detail_level": "standard",
        "max_chars": 4000,
        "max_context_tokens": 1000,
    }


def test_mcp_get_agent_quickstart_does_not_require_supabase(monkeypatch):
    client = _client(monkeypatch)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 47,
            "method": "tools/call",
            "params": {"name": "get_agent_quickstart", "arguments": {}},
        },
    )

    assert response.status_code == 200
    structured = response.json()["result"]["structuredContent"]
    assert structured["version"] == "memexai-agent-quickstart-v1"
    assert "source video context is read-only" in " ".join(structured["coreRules"]).lower()
    assert structured["jsonRpcExamples"]["queueSingleVideo"]["params"]["name"] == (
        "queue_youtube_ingestion"
    )


def test_mcp_get_session_does_not_require_supabase_and_reports_default_scopes(monkeypatch):
    client = _client(monkeypatch)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 50,
            "method": "tools/call",
            "params": {"name": "get_mcp_session", "arguments": {}},
        },
    )

    assert response.status_code == 200
    structured = response.json()["result"]["structuredContent"]
    assert structured["version"] == "memexai-mcp-session-v1"
    assert structured["authKind"] == "local"
    assert structured["effectiveScopes"] == ["context:read", "overlay:write"]
    assert structured["next_mcp_call"]["name"] == "get_agent_quickstart"
    assert "search_video_concepts" in structured["recommendedNextCalls"]
    assert "get_video_knowledge_map" in structured["recommendedNextCalls"]
    assert "get_video_knowledge_map for candidate videos" in structured["preferredRetrievalFlow"]
    assert "queue_youtube_ingestion" not in structured["recommendedNextCalls"]


def test_mcp_get_session_explains_missing_context_scope_without_supabase():
    from backend import mcp_adapter

    response, status = mcp_adapter.handle_mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 51,
            "method": "tools/call",
            "params": {"name": "get_mcp_session", "arguments": {}},
        },
        "user-1",
        None,
        ["ingest:write"],
        {"auth_kind": "mcp_token"},
    )

    assert status == 200
    structured = response["result"]["structuredContent"]
    assert structured["authKind"] == "mcp_token"
    assert structured["effectiveScopes"] == ["ingest:write"]
    assert structured["missingRecommendedScopes"] == ["context:read", "overlay:write"]
    assert structured["next_mcp_call"]["when"] == "after_scope_upgrade"
    read_capability = next(
        capability
        for capability in structured["capabilities"]
        if capability["name"] == "read_saved_video_context"
    )
    assert read_capability["allowed"] is False
    assert "queue_youtube_ingestion" in structured["recommendedNextCalls"]


def test_mcp_validate_repo_context_does_not_require_supabase(monkeypatch):
    client = _client(monkeypatch)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 45,
            "method": "tools/call",
            "params": {
                "name": "validate_repo_context",
                "arguments": {"repo_context": {"repo": "GhostPeony/memexai"}},
            },
        },
    )

    assert response.status_code == 200
    structured = response.json()["result"]["structuredContent"]
    assert structured["valid"] is True
    assert structured["normalized"]["repo"] == "GhostPeony/memexai"
    assert structured["readiness"]["level"] == "partial"
    assert structured["readiness"]["readyForBrief"] is False
    assert structured["next_mcp_call"]["name"] == "validate_repo_context"


def test_mcp_get_ingestion_job_returns_scoped_job_events(monkeypatch):
    from backend import mcp_adapter

    calls = []

    def fake_job(supabase, user_id, job_id):
        calls.append((supabase, user_id, job_id))
        return {
            "id": job_id,
            "status": "running",
            "ingestion_job_events": [{"message": "Starting ingestion"}],
        }

    supabase = Supabase()
    monkeypatch.setattr(mcp_adapter, "get_ingestion_job", fake_job)
    client = _client(monkeypatch, supabase)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 38,
            "method": "tools/call",
            "params": {
                "name": "get_ingestion_job",
                "arguments": {"job_id": "job-1"},
            },
        },
    )

    assert response.status_code == 200
    structured = response.json()["result"]["structuredContent"]
    assert calls == [(supabase, "local", "job-1")]
    assert structured["found"] is True
    assert structured["job"]["ingestion_job_events"][0]["message"] == "Starting ingestion"


def test_mcp_list_workflow_runs_returns_recent_platform_workflows(monkeypatch):
    from backend import mcp_adapter

    calls = []

    def fake_workflows(supabase, user_id, limit):
        calls.append((supabase, user_id, limit))
        return [{"id": "workflow-1", "status": "waiting"}]

    supabase = Supabase()
    monkeypatch.setattr(mcp_adapter, "list_workflow_instances", fake_workflows)
    client = _client(monkeypatch, supabase)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 39,
            "method": "tools/call",
            "params": {
                "name": "list_workflow_runs",
                "arguments": {"limit": 999},
            },
        },
    )

    assert response.status_code == 200
    structured = response.json()["result"]["structuredContent"]
    assert calls == [(supabase, "local", 50)]
    assert structured["workflowInstances"][0]["status"] == "waiting"


def test_mcp_get_workflow_run_returns_steps_and_artifacts(monkeypatch):
    from backend import mcp_adapter

    calls = []

    def fake_workflow(supabase, user_id, instance_id):
        calls.append((supabase, user_id, instance_id))
        return {
            "id": instance_id,
            "status": "completed",
            "workflow_artifacts": [{"artifact_type": "study_guide"}],
        }

    supabase = Supabase()
    monkeypatch.setattr(mcp_adapter, "get_workflow_instance", fake_workflow)
    client = _client(monkeypatch, supabase)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 40,
            "method": "tools/call",
            "params": {
                "name": "get_workflow_run",
                "arguments": {"workflow_instance_id": "workflow-1"},
            },
        },
    )

    assert response.status_code == 200
    structured = response.json()["result"]["structuredContent"]
    assert calls == [(supabase, "local", "workflow-1")]
    assert structured["found"] is True
    assert structured["workflowInstance"]["workflow_artifacts"][0]["artifact_type"] == "study_guide"


def test_mcp_build_agent_brief_accepts_agent_repo_context(monkeypatch):
    from backend import mcp_adapter

    calls = []

    def fake_brief(supabase, user_id, query, repo_context, limit, category_filters=None):
        calls.append((supabase, user_id, query, repo_context, limit, category_filters))
        return {
            "title": "Agent Brief: apply reward models",
            "repoContext": repo_context,
            "categoryFilters": category_filters,
            "keyConcepts": [{"name": "Reward model"}],
            "citations": [{"youtube_video_id": "yt123", "start_seconds": 30}],
        }

    supabase = Supabase()
    monkeypatch.setattr(mcp_adapter, "build_agent_brief", fake_brief)
    client = _client(monkeypatch, supabase)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 34,
            "method": "tools/call",
            "params": {
                "name": "build_agent_brief",
                "arguments": {
                    "query": "apply reward models",
                    "repo_context": {
                        "source": "agent-mcp",
                        "repo": "GhostPeony/open-model-gym",
                        "features": ["evaluation harness"],
                    },
                    "category_filters": {"method": ["reward modeling"]},
                    "limit": 999,
                },
            },
        },
    )

    assert response.status_code == 200
    structured = response.json()["result"]["structuredContent"]
    assert calls[0][1:] == (
        "local",
        "apply reward models",
        {
            "source": "agent-mcp",
            "repo": "GhostPeony/open-model-gym",
            "features": ["evaluation harness"],
        },
        20,
        {"method": ["reward modeling"]},
    )
    assert calls[0][0] is supabase
    assert structured["keyConcepts"][0]["name"] == "Reward model"
    assert structured["categoryFilters"] == {"method": ["reward modeling"]}
    assert structured["citations"][0]["youtube_video_id"] == "yt123"


def test_mcp_queue_youtube_ingestion_requires_ingest_write_scope(monkeypatch):
    client = _client(monkeypatch, Supabase())

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 35,
            "method": "tools/call",
            "params": {
                "name": "queue_youtube_ingestion",
                "arguments": {"url": "https://www.youtube.com/watch?v=uCKhOmth2ms"},
            },
        },
    )

    assert response.status_code == 200
    error = response.json()["error"]
    assert error["code"] == -32002
    assert "ingest:write" in error["message"]


def test_mcp_queue_youtube_ingestion_requires_bulk_approval_for_playlists(monkeypatch):
    from backend import mcp_adapter

    supabase = Supabase()
    response, status = mcp_adapter.handle_mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 39,
            "method": "tools/call",
            "params": {
                "name": "queue_youtube_ingestion",
                "arguments": {
                    "url": "https://www.youtube.com/playlist?list=PL12345678901",
                },
            },
        },
        "user-1",
        supabase,
        ["ingest:write"],
        {},
    )

    assert status == 200
    assert response["error"]["code"] == -32602
    assert "allow_bulk=true" in response["error"]["message"]
    assert ("table", "ingestion_jobs") not in supabase.calls


def test_mcp_queue_youtube_ingestion_creates_queued_job_with_scope(monkeypatch):
    from backend import mcp_adapter

    calls = []

    def fake_count_active(supabase, user_id):
        calls.append(("count", supabase, user_id))
        return 0

    def fake_create_job(supabase, user_id, source_url, source_type, cost_estimate=None):
        calls.append(("create", supabase, user_id, source_url, source_type, cost_estimate))
        return {
            "id": "job-1",
            "user_id": user_id,
            "source_url": source_url,
            "source_type": source_type,
            "status": "queued",
            "cost_estimate": cost_estimate,
        }

    def fake_record_event(supabase, job_id, level, message):
        calls.append(("event", supabase, job_id, level, message))
        return {"id": "event-1"}

    supabase = Supabase()
    monkeypatch.setattr(mcp_adapter, "count_active_ingestion_jobs", fake_count_active)
    monkeypatch.setattr(mcp_adapter, "create_ingestion_job", fake_create_job)
    monkeypatch.setattr(mcp_adapter, "record_ingestion_job_event", fake_record_event)
    monkeypatch.setattr(mcp_adapter, "get_free_max_active_ingestion_jobs", lambda: 1)

    queued_jobs = []
    response, status = mcp_adapter.handle_mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 36,
            "method": "tools/call",
            "params": {
                "name": "queue_youtube_ingestion",
                "arguments": {
                    "url": "https://www.youtube.com/watch?v=uCKhOmth2ms",
                    "created_by_client": "hermes",
                    "digest_depth": "basic",
                },
            },
        },
        "user-1",
        supabase,
        ["ingest:write"],
        {"queued_ingestion_jobs": queued_jobs},
    )

    assert status == 200
    structured = response["result"]["structuredContent"]
    assert structured["job"]["id"] == "job-1"
    assert structured["sourceType"] == "video"
    assert structured["extractedId"] == "uCKhOmth2ms"
    assert structured["digestDepth"] == "basic"
    assert structured["costEstimate"]["digestDepth"] == "basic"
    assert structured["costEstimate"]["videosToEmbed"] == 1
    assert structured["job"]["cost_estimate"]["videosToEmbed"] == 1
    assert calls[0] == ("count", supabase, "user-1")
    assert calls[1][:5] == (
        "create",
        supabase,
        "user-1",
        "https://www.youtube.com/watch?v=uCKhOmth2ms",
        "video",
    )
    assert calls[1][5]["sourceType"] == "video"
    assert calls[2] == ("event", supabase, "job-1", "info", "Queued from MCP by hermes.")
    assert queued_jobs == [structured["job"]]


def test_mcp_search_video_moments_uses_scoped_search_runner(monkeypatch):
    from backend import server

    calls = []

    def fake_search_for_user(
        query,
        user_id,
        limit,
        x_api_key=None,
        category_filters=None,
        retrieval_mode="hybrid",
    ):
        calls.append((query, user_id, limit, x_api_key, category_filters, retrieval_mode))
        return {
            "answer": "Reward models need evaluation loops. [[clip_0]]",
            "retrievalMode": retrieval_mode,
            "retrievalPlan": {
                "primary": "hybrid_vector_keyword_rrf",
                "embeddingUsed": True,
                "llmAnswerUsed": True,
            },
            "categoryFilters": category_filters or {},
            "relevantClips": [
                {
                    "id": "clip_0",
                    "videoId": "yt123",
                    "title": "RLHF lesson",
                    "channelName": "AI Channel",
                    "startSeconds": 120,
                    "endSeconds": 180,
                    "content": "Reward models need evaluation loops.",
                    "accessScope": "video",
                    "accessSource": "shared_existing",
                    "accessReason": "Visible through an explicit saved-video grant.",
                    "matchType": "hybrid",
                }
            ],
        }

    monkeypatch.setattr(server, "search_for_user", fake_search_for_user)
    client = _client(monkeypatch, Supabase())

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 33,
            "method": "tools/call",
            "params": {
                "name": "search_video_moments",
                "arguments": {
                    "query": "reward model eval loops",
                    "category_filters": {"task_fit": ["product spec"]},
                    "detail_level": "compact",
                    "max_context_tokens": 250,
                    "limit": 999,
                },
            },
        },
    )

    assert response.status_code == 200
    structured = response.json()["result"]["structuredContent"]
    assert calls == [
        ("reward model eval loops", "local", 20, None, {"task_fit": ["product spec"]}, "hybrid")
    ]
    assert structured["categoryFilters"] == {"task_fit": ["product spec"]}
    assert structured["retrievalMode"] == "hybrid"
    assert structured["retrievalPlan"]["primary"] == "hybrid_vector_keyword_rrf"
    assert structured["retrievalBudget"]["detailLevel"] == "compact"
    assert structured["retrievalBudget"]["maxChars"] == 1000
    assert structured["relevantClips"][0]["videoId"] == "yt123"
    assert structured["relevantClips"][0]["matchType"] == "hybrid"
    assert structured["relevantClips"][0]["accessScope"] == "video"
    assert structured["relevantClips"][0]["accessSource"] == "shared_existing"
    assert "timestamp citations" in structured["guidance"]
    assert "accessScope" in structured["guidance"]


def test_mcp_search_video_concepts_returns_budgeted_source_knowledge(monkeypatch):
    source_ref = {
        "source_type": "transcript",
        "youtube_video_id": "yt-harness",
        "start_seconds": 120,
        "end_seconds": 180,
    }
    supabase = Supabase(
        {
            "user_channels": [{"channel_id": "channel-db"}],
            "user_videos": [],
            "videos": [
                {
                    "id": "video-db",
                    "channel_id": "channel-db",
                    "youtube_video_id": "yt-harness",
                    "title": "Harness lesson",
                    "thumbnail_url": "thumb",
                    "transcript_seconds": 600,
                }
            ],
            "source_labels": [
                {
                    "id": "label-1",
                    "video_id": "video-db",
                    "label_type": "task_fit",
                    "label": "study guide",
                    "confidence": 0.9,
                }
            ],
            "source_concepts": [
                {
                    "id": "concept-1",
                    "video_id": "video-db",
                    "concept_type": "method",
                    "name": "Harness loop",
                    "summary": "Harness loops help teams evaluate agent behavior.",
                    "source_refs": [source_ref],
                }
            ],
            "source_edges": [],
            "knowledge_artifacts": [
                {
                    "id": "artifact-1",
                    "video_id": "video-db",
                    "artifact_type": "study_guide",
                    "title": "Harness Study Guide",
                    "summary": "A compact study guide for harness loops.",
                    "content": "Harness loop " * 120,
                    "source_refs": [source_ref],
                }
            ],
        }
    )
    client = _client(monkeypatch, supabase)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 35,
            "method": "tools/call",
            "params": {
                "name": "search_video_concepts",
                "arguments": {
                    "query": "harness loop",
                    "category_filters": {"task_fit": ["study guide"]},
                    "detail_level": "compact",
                    "max_chars": 4000,
                    "limit": 5,
                },
            },
        },
    )

    assert response.status_code == 200
    structured = response.json()["result"]["structuredContent"]
    assert structured["retrievalMode"] == "hybrid"
    assert structured["detailLevel"] == "compact"
    assert structured["categoryFilters"] == {"task_fit": ["study guide"]}
    assert structured["retrievalBudget"]["embeddingCalls"] == 0
    assert structured["retrievalBudget"]["llmCalls"] == 0
    assert structured["retrievalPlan"]["fallbackUsed"] is True
    assert structured["retrievalBudget"]["estimatedResponseChars"] <= 4000
    assert {item["resultType"] for item in structured["results"]} == {
        "source_concept",
        "knowledge_artifact",
    }
    assert structured["results"][0]["matchType"] == "concept_keyword"
    assert structured["results"][0]["video"]["accessScope"] == "channel"
    assert structured["results"][0]["video"]["accessSource"] == "channel"
    assert "timestamp evidence" in structured["guidance"]


def test_mcp_search_video_concepts_accepts_keyword_mode_without_embeddings(monkeypatch):
    supabase = Supabase(
        {
            "user_channels": [{"channel_id": "channel-db"}],
            "user_videos": [],
            "videos": [
                {
                    "id": "video-db",
                    "channel_id": "channel-db",
                    "youtube_video_id": "yt-keyword",
                    "title": "Reward modeling lesson",
                    "thumbnail_url": "",
                    "transcript_seconds": 300,
                }
            ],
            "source_labels": [],
            "source_concepts": [
                {
                    "id": "concept-1",
                    "video_id": "video-db",
                    "concept_type": "method",
                    "name": "Reward modeling",
                    "summary": "Reward modeling converts feedback into an evaluation signal.",
                    "source_refs": [],
                }
            ],
            "source_edges": [],
            "knowledge_artifacts": [],
        }
    )
    client = _client(monkeypatch, supabase)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 36,
            "method": "tools/call",
            "params": {
                "name": "search_video_concepts",
                "arguments": {
                    "query": "reward modeling",
                    "retrieval_mode": "keyword",
                    "limit": 5,
                },
            },
        },
    )

    assert response.status_code == 200
    structured = response.json()["result"]["structuredContent"]
    assert structured["retrievalMode"] == "keyword"
    assert structured["retrievalBudget"]["embeddingCalls"] == 0
    assert structured["results"][0]["resultType"] == "source_concept"


def test_mcp_get_video_knowledge_map_returns_compact_navigation(monkeypatch):
    source_ref = {
        "source_type": "transcript",
        "youtube_video_id": "yt-map",
        "start_seconds": 210,
        "end_seconds": 260,
    }
    supabase = Supabase(
        {
            "videos": {
                "id": "video-map",
                "channel_id": "channel-db",
                "youtube_video_id": "yt-map",
                "title": "Agent harness map",
                "thumbnail_url": "thumb",
                "transcript_seconds": 600,
            },
            "user_channels": {"user_id": "user-1"},
            "user_videos": [],
            "channels": {"id": "channel-db", "name": "Agent Channel"},
            "transcript_lines": [],
            "chunks": [],
            "source_edges": [],
            "source_concepts": [
                {
                    "id": "concept-1",
                    "video_id": "video-map",
                    "concept_type": "tool",
                    "name": "Verify step",
                    "summary": "Checks whether the agent actually completed the task.",
                    "source_refs": [source_ref],
                }
            ],
            "knowledge_artifacts": [
                {
                    "id": "artifact-1",
                    "video_id": "video-map",
                    "artifact_type": "study_guide",
                    "title": "Source Report: Agent harness map",
                    "summary": "Report summary.",
                    "content": (
                        "# Agent harness map\n\n"
                        "## Compiled Truth\n\n"
                        "Harnesses make reliability inspectable. (source: 3:30)"
                    ),
                    "source_refs": [source_ref],
                }
            ],
            "source_knowledge_index": [
                {
                    "id": "section-1",
                    "video_id": "video-map",
                    "source_object_type": "report_section",
                    "source_object_id": "artifact:0",
                    "section_key": "compiled-truth",
                    "title": "Compiled Truth",
                    "body": "Harnesses make reliability inspectable.",
                    "aliases": ["main takeaways"],
                    "source_refs": [source_ref],
                    "metadata": {"sectionOrder": 0},
                }
            ],
        }
    )
    client = _client(monkeypatch, supabase)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 37,
            "method": "tools/call",
            "params": {
                "name": "get_video_knowledge_map",
                "arguments": {
                    "youtube_video_id": "yt-map",
                    "detail_level": "compact",
                    "max_chars": 5000,
                },
            },
        },
    )

    assert response.status_code == 200
    structured = response.json()["result"]["structuredContent"]
    assert structured["found"] is True
    assert structured["reportSections"][0]["title"] == "Compiled Truth"
    assert structured["peopleOrganizationsTools"][0]["name"] == "Verify step"
    assert structured["timestampRefs"][0]["start_seconds"] == 210
    assert structured["next_mcp_call"]["name"] == "search_video_moments"


def test_mcp_search_library_components_returns_keyword_graph_matches(monkeypatch):
    from backend import mcp_adapter

    calls = []

    def fake_search(supabase, user_id, query, limit, component_types):
        calls.append((supabase, user_id, query, limit, component_types))
        return {
            "query": query,
            "retrievalMode": "component_keyword",
            "results": [
                {
                    "id": "concept-1",
                    "resultType": "source_concept",
                    "matchType": "concept_keyword",
                    "title": "Harness loop",
                    "summary": "Harness loops help agent QA.",
                    "video": {"videoId": "yt-harness", "title": "Harness lesson"},
                    "sourceRefs": [
                        {
                            "source_type": "transcript",
                            "youtube_video_id": "yt-harness",
                            "start_seconds": 120,
                        }
                    ],
                    "score": 1.0,
                }
            ],
            "componentTypes": ["source_concept"],
            "accessModel": {
                "scope": "current_user_grants",
                "embeddingUsed": False,
                "llmAnswerUsed": False,
            },
            "retrievalBudget": {
                "embeddingCalls": 0,
                "llmCalls": 0,
                "maxResults": limit,
                "searchedVideos": 1,
                "returnedResults": 1,
            },
            "guidance": "Component search is exact keyword matching.",
        }

    supabase = Supabase()
    monkeypatch.setattr(mcp_adapter, "search_library_components", fake_search)
    client = _client(monkeypatch, supabase)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 40,
            "method": "tools/call",
            "params": {
                "name": "search_library_components",
                "arguments": {
                    "query": "harness loop",
                    "component_types": ["source_concept"],
                    "limit": 999,
                    "max_chars": 2500,
                },
            },
        },
    )

    assert response.status_code == 200
    structured = response.json()["result"]["structuredContent"]
    assert calls == [(supabase, "local", "harness loop", 50, ["source_concept"])]
    assert structured["retrievalMode"] == "component_keyword"
    assert structured["accessModel"]["embeddingUsed"] is False
    assert structured["retrievalBudget"]["embeddingCalls"] == 0
    assert structured["retrievalBudget"]["llmCalls"] == 0
    assert structured["retrievalBudget"]["maxChars"] == 2500
    assert structured["results"][0]["resultType"] == "source_concept"


def test_mcp_search_video_moments_can_request_keyword_mode(monkeypatch):
    from backend import server

    calls = []

    def fake_search_for_user(
        query,
        user_id,
        limit,
        x_api_key=None,
        category_filters=None,
        retrieval_mode="hybrid",
    ):
        calls.append((query, user_id, limit, x_api_key, category_filters, retrieval_mode))
        return {
            "answer": "",
            "retrievalMode": retrieval_mode,
            "retrievalPlan": {
                "primary": "keyword_full_text",
                "embeddingUsed": False,
                "llmAnswerUsed": False,
            },
            "retrievalBudget": {
                "embeddingCalls": 0,
                "llmCalls": 0,
                "maxClips": limit,
            },
            "categoryFilters": {},
            "relevantClips": [
                {
                    "id": "clip_0",
                    "videoId": "yt-keyword",
                    "title": "Exact Term Lesson",
                    "channelName": "Research Channel",
                    "startSeconds": 0,
                    "endSeconds": 60,
                    "content": "The exact acronym appears here.",
                    "matchType": "transcript_keyword",
                }
            ],
        }

    monkeypatch.setattr(server, "search_for_user", fake_search_for_user)
    client = _client(monkeypatch, Supabase())

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 36,
            "method": "tools/call",
            "params": {
                "name": "search_video_moments",
                "arguments": {
                    "query": "exact acronym",
                    "retrieval_mode": "keyword",
                    "limit": 3,
                },
            },
        },
    )

    assert response.status_code == 200
    structured = response.json()["result"]["structuredContent"]
    assert calls == [("exact acronym", "local", 3, None, None, "keyword")]
    assert structured["retrievalMode"] == "keyword"
    assert structured["retrievalPlan"]["embeddingUsed"] is False
    assert structured["retrievalBudget"]["embeddingCalls"] == 0
    assert structured["relevantClips"][0]["matchType"] == "transcript_keyword"


def test_mcp_search_transcript_text_uses_keyword_runner_without_embedding_spend(monkeypatch):
    from backend import server

    calls = []

    def fake_search_transcript_text(
        query,
        user_id,
        limit,
        category_filters=None,
    ):
        calls.append((query, user_id, limit, category_filters))
        return {
            "retrievalMode": "keyword",
            "categoryFilters": category_filters or {},
            "retrievalPlan": {
                "primary": "keyword_full_text",
                "embeddingUsed": False,
                "llmAnswerUsed": False,
            },
            "retrievalBudget": {
                "embeddingCalls": 0,
                "llmCalls": 0,
                "maxClips": limit,
            },
            "relevantClips": [
                {
                    "id": "clip_0",
                    "videoId": "yt-china",
                    "title": "China, Robotics, & Open-Source AI",
                    "channelName": "AI Channel",
                    "startSeconds": 0,
                    "endSeconds": 60,
                    "content": "Open-source AI and robotics strategy in China.",
                    "keywordRank": 0.82,
                    "matchType": "title_keyword",
                    "accessScope": "video",
                    "accessSource": "playlist",
                    "accessReason": "Visible through an explicit saved-video grant.",
                }
            ],
        }

    monkeypatch.setattr(server, "search_transcript_text", fake_search_transcript_text)
    client = _client(monkeypatch, Supabase())

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 34,
            "method": "tools/call",
            "params": {
                "name": "search_transcript_text",
                "arguments": {
                    "query": "China Robotics Open-Source AI",
                    "category_filters": {"topic": ["robotics"]},
                    "max_chars": 3000,
                    "limit": 999,
                },
            },
        },
    )

    assert response.status_code == 200
    structured = response.json()["result"]["structuredContent"]
    assert calls == [("China Robotics Open-Source AI", "local", 20, {"topic": ["robotics"]})]
    assert structured["retrievalMode"] == "keyword"
    assert structured["retrievalBudget"]["embeddingCalls"] == 0
    assert structured["retrievalBudget"]["llmCalls"] == 0
    assert structured["retrievalBudget"]["maxChars"] == 3000
    assert structured["relevantClips"][0]["matchType"] == "title_keyword"
    assert "exact names" in structured["guidance"]
    assert "search_video_moments" in structured["guidance"]


def test_mcp_add_context_note_writes_only_personal_overlay(monkeypatch):
    supabase = Supabase()
    client = _client(monkeypatch, supabase)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "add_context_note",
                "arguments": {
                    "content": "Use this clip for the reward model curriculum.",
                    "source_refs": [{"source_type": "video", "source_id": "abc123"}],
                    "tags": ["rlhf"],
                    "created_by_client": "hermes",
                },
            },
        },
    )

    assert response.status_code == 200
    structured = response.json()["result"]["structuredContent"]
    assert structured["note"]["id"] == "new-row"
    assert supabase.inserted["agent_notes"]["user_id"] == "local"
    assert supabase.inserted["agent_notes"]["created_by"] == "agent"
    assert supabase.inserted["agent_notes"]["created_by_client"] == "hermes"
    assert all(call[0] not in {"chunks", "source_concepts", "videos"} for call in supabase.calls)


def test_mcp_source_write_tool_is_denied(monkeypatch):
    from backend import server

    def fail_get_supabase():
        raise AssertionError("source writes should not open the DB")

    monkeypatch.setenv("SEARCHTUBE_AUTH_MODE", "none")
    monkeypatch.setattr(server, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(server, "get_supabase", fail_get_supabase)
    client = TestClient(server.app)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "update_source_concept",
                "arguments": {"id": "concept-1", "summary": "Rewrite source truth"},
            },
        },
    )

    assert response.status_code == 200
    error = response.json()["error"]
    assert error["code"] == -32001
    assert "read-only" in error["message"]


def test_mcp_notification_returns_no_response(monkeypatch):
    client = _client(monkeypatch)

    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
    )

    assert response.status_code == 202
    assert not response.content


def test_mcp_invalid_json_returns_parse_error(monkeypatch):
    client = _client(monkeypatch)

    response = client.post(
        "/mcp",
        content="{",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 200
    error = response.json()["error"]
    assert error["code"] == -32700
