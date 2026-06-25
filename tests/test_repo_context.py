from fastapi.testclient import TestClient

from backend.repo_context import (
    normalize_repo_context,
    repo_context_json_schema,
    repo_context_workflow_contract,
    validate_repo_context,
)


def test_validate_repo_context_normalizes_compact_payload():
    result = validate_repo_context(
        {
            "source": " agent-mcp ",
            "repo": "GhostPeony/open-model-gym",
            "files": [" backend/evals.py ", "backend/evals.py", "agents/harness.ts"],
            "locations": [
                " backend/evals.py:42 run_eval_suite ",
                "backend/evals.py:42 run_eval_suite",
            ],
            "entrypoints": [" POST /api/evals/run "],
            "symbols": [" run_eval_suite ", "AgentHarness", "run_eval_suite"],
            "features": "evaluation harness",
            "dependencies": [" Supabase ", "Supabase", "OpenAI SDK"],
            "commands": "python -m pytest tests/test_evals.py -q",
            "tests": ["tests/test_evals.py"],
            "deployment": ["Cloudflare container worker"],
            "active_changes": ["preserve user-authored eval runner changes"],
            "constraints": ["Supabase remains system of record"],
            "irrelevant_blob": {"note": "kept small"},
        }
    )

    assert result["valid"] is True
    assert result["normalized"]["source"] == "agent-mcp"
    assert result["normalized"]["files"] == ["backend/evals.py", "agents/harness.ts"]
    assert result["normalized"]["locations"] == ["backend/evals.py:42 run_eval_suite"]
    assert result["normalized"]["entrypoints"] == ["POST /api/evals/run"]
    assert result["normalized"]["symbols"] == ["run_eval_suite", "AgentHarness"]
    assert result["normalized"]["features"] == ["evaluation harness"]
    assert result["normalized"]["dependencies"] == ["Supabase", "OpenAI SDK"]
    assert result["normalized"]["commands"] == ["python -m pytest tests/test_evals.py -q"]
    assert result["normalized"]["tests"] == ["tests/test_evals.py"]
    assert result["normalized"]["deployment"] == ["Cloudflare container worker"]
    assert result["normalized"]["active_changes"] == ["preserve user-authored eval runner changes"]
    assert result["normalized"]["extra"]["irrelevant_blob"] == {"note": "kept small"}
    assert "Extra fields" in result["warnings"][0]
    assert result["contract"]["version"] == "caller-supplied-repo-context-v1"
    assert result["contract"]["jsonSchema"]["properties"]["commands"]["oneOf"]
    assert result["readiness"]["level"] == "implementation_ready"
    assert result["readiness"]["readyForBrief"] is True
    assert result["readiness"]["readyForImplementationBrief"] is True
    assert result["readiness"]["signals"]["repoMap"] == [
        "files",
        "entrypoints",
        "symbols",
        "locations",
    ]
    assert result["readiness"]["signals"]["verification"] == ["commands", "tests"]
    assert result["next_mcp_call"]["name"] == "build_agent_brief"
    assert result["next_mcp_call"]["when"] == "next"


def test_repo_context_json_schema_exposes_agent_mcp_fields():
    schema = repo_context_json_schema()

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is True
    assert schema["recommended"] == ["source", "repo", "features", "constraints"]
    assert schema["properties"]["repo"]["type"] == "string"
    assert schema["properties"]["files"]["oneOf"][0]["maxItems"] == 20
    assert schema["properties"]["locations"]["description"]
    assert schema["properties"]["symbols"]["oneOf"][1]["type"] == "string"
    assert schema["properties"]["commands"]["oneOf"][1]["type"] == "string"
    assert schema["properties"]["active_changes"]["description"]


def test_repo_context_workflow_contract_exposes_collect_prompt_output_shape():
    workflow = repo_context_workflow_contract()

    assert workflow["preferred"] == "caller_supplied_repo_context"
    assert workflow["collectionPrompt"] == "collect_repo_context"
    assert workflow["readinessGate"]["preferredForImplementation"] == "implementation_ready"
    assert workflow["readinessGate"]["retryWhen"] == ["missing", "partial"]
    assert workflow["jsonSchema"]["properties"]["commands"]
    expected_output = workflow["collectPromptExpectedOutput"]
    assert expected_output["repo_context"].startswith("normalized repo_context")
    assert expected_output["readiness"]["level"] == (
        "missing | partial | brief_ready | implementation_ready"
    )
    assert expected_output["readiness"]["missingSignals"]["verification"]
    assert expected_output["next_mcp_call"]["name"].startswith("validate_repo_context")


def test_normalize_repo_context_rejects_non_object_payload():
    assert normalize_repo_context("not an object") == {}
    result = validate_repo_context("not an object")
    assert result["valid"] is False
    assert "repo_context must be an object." in result["warnings"]
    assert result["readiness"]["level"] == "missing"
    assert result["readiness"]["readyForBrief"] is False


def test_validate_repo_context_guides_agents_to_inspect_missing_repo_signals():
    result = validate_repo_context(
        {
            "source": "agent-mcp",
            "repo": "GhostPeony/memexai",
            "features": ["agent brief generation"],
            "constraints": ["source context is read-only"],
        }
    )

    assert result["valid"] is True
    assert result["readiness"]["level"] == "partial"
    assert result["readiness"]["readyForBrief"] is False
    assert result["readiness"]["missingSignals"]["repoMap"] == [
        "files",
        "modules",
        "entrypoints",
        "symbols",
        "locations",
    ]
    assert result["readiness"]["missingSignals"]["verification"] == ["commands", "tests"]
    assert any(
        "filesystem/GitHub/code-index MCP" in step
        for step in result["readiness"]["suggestedAgentNextSteps"]
    )
    assert result["next_mcp_call"]["name"] == "validate_repo_context"
    assert result["next_mcp_call"]["when"] == "after_more_repo_inspection"


def test_repo_context_validation_endpoint(monkeypatch):
    from backend import server

    monkeypatch.setenv("SEARCHTUBE_AUTH_MODE", "none")
    client = TestClient(server.app)

    response = client.post(
        "/api/context/repo-context/validate",
        json={
            "repo_context": {
                "source": "agent-mcp",
                "repo": "GhostPeony/memexai",
                "features": ["MCP context"],
            }
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["normalized"]["repo"] == "GhostPeony/memexai"
    assert "constraints" in data["missingRecommended"]
    assert data["readiness"]["level"] == "partial"
    assert data["readiness"]["readyForImplementationBrief"] is False
    assert data["next_mcp_call"]["name"] == "validate_repo_context"
