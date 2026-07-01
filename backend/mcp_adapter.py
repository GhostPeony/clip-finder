"""Minimal MCP JSON-RPC adapter for user-scoped context tools."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import unquote, urlparse

try:
    from .billing import resolve_user_entitlements
    from .capture import build_capture_sources_context, create_playlist_capture_source
    from .capture_workflows import run_capture_sync_workflow
    from .config import get_free_max_active_ingestion_jobs
    from .context import (
        build_agent_brief,
        build_brain_digest_export,
        build_context_bundle,
        build_library_source_graph,
        build_project_context_map,
        build_video_knowledge_map,
        create_agent_note,
        get_video_context,
        list_agent_notes,
        list_context_categories,
        list_video_library_context,
        normalize_detail_level,
        response_char_budget,
        search_library_components,
        search_source_knowledge,
        upsert_personal_concept,
    )
    from .digest_depth import DEFAULT_DIGEST_DEPTH, DIGEST_DEPTH_VALUES, normalize_digest_depth
    from .ingestion_costs import build_ingestion_cost_estimate
    from .jobs import (
        count_active_ingestion_jobs,
        create_ingestion_job,
        get_ingestion_job,
        list_ingestion_jobs,
        record_ingestion_job_event,
    )
    from .projects import create_project, list_projects, resolve_project_scope
    from .repo_context import (
        describe_repo_context_contract,
        repo_context_json_schema,
        repo_context_workflow_contract,
        validate_repo_context,
    )
    from .workflows import (
        build_workflow_status_context,
        get_workflow_instance,
        list_workflow_instances,
    )
    from .youtube_utils import detect_url_type
except ImportError:
    from billing import resolve_user_entitlements
    from capture import build_capture_sources_context, create_playlist_capture_source
    from capture_workflows import run_capture_sync_workflow
    from config import get_free_max_active_ingestion_jobs
    from context import (
        build_agent_brief,
        build_brain_digest_export,
        build_context_bundle,
        build_library_source_graph,
        build_project_context_map,
        build_video_knowledge_map,
        create_agent_note,
        get_video_context,
        list_agent_notes,
        list_context_categories,
        list_video_library_context,
        normalize_detail_level,
        response_char_budget,
        search_library_components,
        search_source_knowledge,
        upsert_personal_concept,
    )
    from digest_depth import DEFAULT_DIGEST_DEPTH, DIGEST_DEPTH_VALUES, normalize_digest_depth
    from ingestion_costs import build_ingestion_cost_estimate
    from jobs import (
        count_active_ingestion_jobs,
        create_ingestion_job,
        get_ingestion_job,
        list_ingestion_jobs,
        record_ingestion_job_event,
    )
    from projects import create_project, list_projects, resolve_project_scope
    from repo_context import (
        describe_repo_context_contract,
        repo_context_json_schema,
        repo_context_workflow_contract,
        validate_repo_context,
    )
    from workflows import (
        build_workflow_status_context,
        get_workflow_instance,
        list_workflow_instances,
    )
    from youtube_utils import detect_url_type

JSONRPC_VERSION = "2.0"
LATEST_PROTOCOL_VERSION = "2025-11-25"
SUPPORTED_PROTOCOL_VERSIONS = (
    "2024-11-05",
    "2025-03-26",
    "2025-06-18",
    "2025-11-25",
)

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
SERVER_ERROR = -32000
SOURCE_READ_ONLY = -32001
FORBIDDEN = -32002

SOURCE_WRITE_TOOL_NAMES = {
    "delete_video",
    "ingest_youtube_url",
    "mutate_source_graph",
    "update_source_concept",
    "update_source_edge",
    "update_transcript",
    "write_transcript_line",
}
READ_TOOL_NAMES = {
    "export_brain_digest",
    "get_brain_sync_contract",
    "get_agent_quickstart",
    "get_project_context_map",
    "get_library_source_graph",
    "get_video_knowledge_map",
    "get_repo_context_contract",
    "get_repo_context_workflow",
    "validate_repo_context",
    "get_ingestion_job",
    "get_workflow_run",
    "list_capture_sources",
    "list_context_categories",
    "list_projects",
    "list_ingestion_jobs",
    "list_workflow_runs",
    "list_video_library",
    "get_video_context",
    "get_transcript_window",
    "list_agent_notes",
    "build_context_bundle",
    "build_agent_brief",
    "search_library_components",
    "search_transcript_text",
    "search_video_concepts",
    "search_video_moments",
}
OVERLAY_WRITE_TOOL_NAMES = {"add_context_note", "upsert_personal_concept"}
INGEST_WRITE_TOOL_NAMES = {"queue_youtube_ingestion"}
CAPTURE_WRITE_TOOL_NAMES = {"link_youtube_playlist_capture_source", "sync_capture_source"}
PROJECT_WRITE_TOOL_NAMES = {"create_project"}
DB_FREE_TOOL_NAMES = {
    "get_brain_sync_contract",
    "get_agent_quickstart",
    "get_mcp_session",
    "get_repo_context_contract",
    "get_repo_context_workflow",
    "validate_repo_context",
}
DEFAULT_SCOPES = ["context:read", "overlay:write"]
MAX_INLINE_TOOL_TEXT_CHARS = 4_000
MAX_TOOL_TEXT_SUMMARY_ITEMS = 5

SERVER_INFO = {
    "name": "memexai-context",
    "title": "Memexai Context",
    "version": "0.1.0",
}


class McpAdapterError(Exception):
    """Structured JSON-RPC error raised by adapter validation."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def parse_error_response() -> dict:
    """Return a JSON-RPC parse error for invalid request bodies."""
    return _error(None, PARSE_ERROR, "Parse error")


def mcp_payload_requires_supabase(payload: Any) -> bool:
    """Return whether the payload includes an allowed MCP request that needs the database."""
    if isinstance(payload, list):
        return any(mcp_payload_requires_supabase(message) for message in payload)
    if not isinstance(payload, dict):
        return False

    method = payload.get("method")
    if method == "resources/read":
        params = payload.get("params")
        if isinstance(params, dict) and params.get("uri") in {
            "context://agent-quickstart",
            "context://brain-sync-contract",
            "context://repo-context-contract",
            "context://repo-context-workflow",
        }:
            return False
        return True
    if method == "resources/list":
        return True
    if method != "tools/call":
        return False

    params = payload.get("params")
    return (
        isinstance(params, dict)
        and params.get("name") in TOOL_HANDLERS
        and params.get("name") not in DB_FREE_TOOL_NAMES
    )


def handle_mcp_request(
    payload: Any,
    user_id: str,
    supabase: Any | None,
    scopes: list[str] | None = None,
    tool_context: dict | None = None,
) -> tuple[Any | None, int]:
    """Handle one MCP JSON-RPC message or batch.

    The adapter is intentionally stateless and only exposes tools. Source
    knowledge remains read-only; writes go to the user's personal overlay.
    """
    if isinstance(payload, list):
        if not payload:
            return _error(None, INVALID_REQUEST, "Invalid Request"), 200

        responses = []
        for message in payload:
            response = _handle_message(message, user_id, supabase, scopes, tool_context or {})
            if response is not None:
                responses.append(response)

        return (responses, 200) if responses else (None, 202)

    response = _handle_message(payload, user_id, supabase, scopes, tool_context or {})
    return (response, 200) if response is not None else (None, 202)


def _handle_message(
    message: Any,
    user_id: str,
    supabase: Any | None,
    scopes: list[str] | None,
    tool_context: dict,
) -> dict | None:
    if not isinstance(message, dict):
        return _error(None, INVALID_REQUEST, "Invalid Request")

    request_id = message.get("id")
    method = message.get("method")
    is_notification = "id" not in message

    if message.get("jsonrpc") != JSONRPC_VERSION or not isinstance(method, str):
        if is_notification:
            return None
        return _error(request_id, INVALID_REQUEST, "Invalid Request")

    try:
        if method == "initialize":
            return _result(request_id, _initialize_result(message.get("params")))
        if method == "ping":
            return _result(request_id, {})
        if method == "tools/list":
            return _result(request_id, {"tools": TOOLS})
        if method == "tools/call":
            return _result(
                request_id,
                _call_tool(message.get("params"), user_id, supabase, scopes, tool_context),
            )
        if method == "prompts/list":
            return _result(request_id, {"prompts": PROMPTS})
        if method == "prompts/get":
            return _result(request_id, _get_prompt(message.get("params")))
        if method == "resources/list":
            return _result(request_id, _list_resources(user_id, supabase, scopes))
        if method == "resources/read":
            return _result(
                request_id, _read_resource(message.get("params"), user_id, supabase, scopes)
            )
        if method.startswith("notifications/"):
            return None
    except McpAdapterError as exc:
        if is_notification:
            return None
        return _error(request_id, exc.code, exc.message)
    except Exception as exc:
        if is_notification:
            return None
        return _error(request_id, INTERNAL_ERROR, f"Internal error: {exc}")

    if is_notification:
        return None
    return _error(request_id, METHOD_NOT_FOUND, f"Method not found: {method}")


def _initialize_result(params: Any) -> dict:
    requested_protocol = None
    if isinstance(params, dict):
        requested_protocol = params.get("protocolVersion")

    protocol_version = (
        requested_protocol
        if requested_protocol in SUPPORTED_PROTOCOL_VERSIONS
        else LATEST_PROTOCOL_VERSION
    )
    return {
        "protocolVersion": protocol_version,
        "capabilities": {
            "tools": {"listChanged": False},
            "resources": {"subscribe": False, "listChanged": False},
            "prompts": {"listChanged": False},
        },
        "serverInfo": SERVER_INFO,
        "instructions": (
            "Read source video context and transcript-derived knowledge. "
            "Write only personal overlay notes or concepts; do not mutate source context. "
            "With ingest:write, agents may queue YouTube URLs for ingestion, but indexed "
            "source context remains read-only. With capture:write, agents may preview and "
            "explicitly queue sync jobs for the user's linked YouTube capture sources."
        ),
    }


def _call_tool(
    params: Any,
    user_id: str,
    supabase: Any | None,
    scopes: list[str] | None,
    tool_context: dict,
) -> dict:
    if not isinstance(params, dict):
        raise McpAdapterError(INVALID_PARAMS, "tools/call params must be an object")

    tool_name = params.get("name")
    if not isinstance(tool_name, str) or not tool_name:
        raise McpAdapterError(INVALID_PARAMS, "tools/call params.name must be a tool name")
    if tool_name in SOURCE_WRITE_TOOL_NAMES:
        raise McpAdapterError(
            SOURCE_READ_ONLY,
            "Source video context is read-only over MCP; write notes or personal concepts instead.",
        )
    if tool_name not in TOOL_HANDLERS:
        raise McpAdapterError(METHOD_NOT_FOUND, f"Tool not found: {tool_name}")

    _authorize_tool_scope(tool_name, scopes)

    arguments = params.get("arguments", {})
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise McpAdapterError(INVALID_PARAMS, "tools/call params.arguments must be an object")

    if supabase is None and tool_name not in DB_FREE_TOOL_NAMES:
        raise McpAdapterError(SERVER_ERROR, "Context MCP tools are only available in hosted mode")

    effective_context = {
        **tool_context,
        "effective_scopes": list(scopes or DEFAULT_SCOPES),
    }
    return TOOL_HANDLERS[tool_name](supabase, user_id, arguments, effective_context)


def _authorize_tool_scope(tool_name: str, scopes: list[str] | None) -> None:
    effective_scopes = set(scopes or DEFAULT_SCOPES)
    if tool_name in READ_TOOL_NAMES and "context:read" not in effective_scopes:
        raise McpAdapterError(FORBIDDEN, "MCP token is missing the context:read scope")
    if tool_name in OVERLAY_WRITE_TOOL_NAMES and "overlay:write" not in effective_scopes:
        raise McpAdapterError(FORBIDDEN, "MCP token is missing the overlay:write scope")
    if tool_name in INGEST_WRITE_TOOL_NAMES and "ingest:write" not in effective_scopes:
        raise McpAdapterError(FORBIDDEN, "MCP token is missing the ingest:write scope")
    if tool_name in CAPTURE_WRITE_TOOL_NAMES and "capture:write" not in effective_scopes:
        raise McpAdapterError(FORBIDDEN, "MCP token is missing the capture:write scope")
    if tool_name in PROJECT_WRITE_TOOL_NAMES and "project:write" not in effective_scopes:
        raise McpAdapterError(FORBIDDEN, "MCP token is missing the project:write scope")


def _authorize_context_read(scopes: list[str] | None) -> None:
    if "context:read" not in set(scopes or DEFAULT_SCOPES):
        raise McpAdapterError(FORBIDDEN, "MCP token is missing the context:read scope")


def _get_prompt(params: Any) -> dict:
    if not isinstance(params, dict):
        raise McpAdapterError(INVALID_PARAMS, "prompts/get params must be an object")

    prompt_name = params.get("name")
    if not isinstance(prompt_name, str) or not prompt_name:
        raise McpAdapterError(INVALID_PARAMS, "prompts/get params.name must be a prompt name")
    if prompt_name not in PROMPT_BUILDERS:
        raise McpAdapterError(METHOD_NOT_FOUND, f"Prompt not found: {prompt_name}")

    arguments = params.get("arguments", {})
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise McpAdapterError(INVALID_PARAMS, "prompts/get params.arguments must be an object")

    return PROMPT_BUILDERS[prompt_name](arguments)


def _ensure_supabase(supabase: Any | None) -> Any:
    if supabase is None:
        raise McpAdapterError(
            SERVER_ERROR, "Context MCP resources are only available in hosted mode"
        )
    return supabase


def describe_brain_sync_contract() -> dict:
    """Return the compact contract external agent brains should sync against."""
    return {
        "version": "memexai-brain-sync-v1",
        "purpose": (
            "Let a user's existing personal agent or central brain ingest Memexai "
            "as a governed source of saved-video knowledge without direct database access."
        ),
        "role": {
            "embedMoments": (
                "Canonical saved-video source system: videos, transcript chunks, source "
                "labels, extracted concepts, and generated artifacts."
            ),
            "externalBrain": (
                "Personal memory, project memory, or agent operating context that can pull "
                "compact digests, remember preferences, and write user-specific notes back."
            ),
        },
        "sourceTruth": {
            "readOnly": True,
            "mutableByExternalBrain": False,
            "provenanceRequired": [
                "videoId",
                "youtubeUrl",
                "timestampRefs",
                "accessScope",
                "accessSource",
                "accessReason",
            ],
        },
        "personalOverlay": {
            "writeAllowed": True,
            "tools": ["add_context_note", "upsert_personal_concept"],
            "guidance": (
                "External brains should store subjective takeaways, preferences, and "
                "project relevance in the overlay, not by rewriting source video context."
            ),
        },
        "currentPullSurfaces": [
            {
                "name": "project_scopes",
                "use": ["list_projects", "context://projects", "get_project_context_map"],
                "defaultGranularity": "explicit user project boundaries and scoped video maps",
            },
            {
                "name": "library_snapshot",
                "use": ["list_video_library", "context://library"],
                "defaultGranularity": "video metadata and access provenance",
            },
            {
                "name": "category_map",
                "use": ["list_context_categories", "context://categories"],
                "defaultGranularity": "facets, labels, and personal concepts",
            },
            {
                "name": "evidence_search",
                "use": [
                    "search_video_concepts",
                    "get_video_knowledge_map",
                    "search_transcript_text",
                    "search_video_moments",
                ],
                "defaultGranularity": "bounded source knowledge, report maps, and timestamp clips",
            },
            {
                "name": "video_context",
                "use": [
                    "get_video_knowledge_map",
                    "context://video-map/{videoId}",
                    "get_video_context",
                    "context://video/{videoId}",
                ],
                "defaultGranularity": "knowledge map first, full context/transcript only when needed",
            },
            {
                "name": "agent_brief",
                "use": ["build_context_bundle", "build_agent_brief"],
                "defaultGranularity": "task-focused source highlights and overlay context",
            },
            {
                "name": "incremental_digest_export",
                "use": ["export_brain_digest", "context://brain-digest"],
                "status": "available",
                "defaultGranularity": "compact changed videos, concepts, artifacts, labels, notes, and personal concepts",
                "shape": {
                    "cursor": "opaque per-user sync cursor",
                    "since": "optional ISO timestamp",
                    "objects": [
                        "videos",
                        "labels",
                        "concepts",
                        "artifacts",
                        "notes",
                        "personal_concepts",
                    ],
                    "maxChars": "caller-provided response budget",
                    "includeTranscript": "false by default; explicit deep mode only",
                },
            },
        ],
        "currentPushSurfaces": [
            {
                "name": "outbound_sync_outbox",
                "status": "available",
                "delivery": "queued_outbox",
                "events": [
                    "video.ingested",
                    "knowledge.published",
                    "overlay.note.created",
                    "capture_source.synced",
                ],
                "guidance": (
                    "Connected personal brains can subscribe to compact sync events. "
                    "Events point consumers back to export_brain_digest for changed context."
                ),
            },
        ],
        "plannedSyncSurfaces": [
            {
                "name": "webhook_delivery_worker",
                "status": "planned",
                "guidance": (
                    "Deliver queued external_brain_sync_events to custom webhooks or "
                    "provider-specific integrations with retry/dead-letter handling."
                ),
            },
            {
                "name": "portable_jsonl_export",
                "status": "planned",
                "guidance": "Workspace or enterprise export path; still preserves source provenance.",
            },
        ],
        "recommendedFlow": [
            "Call get_mcp_session to confirm context:read and overlay:write scopes.",
            "Read context://brain-sync-contract or call get_brain_sync_contract.",
            "Call list_projects and choose a project_id/project_slug when the user is working inside a specific project.",
            "Pull get_project_context_map, list_video_library, and list_context_categories as the current map.",
            "Search source knowledge first with search_video_concepts retrieval_mode=hybrid, scoped by project when appropriate.",
            "Call get_video_knowledge_map for candidate videos before pulling transcript clips.",
            "Use search_video_moments for timestamp evidence, and get_video_context/include_transcript only when needed.",
            "Store only compact source refs in the external brain unless the user asks for deep context.",
            "Write personalized takeaways back with add_context_note or upsert_personal_concept.",
        ],
        "budgetControls": {
            "defaultMode": "compact",
            "avoidByDefault": [
                "full transcripts",
                "large source reports",
                "uncited paraphrase dumps",
            ],
            "plannedFields": [
                "detail_level",
                "max_chars",
                "max_context_tokens",
                "estimatedResponseChars",
            ],
        },
        "accessModel": {
            "scope": "current_user_grants",
            "globalSearch": "not_exposed",
            "visibilityGrants": ["user_videos", "user_channels"],
            "revocation": "When a user revokes a token or grant, external brains should stop syncing that source.",
        },
    }


def _agent_quickstart_payload() -> dict:
    """Return machine-readable onboarding steps for connected agents."""
    repo_workflow = repo_context_workflow_contract()
    return {
        "version": "memexai-agent-quickstart-v1",
        "purpose": (
            "Help agents use Memexai as a saved-video context MCP without forcing "
            "a hosted repo connection when the caller already has repo/filesystem/GitHub tools."
        ),
        "coreRules": [
            "Source video context is read-only.",
            "Search is scoped to the current user's video and channel grants, not the global corpus.",
            "Project scopes are explicit MCP arguments; do not infer them from the web UI.",
            "Search clips, library videos, and video context include accessScope/accessSource/accessReason so shared canonical videos stay explainable.",
            "Use caller-supplied repo_context from the agent's own repo tools.",
            "Existing personal brains should pull compact Memexai digests through the brain sync contract, not by reading the database.",
            "Write only personal overlay notes/concepts unless ingest:write is explicitly granted.",
            "Use project:write only when the user asks the agent to create a project scope.",
            "Use capture:write for already-linked playlist capture sources; preview with max_jobs=0 before queueing.",
            "Ask for explicit user approval before setting allow_bulk=true for playlists/channels.",
            "Poll ingestion jobs or workflow runs before assuming newly submitted videos are searchable.",
        ],
        "recommendedFlow": [
            {
                "step": "discover_contract",
                "use": ["get_mcp_session", "get_agent_quickstart", "context://agent-quickstart"],
                "why": (
                    "Confirm effective scopes, then understand the safe agent workflow "
                    "before using video knowledge."
                ),
            },
            {
                "step": "inspect_repo_with_existing_tools",
                "use": ["filesystem MCP", "GitHub MCP", "code-index MCP", "local repo tools"],
                "why": "Keep repo access low-friction and caller-controlled.",
            },
            {
                "step": "shape_repo_context",
                "use": [
                    "prompts/get: collect_repo_context",
                    "get_repo_context_contract",
                    "get_repo_context_workflow",
                    "validate_repo_context",
                ],
                "why": (
                    "Pass compact repo references and constraints, then check readiness "
                    "before asking for an implementation brief."
                ),
            },
            {
                "step": "discover_saved_video_context",
                "use": [
                    "list_projects",
                    "context://projects",
                    "get_project_context_map",
                    "list_video_library",
                    "context://library",
                    "list_context_categories",
                    "get_brain_sync_contract",
                ],
                "why": (
                    "Find explicit project scopes first, then inspect the relevant project "
                    "or full library and useful category filters."
                ),
            },
            {
                "step": "sync_external_brain",
                "use": [
                    "get_brain_sync_contract",
                    "context://brain-sync-contract",
                    "export_brain_digest",
                    "context://brain-digest",
                ],
                "why": (
                    "If the user already has a personal brain, sync compact digests, "
                    "source refs, and overlay notes instead of duplicating raw transcripts."
                ),
            },
            {
                "step": "retrieve_source_knowledge",
                "use": [
                    "search_video_concepts",
                    "get_video_knowledge_map",
                    "context://video-map/{videoId}",
                ],
                "why": (
                    "Use hybrid source-knowledge search first, scoped by project_id/project_slug "
                    "when relevant, then inspect a candidate video's map so the agent can "
                    "navigate report sections, concepts, and timestamp refs."
                ),
            },
            {
                "step": "retrieve_timestamp_evidence",
                "use": [
                    "search_video_moments",
                    "search_transcript_text",
                    "get_transcript_window",
                    "get_video_context",
                ],
                "why": (
                    "Use timestamp clips to verify selected map items. Use transcript text for "
                    "exact phrases. For known videos, pass youtube_video_id/video_id and pull "
                    "only the relevant transcript window; full video context is a last resort."
                ),
            },
            {
                "step": "build_actionable_output",
                "use": ["build_agent_brief", "build_context_bundle", "prompts/get"],
                "why": "Turn saved-video concepts into specs, plans, prompts, or source reports.",
            },
            {
                "step": "persist_only_overlay_context",
                "use": ["add_context_note", "upsert_personal_concept"],
                "why": "Keep personal takeaways separate from canonical source context.",
            },
        ],
        "scopeHints": {
            "context:read": [
                "read resources",
                "search timestamped moments",
                "build context bundles",
                "build agent briefs",
            ],
            "overlay:write": ["add notes", "upsert personal concepts"],
            "ingest:write": ["queue user-provided or user-approved YouTube URLs"],
            "capture:write": ["preview and queue sync for linked YouTube capture sources"],
            "project:write": ["create user-owned project scopes"],
        },
        "repoContextWorkflow": repo_workflow,
        "brainSyncContract": describe_brain_sync_contract(),
        "jsonRpcExamples": {
            "getBrainSyncContract": {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "get_brain_sync_contract", "arguments": {}},
            },
            "getRepoContextContract": {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "get_repo_context_contract", "arguments": {}},
            },
            "readRepoContextWorkflow": {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "resources/read",
                "params": {"uri": "context://repo-context-workflow"},
            },
            "getRepoContextWorkflow": {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "get_repo_context_workflow", "arguments": {}},
            },
            "collectRepoContextPrompt": {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "prompts/get",
                "params": {
                    "name": "collect_repo_context",
                    "arguments": {
                        "implementation_goal": "apply saved-video lessons to this repo",
                        "repo_context_hint": "relevant files, symbols, locations, entrypoints, commands, tests, and constraints",
                    },
                },
            },
            "validateRepoContext": {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "validate_repo_context",
                    "arguments": {
                        "repo_context": {
                            "source": "agent-mcp",
                            "repo": "owner/name",
                            "files": ["src/agent.ts", "tests/agent.test.ts"],
                            "locations": ["src/agent.ts:42 runAgentWorkflow"],
                            "entrypoints": ["POST /api/agent/run"],
                            "symbols": ["runAgentWorkflow", "AgentHarness"],
                            "features": ["workflow orchestration"],
                            "dependencies": ["Supabase", "Cloudflare Workers"],
                            "commands": ["npm test -- --run"],
                            "tests": ["tests/agent.test.ts"],
                            "constraints": ["source video context is read-only"],
                        }
                    },
                },
            },
            "buildAgentBrief": {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "build_agent_brief",
                    "arguments": {
                        "query": "apply saved-video lessons to this repo",
                        "repo_context": {
                            "source": "agent-mcp",
                            "repo": "owner/name",
                            "files": ["src/agent.ts", "tests/agent.test.ts"],
                            "locations": ["src/agent.ts:42 runAgentWorkflow"],
                            "entrypoints": ["POST /api/agent/run"],
                            "symbols": ["runAgentWorkflow", "AgentHarness"],
                            "features": ["workflow orchestration"],
                            "dependencies": ["Supabase", "Cloudflare Workers"],
                            "commands": ["npm test -- --run"],
                            "tests": ["tests/agent.test.ts"],
                            "constraints": ["source video context is read-only"],
                        },
                    },
                },
            },
            "queueSingleVideo": {
                "jsonrpc": "2.0",
                "id": 8,
                "method": "tools/call",
                "params": {
                    "name": "queue_youtube_ingestion",
                    "arguments": {
                        "url": "https://www.youtube.com/watch?v=VIDEO_ID",
                        "created_by_client": "agent-name",
                    },
                },
            },
            "previewCaptureSourceSync": {
                "jsonrpc": "2.0",
                "id": 9,
                "method": "tools/call",
                "params": {
                    "name": "sync_capture_source",
                    "arguments": {
                        "capture_source_id": "capture_source_id",
                        "max_jobs": 0,
                    },
                },
            },
            "queueConfirmedCaptureSourceSync": {
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/call",
                "params": {
                    "name": "sync_capture_source",
                    "arguments": {
                        "capture_source_id": "capture_source_id",
                        "max_jobs": 3,
                        "allow_queue": True,
                        "confirmed_queue_count": 3,
                        "created_by_client": "agent-name",
                    },
                },
            },
            "createProject": {
                "jsonrpc": "2.0",
                "id": 11,
                "method": "tools/call",
                "params": {
                    "name": "create_project",
                    "arguments": {
                        "name": "Agent project",
                        "description": "Project scope created from the user's agent chat.",
                        "created_by_client": "agent-name",
                    },
                },
            },
            "linkPlaylistToProject": {
                "jsonrpc": "2.0",
                "id": 12,
                "method": "tools/call",
                "params": {
                    "name": "link_youtube_playlist_capture_source",
                    "arguments": {
                        "playlist_url": "https://www.youtube.com/playlist?list=PLAYLIST_ID",
                        "project_id": "project_id",
                        "title": "Agent project inbox",
                        "created_by_client": "agent-name",
                    },
                },
            },
            "knownVideoRetrieval": {
                "jsonrpc": "2.0",
                "id": 8,
                "method": "tools/call",
                "params": {
                    "name": "search_transcript_text",
                    "arguments": {
                        "query": "exact phrase or concept",
                        "youtube_video_id": "VIDEO_ID",
                        "retrieval_mode": "keyword",
                        "max_chars": 4000,
                    },
                },
            },
        },
    }


def _mcp_session_payload(user_id: str, scopes: list[str] | None, auth_kind: str) -> dict:
    """Return scope-aware next steps for the current MCP connection."""
    effective_scopes = scopes or DEFAULT_SCOPES
    scope_set = set(effective_scopes)
    has_context = "context:read" in scope_set
    has_overlay = "overlay:write" in scope_set
    has_ingest = "ingest:write" in scope_set
    has_capture = "capture:write" in scope_set
    has_project_write = "project:write" in scope_set
    capabilities = [
        {
            "name": "read_saved_video_context",
            "allowed": has_context,
            "requiredScope": "context:read",
            "tools": [
                "list_projects",
                "get_project_context_map",
                "list_video_library",
                "list_context_categories",
                "search_video_concepts",
                "get_video_knowledge_map",
                "search_transcript_text",
                "search_video_moments",
                "get_video_context",
                "build_context_bundle",
                "build_agent_brief",
                "get_brain_sync_contract",
            ],
        },
        {
            "name": "write_personal_overlay",
            "allowed": has_overlay,
            "requiredScope": "overlay:write",
            "tools": ["add_context_note", "upsert_personal_concept"],
        },
        {
            "name": "queue_user_approved_youtube_ingestion",
            "allowed": has_ingest,
            "requiredScope": "ingest:write",
            "tools": ["queue_youtube_ingestion"],
            "guardrail": "Playlist and channel URLs still require allow_bulk=true.",
        },
        {
            "name": "sync_linked_youtube_capture_sources",
            "allowed": has_capture,
            "requiredScope": "capture:write",
            "tools": ["link_youtube_playlist_capture_source", "sync_capture_source"],
            "guardrail": (
                "Use max_jobs=0 to preview, then queue only with allow_queue=true and "
                "confirmed_queue_count equal to max_jobs."
            ),
        },
        {
            "name": "create_user_projects",
            "allowed": has_project_write,
            "requiredScope": "project:write",
            "tools": ["create_project"],
            "guardrail": "Create projects only when the user asks for a new project scope.",
        },
    ]

    if has_context:
        next_mcp_call = {
            "name": "get_agent_quickstart",
            "when": "next",
            "reason": (
                "The connection can read context; load the safe workflow before "
                "searching videos or building briefs."
            ),
            "argumentsTemplate": {},
        }
    else:
        next_mcp_call = {
            "name": "none",
            "when": "after_scope_upgrade",
            "reason": (
                "This token does not include context:read, so it cannot read saved "
                "video context or repo workflow resources."
            ),
            "argumentsTemplate": {},
        }

    recommended_calls = []
    if has_context:
        recommended_calls.extend(
            [
                "get_agent_quickstart",
                "get_brain_sync_contract",
                "get_repo_context_workflow",
                "get_repo_context_contract",
                "list_projects",
                "get_project_context_map",
                "list_video_library",
                "list_context_categories",
                "search_video_concepts",
                "get_video_knowledge_map",
                "search_transcript_text",
            ]
        )
    if has_overlay:
        recommended_calls.append("add_context_note")
    if has_ingest:
        recommended_calls.append("queue_youtube_ingestion")
    if has_capture:
        recommended_calls.append("sync_capture_source")
        recommended_calls.append("link_youtube_playlist_capture_source")
    if has_project_write:
        recommended_calls.append("create_project")

    missing_recommended_scopes = [scope for scope in DEFAULT_SCOPES if scope not in scope_set]
    return {
        "version": "memexai-mcp-session-v1",
        "authenticated": True,
        "authKind": auth_kind,
        "userScope": "current_user_grants",
        "effectiveScopes": effective_scopes,
        "missingRecommendedScopes": missing_recommended_scopes,
        "capabilities": capabilities,
        "next_mcp_call": next_mcp_call,
        "recommendedNextCalls": recommended_calls,
        "repoContextWorkflow": {
            "preferred": "caller_supplied_repo_context",
            "firstCalls": ["get_repo_context_workflow", "get_repo_context_contract"],
            "validationTool": "validate_repo_context",
            "briefTool": "build_agent_brief",
            "guidance": (
                "Use the agent's own repo/filesystem/GitHub MCP tools, then pass compact "
                "repo_context into Memexai. Do not require a hosted GitHub connection."
            ),
        },
        "brainSync": {
            "contractResource": "context://brain-sync-contract",
            "contractTool": "get_brain_sync_contract",
            "guidance": (
                "External brains should pull compact saved-video digests and source refs, "
                "then write personalized takeaways only to the overlay."
            ),
        },
        "preferredRetrievalFlow": [
            "get_mcp_session",
            "list_projects to identify explicit project scopes",
            "get_project_context_map when a project matches the user's task",
            "list_video_library",
            "search_video_concepts with retrieval_mode=hybrid and project_id/project_slug when scoped",
            "get_video_knowledge_map for candidate videos",
            "search_video_moments for timestamp evidence",
            "get_video_context/include_transcript only when needed",
        ],
        "guardrails": [
            "Source transcripts, chunks, source labels, source concepts, and generated artifacts are read-only.",
            "Search is scoped to the current user's user_videos and user_channels grants.",
            "Project scope is explicit per MCP call; agents must not assume the web UI's selected project.",
            "Use accessScope, accessSource, and accessReason on search clips, library videos, and video context to explain shared canonical video access.",
            "Write durable takeaways only to the personal overlay unless the user explicitly grants ingestion.",
            "Capture-source sync uses capture:write and returns workflow/job handles; poll those handles for confirmations and errors.",
            "Project creation uses project:write; playlist linking uses capture:write and must target a user-owned project.",
        ],
    }


def _list_resources(user_id: str, supabase: Any | None, scopes: list[str] | None) -> dict:
    _authorize_context_read(scopes)
    db = _ensure_supabase(supabase)
    library = list_video_library_context(db, user_id, 100)
    projects = list_projects(db, user_id, 100)
    resources = [
        {
            "uri": "context://agent-quickstart",
            "name": "agent_quickstart",
            "title": "Agent Quickstart",
            "description": "Machine-readable first steps for connected agents.",
            "mimeType": "application/json",
        },
        {
            "uri": "context://brain-sync-contract",
            "name": "brain_sync_contract",
            "title": "Brain Sync Contract",
            "description": (
                "How external personal brains should pull compact saved-video knowledge "
                "and write personalized overlay context."
            ),
            "mimeType": "application/json",
        },
        {
            "uri": "context://brain-digest",
            "name": "brain_digest",
            "title": "External Brain Digest",
            "description": (
                "Compact incremental digest of user-granted saved-video knowledge for "
                "external personal brains."
            ),
            "mimeType": "application/json",
        },
        {
            "uri": "context://repo-context-contract",
            "name": "repo_context_contract",
            "title": "Repo Context Contract",
            "description": (
                "How agents should pass compact repo context from their own MCP tools into Memexai."
            ),
            "mimeType": "application/json",
        },
        {
            "uri": "context://repo-context-workflow",
            "name": "repo_context_workflow",
            "title": "Repo Context Workflow",
            "description": (
                "Machine-readable collection flow, readiness gate, and expected output "
                "for repo_context gathered by the calling agent's own MCP tools."
            ),
            "mimeType": "application/json",
        },
        {
            "uri": "context://library",
            "name": "video_library",
            "title": "Saved Video Library",
            "description": "Indexed channels and recent saved videos available to this account.",
            "mimeType": "application/json",
        },
        {
            "uri": "context://projects",
            "name": "video_projects",
            "title": "Video Projects",
            "description": (
                "User-defined project scopes for narrowing library and agent retrieval."
            ),
            "mimeType": "application/json",
        },
        {
            "uri": "context://library-graph",
            "name": "library_source_graph",
            "title": "Library Source Graph",
            "description": (
                "Inspectable source graph, component counts, review flags, and conflict "
                "candidates for user-granted videos."
            ),
            "mimeType": "application/json",
        },
        {
            "uri": "context://notes",
            "name": "agent_notes",
            "title": "Personal Agent Notes",
            "description": "Recent notes written by the user or connected agents.",
            "mimeType": "application/json",
        },
        {
            "uri": "context://categories",
            "name": "context_categories",
            "title": "Context Categories",
            "description": "Browsable labels, facets, and personal concepts for agent discovery.",
            "mimeType": "application/json",
        },
        {
            "uri": "context://capture-sources",
            "name": "capture_sources",
            "title": "YouTube Capture Sources",
            "description": "Standing YouTube sources that can feed future ingestion jobs.",
            "mimeType": "application/json",
        },
        {
            "uri": "context://workflows",
            "name": "workflow_runs",
            "title": "Workflow Runs",
            "description": "Recent durable platform workflow runs for long-running agent work.",
            "mimeType": "application/json",
        },
    ]

    for project in projects.get("projects", []):
        project_id = project.get("id")
        if not project_id:
            continue
        resources.append(
            {
                "uri": f"context://project/{project_id}",
                "name": f"project_{project_id}",
                "title": project.get("name") or project.get("slug") or project_id,
                "description": ("Project-scoped saved-video map for agent retrieval and browsing."),
                "mimeType": "application/json",
            }
        )

    for channel in library.get("channels", []):
        channel_name = channel.get("name") or "Unknown channel"
        for video in channel.get("videos", []):
            video_id = video.get("videoId")
            if not video_id:
                continue
            resources.append(
                {
                    "uri": f"context://video/{video_id}",
                    "name": f"video_{video_id}",
                    "title": video.get("title") or video_id,
                    "description": f"Transcript-derived context from {channel_name}.",
                    "mimeType": "application/json",
                }
            )
            resources.append(
                {
                    "uri": f"context://video-map/{video_id}",
                    "name": f"video_map_{video_id}",
                    "title": f"Knowledge map: {video.get('title') or video_id}",
                    "description": f"Navigable source-report map from {channel_name}.",
                    "mimeType": "application/json",
                }
            )

    return {"resources": resources}


def _read_resource(
    params: Any,
    user_id: str,
    supabase: Any | None,
    scopes: list[str] | None,
) -> dict:
    _authorize_context_read(scopes)
    if not isinstance(params, dict):
        raise McpAdapterError(INVALID_PARAMS, "resources/read params must be an object")

    uri = params.get("uri")
    if not isinstance(uri, str) or not uri.strip():
        raise McpAdapterError(INVALID_PARAMS, "resources/read params.uri must be a URI")

    parsed = urlparse(uri.strip())
    if parsed.scheme != "context":
        raise McpAdapterError(INVALID_PARAMS, "Unsupported resource URI scheme")

    if parsed.netloc == "agent-quickstart" and parsed.path in {"", "/"}:
        return _resource_response(uri, _agent_quickstart_payload())
    if parsed.netloc == "brain-sync-contract" and parsed.path in {"", "/"}:
        return _resource_response(uri, describe_brain_sync_contract())
    if parsed.netloc == "repo-context-contract" and parsed.path in {"", "/"}:
        return _resource_response(uri, describe_repo_context_contract())
    if parsed.netloc == "repo-context-workflow" and parsed.path in {"", "/"}:
        return _resource_response(uri, repo_context_workflow_contract())

    db = _ensure_supabase(supabase)
    if parsed.netloc == "library" and parsed.path in {"", "/"}:
        return _resource_response(uri, list_video_library_context(db, user_id, 100))
    if parsed.netloc == "projects" and parsed.path in {"", "/"}:
        return _resource_response(uri, list_projects(db, user_id, 100))
    if parsed.netloc == "project" and parsed.path.strip("/"):
        project_id = unquote(parsed.path.strip("/"))
        context = build_project_context_map(db, user_id, project_id=project_id)
        if not context.get("found"):
            raise McpAdapterError(INVALID_PARAMS, "Project resource not found")
        return _resource_response(uri, context)
    if parsed.netloc == "library-graph" and parsed.path in {"", "/"}:
        return _resource_response(uri, build_library_source_graph(db, user_id, 50))
    if parsed.netloc == "brain-digest" and parsed.path in {"", "/"}:
        return _resource_response(uri, build_brain_digest_export(db, user_id, limit=20))
    if parsed.netloc == "notes" and parsed.path in {"", "/"}:
        return _resource_response(uri, {"notes": list_agent_notes(db, user_id, 50)})
    if parsed.netloc == "categories" and parsed.path in {"", "/"}:
        return _resource_response(uri, list_context_categories(db, user_id, 100))
    if parsed.netloc == "capture-sources" and parsed.path in {"", "/"}:
        return _resource_response(uri, build_capture_sources_context(db, user_id, 100))
    if parsed.netloc == "workflows" and parsed.path in {"", "/"}:
        return _resource_response(uri, build_workflow_status_context(db, user_id, 50))
    if parsed.netloc == "workflow" and parsed.path.strip("/"):
        workflow_instance_id = unquote(parsed.path.strip("/"))
        workflow = get_workflow_instance(db, user_id, workflow_instance_id)
        if not workflow:
            raise McpAdapterError(INVALID_PARAMS, "Workflow instance not found")
        return _resource_response(uri, {"workflowInstance": workflow})
    if parsed.netloc == "video" and parsed.path.strip("/"):
        video_id = unquote(parsed.path.strip("/"))
        context = get_video_context(db, user_id, video_id)
        if not context:
            raise McpAdapterError(INVALID_PARAMS, "Video resource not found in this user's library")
        return _resource_response(
            uri,
            _budget_video_context_payload(context, _budget_args({}), include_transcript=False),
        )
    if parsed.netloc == "video-map" and parsed.path.strip("/"):
        video_id = unquote(parsed.path.strip("/"))
        context = build_video_knowledge_map(db, user_id, video_id)
        if not context.get("found"):
            raise McpAdapterError(INVALID_PARAMS, "Video map not found in this user's library")
        return _resource_response(uri, context)

    raise McpAdapterError(INVALID_PARAMS, "Unknown context resource URI")


def _get_video_context_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    del tool_context
    _ensure_allowed_args(
        arguments,
        {
            "youtube_video_id",
            "video_id",
            "include_transcript",
            "detail_level",
            "max_chars",
            "max_context_tokens",
            "project_id",
            "project_slug",
        },
    )
    video_id = arguments.get("youtube_video_id") or arguments.get("video_id")
    if not isinstance(video_id, str) or not video_id.strip():
        raise McpAdapterError(INVALID_PARAMS, "youtube_video_id is required")
    include_transcript = arguments.get("include_transcript", False)
    if not isinstance(include_transcript, bool):
        raise McpAdapterError(INVALID_PARAMS, "include_transcript must be a boolean")
    budget = _budget_args(arguments)
    project_id = _optional_string(arguments, "project_id")
    project_slug = _optional_string(arguments, "project_slug")

    if project_id or project_slug:
        context = get_video_context(
            supabase,
            user_id,
            video_id.strip(),
            project_id=project_id,
            project_slug=project_slug,
        )
    else:
        context = get_video_context(supabase, user_id, video_id.strip())
    if not context:
        return _tool_response({"found": False, "videoId": video_id.strip()})
    return _tool_response(
        _budget_video_context_payload(context, budget, include_transcript=include_transcript)
    )


def _get_transcript_window_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    del tool_context
    _ensure_allowed_args(
        arguments,
        {
            "youtube_video_id",
            "video_id",
            "start_seconds",
            "end_seconds",
            "detail_level",
            "max_chars",
            "max_context_tokens",
            "project_id",
            "project_slug",
        },
    )
    video_id = _optional_video_id(arguments)
    if not video_id:
        raise McpAdapterError(INVALID_PARAMS, "youtube_video_id is required")
    start_seconds = _bounded_int(
        arguments.get("start_seconds", 0),
        minimum=0,
        maximum=86_399,
        name="start_seconds",
    )
    raw_end_seconds = arguments.get("end_seconds", start_seconds + 180)
    end_seconds = _bounded_int(raw_end_seconds, minimum=1, maximum=86_400, name="end_seconds")
    if end_seconds <= start_seconds:
        raise McpAdapterError(INVALID_PARAMS, "end_seconds must be greater than start_seconds")
    budget = _budget_args(arguments)
    project_id = _optional_string(arguments, "project_id")
    project_slug = _optional_string(arguments, "project_slug")
    context = get_video_context(
        supabase,
        user_id,
        video_id,
        project_id=project_id,
        project_slug=project_slug,
    )
    if not context:
        return _tool_response({"found": False, "videoId": video_id})

    transcript_lines = _items_overlapping_window(
        context.get("transcriptLines") or [], start_seconds, end_seconds
    )
    transcript_chunks = _items_overlapping_window(
        context.get("transcriptChunks") or [], start_seconds, end_seconds
    )
    payload = {
        "found": True,
        "video": context.get("video", {}),
        "projectScope": context.get("projectScope"),
        "timeWindow": {
            "startSeconds": start_seconds,
            "endSeconds": end_seconds,
            "youtubeUrl": _youtube_timestamp_url(video_id, start_seconds),
        },
        "transcriptLines": transcript_lines,
        "transcriptChunks": transcript_chunks,
        "transcriptBudget": {
            "includeTranscript": True,
            "availableTranscriptLines": len(transcript_lines),
            "availableTranscriptChunks": len(transcript_chunks),
            "returnedTranscriptLines": len(transcript_lines),
            "returnedTranscriptChunks": len(transcript_chunks),
            "guidance": (
                "Use this bounded transcript window for direct evidence after "
                "search_video_moments, search_transcript_text, or get_video_knowledge_map "
                "identifies a relevant timestamp."
            ),
        },
        "next_mcp_call": {
            "name": "search_video_moments",
            "when": "if_this_window_is_not_enough",
            "arguments": {
                "query": "narrow follow-up question",
                "youtube_video_id": video_id,
                "retrieval_mode": "hybrid",
            },
        },
    }
    return _tool_response(_budget_transcript_payload(payload, budget))


def _list_video_library_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    del tool_context
    _ensure_allowed_args(arguments, {"limit", "project_id", "project_slug"})
    limit = _bounded_int(arguments.get("limit", 50), minimum=1, maximum=100, name="limit")
    project_id = _optional_string(arguments, "project_id")
    project_slug = _optional_string(arguments, "project_slug")
    if project_id or project_slug:
        return _tool_response(
            list_video_library_context(
                supabase,
                user_id,
                limit,
                project_id=project_id,
                project_slug=project_slug,
            )
        )
    return _tool_response(list_video_library_context(supabase, user_id, limit))


def _list_projects_tool(supabase: Any, user_id: str, arguments: dict, tool_context: dict) -> dict:
    del tool_context
    _ensure_allowed_args(arguments, {"limit"})
    limit = _bounded_int(arguments.get("limit", 50), minimum=1, maximum=100, name="limit")
    payload = list_projects(supabase, user_id, limit)
    payload["guidance"] = (
        "Projects are explicit retrieval scopes. Choose a project_id or project_slug for "
        "search_video_concepts, get_project_context_map, list_video_library, "
        "get_video_knowledge_map, and transcript searches when the user is working in a "
        "specific project. If no project is clearly relevant, search the full library and "
        "state that you broadened scope."
    )
    return _tool_response(payload)


def _get_project_context_map_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    del tool_context
    _ensure_allowed_args(
        arguments,
        {
            "project_id",
            "project_slug",
            "limit",
            "detail_level",
            "max_chars",
            "max_context_tokens",
        },
    )
    project_id = _optional_string(arguments, "project_id")
    project_slug = _optional_string(arguments, "project_slug")
    if not (project_id or project_slug):
        raise McpAdapterError(INVALID_PARAMS, "project_id or project_slug is required")
    limit = _bounded_int(arguments.get("limit", 25), minimum=1, maximum=100, name="limit")
    budget = _budget_args(arguments)
    payload = build_project_context_map(
        supabase,
        user_id,
        project_id=project_id,
        project_slug=project_slug,
        limit=limit,
        detail_level=budget["detailLevel"],
        max_chars=budget["requestedMaxChars"],
        max_context_tokens=budget["maxContextTokens"],
    )
    return _tool_response(payload)


def _get_library_source_graph_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    del tool_context
    _ensure_allowed_args(
        arguments,
        {
            "limit",
            "detail_level",
            "max_chars",
            "max_context_tokens",
            "project_id",
            "project_slug",
        },
    )
    limit = _bounded_int(arguments.get("limit", 50), minimum=1, maximum=100, name="limit")
    budget = _budget_args(arguments)
    project_id = _optional_string(arguments, "project_id")
    project_slug = _optional_string(arguments, "project_slug")
    if project_id or project_slug:
        payload = build_library_source_graph(
            supabase,
            user_id,
            limit,
            project_id=project_id,
            project_slug=project_slug,
        )
    else:
        payload = build_library_source_graph(supabase, user_id, limit)
    return _tool_response(_apply_response_budget(payload, budget))


def _search_library_components_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    del tool_context
    _ensure_allowed_args(
        arguments,
        {
            "query",
            "limit",
            "component_types",
            "detail_level",
            "max_chars",
            "max_context_tokens",
            "project_id",
            "project_slug",
        },
    )
    query = _required_string(arguments, "query").strip()
    if not query:
        raise McpAdapterError(INVALID_PARAMS, "query cannot be empty")
    component_types = arguments.get("component_types")
    if component_types is not None:
        if not isinstance(component_types, list) or any(
            not isinstance(item, str) for item in component_types
        ):
            raise McpAdapterError(INVALID_PARAMS, "component_types must be an array of strings")
    limit = _bounded_int(arguments.get("limit", 20), minimum=1, maximum=50, name="limit")
    budget = _budget_args(arguments)
    project_id = _optional_string(arguments, "project_id")
    project_slug = _optional_string(arguments, "project_slug")
    if project_id or project_slug:
        payload = search_library_components(
            supabase,
            user_id,
            query,
            limit,
            component_types,
            project_id=project_id,
            project_slug=project_slug,
        )
    else:
        payload = search_library_components(supabase, user_id, query, limit, component_types)
    return _tool_response(_apply_retrieval_budget(payload, "results", budget))


def _list_capture_sources_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    del tool_context
    _ensure_allowed_args(arguments, {"limit"})
    limit = _bounded_int(arguments.get("limit", 50), minimum=1, maximum=100, name="limit")
    return _tool_response(build_capture_sources_context(supabase, user_id, limit))


def _list_context_categories_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    del tool_context
    _ensure_allowed_args(arguments, {"limit", "project_id", "project_slug"})
    limit = _bounded_int(arguments.get("limit", 100), minimum=1, maximum=200, name="limit")
    project_id = _optional_string(arguments, "project_id")
    project_slug = _optional_string(arguments, "project_slug")
    if project_id or project_slug:
        return _tool_response(
            list_context_categories(
                supabase,
                user_id,
                limit,
                project_id=project_id,
                project_slug=project_slug,
            )
        )
    return _tool_response(list_context_categories(supabase, user_id, limit))


def _list_ingestion_jobs_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    del tool_context
    _ensure_allowed_args(arguments, {"limit"})
    limit = _bounded_int(arguments.get("limit", 10), minimum=1, maximum=50, name="limit")
    jobs = list_ingestion_jobs(supabase, user_id, limit)
    return _tool_response(
        {
            "jobs": [_compact_ingestion_job(job) for job in jobs if isinstance(job, dict)],
            "returnedJobs": len(jobs),
            "detailTool": "get_ingestion_job",
            "guidance": (
                "This list is compact by default. Use get_ingestion_job with a specific "
                "job_id to inspect ingestion_job_events, full cost estimates, warnings, "
                "and failure details."
            ),
        }
    )


def _get_ingestion_job_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    del tool_context
    _ensure_allowed_args(arguments, {"job_id"})
    job_id = _required_string(arguments, "job_id").strip()
    if not job_id:
        raise McpAdapterError(INVALID_PARAMS, "job_id cannot be empty")
    job = get_ingestion_job(supabase, user_id, job_id)
    return _tool_response({"job": job, "found": bool(job)})


def _list_workflow_runs_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    del tool_context
    _ensure_allowed_args(arguments, {"limit"})
    limit = _bounded_int(arguments.get("limit", 10), minimum=1, maximum=50, name="limit")
    return _tool_response(
        {
            "workflowInstances": list_workflow_instances(supabase, user_id, limit),
            "guidance": (
                "Use workflow_instance_id handles to poll long-running platform work. "
                "Published source context becomes available through library and video "
                "context resources after the workflow completes."
            ),
        }
    )


def _get_workflow_run_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    del tool_context
    _ensure_allowed_args(arguments, {"workflow_instance_id", "instance_id"})
    instance_id = arguments.get("workflow_instance_id") or arguments.get("instance_id")
    if not isinstance(instance_id, str) or not instance_id.strip():
        raise McpAdapterError(INVALID_PARAMS, "workflow_instance_id is required")
    workflow = get_workflow_instance(supabase, user_id, instance_id.strip())
    return _tool_response({"workflowInstance": workflow, "found": bool(workflow)})


def _validate_repo_context_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    del supabase, user_id, tool_context
    _ensure_allowed_args(arguments, {"repo_context"})
    return _tool_response(validate_repo_context(arguments.get("repo_context")))


def _get_repo_context_contract_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    del supabase, user_id, tool_context
    _ensure_allowed_args(arguments, set())
    return _tool_response(describe_repo_context_contract())


def _get_brain_sync_contract_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    del supabase, user_id, tool_context
    _ensure_allowed_args(arguments, set())
    return _tool_response(describe_brain_sync_contract())


def _export_brain_digest_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    del tool_context
    _ensure_allowed_args(
        arguments,
        {
            "cursor",
            "since",
            "objects",
            "limit",
            "detail_level",
            "max_chars",
            "max_context_tokens",
            "project_id",
            "project_slug",
        },
    )
    cursor = _optional_string(arguments, "cursor")
    since = _optional_string(arguments, "since")
    objects = _optional_list_of_strings(arguments, "objects")
    limit = _bounded_int(arguments.get("limit", 20), minimum=1, maximum=50, name="limit")
    budget = _budget_args(arguments)
    payload = build_brain_digest_export(
        supabase,
        user_id,
        cursor=cursor,
        since=since,
        objects=objects,
        limit=limit,
        detail_level=budget["detailLevel"],
        max_chars=budget["requestedMaxChars"],
        max_context_tokens=budget["maxContextTokens"],
    )
    return _tool_response(payload)


def _get_repo_context_workflow_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    del supabase, user_id, tool_context
    _ensure_allowed_args(arguments, set())
    return _tool_response(repo_context_workflow_contract())


def _get_agent_quickstart_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    del supabase, user_id, tool_context
    _ensure_allowed_args(arguments, set())
    return _tool_response(_agent_quickstart_payload())


def _get_mcp_session_tool(supabase: Any, user_id: str, arguments: dict, tool_context: dict) -> dict:
    del supabase
    _ensure_allowed_args(arguments, set())
    return _tool_response(
        _mcp_session_payload(
            user_id,
            tool_context.get("effective_scopes"),
            tool_context.get("auth_kind", "app_user"),
        )
    )


def _list_agent_notes_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    del tool_context
    _ensure_allowed_args(arguments, {"limit"})
    limit = _bounded_int(arguments.get("limit", 50), minimum=1, maximum=100, name="limit")
    return _tool_response({"notes": list_agent_notes(supabase, user_id, limit)})


def _add_context_note_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    del tool_context
    _ensure_allowed_args(
        arguments,
        {"content", "source_refs", "tags", "created_by_client"},
    )
    content = _required_string(arguments, "content").strip()
    if not content:
        raise McpAdapterError(INVALID_PARAMS, "content cannot be empty")

    note = create_agent_note(
        supabase,
        user_id,
        content,
        _optional_list_of_objects(arguments, "source_refs"),
        _optional_list_of_strings(arguments, "tags"),
        "agent",
        _optional_string(arguments, "created_by_client"),
    )
    return _tool_response({"note": note})


def _upsert_personal_concept_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    del tool_context
    _ensure_allowed_args(
        arguments,
        {"name", "summary", "source_refs", "status", "created_by_client"},
    )
    name = _required_string(arguments, "name").strip()
    if not name:
        raise McpAdapterError(INVALID_PARAMS, "name cannot be empty")

    status = arguments.get("status", "active")
    if status not in {"active", "learning", "applied", "ignored", "archived"}:
        raise McpAdapterError(INVALID_PARAMS, "Invalid concept status")

    concept = upsert_personal_concept(
        supabase,
        user_id,
        name,
        _optional_string(arguments, "summary") or "",
        _optional_list_of_objects(arguments, "source_refs"),
        status,
        "agent",
        _optional_string(arguments, "created_by_client"),
    )
    return _tool_response({"concept": concept})


def _plan_limit_snapshot(supabase: Any, user_id: str) -> dict:
    try:
        billing = resolve_user_entitlements(supabase, user_id)
        entitlements = billing.get("entitlements") if isinstance(billing, dict) else {}
    except Exception:
        entitlements = {}

    def as_int(key: str, fallback: int) -> int:
        try:
            value = int((entitlements or {}).get(key, fallback))
        except (TypeError, ValueError):
            value = fallback
        return max(1, value)

    return {
        "planKey": (entitlements or {}).get("planKey", "free"),
        "billingStatus": (entitlements or {}).get("billingStatus", "free"),
        "maxActiveIngestionJobs": as_int(
            "maxActiveIngestionJobs",
            get_free_max_active_ingestion_jobs(),
        ),
        "maxImportVideos": as_int("maxImportVideos", 1),
    }


def _require_available_ingestion_slot(supabase: Any, user_id: str) -> dict:
    limits = _plan_limit_snapshot(supabase, user_id)
    active_jobs = count_active_ingestion_jobs(supabase, user_id)
    limits["activeIngestionJobs"] = active_jobs
    if active_jobs >= limits["maxActiveIngestionJobs"]:
        raise McpAdapterError(
            SERVER_ERROR,
            (
                "This user already has the maximum number of imports running for their plan. "
                "Poll existing ingestion jobs and try again after one finishes."
            ),
        )
    return limits


def _resolve_agent_project_target(
    supabase: Any,
    user_id: str,
    *,
    project_id: str | None,
    project_slug: str | None,
    source_type: str,
) -> dict | None:
    if not project_id and not project_slug:
        return None
    if source_type != "video":
        raise McpAdapterError(
            INVALID_PARAMS,
            (
                "project_id/project_slug is only supported for single-video URL ingestion. "
                "For project-linked playlists, use list_capture_sources then sync_capture_source."
            ),
        )
    try:
        project_scope = resolve_project_scope(
            supabase,
            user_id,
            project_id=project_id,
            project_slug=project_slug,
        )
    except ValueError as exc:
        raise McpAdapterError(INVALID_PARAMS, str(exc)) from exc
    if not project_scope:
        raise McpAdapterError(INVALID_PARAMS, "Project not found")
    return {
        "id": project_scope.get("id"),
        "name": project_scope.get("name"),
        "slug": project_scope.get("slug"),
    }


def _ingestion_polling_payload(
    job: dict | None = None, workflow_instance_id: str | None = None
) -> dict:
    job_ids = []
    if isinstance(job, dict) and job.get("id"):
        job_ids.append(job.get("id"))
    return {
        "mode": "poll",
        "jobStatusTool": "get_ingestion_job",
        "workflowStatusTool": "get_workflow_run",
        "workflow_instance_id": workflow_instance_id,
        "job_ids": job_ids,
        "errorSurface": "get_ingestion_job returns ingestion_job_events with warning/error rows",
        "confirmationSurface": (
            "A completed ingestion job confirms searchable video context. A failed or partial "
            "job explains errors in ingestion_job_events."
        ),
    }


def _compact_queued_jobs(jobs: list[dict]) -> list[dict]:
    compact = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        compact.append(
            {
                "id": job.get("id"),
                "status": job.get("status"),
                "sourceUrl": job.get("source_url"),
                "sourceType": job.get("source_type"),
            }
        )
    return compact


def _compact_ingestion_job(job: dict) -> dict:
    cost_estimate = job.get("cost_estimate") if isinstance(job.get("cost_estimate"), dict) else {}
    mcp_context = cost_estimate.get("mcp") if isinstance(cost_estimate, dict) else {}
    project_target = mcp_context.get("requestedProject") if isinstance(mcp_context, dict) else None
    return {
        "id": job.get("id"),
        "status": job.get("status"),
        "sourceUrl": job.get("source_url"),
        "sourceType": job.get("source_type"),
        "requestedVideoCount": job.get("requested_video_count"),
        "indexedVideoCount": job.get("indexed_video_count"),
        "skippedVideoCount": job.get("skipped_video_count"),
        "failedVideoCount": job.get("failed_video_count"),
        "lastMessage": job.get("last_message"),
        "error": job.get("error"),
        "createdAt": job.get("created_at"),
        "startedAt": job.get("started_at"),
        "completedAt": job.get("completed_at"),
        "digestDepth": cost_estimate.get("digestDepth"),
        "projectTarget": project_target,
    }


def _metadata_argument(arguments: dict) -> dict:
    metadata = arguments.get("metadata", {})
    if metadata is None:
        return {}
    if not isinstance(metadata, dict):
        raise McpAdapterError(INVALID_PARAMS, "metadata must be an object")
    return metadata


def _create_project_tool(supabase: Any, user_id: str, arguments: dict, tool_context: dict) -> dict:
    del tool_context
    _ensure_allowed_args(arguments, {"name", "description", "metadata", "created_by_client"})
    name = _required_string(arguments, "name").strip()
    if not name:
        raise McpAdapterError(INVALID_PARAMS, "name cannot be empty")

    description = (_optional_string(arguments, "description") or "").strip()
    created_by_client = _optional_string(arguments, "created_by_client") or "mcp"
    metadata = {
        **_metadata_argument(arguments),
        "mcp": {
            "createdBy": "agent",
            "createdByClient": created_by_client,
        },
    }
    try:
        project = create_project(
            supabase,
            user_id,
            name,
            description,
            metadata,
        )
    except ValueError as exc:
        raise McpAdapterError(INVALID_PARAMS, str(exc)) from exc

    return _tool_response(
        {
            "project": project,
            "guidance": (
                "Project created for this authenticated user. Use project.id or "
                "project.slug in scoped retrieval calls, queue_youtube_ingestion for "
                "single-video project imports, or link_youtube_playlist_capture_source "
                "to attach a standing YouTube playlist to the project."
            ),
            "nextMcpCalls": [
                {
                    "name": "link_youtube_playlist_capture_source",
                    "requiresScope": "capture:write",
                    "argumentsTemplate": {
                        "playlist_url": "https://www.youtube.com/playlist?list=PLAYLIST_ID",
                        "project_id": project.get("id"),
                    },
                },
                {
                    "name": "get_project_context_map",
                    "requiresScope": "context:read",
                    "argumentsTemplate": {"project_id": project.get("id")},
                },
            ],
        }
    )


def _link_youtube_playlist_capture_source_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    del tool_context
    _ensure_allowed_args(
        arguments,
        {
            "playlist_url",
            "title",
            "project_id",
            "project_slug",
            "created_by_client",
        },
    )
    playlist_url = _required_string(arguments, "playlist_url").strip()
    if not playlist_url:
        raise McpAdapterError(INVALID_PARAMS, "playlist_url cannot be empty")
    source_type, playlist_id = detect_url_type(playlist_url)
    if source_type != "playlist" or not playlist_id:
        raise McpAdapterError(INVALID_PARAMS, "playlist_url must be a valid YouTube playlist URL")

    project_id = _optional_string(arguments, "project_id")
    project_slug = _optional_string(arguments, "project_slug")
    if not project_id and not project_slug:
        raise McpAdapterError(
            INVALID_PARAMS,
            "project_id or project_slug is required so the playlist is attached to a project.",
        )
    try:
        project_scope = resolve_project_scope(
            supabase,
            user_id,
            project_id=project_id,
            project_slug=project_slug,
        )
    except ValueError as exc:
        raise McpAdapterError(INVALID_PARAMS, str(exc)) from exc
    if not project_scope:
        raise McpAdapterError(INVALID_PARAMS, "Project not found")

    client = _optional_string(arguments, "created_by_client") or "mcp"
    try:
        source = create_playlist_capture_source(
            supabase,
            user_id,
            playlist_url,
            _optional_string(arguments, "title") or "",
            project_scope["id"],
            "agent",
            client,
        )
    except ValueError as exc:
        raise McpAdapterError(INVALID_PARAMS, str(exc)) from exc

    return _tool_response(
        {
            "captureSource": source,
            "projectTarget": {
                "id": project_scope.get("id"),
                "name": project_scope.get("name"),
                "slug": project_scope.get("slug"),
            },
            "playlist": {"playlistId": playlist_id, "url": playlist_url},
            "guidance": (
                "Playlist capture source linked to the project. Call sync_capture_source "
                "with max_jobs=0 to preview pending videos, then queue only after explicit "
                "confirmation with allow_queue=true and confirmed_queue_count."
            ),
            "nextMcpCalls": [
                {
                    "name": "sync_capture_source",
                    "requiresScope": "capture:write",
                    "argumentsTemplate": {
                        "capture_source_id": source.get("id"),
                        "max_jobs": 0,
                    },
                },
                {
                    "name": "list_capture_sources",
                    "requiresScope": "context:read",
                    "argumentsTemplate": {},
                },
            ],
        }
    )


def _build_context_bundle_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    del tool_context
    _ensure_allowed_args(
        arguments,
        {
            "query",
            "repo_context",
            "category_filters",
            "limit",
            "detail_level",
            "max_chars",
            "max_context_tokens",
        },
    )
    query = _required_string(arguments, "query").strip()
    if not query:
        raise McpAdapterError(INVALID_PARAMS, "query cannot be empty")

    repo_context = arguments.get("repo_context")
    if repo_context is not None and not isinstance(repo_context, dict):
        raise McpAdapterError(INVALID_PARAMS, "repo_context must be an object")
    category_filters = arguments.get("category_filters")
    if category_filters is not None and not isinstance(category_filters, dict):
        raise McpAdapterError(INVALID_PARAMS, "category_filters must be an object")

    limit = _bounded_int(arguments.get("limit", 8), minimum=1, maximum=20, name="limit")
    budget = _budget_args(arguments)
    payload = build_context_bundle(supabase, user_id, query, repo_context, limit, category_filters)
    payload["detailLevel"] = budget["detailLevel"]
    return _tool_response(_apply_response_budget(payload, budget))


def _build_agent_brief_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    _ensure_allowed_args(
        arguments,
        {
            "query",
            "repo_context",
            "category_filters",
            "limit",
            "detail_level",
            "max_chars",
            "max_context_tokens",
        },
    )
    query = _required_string(arguments, "query").strip()
    if not query:
        raise McpAdapterError(INVALID_PARAMS, "query cannot be empty")

    repo_context = arguments.get("repo_context")
    if repo_context is not None and not isinstance(repo_context, dict):
        raise McpAdapterError(INVALID_PARAMS, "repo_context must be an object")
    category_filters = arguments.get("category_filters")
    if category_filters is not None and not isinstance(category_filters, dict):
        raise McpAdapterError(INVALID_PARAMS, "category_filters must be an object")

    limit = _bounded_int(arguments.get("limit", 8), minimum=1, maximum=20, name="limit")
    budget = _budget_args(arguments)
    payload = build_agent_brief(
        supabase,
        user_id,
        query,
        repo_context,
        limit,
        category_filters,
        embedding_provider=tool_context.get("embed_source_query"),
        retrieval_mode="hybrid",
    )
    payload["detailLevel"] = budget["detailLevel"]
    return _tool_response(_apply_response_budget(payload, budget))


def _queue_youtube_ingestion_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    _ensure_allowed_args(
        arguments,
        {
            "url",
            "allow_bulk",
            "created_by_client",
            "digest_depth",
            "project_id",
            "project_slug",
        },
    )
    url = _required_string(arguments, "url").strip()
    if not url:
        raise McpAdapterError(INVALID_PARAMS, "url cannot be empty")

    source_type, extracted_id = detect_url_type(url)
    if source_type == "unknown":
        raise McpAdapterError(
            INVALID_PARAMS,
            "url must be a valid YouTube video, playlist, channel, or Shorts URL",
        )
    if source_type in {"playlist", "channel"} and arguments.get("allow_bulk") is not True:
        raise McpAdapterError(
            INVALID_PARAMS,
            "playlist and channel ingestion require allow_bulk=true after explicit user approval",
        )

    project_target = _resolve_agent_project_target(
        supabase,
        user_id,
        project_id=_optional_string(arguments, "project_id"),
        project_slug=_optional_string(arguments, "project_slug"),
        source_type=source_type,
    )
    limits = _require_available_ingestion_slot(supabase, user_id)

    digest_depth = normalize_digest_depth(arguments.get("digest_depth", DEFAULT_DIGEST_DEPTH))
    cost_estimate = build_ingestion_cost_estimate(
        supabase,
        user_id,
        url,
        source_type,
        digest_depth=digest_depth,
    )
    client = _optional_string(arguments, "created_by_client") or "mcp"
    cost_estimate = {
        **cost_estimate,
        "mcp": {
            "createdBy": "agent",
            "createdByClient": client,
            "requestedProject": project_target,
        },
    }
    job = create_ingestion_job(supabase, user_id, url, source_type, cost_estimate)
    job_id = job.get("id")
    if job_id:
        record_ingestion_job_event(
            supabase,
            job_id,
            "info",
            f"Queued from MCP by {client}.",
        )
        queued_jobs = tool_context.get("queued_ingestion_jobs")
        if isinstance(queued_jobs, list):
            queued_jobs.append(job)

    return _tool_response(
        {
            "job": job,
            "sourceType": source_type,
            "extractedId": extracted_id,
            "digestDepth": digest_depth,
            "costEstimate": job.get("cost_estimate") or cost_estimate,
            "limits": limits,
            "projectTarget": project_target,
            "notifications": _ingestion_polling_payload(job),
            "guidance": (
                "The URL has been queued for the user's hosted ingestion pipeline. "
                "Use list_video_library or context://library after the job completes; "
                "source transcript and generated knowledge remain read-only over MCP. "
                "Inspect costEstimate, limits, and digestDepth before approving more bulk "
                "submissions. If projectTarget is set, a successful single-video job will be "
                "attached to that project after ingestion finishes."
            ),
        }
    )


def _sync_capture_source_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    _ensure_allowed_args(
        arguments,
        {
            "capture_source_id",
            "max_jobs",
            "allow_queue",
            "confirmed_queue_count",
            "created_by_client",
        },
    )
    capture_source_id = _required_string(arguments, "capture_source_id").strip()
    if not capture_source_id:
        raise McpAdapterError(INVALID_PARAMS, "capture_source_id cannot be empty")

    max_jobs = _bounded_int(arguments.get("max_jobs", 0), minimum=0, maximum=100, name="max_jobs")
    allow_queue = arguments.get("allow_queue", False)
    if not isinstance(allow_queue, bool):
        raise McpAdapterError(INVALID_PARAMS, "allow_queue must be a boolean")

    confirmed_queue_count = arguments.get("confirmed_queue_count")
    if confirmed_queue_count is not None:
        confirmed_queue_count = _bounded_int(
            confirmed_queue_count,
            minimum=0,
            maximum=100,
            name="confirmed_queue_count",
        )

    limits = _plan_limit_snapshot(supabase, user_id)
    limits["activeIngestionJobs"] = count_active_ingestion_jobs(supabase, user_id)
    if max_jobs > limits["maxImportVideos"]:
        raise McpAdapterError(
            INVALID_PARAMS,
            (
                f"max_jobs exceeds this user's plan import limit of "
                f"{limits['maxImportVideos']} videos per request"
            ),
        )
    if max_jobs > 0:
        if allow_queue is not True:
            raise McpAdapterError(
                INVALID_PARAMS,
                "Queueing capture-source ingestion jobs requires allow_queue=true.",
            )
        if confirmed_queue_count != max_jobs:
            raise McpAdapterError(
                INVALID_PARAMS,
                "confirmed_queue_count must equal max_jobs after the agent shows the user a preview.",
            )
        if limits["activeIngestionJobs"] >= limits["maxActiveIngestionJobs"]:
            raise McpAdapterError(
                SERVER_ERROR,
                (
                    "This user already has the maximum number of imports running for their plan. "
                    "Poll existing ingestion jobs and try again after one finishes."
                ),
            )

    queued_capture_sync_jobs = tool_context.get("queued_capture_sync_jobs")

    def defer_dispatch(job: dict) -> dict:
        if isinstance(queued_capture_sync_jobs, list):
            queued_capture_sync_jobs.append(job)
        return {
            "status": "scheduled_after_mcp_response",
            "source": "mcp-capture-sync",
        }

    client = _optional_string(arguments, "created_by_client") or "mcp"
    try:
        sync_result = run_capture_sync_workflow(
            supabase,
            user_id,
            capture_source_id,
            max_jobs,
            dispatch_job=defer_dispatch,
            trigger="mcp.capture.sync",
            created_by="agent",
            created_by_client=client,
        )
    except ValueError as exc:
        raise McpAdapterError(INVALID_PARAMS, str(exc)) from exc

    queued_jobs = sync_result.get("queuedJobs", [])
    workflow_instance_id = sync_result.get("workflow_instance_id")
    return _tool_response(
        {
            "mode": "queued" if max_jobs > 0 else "preview",
            "captureSource": sync_result.get("captureSource"),
            "workflowInstance": sync_result.get("workflowInstance"),
            "workflow_instance_id": workflow_instance_id,
            "counts": {
                "discoveredCount": sync_result.get("discoveredCount", 0),
                "newItemCount": sync_result.get("newItemCount", 0),
                "queueCandidateCount": sync_result.get("queueCandidateCount", 0),
                "queuedJobCount": sync_result.get("queuedJobCount", 0),
                "requestedJobCount": sync_result.get("requestedJobCount", max_jobs),
                "remainingQueueCount": sync_result.get("remainingQueueCount", 0),
                "skippedExistingCount": sync_result.get("skippedExistingCount", 0),
            },
            "costEstimate": sync_result.get("costEstimate"),
            "limits": limits,
            "queuedJobs": _compact_queued_jobs(queued_jobs),
            "dispatchResults": sync_result.get("dispatchResults", []),
            "notifications": {
                **_ingestion_polling_payload(None, workflow_instance_id),
                "job_ids": [job.get("id") for job in queued_jobs if isinstance(job, dict)],
            },
            "guidance": (
                "Use max_jobs=0 first to preview queueCandidateCount. Queueing requires "
                "allow_queue=true and confirmed_queue_count equal to max_jobs. Poll "
                "get_workflow_run for sync status and get_ingestion_job for per-video "
                "errors or confirmations."
            ),
        }
    )


def _search_video_concepts_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    _ensure_allowed_args(
        arguments,
        {
            "query",
            "limit",
            "category_filters",
            "retrieval_mode",
            "detail_level",
            "max_chars",
            "max_context_tokens",
            "project_id",
            "project_slug",
        },
    )
    query = _required_string(arguments, "query").strip()
    if not query:
        raise McpAdapterError(INVALID_PARAMS, "query cannot be empty")
    category_filters = arguments.get("category_filters")
    if category_filters is not None and not isinstance(category_filters, dict):
        raise McpAdapterError(INVALID_PARAMS, "category_filters must be an object")

    limit = _bounded_int(arguments.get("limit", 8), minimum=1, maximum=20, name="limit")
    budget = _budget_args(arguments)
    retrieval_mode = _source_knowledge_retrieval_mode(arguments)
    project_id = _optional_string(arguments, "project_id")
    project_slug = _optional_string(arguments, "project_slug")
    if project_id or project_slug:
        payload = search_source_knowledge(
            supabase,
            user_id,
            query,
            limit,
            category_filters,
            budget["detailLevel"],
            budget["requestedMaxChars"],
            budget["maxContextTokens"],
            retrieval_mode=retrieval_mode,
            embedding_provider=tool_context.get("embed_source_query"),
            project_id=project_id,
            project_slug=project_slug,
        )
    else:
        payload = search_source_knowledge(
            supabase,
            user_id,
            query,
            limit,
            category_filters,
            budget["detailLevel"],
            budget["requestedMaxChars"],
            budget["maxContextTokens"],
            retrieval_mode=retrieval_mode,
            embedding_provider=tool_context.get("embed_source_query"),
        )
    return _tool_response(payload)


def _get_video_knowledge_map_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    del tool_context
    _ensure_allowed_args(
        arguments,
        {
            "youtube_video_id",
            "video_id",
            "detail_level",
            "max_chars",
            "max_context_tokens",
            "project_id",
            "project_slug",
        },
    )
    video_id = arguments.get("youtube_video_id") or arguments.get("video_id")
    if not isinstance(video_id, str) or not video_id.strip():
        raise McpAdapterError(INVALID_PARAMS, "youtube_video_id is required")
    budget = _budget_args(arguments)
    project_id = _optional_string(arguments, "project_id")
    project_slug = _optional_string(arguments, "project_slug")
    if project_id or project_slug:
        payload = build_video_knowledge_map(
            supabase,
            user_id,
            video_id.strip(),
            detail_level=budget["detailLevel"],
            max_chars=budget["requestedMaxChars"],
            max_context_tokens=budget["maxContextTokens"],
            project_id=project_id,
            project_slug=project_slug,
        )
    else:
        payload = build_video_knowledge_map(
            supabase,
            user_id,
            video_id.strip(),
            detail_level=budget["detailLevel"],
            max_chars=budget["requestedMaxChars"],
            max_context_tokens=budget["maxContextTokens"],
        )
    return _tool_response(payload)


def _search_transcript_text_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    del supabase, user_id
    _ensure_allowed_args(
        arguments,
        {
            "query",
            "limit",
            "category_filters",
            "retrieval_mode",
            "detail_level",
            "max_chars",
            "max_context_tokens",
            "project_id",
            "project_slug",
            "youtube_video_id",
            "video_id",
        },
    )
    query = _required_string(arguments, "query").strip()
    if not query:
        raise McpAdapterError(INVALID_PARAMS, "query cannot be empty")
    category_filters = arguments.get("category_filters")
    if category_filters is not None and not isinstance(category_filters, dict):
        raise McpAdapterError(INVALID_PARAMS, "category_filters must be an object")
    if arguments.get("retrieval_mode") is not None:
        retrieval_mode = _moment_retrieval_mode(arguments)
        if retrieval_mode != "keyword":
            raise McpAdapterError(
                INVALID_PARAMS,
                "search_transcript_text only supports retrieval_mode=keyword",
            )

    limit = _bounded_int(arguments.get("limit", 5), minimum=1, maximum=20, name="limit")
    budget = _budget_args(arguments)
    search_runner = tool_context.get("search_transcript_text")
    if not callable(search_runner):
        raise McpAdapterError(SERVER_ERROR, "Keyword transcript search is not configured")

    project_id = _optional_string(arguments, "project_id")
    project_slug = _optional_string(arguments, "project_slug")
    video_id = _optional_video_id(arguments)
    try:
        if project_id or project_slug:
            result = search_runner(
                query,
                limit,
                category_filters,
                project_id,
                project_slug,
                video_id,
            )
        else:
            result = search_runner(query, limit, category_filters, youtube_video_id=video_id)
    except ValueError as exc:
        raise McpAdapterError(SERVER_ERROR, str(exc)) from exc

    payload = {
        "query": query,
        "retrievalMode": result.get("retrievalMode", "keyword"),
        "detailLevel": budget["detailLevel"],
        "categoryFilters": result.get("categoryFilters", category_filters or {}),
        "projectScope": result.get("projectScope"),
        "videoScope": result.get(
            "videoScope",
            {"scope": "video" if video_id else "all_videos", "youtubeVideoId": video_id},
        ),
        "relevantClips": [
            _budget_clip({**clip, "matchType": clip.get("matchType", "transcript_keyword")}, budget)
            for clip in result.get("relevantClips", [])
        ],
        "retrievalPlan": result.get(
            "retrievalPlan",
            {
                "primary": "keyword_full_text",
                "embeddingUsed": False,
                "llmAnswerUsed": False,
            },
        ),
        "retrievalBudget": result.get(
            "retrievalBudget",
            {
                "embeddingCalls": 0,
                "llmCalls": 0,
                "maxClips": limit,
            },
        ),
        "guidance": (
            "Use this for exact names, acronyms, product terms, and phrase searches. "
            "It does not spend embedding or LLM calls. If results are sparse, call "
            "search_video_moments with retrieval_mode=hybrid for timestamp neighbors. "
            "When the user names a specific video, pass youtube_video_id/video_id to keep "
            "results inside that video."
        ),
    }
    return _tool_response(_apply_retrieval_budget(payload, "relevantClips", budget))


def _search_video_moments_tool(
    supabase: Any, user_id: str, arguments: dict, tool_context: dict
) -> dict:
    del supabase, user_id
    _ensure_allowed_args(
        arguments,
        {
            "query",
            "limit",
            "category_filters",
            "retrieval_mode",
            "detail_level",
            "max_chars",
            "max_context_tokens",
            "project_id",
            "project_slug",
            "youtube_video_id",
            "video_id",
        },
    )
    query = _required_string(arguments, "query").strip()
    if not query:
        raise McpAdapterError(INVALID_PARAMS, "query cannot be empty")
    category_filters = arguments.get("category_filters")
    if category_filters is not None and not isinstance(category_filters, dict):
        raise McpAdapterError(INVALID_PARAMS, "category_filters must be an object")

    limit = _bounded_int(arguments.get("limit", 5), minimum=1, maximum=20, name="limit")
    budget = _budget_args(arguments)
    retrieval_mode = _moment_retrieval_mode(arguments)
    search_runner = tool_context.get("search_video_moments")
    if not callable(search_runner):
        raise McpAdapterError(SERVER_ERROR, "Semantic moment search is not configured")

    project_id = _optional_string(arguments, "project_id")
    project_slug = _optional_string(arguments, "project_slug")
    video_id = _optional_video_id(arguments)
    try:
        if project_id or project_slug:
            result = search_runner(
                query,
                limit,
                category_filters,
                retrieval_mode,
                project_id,
                project_slug,
                video_id,
            )
        else:
            result = search_runner(
                query,
                limit,
                category_filters,
                retrieval_mode,
                youtube_video_id=video_id,
            )
    except ValueError as exc:
        raise McpAdapterError(SERVER_ERROR, str(exc)) from exc

    answer = _truncate_tool_text(result.get("answer", ""), budget["answer_chars"])
    payload = {
        "query": query,
        "retrievalMode": result.get("retrievalMode", retrieval_mode),
        "detailLevel": budget["detailLevel"],
        "categoryFilters": result.get("categoryFilters", category_filters or {}),
        "projectScope": result.get("projectScope"),
        "videoScope": result.get(
            "videoScope",
            {"scope": "video" if video_id else "all_videos", "youtubeVideoId": video_id},
        ),
        "answer": answer,
        "relevantClips": [
            _budget_clip(
                {**clip, "matchType": clip.get("matchType", "semantic_transcript")}, budget
            )
            for clip in result.get("relevantClips", [])
        ],
        "retrievalPlan": result.get(
            "retrievalPlan",
            {
                "primary": (
                    "hybrid_vector_keyword_rrf"
                    if retrieval_mode == "hybrid"
                    else (
                        "keyword_full_text"
                        if retrieval_mode == "keyword"
                        else "semantic_vector_transcript"
                    )
                ),
                "embeddingUsed": retrieval_mode != "keyword",
                "llmAnswerUsed": bool(answer),
                "fallback": (
                    "Use search_transcript_text for exact phrases or search_video_concepts "
                    "for source concepts and generated artifacts before pulling clips."
                ),
            },
        ),
        "retrievalBudget": result.get(
            "retrievalBudget",
            {
                "embeddingCalls": 0 if retrieval_mode == "keyword" else 1,
                "llmCalls": 1 if answer else 0,
                "maxClips": limit,
            },
        ),
        "guidance": (
            "Use relevantClips as timestamp citations. Each clip includes videoId, "
            "startSeconds, endSeconds, title, channelName, transcript content, "
            "and accessScope/accessReason explaining why it is visible to this user."
            " For exact phrases, names, acronyms, and product terms, use "
            "search_transcript_text first to avoid embedding/LLM spend. For concepts, "
            "source reports, TLDRs, methods, tools, or pitfalls, call search_video_concepts. "
            "When answering about one known video, pass youtube_video_id/video_id."
        ),
    }
    return _tool_response(_apply_retrieval_budget(payload, "relevantClips", budget))


def _tool_response(payload: dict) -> dict:
    full_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
    text = (
        full_text
        if len(full_text) <= MAX_INLINE_TOOL_TEXT_CHARS
        else _large_tool_response_summary(payload, len(full_text))
    )
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": payload,
        "isError": False,
    }


def _large_tool_response_summary(payload: dict, full_json_chars: int) -> str:
    lines = [
        "Large structured MCP payload returned.",
        "Read result.structuredContent for the full JSON object.",
        f"Full structured payload is about {full_json_chars} JSON characters.",
    ]

    if isinstance(payload.get("query"), str):
        lines.append(f"Query: {_truncate_tool_text(payload.get('query'), 180)}")

    video = payload.get("video")
    if isinstance(video, dict):
        title = video.get("title") or video.get("videoId") or video.get("id")
        if title:
            lines.append(f"Video: {_truncate_tool_text(title, 180)}")

    for key, label in (
        ("results", "results"),
        ("relevantClips", "clips"),
        ("channels", "channels"),
        ("knowledgeArtifacts", "artifacts"),
        ("sourceConcepts", "concepts"),
        ("sourceEdges", "edges"),
    ):
        value = payload.get(key)
        if isinstance(value, list):
            lines.append(f"{label}: {len(value)}")
            _append_tool_summary_items(lines, value)

    transcript_budget = payload.get("transcriptBudget")
    if isinstance(transcript_budget, dict):
        lines.append(
            "Transcript: "
            f"{transcript_budget.get('returnedTranscriptChunks', 0)} of "
            f"{transcript_budget.get('availableTranscriptChunks', 0)} chunks returned."
        )

    response_budget = payload.get("responseBudget")
    if isinstance(response_budget, dict):
        lines.append(
            "Response budget: "
            f"{response_budget.get('detailLevel')} detail, "
            f"estimated {response_budget.get('estimatedResponseChars')} chars, "
            f"truncated={bool(response_budget.get('truncatedToBudget'))}."
        )

    retrieval_budget = payload.get("retrievalBudget")
    if isinstance(retrieval_budget, dict):
        lines.append(
            "Retrieval budget: "
            f"embeddingCalls={retrieval_budget.get('embeddingCalls', 0)}, "
            f"llmCalls={retrieval_budget.get('llmCalls', 0)}, "
            f"returnedResults={retrieval_budget.get('returnedResults', 0)}."
        )

    answer = payload.get("answer")
    if isinstance(answer, str) and answer.strip():
        lines.append(f"Answer preview: {_truncate_tool_text(answer, 500)}")

    return "\n".join(lines)


def _append_tool_summary_items(lines: list[str], items: list[Any]) -> None:
    previews = []
    for item in items[:MAX_TOOL_TEXT_SUMMARY_ITEMS]:
        if not isinstance(item, dict):
            continue
        title = (
            item.get("title")
            or item.get("name")
            or item.get("resultType")
            or item.get("artifactType")
            or item.get("conceptType")
        )
        if not title and isinstance(item.get("video"), dict):
            title = item["video"].get("title") or item["video"].get("videoId")
        if not title:
            title = item.get("videoId") or item.get("id")
        if title:
            previews.append(_truncate_tool_text(title, 120))
    if previews:
        lines.append(f"First items: {', '.join(previews)}")


def _resource_response(uri: str, payload: dict) -> dict:
    return {
        "contents": [
            {
                "uri": uri,
                "mimeType": "application/json",
                "text": json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            }
        ]
    }


def _prompt_response(description: str, text: str) -> dict:
    return {
        "description": description,
        "messages": [
            {
                "role": "user",
                "content": {"type": "text", "text": text},
            }
        ],
    }


def _result(request_id: Any, result: Any) -> dict:
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict:
    return {
        "jsonrpc": JSONRPC_VERSION,
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _ensure_allowed_args(arguments: dict, allowed: set[str]) -> None:
    extra = sorted(set(arguments) - allowed)
    if extra:
        raise McpAdapterError(INVALID_PARAMS, f"Unexpected argument(s): {', '.join(extra)}")


def _required_string(arguments: dict, name: str) -> str:
    value = arguments.get(name)
    if not isinstance(value, str):
        raise McpAdapterError(INVALID_PARAMS, f"{name} must be a string")
    return value


def _optional_string(arguments: dict, name: str) -> str | None:
    value = arguments.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise McpAdapterError(INVALID_PARAMS, f"{name} must be a string")
    return value


def _optional_video_id(arguments: dict) -> str | None:
    value = _optional_string(arguments, "youtube_video_id") or _optional_string(
        arguments, "video_id"
    )
    if value is None:
        return None
    return value.strip() or None


def _optional_list_of_objects(arguments: dict, name: str) -> list[dict]:
    value = arguments.get(name, [])
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise McpAdapterError(INVALID_PARAMS, f"{name} must be an array of objects")
    return value


def _optional_list_of_strings(arguments: dict, name: str) -> list[str]:
    value = arguments.get(name, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise McpAdapterError(INVALID_PARAMS, f"{name} must be an array of strings")
    return value


def _bounded_int(value: Any, minimum: int, maximum: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise McpAdapterError(INVALID_PARAMS, f"{name} must be an integer")
    return max(minimum, min(value, maximum))


TOOL_DETAIL_BUDGETS = {
    "compact": {
        "clip_chars": 240,
        "answer_chars": 900,
        "summary_chars": 360,
        "content_chars": 700,
    },
    "standard": {
        "clip_chars": 600,
        "answer_chars": 1800,
        "summary_chars": 800,
        "content_chars": 2200,
    },
    "deep": {
        "clip_chars": 1200,
        "answer_chars": 4000,
        "summary_chars": 1600,
        "content_chars": 9000,
    },
}
MOMENT_RETRIEVAL_MODES = {"hybrid", "semantic", "keyword"}
SOURCE_KNOWLEDGE_RETRIEVAL_MODES = {"hybrid", "semantic", "keyword"}

BUDGET_TOOL_PROPERTIES = {
    "detail_level": {
        "type": "string",
        "enum": ["compact", "standard", "deep"],
        "default": "compact",
        "description": "Controls response size. compact is the default for agent token discipline.",
    },
    "max_chars": {
        "type": "integer",
        "minimum": 1000,
        "maximum": 30000,
        "description": "Approximate maximum JSON response characters to return.",
    },
    "max_context_tokens": {
        "type": "integer",
        "minimum": 250,
        "maximum": 7500,
        "description": "Optional token budget converted to roughly four response characters per token.",
    },
}

PROJECT_SCOPE_TOOL_PROPERTIES = {
    "project_id": {
        "type": "string",
        "description": (
            "Optional user project ID to scope search/context. Agents should choose this "
            "explicitly after list_projects instead of assuming the web UI's current filter."
        ),
    },
    "project_slug": {
        "type": "string",
        "description": "Optional user project slug to scope search/context.",
    },
}

VIDEO_SCOPE_TOOL_PROPERTIES = {
    "youtube_video_id": {
        "type": "string",
        "description": (
            "Optional YouTube video ID to constrain retrieval to one known saved video. "
            "Use this whenever the user asks about a specific video."
        ),
    },
    "video_id": {
        "type": "string",
        "description": "Alias for youtube_video_id.",
    },
}


def _budget_args(arguments: dict) -> dict:
    raw_detail = arguments.get("detail_level", "compact")
    if raw_detail is not None and not isinstance(raw_detail, str):
        raise McpAdapterError(INVALID_PARAMS, "detail_level must be a string")
    detail_level = normalize_detail_level(raw_detail)
    if raw_detail is not None and str(raw_detail).strip().lower() not in TOOL_DETAIL_BUDGETS:
        raise McpAdapterError(INVALID_PARAMS, "detail_level must be compact, standard, or deep")

    max_chars = None
    if arguments.get("max_chars") is not None:
        max_chars = _bounded_int(
            arguments["max_chars"],
            minimum=1000,
            maximum=30000,
            name="max_chars",
        )

    max_context_tokens = None
    if arguments.get("max_context_tokens") is not None:
        max_context_tokens = _bounded_int(
            arguments["max_context_tokens"],
            minimum=250,
            maximum=7500,
            name="max_context_tokens",
        )

    return {
        "detailLevel": detail_level,
        "maxChars": response_char_budget(detail_level, max_chars, max_context_tokens),
        "requestedMaxChars": max_chars,
        "maxContextTokens": max_context_tokens,
        **TOOL_DETAIL_BUDGETS[detail_level],
    }


def _moment_retrieval_mode(arguments: dict) -> str:
    raw_mode = arguments.get("retrieval_mode", "hybrid")
    if not isinstance(raw_mode, str):
        raise McpAdapterError(INVALID_PARAMS, "retrieval_mode must be a string")
    mode = raw_mode.strip().lower()
    if mode not in MOMENT_RETRIEVAL_MODES:
        raise McpAdapterError(INVALID_PARAMS, "retrieval_mode must be hybrid, semantic, or keyword")
    return mode


def _source_knowledge_retrieval_mode(arguments: dict) -> str:
    raw_mode = arguments.get("retrieval_mode", "hybrid")
    if not isinstance(raw_mode, str):
        raise McpAdapterError(INVALID_PARAMS, "retrieval_mode must be a string")
    mode = raw_mode.strip().lower()
    if mode not in SOURCE_KNOWLEDGE_RETRIEVAL_MODES:
        raise McpAdapterError(INVALID_PARAMS, "retrieval_mode must be hybrid, semantic, or keyword")
    return mode


def _truncate_tool_text(value: Any, max_chars: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 1].rstrip()}…"


def _estimated_response_chars(payload: dict) -> int:
    return len(json.dumps(payload, ensure_ascii=False, default=str))


def _budget_clip(clip: dict, budget: dict) -> dict:
    budgeted = dict(clip)
    if "content" in budgeted:
        budgeted["content"] = _truncate_tool_text(budgeted["content"], budget["clip_chars"])
    if "matchSnippet" in budgeted:
        budgeted["matchSnippet"] = _truncate_tool_text(
            budgeted["matchSnippet"], min(240, budget["clip_chars"])
        )
    budgeted.setdefault("matchType", "semantic_transcript")
    return budgeted


def _apply_retrieval_budget(payload: dict, list_key: str, budget: dict) -> dict:
    retrieval_budget = dict(payload.get("retrievalBudget") or {})
    original_answer = payload.get("answer")
    retrieval_budget.update(
        {
            "detailLevel": budget["detailLevel"],
            "maxChars": budget["maxChars"],
            "maxContextTokens": budget["maxContextTokens"],
            "truncatedToBudget": False,
        }
    )
    payload["retrievalBudget"] = retrieval_budget
    retrieval_budget["estimatedResponseChars"] = _estimated_response_chars(payload)

    results = payload.get(list_key)
    if isinstance(results, list):
        while len(results) > 1 and retrieval_budget["estimatedResponseChars"] > budget["maxChars"]:
            results.pop()
            retrieval_budget["truncatedToBudget"] = True
            retrieval_budget["estimatedResponseChars"] = _estimated_response_chars(payload)
        if retrieval_budget["estimatedResponseChars"] > budget["maxChars"]:
            retrieval_budget["truncatedToBudget"] = True
        retrieval_budget["returnedResults"] = len(results)

    if retrieval_budget.get("truncatedToBudget") and original_answer:
        payload["answer"] = ""
        retrieval_budget["answerOmittedReason"] = (
            "Generated answer omitted because response budgeting removed one or more clips; "
            "use the returned clips as timestamp evidence or retry with a larger max_chars."
        )
        retrieval_plan = payload.get("retrievalPlan")
        if isinstance(retrieval_plan, dict):
            retrieval_plan["llmAnswerVisible"] = False
        retrieval_budget["estimatedResponseChars"] = _estimated_response_chars(payload)

    return payload


def _trim_response_text(value: Any, budget: dict, key: str = "") -> Any:
    if isinstance(value, list):
        return [_trim_response_text(item, budget) for item in value]
    if isinstance(value, dict):
        return {
            item_key: _trim_response_text(item_value, budget, item_key)
            for item_key, item_value in value.items()
        }
    if isinstance(value, str):
        if key in {"content", "contentExcerpt"}:
            return _truncate_tool_text(value, budget["content_chars"])
        if key in {"summary", "guidance"}:
            return _truncate_tool_text(value, budget["summary_chars"])
        if key == "answer":
            return _truncate_tool_text(value, budget["answer_chars"])
    return value


def _apply_response_budget(payload: dict, budget: dict) -> dict:
    budgeted = _trim_response_text(payload, budget)
    response_budget = {
        "detailLevel": budget["detailLevel"],
        "maxChars": budget["maxChars"],
        "maxContextTokens": budget["maxContextTokens"],
        "estimatedResponseChars": _estimated_response_chars(budgeted),
    }
    response_budget["truncatedToBudget"] = (
        response_budget["estimatedResponseChars"] > budget["maxChars"]
    )
    budgeted["responseBudget"] = response_budget
    return budgeted


VIDEO_TRANSCRIPT_ITEM_LIMITS = {"compact": 10, "standard": 50, "deep": 200}


def _items_overlapping_window(
    items: list[dict], start_seconds: int, end_seconds: int
) -> list[dict]:
    windowed: list[dict] = []
    for item in items:
        item_start = item.get("start_seconds", item.get("startSeconds"))
        item_end = item.get("end_seconds", item.get("endSeconds"))
        if not isinstance(item_start, (int, float)) or not isinstance(item_end, (int, float)):
            continue
        if item_start < end_seconds and item_end > start_seconds:
            windowed.append(item)
    return windowed


def _youtube_timestamp_url(youtube_video_id: str, start_seconds: int) -> str:
    return f"https://www.youtube.com/watch?v={youtube_video_id}&t={max(0, int(start_seconds))}s"


def _budget_transcript_payload(payload: dict, budget: dict) -> dict:
    budgeted = _apply_response_budget(payload, budget)
    return _fit_payload_lists_to_response_budget(
        budgeted,
        budget,
        ["transcriptChunks", "transcriptLines"],
        transcript_budget_key="transcriptBudget",
    )


def _fit_payload_lists_to_response_budget(
    payload: dict,
    budget: dict,
    list_keys: list[str],
    transcript_budget_key: str | None = None,
) -> dict:
    response_budget = dict(payload.get("responseBudget") or {})
    response_budget.update(
        {
            "detailLevel": budget["detailLevel"],
            "maxChars": budget["maxChars"],
            "maxContextTokens": budget["maxContextTokens"],
            "estimatedResponseChars": _estimated_response_chars(payload),
            "truncatedToBudget": bool(response_budget.get("truncatedToBudget")),
        }
    )
    payload["responseBudget"] = response_budget

    for key in list_keys:
        items = payload.get(key)
        if not isinstance(items, list):
            continue
        while items and response_budget["estimatedResponseChars"] > budget["maxChars"]:
            items.pop()
            response_budget["truncatedToBudget"] = True
            response_budget["estimatedResponseChars"] = _estimated_response_chars(payload)

    if transcript_budget_key and isinstance(payload.get(transcript_budget_key), dict):
        transcript_budget = payload[transcript_budget_key]
        if isinstance(payload.get("transcriptLines"), list):
            transcript_budget["returnedTranscriptLines"] = len(payload["transcriptLines"])
        if isinstance(payload.get("transcriptChunks"), list):
            transcript_budget["returnedTranscriptChunks"] = len(payload["transcriptChunks"])

    response_budget["estimatedResponseChars"] = _estimated_response_chars(payload)
    if response_budget["estimatedResponseChars"] > budget["maxChars"]:
        response_budget["truncatedToBudget"] = True
    return payload


def _budget_video_context_payload(
    payload: dict,
    budget: dict,
    include_transcript: bool = False,
) -> dict:
    budgeted = dict(payload)
    line_count = len(budgeted.get("transcriptLines") or [])
    chunk_count = len(budgeted.get("transcriptChunks") or [])
    if include_transcript:
        item_limit = VIDEO_TRANSCRIPT_ITEM_LIMITS[budget["detailLevel"]]
        budgeted["transcriptLines"] = (budgeted.get("transcriptLines") or [])[:item_limit]
        budgeted["transcriptChunks"] = (budgeted.get("transcriptChunks") or [])[:item_limit]
        transcript_note = (
            f"Transcript included up to {item_limit} lines/chunks for {budget['detailLevel']} mode."
        )
    else:
        budgeted["transcriptLines"] = []
        budgeted["transcriptChunks"] = []
        transcript_note = (
            "Transcript lines/chunks are omitted by default for MCP token discipline. "
            "Call get_video_context with include_transcript=true and a larger detail_level "
            "only when the user asks for deeper source inspection."
        )

    budgeted["transcriptBudget"] = {
        "includeTranscript": include_transcript,
        "availableTranscriptLines": line_count,
        "availableTranscriptChunks": chunk_count,
        "returnedTranscriptLines": len(budgeted.get("transcriptLines") or []),
        "returnedTranscriptChunks": len(budgeted.get("transcriptChunks") or []),
        "guidance": transcript_note,
    }
    budgeted = _apply_response_budget(budgeted, budget)
    return _fit_payload_lists_to_response_budget(
        budgeted,
        budget,
        [
            "transcriptChunks",
            "transcriptLines",
            "sourceEdges",
            "sourceConcepts",
            "knowledgeArtifacts",
        ],
        transcript_budget_key="transcriptBudget",
    )


TOOLS = [
    {
        "name": "list_video_library",
        "title": "List Video Library",
        "description": (
            "List indexed channels and recent videos available in the current user's saved "
            "video library so agents can discover video IDs before reading context."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 50,
                    "description": "Maximum number of recent videos to return across channels.",
                },
                **PROJECT_SCOPE_TOOL_PROPERTIES,
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "list_projects",
        "title": "List Projects",
        "description": (
            "List user-created project scopes. Agents should call this before scoped "
            "retrieval, then pass project_id or project_slug explicitly to search and "
            "context tools when the user is working inside a project."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 50,
                },
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "get_project_context_map",
        "title": "Get Project Context Map",
        "description": (
            "Return a compact navigable map for one project: videos, component counts, "
            "top categories, capture-source links, suggested follow-up queries, and "
            "next MCP calls. Use this after list_projects and before broad library search."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                **PROJECT_SCOPE_TOOL_PROPERTIES,
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 25,
                    "description": "Maximum scoped videos to include in the map.",
                },
                **BUDGET_TOOL_PROPERTIES,
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "get_library_source_graph",
        "title": "Get Library Source Graph",
        "description": (
            "Return an inspectable source graph for the current user's library, including "
            "videos, labels, concepts, edges, artifacts, transcript chunk samples, overlay "
            "notes, review flags, and potential conflict candidates."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 50,
                    "description": "Maximum user-visible videos to include before graph sampling.",
                },
                **PROJECT_SCOPE_TOOL_PROPERTIES,
                **BUDGET_TOOL_PROPERTIES,
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "search_library_components",
        "title": "Search Library Components",
        "description": (
            "Keyword-search library source graph components without embeddings or an LLM. "
            "Covers video metadata, labels, concepts, edges, artifacts, transcript chunks, "
            "agent notes, and personal concepts."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Exact words, acronyms, names, tools, or claims to find.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 20,
                },
                "component_types": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [
                            "video",
                            "source_label",
                            "source_concept",
                            "source_edge",
                            "knowledge_artifact",
                            "transcript_chunk",
                            "agent_note",
                            "personal_concept",
                        ],
                    },
                    "description": "Optional component kinds to search.",
                },
                **PROJECT_SCOPE_TOOL_PROPERTIES,
                **BUDGET_TOOL_PROPERTIES,
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "list_capture_sources",
        "title": "List Capture Sources",
        "description": (
            "List standing YouTube capture sources, such as a user-selected playlist, "
            "that can feed future ingestion jobs."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 50,
                },
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "get_brain_sync_contract",
        "title": "Get Brain Sync Contract",
        "description": (
            "Return the machine-readable contract for syncing Memexai into an "
            "external personal brain or agent memory without direct database access."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "export_brain_digest",
        "title": "Export Brain Digest",
        "description": (
            "Export a compact incremental digest of user-granted saved-video knowledge "
            "for an external personal brain. Uses opaque cursors, optional since/object "
            "filters, access provenance, and response budgets; raw transcripts are not "
            "included."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "cursor": {
                    "type": "string",
                    "description": "Opaque nextCursor from a previous export_brain_digest response.",
                },
                "since": {
                    "type": "string",
                    "description": "Optional ISO timestamp override for incremental sync.",
                },
                "objects": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [
                            "videos",
                            "labels",
                            "concepts",
                            "artifacts",
                            "notes",
                            "personal_concepts",
                        ],
                    },
                    "description": "Optional object types to include. Defaults to all digest objects.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 20,
                },
                **BUDGET_TOOL_PROPERTIES,
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "search_transcript_text",
        "title": "Search Transcript Text",
        "description": (
            "Keyword-search the current user's indexed transcripts and titles without "
            "embedding or LLM spend. Use this for exact phrases, entities, acronyms, "
            "product names, or when semantic search returns noisy results. Pass "
            "youtube_video_id/video_id when the user asks about one known video. Results "
            "are limited to user_videos/user_channels grants and include access provenance."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                **VIDEO_SCOPE_TOOL_PROPERTIES,
                "category_filters": {
                    "type": "object",
                    "additionalProperties": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ]
                    },
                    "description": (
                        "Optional source-label filters such as "
                        '{"task_fit":["product spec"],"tool":["MCP"]}. '
                        "Values within a facet are OR; facets are AND."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 20,
                    "default": 5,
                },
                "retrieval_mode": {
                    "type": "string",
                    "enum": ["keyword"],
                    "default": "keyword",
                    "description": (
                        "Keyword-only search. This tool makes zero embedding and zero LLM calls."
                    ),
                },
                **PROJECT_SCOPE_TOOL_PROPERTIES,
                **BUDGET_TOOL_PROPERTIES,
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "search_video_concepts",
        "title": "Search Video Source Knowledge",
        "description": (
            "Search indexed source concepts, generated TLDRs/source reports, report "
            "sections, aliases, and timestamp refs. Defaults to hybrid vector + keyword "
            "retrieval with no LLM call; use retrieval_mode=keyword for zero embedding "
            "spend. Use this before timestamp retrieval so agents do not scan full transcripts."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "category_filters": {
                    "type": "object",
                    "additionalProperties": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ]
                    },
                    "description": (
                        "Optional source-label filters such as "
                        '{"task_fit":["study guide"],"tool":["MCP"]}. '
                        "Values within a facet are OR; facets are AND."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 20,
                    "default": 8,
                },
                "retrieval_mode": {
                    "type": "string",
                    "enum": ["hybrid", "semantic", "keyword"],
                    "default": "hybrid",
                    "description": (
                        "hybrid fuses source-report/concept vectors with keyword/title/alias "
                        "matches; semantic uses vector matches only; keyword makes zero "
                        "embedding calls."
                    ),
                },
                **PROJECT_SCOPE_TOOL_PROPERTIES,
                **BUDGET_TOOL_PROPERTIES,
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "get_video_knowledge_map",
        "title": "Get Video Knowledge Map",
        "description": (
            "Return a compact navigable table of contents for one saved video: report "
            "sections, concepts, people/orgs/tools, claims, decisions, timeline cues, "
            "timestamp refs, and suggested follow-up queries. Use this after "
            "search_video_concepts and before pulling transcript clips or full context."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "youtube_video_id": {
                    "type": "string",
                    "description": "The YouTube video ID to map.",
                },
                "video_id": {
                    "type": "string",
                    "description": "Alias for youtube_video_id.",
                },
                **PROJECT_SCOPE_TOOL_PROPERTIES,
                **BUDGET_TOOL_PROPERTIES,
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "search_video_moments",
        "title": "Search Video Moments",
        "description": (
            "Search the current user's indexed video transcripts and return timestamped "
            "clips with optional cited answer text. retrieval_mode defaults to hybrid "
            "vector + keyword/title fusion; semantic and keyword are available for "
            "narrower follow-up. Pass youtube_video_id/video_id when the user asks about "
            "one known video. Use category_filters to narrow search to source-label facets "
            "discovered with list_context_categories. Results are limited to user_videos/"
            "user_channels grants and include access provenance fields."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                **VIDEO_SCOPE_TOOL_PROPERTIES,
                "category_filters": {
                    "type": "object",
                    "additionalProperties": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ]
                    },
                    "description": (
                        "Optional source-label filters such as "
                        '{"task_fit":["product spec"],"tool":["MCP"]}. '
                        "Values within a facet are OR; facets are AND."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 20,
                    "default": 5,
                },
                "retrieval_mode": {
                    "type": "string",
                    "enum": ["hybrid", "semantic", "keyword"],
                    "default": "hybrid",
                    "description": (
                        "hybrid fuses vector and keyword/title candidates; semantic uses "
                        "vector search only; keyword avoids embedding spend."
                    ),
                },
                **PROJECT_SCOPE_TOOL_PROPERTIES,
                **BUDGET_TOOL_PROPERTIES,
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "list_context_categories",
        "title": "List Context Categories",
        "description": (
            "List browsable source labels, facets, concept categories, and personal "
            "concepts so agents can discover what knowledge exists before searching."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 200,
                    "default": 100,
                    "description": "Maximum number of categories to return.",
                },
                **PROJECT_SCOPE_TOOL_PROPERTIES,
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "list_ingestion_jobs",
        "title": "List Ingestion Jobs",
        "description": (
            "List recent hosted ingestion jobs for the current user in compact form so "
            "agents can check whether submitted YouTube links have been indexed. Use "
            "get_ingestion_job for full events and detailed diagnostics."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 10,
                },
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "get_ingestion_job",
        "title": "Get Ingestion Job",
        "description": (
            "Read one hosted ingestion job and its events, scoped to the current user."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "Durable ingestion job id returned by queue_youtube_ingestion.",
                },
            },
            "required": ["job_id"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "list_workflow_runs",
        "title": "List Workflow Runs",
        "description": (
            "List recent durable platform workflow runs such as capture sync, video "
            "ingestion, knowledge release, eval, and agent brief generation."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 10,
                },
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "get_workflow_run",
        "title": "Get Workflow Run",
        "description": (
            "Read one durable platform workflow run with step and artifact details, scoped "
            "to the current user."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "workflow_instance_id": {
                    "type": "string",
                    "description": "Durable workflow instance id returned by a long-running action.",
                },
                "instance_id": {
                    "type": "string",
                    "description": "Alias for workflow_instance_id.",
                },
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "get_mcp_session",
        "title": "Get MCP Session",
        "description": (
            "Return the current MCP connection's effective scopes, allowed capabilities, "
            "guardrails, and recommended next calls. This does not require database access "
            "and does not expose token secrets."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "get_agent_quickstart",
        "title": "Get Agent Quickstart",
        "description": (
            "Return machine-readable first steps for using Memexai MCP, including "
            "repo_context, saved-video discovery, timestamp search, briefs, overlay writes, "
            "and guarded ingestion. This does not require database access."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "get_repo_context_contract",
        "title": "Get Repo Context Contract",
        "description": (
            "Return the compact repo_context schema agents should populate using their own "
            "repo/filesystem/GitHub MCP tools before calling build_context_bundle or "
            "build_agent_brief. This does not read or store repository data."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "get_repo_context_workflow",
        "title": "Get Repo Context Workflow",
        "description": (
            "Return the machine-readable workflow for collecting caller-supplied "
            "repo_context with the agent's own repo/filesystem/GitHub MCP tools, "
            "including readiness gates and the collect_repo_context expected output. "
            "This does not read or store repository data."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "validate_repo_context",
        "title": "Validate Repo Context",
        "description": (
            "Validate and normalize caller-supplied repo_context before using it with "
            "build_context_bundle or build_agent_brief. This does not store repo data."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_context": repo_context_json_schema(),
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "get_video_context",
        "title": "Get Video Context",
        "description": (
            "Read source-derived transcript lines, chunks, concepts, edges, and artifacts "
            "for a video in the current user's library. Prefer get_video_knowledge_map, "
            "search_video_moments/search_transcript_text with youtube_video_id, or "
            "get_transcript_window before requesting full transcript context."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "youtube_video_id": {
                    "type": "string",
                    "description": "The YouTube video ID to inspect.",
                },
                "video_id": {
                    "type": "string",
                    "description": "Alias for youtube_video_id.",
                },
                "include_transcript": {
                    "type": "boolean",
                    "default": False,
                    "description": (
                        "When false, return concepts/artifacts and omit transcript lines/chunks. "
                        "Set true only for deeper source inspection."
                    ),
                },
                **PROJECT_SCOPE_TOOL_PROPERTIES,
                **BUDGET_TOOL_PROPERTIES,
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "get_transcript_window",
        "title": "Get Transcript Window",
        "description": (
            "Return a bounded transcript slice for one saved video between start_seconds "
            "and end_seconds. Use this after search_video_moments, search_transcript_text, "
            "or get_video_knowledge_map identifies the relevant timestamp; avoid pulling "
            "the full transcript for local grepping."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "youtube_video_id": {
                    "type": "string",
                    "description": "The YouTube video ID to inspect.",
                },
                "video_id": {
                    "type": "string",
                    "description": "Alias for youtube_video_id.",
                },
                "start_seconds": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 86400,
                    "default": 0,
                },
                "end_seconds": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 86400,
                    "description": "Exclusive end of the transcript window in seconds.",
                },
                **PROJECT_SCOPE_TOOL_PROPERTIES,
                **BUDGET_TOOL_PROPERTIES,
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "list_agent_notes",
        "title": "List Agent Notes",
        "description": "Read recent notes from the user's personal context overlay.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 50,
                }
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "add_context_note",
        "title": "Add Context Note",
        "description": (
            "Write a user-scoped agent note in the personal overlay. This never mutates "
            "source transcripts, videos, or generated source concepts."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "source_refs": {
                    "type": "array",
                    "items": {"type": "object", "additionalProperties": True},
                    "default": [],
                },
                "tags": {"type": "array", "items": {"type": "string"}, "default": []},
                "created_by_client": {"type": "string"},
            },
            "required": ["content"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "upsert_personal_concept",
        "title": "Upsert Personal Concept",
        "description": (
            "Create or update a user-specific concept in the personal overlay, with optional "
            "citations back to source video context."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "summary": {"type": "string", "default": ""},
                "source_refs": {
                    "type": "array",
                    "items": {"type": "object", "additionalProperties": True},
                    "default": [],
                },
                "status": {
                    "type": "string",
                    "enum": ["active", "learning", "applied", "ignored", "archived"],
                    "default": "active",
                },
                "created_by_client": {"type": "string"},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    },
    {
        "name": "build_context_bundle",
        "title": "Build Context Bundle",
        "description": (
            "Build an agent-friendly bundle from the user's personal overlay and optional "
            "repo context supplied by the calling agent."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "repo_context": repo_context_json_schema(),
                "category_filters": {
                    "type": "object",
                    "additionalProperties": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ]
                    },
                    "description": (
                        "Optional source-label filters such as "
                        '{"task_fit":["product spec"],"tool":["MCP"]}. '
                        "Values within a facet are OR; facets are AND."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 20,
                    "default": 8,
                },
                **BUDGET_TOOL_PROPERTIES,
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "build_agent_brief",
        "title": "Build Agent Brief",
        "description": (
            "Build a spec/prompt-oriented brief from saved video knowledge, personal overlay, "
            "and optional repo context supplied by the calling agent."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "repo_context": repo_context_json_schema(),
                "category_filters": {
                    "type": "object",
                    "additionalProperties": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ]
                    },
                    "description": (
                        "Optional source-label filters such as "
                        '{"task_fit":["implementation plan"],"difficulty":["advanced"]}. '
                        "Values within a facet are OR; facets are AND."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 20,
                    "default": 8,
                },
                **BUDGET_TOOL_PROPERTIES,
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "create_project",
        "title": "Create Project",
        "description": (
            "Create a user-owned Memexai project scope that can group saved videos, "
            "playlist capture sources, and project-scoped retrieval. Requires project:write."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Human-readable project name requested by the user.",
                },
                "description": {
                    "type": "string",
                    "description": "Optional short project description.",
                },
                "metadata": {
                    "type": "object",
                    "description": "Optional structured project metadata.",
                    "additionalProperties": True,
                },
                "created_by_client": {
                    "type": "string",
                    "description": "Optional agent/client name recorded in project metadata.",
                },
            },
            "required": ["name"],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "openWorldHint": False,
        },
    },
    {
        "name": "link_youtube_playlist_capture_source",
        "title": "Link YouTube Playlist To Project",
        "description": (
            "Create a YouTube playlist capture source and attach it to an existing "
            "user-owned project. Requires capture:write."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "playlist_url": {
                    "type": "string",
                    "description": "YouTube playlist URL to use as a standing capture source.",
                },
                "title": {
                    "type": "string",
                    "description": "Optional display title for the capture source.",
                },
                "project_id": {
                    "type": "string",
                    "description": "Project id returned by list_projects or create_project.",
                },
                "project_slug": {
                    "type": "string",
                    "description": "Project slug returned by list_projects or create_project.",
                },
                "created_by_client": {
                    "type": "string",
                    "description": "Optional agent/client name recorded on the capture source.",
                },
            },
            "required": ["playlist_url"],
            "anyOf": [{"required": ["project_id"]}, {"required": ["project_slug"]}],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "openWorldHint": False,
        },
    },
    {
        "name": "sync_capture_source",
        "title": "Sync Linked YouTube Capture Source",
        "description": (
            "Preview or queue ingestion for a YouTube playlist capture source already linked "
            "to the current user's Memexai project/library. Requires capture:write."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "capture_source_id": {
                    "type": "string",
                    "description": "User-owned capture source id from list_capture_sources.",
                },
                "max_jobs": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "default": 0,
                    "description": (
                        "0 previews pending videos without queueing. A positive value queues "
                        "that many ingestion jobs after explicit confirmation."
                    ),
                },
                "allow_queue": {
                    "type": "boolean",
                    "default": False,
                    "description": "Must be true to queue ingestion jobs.",
                },
                "confirmed_queue_count": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": (
                        "Must equal max_jobs when queueing, after the agent shows the user "
                        "the previewed queue count."
                    ),
                },
                "created_by_client": {
                    "type": "string",
                    "description": "Optional agent/client name recorded on the workflow.",
                },
            },
            "required": ["capture_source_id"],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "openWorldHint": False,
        },
    },
    {
        "name": "queue_youtube_ingestion",
        "title": "Queue YouTube Ingestion",
        "description": (
            "Submit a YouTube video, playlist, channel, or Shorts URL from an agent chat "
            "session into the current user's hosted ingestion queue. Requires ingest:write."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "YouTube URL the user or agent wants indexed.",
                },
                "allow_bulk": {
                    "type": "boolean",
                    "default": False,
                    "description": (
                        "Required for playlist or channel URLs after explicit user approval. "
                        "Single-video and Shorts URLs do not need this."
                    ),
                },
                "created_by_client": {
                    "type": "string",
                    "description": "Optional agent/client name for the ingestion job event.",
                },
                "digest_depth": {
                    "type": "string",
                    "enum": list(DIGEST_DEPTH_VALUES),
                    "default": DEFAULT_DIGEST_DEPTH,
                    "description": (
                        "How much transcript-derived source knowledge to generate: none stores "
                        "only transcript/search rows; basic creates compact labels/concepts/TLDR; "
                        "standard creates labels, concepts, edges, TLDR, and source report; deep "
                        "uses a larger transcript/output budget."
                    ),
                },
                "project_id": {
                    "type": "string",
                    "description": (
                        "Optional user-owned project id for single-video URL ingestion. "
                        "Bulk playlist/channel project targeting must use sync_capture_source."
                    ),
                },
                "project_slug": {
                    "type": "string",
                    "description": (
                        "Optional user-owned project slug for single-video URL ingestion. "
                        "Bulk playlist/channel project targeting must use sync_capture_source."
                    ),
                },
            },
            "required": ["url"],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "openWorldHint": True,
        },
    },
]

PROMPTS = [
    {
        "name": "retrieve_video_insight",
        "title": "Retrieve Video Insight",
        "description": (
            "Use Memexai's proven retrieval path for a user question, especially when "
            "the user names a specific saved video."
        ),
        "arguments": [
            {
                "name": "question",
                "description": "The user's question about saved video context.",
                "required": True,
            },
            {
                "name": "video_id",
                "description": "Optional YouTube video ID if the user already selected one.",
                "required": False,
            },
            {
                "name": "project_id",
                "description": "Optional Memexai project ID for project-scoped retrieval.",
                "required": False,
            },
        ],
    },
    {
        "name": "source_report_from_saved_video",
        "title": "Source Report From Saved Video",
        "description": (
            "Use saved video context to produce a robust TLDR, source report, questions, "
            "and action items with timestamp citations."
        ),
        "arguments": [
            {
                "name": "topic",
                "description": "Learning topic or question to focus on.",
                "required": False,
            },
            {
                "name": "video_id",
                "description": "Optional YouTube video ID if the user already selected one.",
                "required": False,
            },
        ],
    },
    {
        "name": "repo_implementation_brief",
        "title": "Repo Implementation Brief",
        "description": (
            "Combine the caller's repo context with saved video knowledge to draft a "
            "product spec, implementation plan, or agent prompt."
        ),
        "arguments": [
            {
                "name": "query",
                "description": "The implementation goal or product question.",
                "required": True,
            },
            {
                "name": "repo_context_hint",
                "description": (
                    "Optional hint about repo files, symbols, locations, entrypoints, commands, "
                    "tests, features, or modules to inspect."
                ),
                "required": False,
            },
        ],
    },
    {
        "name": "collect_repo_context",
        "title": "Collect Repo Context",
        "description": (
            "Inspect the caller's repo with existing repo/filesystem/GitHub tools, build a "
            "compact repo_context payload, and validate readiness before any brief is requested."
        ),
        "arguments": [
            {
                "name": "implementation_goal",
                "description": "Optional implementation goal or product question to focus inspection.",
                "required": False,
            },
            {
                "name": "repo_context_hint",
                "description": (
                    "Optional hint about repo files, symbols, locations, entrypoints, commands, "
                    "tests, features, or modules to inspect."
                ),
                "required": False,
            },
        ],
    },
    {
        "name": "categorize_saved_video",
        "title": "Categorize Saved Video",
        "description": (
            "Inspect a saved video and produce agent-friendly labels such as topic, "
            "methods, tools, difficulty, and project applicability."
        ),
        "arguments": [
            {
                "name": "video_id",
                "description": "YouTube video ID to categorize.",
                "required": False,
            },
            {
                "name": "project_goal",
                "description": "Optional user or repo goal to tailor labels around.",
                "required": False,
            },
        ],
    },
    {
        "name": "capture_personal_context",
        "title": "Capture Personal Context",
        "description": (
            "Save durable user-specific takeaways as overlay notes or personal concepts "
            "without mutating source video context."
        ),
        "arguments": [
            {
                "name": "takeaway",
                "description": "The durable insight or preference to preserve.",
                "required": True,
            }
        ],
    },
]


def _study_guide_prompt(arguments: dict) -> dict:
    topic = _prompt_arg(arguments, "topic", "the user's current learning goal")
    video_id = _prompt_arg(arguments, "video_id", "")
    video_instruction = (
        f"Start with context://video/{video_id} or get_video_context for video {video_id}."
        if video_id
        else "Start with resources/list or list_video_library to choose the best saved video."
    )
    return _prompt_response(
        "Create a cited source report from saved video knowledge.",
        "\n".join(
            [
                "Use Memexai as the user's saved-video knowledge base.",
                video_instruction,
                f"Focus the guide on: {topic}.",
                "Use search_video_moments for exact timestamp evidence before making specific claims.",
                "Return a concise TLDR, a structured source report, key concepts, questions, and action items.",
                "Cite timestamped source_refs or relevantClips for claims that came from a video.",
                "If the user learns something durable, offer to save it with add_context_note or upsert_personal_concept.",
            ]
        ),
    )


def _retrieve_video_insight_prompt(arguments: dict) -> dict:
    question = _required_prompt_arg(arguments, "question")
    video_id = _prompt_arg(arguments, "video_id", "")
    project_id = _prompt_arg(arguments, "project_id", "")
    scope_instruction = (
        f"Known video: pass youtube_video_id={video_id} to transcript and moment search tools."
        if video_id
        else "If the user named a video but not an ID, call list_video_library or search_video_concepts to identify the video first."
    )
    project_instruction = (
        f"Project scope: pass project_id={project_id} where supported."
        if project_id
        else "If the user named a project, call list_projects and pass the selected project_id/project_slug."
    )
    return _prompt_response(
        "Retrieve a saved-video insight with bounded MCP calls.",
        "\n".join(
            [
                "Use Memexai as a saved-video knowledge MCP. Keep retrieval bounded and source-backed.",
                f"Question: {question}",
                scope_instruction,
                project_instruction,
                "Preferred path:",
                "1. Call search_video_concepts with retrieval_mode=hybrid for source reports, sections, concepts, aliases, and timestamp refs.",
                "2. For a candidate video, call get_video_knowledge_map to inspect sections and timestamp-backed concepts.",
                "3. For exact phrases, call search_transcript_text with retrieval_mode=keyword; pass youtube_video_id/video_id for known-video questions.",
                "4. For timestamp evidence, call search_video_moments with retrieval_mode=hybrid; pass youtube_video_id/video_id for known-video questions.",
                "5. If a timestamp window needs more direct evidence, call get_transcript_window instead of get_video_context/include_transcript.",
                "6. Use get_video_context/include_transcript only when the map, search results, and transcript window are insufficient.",
                "Return a concise answer with timestamps and mention uncertainty when evidence is sparse.",
            ]
        ),
    )


def _repo_implementation_prompt(arguments: dict) -> dict:
    query = _required_prompt_arg(arguments, "query")
    repo_hint = _prompt_arg(
        arguments,
        "repo_context_hint",
        "the relevant repo files, symbols, locations, and features",
    )
    return _prompt_response(
        "Turn saved video knowledge into a repo-aware implementation brief.",
        "\n".join(
            [
                "Use the calling agent's existing repo, filesystem, GitHub, or code-index tools to inspect repo context first.",
                f"Implementation goal: {query}.",
                f"Repo context to inspect: {repo_hint}.",
                "Build a compact repo_context object with repo name, files, symbols, locations, entrypoints, dependencies, commands, tests, features, and constraints.",
                "Call validate_repo_context with the draft repo_context before implementation planning.",
                "For implementation plans, prefer readiness.level = implementation_ready.",
                "If readiness.level is partial, follow readiness.suggestedAgentNextSteps with your existing repo tools, update repo_context, and validate again.",
                "Call build_agent_brief with the query and repo_context after validation; use its repoContextValidation and suggestedNextActions to decide whether more repo inspection is needed.",
                "Use the returned keyConcepts, sourceHighlights, implementationGuidance, and citations to draft the plan.",
                "Do not require the user to connect GitHub inside Memexai when the caller already has repo MCP access.",
                "Save only durable user-specific takeaways with add_context_note or upsert_personal_concept.",
            ]
        ),
    )


def _collect_repo_context_prompt(arguments: dict) -> dict:
    goal = _prompt_arg(arguments, "implementation_goal", "the user's likely implementation goal")
    repo_hint = _prompt_arg(
        arguments,
        "repo_context_hint",
        "the relevant repo files, symbols, locations, and features",
    )
    expected_output = json.dumps(
        repo_context_workflow_contract()["collectPromptExpectedOutput"],
        ensure_ascii=False,
        indent=2,
    )
    return _prompt_response(
        "Collect and validate caller-supplied repo_context.",
        "\n".join(
            [
                "Use the calling agent's existing repo, filesystem, GitHub, or code-index tools; do not ask the user to connect GitHub inside Memexai.",
                f"Focus inspection on: {goal}.",
                f"Repo context hint: {repo_hint}.",
                "Call get_repo_context_contract or read context://repo-context-contract for the current schema.",
                "Inspect relevant files, symbols, locations, modules, entrypoints, dependencies, commands, tests, deployment facts, active changes, features, and constraints.",
                "Build a compact repo_context object with references and facts, not file dumps.",
                "Call validate_repo_context with the draft repo_context.",
                "If readiness.level is partial, follow readiness.suggestedAgentNextSteps with your repo tools, update repo_context, and validate again.",
                "Return the final normalized repo_context, readiness.level, missingSignals, suggestedAgentNextSteps, open_questions, and next_mcp_call from validate_repo_context.",
                "Expected output shape:",
                expected_output,
                "Do not call build_agent_brief unless the user specifically asks for the implementation brief next.",
            ]
        ),
    )


def _categorize_saved_video_prompt(arguments: dict) -> dict:
    video_id = _prompt_arg(arguments, "video_id", "")
    project_goal = _prompt_arg(arguments, "project_goal", "future agent retrieval")
    source_instruction = (
        f"Read context://video/{video_id} or call get_video_context for {video_id}."
        if video_id
        else "Use resources/list or list_video_library to choose a saved video before categorizing."
    )
    return _prompt_response(
        "Categorize a saved video for future agent retrieval.",
        "\n".join(
            [
                source_instruction,
                f"Tailor categories toward: {project_goal}.",
                "Create labels for topic, domain, methods, algorithms, tools, entities, difficulty, maturity, pitfalls, and implementation fit.",
                "Prefer sourceConcepts and knowledgeArtifacts over freeform guessing.",
                "Use timestamp citations for the labels that depend on transcript evidence.",
                "If labels are personalized to the user's work, save them as personal concepts or an agent note.",
                "Never rewrite source transcripts, source concepts, source edges, or system-generated artifacts.",
            ]
        ),
    )


def _capture_personal_context_prompt(arguments: dict) -> dict:
    takeaway = _required_prompt_arg(arguments, "takeaway")
    return _prompt_response(
        "Capture durable personal context without mutating source data.",
        "\n".join(
            [
                f"Durable takeaway: {takeaway}.",
                "Decide whether this belongs as an agent note, a personal concept, or both.",
                "Use add_context_note for narrative notes, decisions, preferences, and project-specific memories.",
                "Use upsert_personal_concept for reusable concepts the user is learning or applying.",
                "Include source_refs when the takeaway came from a saved video or timestamped clip.",
                "Do not edit source video context; source context is read-only.",
            ]
        ),
    )


def _prompt_arg(arguments: dict, name: str, default: str) -> str:
    value = arguments.get(name)
    if value is None:
        return default
    if not isinstance(value, str):
        raise McpAdapterError(INVALID_PARAMS, f"{name} must be a string")
    return value.strip() or default


def _required_prompt_arg(arguments: dict, name: str) -> str:
    value = arguments.get(name)
    if not isinstance(value, str) or not value.strip():
        raise McpAdapterError(INVALID_PARAMS, f"{name} must be a non-empty string")
    return value.strip()


PROMPT_BUILDERS = {
    "retrieve_video_insight": _retrieve_video_insight_prompt,
    "source_report_from_saved_video": _study_guide_prompt,
    "study_guide_from_saved_video": _study_guide_prompt,
    "repo_implementation_brief": _repo_implementation_prompt,
    "collect_repo_context": _collect_repo_context_prompt,
    "categorize_saved_video": _categorize_saved_video_prompt,
    "capture_personal_context": _capture_personal_context_prompt,
}

TOOL_HANDLERS = {
    "list_video_library": _list_video_library_tool,
    "list_projects": _list_projects_tool,
    "get_project_context_map": _get_project_context_map_tool,
    "get_library_source_graph": _get_library_source_graph_tool,
    "search_library_components": _search_library_components_tool,
    "list_capture_sources": _list_capture_sources_tool,
    "list_context_categories": _list_context_categories_tool,
    "list_ingestion_jobs": _list_ingestion_jobs_tool,
    "get_ingestion_job": _get_ingestion_job_tool,
    "list_workflow_runs": _list_workflow_runs_tool,
    "get_workflow_run": _get_workflow_run_tool,
    "get_mcp_session": _get_mcp_session_tool,
    "get_agent_quickstart": _get_agent_quickstart_tool,
    "get_brain_sync_contract": _get_brain_sync_contract_tool,
    "export_brain_digest": _export_brain_digest_tool,
    "get_repo_context_contract": _get_repo_context_contract_tool,
    "get_repo_context_workflow": _get_repo_context_workflow_tool,
    "validate_repo_context": _validate_repo_context_tool,
    "search_video_concepts": _search_video_concepts_tool,
    "get_video_knowledge_map": _get_video_knowledge_map_tool,
    "search_transcript_text": _search_transcript_text_tool,
    "search_video_moments": _search_video_moments_tool,
    "get_video_context": _get_video_context_tool,
    "get_transcript_window": _get_transcript_window_tool,
    "list_agent_notes": _list_agent_notes_tool,
    "add_context_note": _add_context_note_tool,
    "upsert_personal_concept": _upsert_personal_concept_tool,
    "create_project": _create_project_tool,
    "link_youtube_playlist_capture_source": _link_youtube_playlist_capture_source_tool,
    "build_context_bundle": _build_context_bundle_tool,
    "build_agent_brief": _build_agent_brief_tool,
    "sync_capture_source": _sync_capture_source_tool,
    "queue_youtube_ingestion": _queue_youtube_ingestion_tool,
}
