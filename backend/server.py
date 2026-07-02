"""
server.py - FastAPI Backend for Memexai

Provides REST API for the React frontend:
- GET  /              - Health check (public)
- GET  /api/library   - User's indexed channels & videos (auth)
- POST /api/ingest    - Index a YouTube channel (SSE stream, auth)
- POST /api/search    - Search indexed content (auth)
- GET  /api/transcript/{video_id} - Download SRT transcript (auth)
- DELETE /api/video/{video_id}    - Remove a video (auth)
- GET  /api/usage     - Quota status (auth)
- GET  /api/profile   - User profile (auth)
- PUT  /api/settings/key   - Save Gemini API key (auth)
- DELETE /api/settings/key - Remove Gemini API key (auth)

Run with: python server.py
Or: uvicorn server:app --reload --host 0.0.0.0 --port 8000

Updated: 2026-02-28
"""

import asyncio
import hmac
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from json import JSONDecodeError
from typing import AsyncGenerator
from urllib.parse import urlencode

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

try:
    from .billing import (
        construct_stripe_event,
        create_checkout_session,
        create_portal_session,
        describe_promo_trial,
        process_stripe_event,
        resolve_user_entitlements,
    )
    from .capture import (
        build_capture_sources_context,
        create_playlist_capture_source,
        delete_capture_source,
    )
    from .capture_workflows import run_capture_sync_workflow
    from .config import (
        NO_AUTH,
        SUPABASE_AUTH,
        allow_user_keys,
        get_allowed_origins,
        get_api_key_mode,
        get_auth_mode,
        get_public_app_url,
        get_public_config,
        get_server_api_key,
        get_workflow_internal_secret,
    )
    from .context import (
        build_context_bundle,
        build_library_source_graph,
        build_project_context_map,
        create_agent_note,
        get_library_artifact,
        get_video_context,
        list_agent_notes,
        search_library_components,
        upsert_personal_concept,
    )
    from .db import (
        check_search_quota,
        encrypt_api_key,
        get_current_user,
        get_supabase,
        get_user_profile,
        increment_search_usage,
    )
    from .digest_depth import DEFAULT_DIGEST_DEPTH, normalize_digest_depth
    from .hosted_ingestion import process_hosted_ingestion_job, resolve_api_key
    from .ingestion_costs import build_ingestion_cost_estimate
    from .jobs import (
        classify_ingestion_event_level,
        clear_ingestion_job_history,
        count_active_ingestion_jobs,
        create_ingestion_job,
        extract_ingestion_event_reason,
        failed_ingestion_fields,
        get_ingestion_job,
        list_ingestion_jobs,
        record_ingestion_job_event,
        summarize_ingestion_messages,
        update_ingestion_job,
    )
    from .mcp_adapter import (
        PROMPTS,
        TOOLS,
        describe_brain_sync_contract,
        handle_mcp_request,
        mcp_payload_requires_supabase,
        parse_error_response,
    )
    from .mcp_oauth import (
        authorization_server_metadata,
        create_authorization_redirect,
        exchange_authorization_code,
        parse_oauth_token_body,
        protected_resource_metadata,
        register_oauth_client,
        validate_authorization_request,
    )
    from .mcp_tokens import (
        MCP_AUTH_PREFIX,
        authenticate_mcp_token,
        create_mcp_token,
        list_mcp_tokens,
        revoke_mcp_token,
    )
    from .onboarding import build_onboarding_status, build_onboarding_update
    from .projects import (
        add_videos_to_project,
        create_project,
        delete_project,
        list_projects,
        remove_video_from_project,
        set_capture_source_project,
        update_project,
    )
    from .queue_dispatch import dispatch_ingestion_job
    from .rag import _get_embeddings as get_query_embeddings
    from .repo_context import repo_context_workflow_contract, validate_repo_context
    from .storage import (
        LOCAL_USER_ID,
        delete_video,
        get_library,
        get_video_transcript,
        ingest_url,
        is_supabase_mode,
        search,
        search_transcript_text,
    )
    from .workflows import (
        get_workflow_instance,
        list_workflow_definitions,
        list_workflow_instances,
    )
    from .youtube_oauth import (
        disconnect_youtube_oauth,
        get_youtube_oauth_status,
        upsert_youtube_oauth_connection,
    )
    from .youtube_utils import detect_url_type
except ImportError:
    from billing import (
        construct_stripe_event,
        create_checkout_session,
        create_portal_session,
        describe_promo_trial,
        process_stripe_event,
        resolve_user_entitlements,
    )
    from capture import (
        build_capture_sources_context,
        create_playlist_capture_source,
        delete_capture_source,
    )
    from capture_workflows import run_capture_sync_workflow
    from config import (
        NO_AUTH,
        SUPABASE_AUTH,
        allow_user_keys,
        get_allowed_origins,
        get_api_key_mode,
        get_auth_mode,
        get_public_app_url,
        get_public_config,
        get_server_api_key,
        get_workflow_internal_secret,
    )
    from context import (
        build_context_bundle,
        build_library_source_graph,
        build_project_context_map,
        create_agent_note,
        get_library_artifact,
        get_video_context,
        list_agent_notes,
        search_library_components,
        upsert_personal_concept,
    )
    from db import (
        check_search_quota,
        encrypt_api_key,
        get_current_user,
        get_supabase,
        get_user_profile,
        increment_search_usage,
    )
    from digest_depth import DEFAULT_DIGEST_DEPTH, normalize_digest_depth
    from hosted_ingestion import process_hosted_ingestion_job, resolve_api_key
    from ingestion_costs import build_ingestion_cost_estimate
    from jobs import (
        classify_ingestion_event_level,
        clear_ingestion_job_history,
        count_active_ingestion_jobs,
        create_ingestion_job,
        extract_ingestion_event_reason,
        failed_ingestion_fields,
        get_ingestion_job,
        list_ingestion_jobs,
        record_ingestion_job_event,
        summarize_ingestion_messages,
        update_ingestion_job,
    )
    from mcp_adapter import (
        PROMPTS,
        TOOLS,
        describe_brain_sync_contract,
        handle_mcp_request,
        mcp_payload_requires_supabase,
        parse_error_response,
    )
    from mcp_oauth import (
        authorization_server_metadata,
        create_authorization_redirect,
        exchange_authorization_code,
        parse_oauth_token_body,
        protected_resource_metadata,
        register_oauth_client,
        validate_authorization_request,
    )
    from mcp_tokens import (
        MCP_AUTH_PREFIX,
        authenticate_mcp_token,
        create_mcp_token,
        list_mcp_tokens,
        revoke_mcp_token,
    )
    from onboarding import build_onboarding_status, build_onboarding_update
    from projects import (
        add_videos_to_project,
        create_project,
        delete_project,
        list_projects,
        remove_video_from_project,
        set_capture_source_project,
        update_project,
    )
    from queue_dispatch import dispatch_ingestion_job
    from rag import _get_embeddings as get_query_embeddings
    from repo_context import repo_context_workflow_contract, validate_repo_context
    from storage import (
        LOCAL_USER_ID,
        delete_video,
        get_library,
        get_video_transcript,
        ingest_url,
        is_supabase_mode,
        search,
        search_transcript_text,
    )
    from workflows import (
        get_workflow_instance,
        list_workflow_definitions,
        list_workflow_instances,
    )
    from youtube_oauth import (
        disconnect_youtube_oauth,
        get_youtube_oauth_status,
        upsert_youtube_oauth_connection,
    )
    from youtube_utils import detect_url_type


# Pydantic models for request/response validation
class IngestRequest(BaseModel):
    url: str
    digest_depth: str = DEFAULT_DIGEST_DEPTH


class SearchRequest(BaseModel):
    query: str
    limit: int = 5  # Default to 5 results, frontend can override
    category_filters: dict | None = None
    retrieval_mode: str = "hybrid"
    project_id: str | None = None
    project_slug: str | None = None


class ProjectRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""
    metadata: dict = Field(default_factory=dict)


class ProjectUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    metadata: dict | None = None


class ProjectVideosRequest(BaseModel):
    video_ids: list[str] = Field(default_factory=list)
    youtube_video_ids: list[str] = Field(default_factory=list)
    added_source: str = "manual"


class CaptureSourceProjectRequest(BaseModel):
    project_id: str | None = None


class BillingCheckoutRequest(BaseModel):
    lookupKey: str = Field(..., min_length=1)
    promoCode: str | None = None


class ApiKeyRequest(BaseModel):
    api_key: str


class AgentNoteRequest(BaseModel):
    content: str
    source_refs: list[dict] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_by: str = "agent"
    created_by_client: str | None = None


class PersonalConceptRequest(BaseModel):
    name: str
    summary: str = ""
    source_refs: list[dict] = Field(default_factory=list)
    status: str = "active"
    created_by: str = "agent"
    created_by_client: str | None = None


class ContextBundleRequest(BaseModel):
    query: str
    repo_context: dict | None = None
    category_filters: dict | None = None
    limit: int = 8


class RepoContextValidationRequest(BaseModel):
    repo_context: dict | None = None


class CaptureSourceRequest(BaseModel):
    playlist_url: str
    title: str = ""
    project_id: str | None = None
    created_by: str = "user"
    created_by_client: str | None = None


class CaptureSourceSyncRequest(BaseModel):
    max_jobs: int = 1


class YoutubeOAuthConnectionRequest(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    expires_in: int | None = None
    expires_at: str | None = None
    scopes: list[str] | str = Field(default_factory=list)


class InternalWorkflowCaptureSyncRequest(BaseModel):
    user_id: str
    capture_source_id: str
    max_jobs: int = 1
    created_by_client: str | None = None


class McpTokenRequest(BaseModel):
    name: str = "MCP token"
    scopes: list[str] = Field(default_factory=lambda: ["context:read", "overlay:write"])


class McpOAuthClientRegistrationRequest(BaseModel):
    redirect_uris: list[str]
    client_name: str = "MCP client"
    client_uri: str | None = None
    logo_uri: str | None = None
    token_endpoint_auth_method: str = "none"  # noqa: S105 - OAuth public-client method.
    grant_types: list[str] = Field(default_factory=lambda: ["authorization_code"])
    response_types: list[str] = Field(default_factory=lambda: ["code"])


class McpOAuthApproveRequest(BaseModel):
    response_type: str
    client_id: str
    redirect_uri: str
    code_challenge: str
    code_challenge_method: str = "S256"
    scope: str = "context:read overlay:write"
    state: str | None = None
    resource: str | None = None


class OnboardingStatusUpdateRequest(BaseModel):
    onboarding_step: str | None = None
    onboarding_state: dict | None = None
    complete: bool = False
    skip: bool = False


async def stream_sync_generator(factory) -> AsyncGenerator[str, None]:
    """Bridge a blocking string generator into async streaming output."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[object] = asyncio.Queue()
    sentinel = object()

    def publish(item: object) -> None:
        asyncio.run_coroutine_threadsafe(queue.put(item), loop).result()

    def worker() -> None:
        try:
            for item in factory():
                publish(item)
        except Exception as exc:
            publish(exc)
        finally:
            publish(sentinel)

    threading.Thread(target=worker, daemon=True).start()

    while True:
        item = await queue.get()
        if item is sentinel:
            break
        if isinstance(item, Exception):
            raise item
        yield str(item)


# Lifespan handler (replaces deprecated on_startup/on_shutdown)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("[Memexai] Backend Starting...")
    print("   API Docs: http://localhost:8080/docs")
    print("   Health:   http://localhost:8080/")
    yield
    # Shutdown
    print("[Memexai] Backend Shutting Down...")


# Create FastAPI app
app = FastAPI(
    title="Memexai API",
    description="YouTube context engine powered by Gemini",
    version="2.0.0",
    lifespan=lifespan,
)

allowed_origins = get_allowed_origins()

# CORS middleware for frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials="*" not in allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------


@app.get("/")
async def health_check():
    """
    Health check endpoint.
    Frontend polls this to show "Backend Online" status.
    Also reports if server has API key configured.
    """
    public_config = get_public_config()
    return {
        "status": "ok",
        "message": "Memexai Backend is running",
        "hasApiKey": public_config.hasServerKey,
    }


@app.get("/api/config")
async def config_endpoint():
    """Return public runtime configuration used by the frontend."""
    return get_public_config().__dict__


def _public_base_url(request: Request) -> str:
    host = (
        request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    )
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    if scheme == "http" and (
        host.endswith(".workers.dev") or host.endswith(".pages.dev") or host.endswith("memexai.xyz")
    ):
        scheme = "https"
    if host:
        return f"{scheme}://{host}".rstrip("/")
    return str(request.base_url).rstrip("/")


def _mcp_agent_setup_bundle(base_url: str, token: str | None = None) -> dict:
    credential_env_var = "MEMEXAI_MCP_TOKEN"
    claude_setup_steps = [
        "Open Claude settings, then Customize > Connectors.",
        "Choose Add custom connector and paste the Memexai MCP URL.",
        "Name it Memexai, finish adding it, then click Connect.",
        "Sign in with Google, approve Memexai access, and enable the connector in the chat.",
    ]
    claude_initial_prompt = (
        "Use my Memexai connector. Start with get_mcp_session, then list_projects. "
        "If a project matches my task, open its project context map before searching "
        "source reports or transcript moments."
    )
    hermes_config = [
        "mcp_servers:",
        "  memexai:",
        f'    url: "{base_url}/mcp"',
        "    headers:",
        f'      Authorization: "Bearer ${{{credential_env_var}}}"',
        "    timeout: 180",
        "    connect_timeout: 30",
    ]
    codex_config = [
        "[mcp_servers.memexai]",
        f'url = "{base_url}/mcp"',
        f'bearer_token_env_var = "{credential_env_var}"',
        "startup_timeout_sec = 20",
        "tool_timeout_sec = 120",
    ]
    first_steps = [
        "Call get_mcp_session to confirm token scopes, owner context, and safe next calls.",
        "Call get_agent_quickstart or read context://agent-quickstart.",
        "If the user has a personal brain, call get_brain_sync_contract or read context://brain-sync-contract.",
        "Use export_brain_digest or read context://brain-digest to sync compact saved-video digests into a personal brain.",
        "Call list_projects or read context://projects to identify explicit project scopes.",
        "Call get_project_context_map when a project matches the user's task.",
        "If granted project:write, call create_project only when the user asks for a new project scope.",
        "If granted capture:write, call link_youtube_playlist_capture_source to attach a user-provided playlist URL to a project.",
        "Use sync_capture_source with max_jobs=0 to preview playlist videos, then queue only after explicit confirmation.",
        "Call list_video_library or read context://library before searching; pass project_id/project_slug when scoped.",
        "Call list_context_categories or read context://categories when you need filters.",
        "Use search_video_concepts with retrieval_mode=hybrid for concepts, TLDRs, source reports, report sections, aliases, tools, and pitfalls before pulling timestamp clips; pass project_id/project_slug when scoped.",
        "Call get_video_knowledge_map for promising videos to inspect report sections, concepts, claims, decisions, timeline cues, and timestamp refs.",
        "Use search_transcript_text for exact phrases, names, acronyms, and product terms when keyword precision matters; pass youtube_video_id/video_id for known-video questions.",
        "Use get_transcript_window for direct evidence around a known timestamp before pulling full transcript context.",
        "Use get_repo_context_workflow or read context://repo-context-workflow for the repo-via-MCP collection flow.",
        "Use get_repo_context_contract or read context://repo-context-contract for the expected repo_context shape.",
        "Optional: use prompts/get collect_repo_context to gather repo_context with the agent's own repo MCP.",
        "Call validate_repo_context and follow readiness.suggestedAgentNextSteps before implementation planning.",
        "Use search_video_moments with retrieval_mode=hybrid for timestamp evidence and inspect accessScope/accessReason; pass youtube_video_id/video_id for known-video questions.",
        "Call build_agent_brief with a query and validated repo_context.",
    ]
    setup = {
        "serverName": "memexai",
        "mcpEndpoint": f"{base_url}/mcp",
        "manifestUrl": f"{base_url}/mcp.json",
        "agentGuideUrl": f"{base_url}/llms.txt",
        "fullAgentGuideUrl": f"{base_url}/llms-full.txt",
        "claudeCustomConnector": {
            "name": "Memexai",
            "url": f"{base_url}/mcp",
            "setupSteps": claude_setup_steps,
            "initialPrompt": claude_initial_prompt,
            "authMode": "Remote MCP OAuth through Google sign-in and Memexai approval.",
            "fallback": (
                "If the Claude client cannot complete OAuth, create a scoped MCP token in "
                "Settings and use a client that supports bearer-token MCP headers."
            ),
        },
        "tokenEnvironmentVariable": credential_env_var,
        "hermesConfig": "\n".join(hermes_config),
        "codexConfig": "\n".join(codex_config),
        "codexSetupNote": (
            "Add codexConfig to ~/.codex/config.toml and set MEMEXAI_MCP_TOKEN in "
            "the environment where Codex runs. Codex usage stays under the user's own "
            "Codex/ChatGPT or API-key authentication; Memexai does not spend a "
            "user's Codex subscription from hosted servers."
        ),
        "firstSteps": first_steps,
        "firstCalls": [
            {
                "tool": "get_mcp_session",
                "purpose": "Confirm effective scopes and the MCP token owner's context.",
            },
            {
                "tool": "get_agent_quickstart",
                "purpose": "Load the recommended workflow for the connected agent.",
            },
            {
                "tool": "get_brain_sync_contract",
                "purpose": "Learn how to sync compact saved-video knowledge into an external personal brain.",
            },
            {
                "tool": "export_brain_digest",
                "purpose": "Pull a compact incremental digest for an external personal brain without raw transcripts.",
            },
            {
                "tool": "list_video_library",
                "purpose": "Inspect only the videos granted to this user before searching.",
            },
            {
                "tool": "list_projects",
                "purpose": "Inspect user-created project scopes before scoped retrieval.",
            },
            {
                "tool": "get_project_context_map",
                "purpose": "Inspect a project-scoped video/context map before broader library search.",
            },
            {
                "tool": "create_project",
                "purpose": "Create a new user-owned project scope only after explicit user request.",
            },
            {
                "tool": "link_youtube_playlist_capture_source",
                "purpose": "Attach a user-provided YouTube playlist to an existing project as a standing capture source.",
            },
            {
                "tool": "sync_capture_source",
                "purpose": "Preview and, after confirmation, queue ingestion for a linked playlist capture source.",
            },
            {
                "tool": "list_context_categories",
                "purpose": "Discover category_filters for narrower retrieval.",
            },
            {
                "tool": "search_transcript_text",
                "purpose": "Find exact names, acronyms, titles, and phrases without embedding or LLM spend.",
            },
            {
                "tool": "search_video_concepts",
                "purpose": "Hybrid-search source concepts, reports, report sections, aliases, and timestamp refs without an LLM call.",
            },
            {
                "tool": "get_video_knowledge_map",
                "purpose": "Inspect a candidate video's navigable source-report map before pulling transcript clips.",
            },
            {
                "tool": "search_video_moments",
                "purpose": "Retrieve hybrid, semantic, or keyword timestamped evidence from user-granted videos.",
            },
        ],
        "accessModel": {
            "searchScope": "current_user_grants",
            "globalSearch": "not_exposed",
            "visibilityGrants": ["user_videos", "user_channels"],
            "canonicalStorage": "Videos and transcript-derived context are stored once per YouTube video.",
            "dedupeBehavior": (
                "Already-indexed videos are attached to the user's library with an access grant "
                "instead of re-embedding duplicate chunks."
            ),
            "agentInstruction": (
                "Do not treat shared canonical rows as globally searchable. Use only results "
                "returned through the current MCP token and preserve accessScope/accessReason "
                "when explaining provenance. Project scope is explicit per MCP call; do not "
                "assume the web UI's current project."
            ),
        },
    }
    if token:
        setup["oneTimeCredential"] = {
            "bearerToken": token,
            "envLine": f"{credential_env_var}={token}",
            "codexEnvLine": f"{credential_env_var}={token}",
            "hermesConfig": "\n".join(
                line.replace(f"${{{credential_env_var}}}", token) for line in hermes_config
            ),
        }
    return setup


def _public_mcp_manifest(base_url: str) -> dict:
    tool_summaries = [
        {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "readOnly": bool(tool.get("annotations", {}).get("readOnlyHint")),
        }
        for tool in TOOLS
    ]
    prompt_summaries = [
        {
            "name": prompt["name"],
            "description": prompt.get("description", ""),
        }
        for prompt in PROMPTS
    ]
    return {
        "name": "memexai-context",
        "title": "Memexai Context",
        "version": "0.1.0",
        "description": (
            "Read-only saved-video context MCP with writable personal overlays, "
            "optional scoped YouTube ingestion, project creation, and playlist capture sync."
        ),
        "transport": {
            "type": "streamable-http",
            "url": f"{base_url}/mcp",
            "protocol": "json-rpc-2.0",
        },
        "auth": {
            "type": "oauth_or_bearer",
            "preferred": "oauth_custom_connector",
            "setup": (
                "Preferred: add the Memexai remote MCP URL as a Claude custom connector "
                "and complete OAuth with Google sign-in plus Memexai approval. Fallback: "
                "create an MCP token in Settings under Agent access, then call "
                "get_mcp_session after connecting to confirm effective scopes."
            ),
            "setupBundle": _mcp_agent_setup_bundle(base_url),
            "oauth": {
                "mcpEndpoint": f"{base_url}/mcp",
                "protectedResourceMetadata": f"{base_url}/.well-known/oauth-protected-resource/mcp",
                "authorizationServerMetadata": f"{base_url}/.well-known/oauth-authorization-server",
                "clientRegistration": f"{base_url}/oauth/register",
                "authorization": f"{base_url}/oauth/authorize",
                "token": f"{base_url}/oauth/token",
                "defaultScopes": ["context:read", "overlay:write"],
            },
            "tokenManagement": {
                "list": f"{base_url}/api/mcp/tokens",
                "create": f"{base_url}/api/mcp/tokens",
                "revoke": f"{base_url}/api/mcp/tokens/{{token_id}}",
            },
            "scopes": [
                {
                    "name": "context:read",
                    "description": "Read saved video context, categories, resources, and briefs.",
                },
                {
                    "name": "overlay:write",
                    "description": "Write personal notes and personalized concepts only.",
                },
                {
                    "name": "ingest:write",
                    "description": (
                        "Opt-in scope to queue YouTube links for hosted ingestion. "
                        "Playlist and channel URLs require allow_bulk=true."
                    ),
                },
                {
                    "name": "capture:write",
                    "description": (
                        "Opt-in scope to link YouTube playlist capture sources and sync "
                        "already-linked capture sources with explicit queue confirmation."
                    ),
                },
                {
                    "name": "project:write",
                    "description": "Opt-in scope to create user-owned project scopes.",
                },
            ],
        },
        "resources": [
            "context://agent-quickstart",
            "context://brain-sync-contract",
            "context://brain-digest",
            "context://projects",
            "context://project/{projectId}",
            "context://library",
            "context://repo-context-contract",
            "context://repo-context-workflow",
            "context://capture-sources",
            "context://categories",
            "context://notes",
            "context://workflows",
            "context://workflow/{workflowInstanceId}",
            "context://video/{videoId}",
        ],
        "accessModel": {
            "canonicalStorage": (
                "YouTube videos, transcript chunks, transcript lines, source labels, "
                "source concepts, source edges, and generated artifacts are stored once "
                "per source video."
            ),
            "visibilityGrants": ["user_videos", "user_channels"],
            "searchScope": (
                "Search and context tools return only videos granted to the current "
                "user or MCP token owner."
            ),
            "searchProvenanceFields": ["accessScope", "accessSource", "accessReason"],
            "searchModes": {
                "default": "current_user_grants",
                "globalSearch": "not_exposed",
                "sharedCanonicalRows": (
                    "Shared storage can be reused only after a user_videos or "
                    "user_channels grant makes the video visible to that user."
                ),
            },
            "dedupeBehavior": (
                "If a user ingests an already-indexed YouTube video, Memexai "
                "grants access instead of re-embedding duplicate chunks."
            ),
        },
        "retrievalCapabilities": {
            "current": [
                "hybrid vector plus keyword/title retrieval over transcript chunks",
                "semantic pgvector search over transcript chunks",
                "keyword full-text search over transcript chunks and video titles",
                "user-scoped access filtering through video/channel grants",
                "explicit project-scoped retrieval through project_id or project_slug",
                "category_filters over source-label facets",
                "read-only source context resources",
                "personal overlay notes and concepts",
            ],
            "planned": [
                "hybrid full-text plus vector retrieval",
                "reciprocal-rank fusion",
                "reranking",
                "knowledge-graph neighbor expansion",
                "topic clustering for library navigation",
            ],
            "categoryFilterSyntax": {
                "shape": {"category_filters": {"facet_name": ["label one", "label two"]}},
                "logic": "OR within a facet, AND across facets",
                "discovery": ["context://categories", "list_context_categories"],
            },
        },
        "storageDecision": {
            "hostedDefault": "supabase_postgres_pgvector",
            "userSelectableDatabase": "not_for_normal_hosted_onboarding",
            "reason": (
                "Supabase keeps auth, RLS-style permission joins, relational source "
                "knowledge, overlay data, usage logs, workflow state, and vectors in "
                "one system. Agent clients should use MCP instead of choosing a DB."
            ),
            "futureOptions": [
                "data export",
                "enterprise BYO storage",
                "optional vector sidecar if pgvector becomes a proven bottleneck",
            ],
        },
        "tools": tool_summaries,
        "prompts": prompt_summaries,
        "repoContextWorkflow": repo_context_workflow_contract(),
        "brainSync": describe_brain_sync_contract(),
        "agentOnboarding": {
            "preferred": "oauth_custom_connector",
            "sessionTool": "get_mcp_session",
            "quickstartResource": "context://agent-quickstart",
            "quickstartTool": "get_agent_quickstart",
            "humanLightFlow": [
                "User adds https://api.memexai.xyz/mcp or the current MCP endpoint as a Claude custom connector.",
                "Claude follows the OAuth challenge, opens Google sign-in, and asks for Memexai approval.",
                "Agent calls get_mcp_session to confirm scopes and safe next calls after OAuth succeeds.",
                "Agent uses context:read by default, overlay:write for notes, and write scopes only by explicit opt-in.",
            ],
            "fallbackFlow": [
                "User creates a scoped MCP token once in Settings.",
                "Agent configures the streamable HTTP MCP endpoint with that bearer token.",
                "Agent calls get_mcp_session to confirm scopes and safe next calls.",
            ],
            "future": [
                "service-account style workspaces",
                "agent-assisted project and playlist setup onboarding",
            ],
        },
        "safety": {
            "sourceContext": "read-only",
            "overlayWrites": ["add_context_note", "upsert_personal_concept"],
            "bulkIngestion": "requires ingest:write and allow_bulk=true for playlists/channels",
            "captureSync": "requires capture:write plus preview and explicit queue confirmation",
            "projectCreation": "requires project:write",
        },
        "docs": {
            "llms": f"{base_url}/llms.txt",
            "llmsFull": f"{base_url}/llms-full.txt",
            "mcpManifest": f"{base_url}/mcp.json",
        },
    }


def _llms_text(base_url: str, full: bool = False) -> str:
    manifest = _public_mcp_manifest(base_url)
    tool_names = ", ".join(tool["name"] for tool in manifest["tools"])
    prompt_names = ", ".join(prompt["name"] for prompt in manifest["prompts"])
    lines = [
        "# Memexai Agent Guide",
        "",
        "Memexai is a saved YouTube video knowledge base for agents and humans.",
        f"MCP endpoint: {base_url}/mcp",
        f"MCP manifest: {base_url}/mcp.json",
        "Agent quickstart: context://agent-quickstart or get_agent_quickstart",
        "Brain sync contract: context://brain-sync-contract or get_brain_sync_contract",
        "Brain digest export: context://brain-digest or export_brain_digest",
        "",
        "Authentication:",
        "- Preferred Claude path: add this MCP endpoint as a Claude custom connector, sign in with Google, approve Memexai access, then enable the connector in the chat.",
        "- Claude custom connector URL: " + f"{base_url}/mcp",
        "- Fallback path: create a bearer MCP token in the web app settings under Agent access for clients that need explicit bearer-token config.",
        "- After connecting, call get_mcp_session to confirm token scopes and recommended next calls.",
        "- Default scopes: context:read, overlay:write.",
        "- Optional scope: ingest:write for queuing YouTube links from agent sessions.",
        "- Optional scope: project:write for creating project scopes.",
        "- Optional scope: capture:write for linking and syncing YouTube playlist capture sources.",
        "",
        "Core rule:",
        "- Source video context is read-only. Do not rewrite transcripts, source labels, source concepts, source edges, or generated artifacts.",
        "- Search is limited to the MCP token owner's user_videos/user_channels grants, even though canonical video rows may be shared.",
        "- Project scope is explicit per call. Use list_projects and pass project_id or project_slug when the user is working in a project.",
        "- Create projects only with project:write and explicit user intent.",
        "- Link playlists only with capture:write, a user-provided YouTube playlist URL, and a user-owned project target.",
        "- Preview capture sync with max_jobs=0, then queue only after explicit confirmation.",
        "- Search clips, library videos, and video context include accessScope, accessSource, and accessReason so agents can explain why a shared canonical video is visible.",
        "- Write only personal overlay notes or personal concepts unless explicitly queuing ingestion.",
        "- If the user has an external personal brain, sync compact source refs and digests through context://brain-sync-contract rather than direct database access.",
        "- Use export_brain_digest or context://brain-digest for compact incremental external-brain sync.",
        "",
        "Low-friction repo workflow:",
        "- Use your own repo, filesystem, GitHub, or code-index MCP tools to inspect the user's project.",
        "- Read context://repo-context-workflow or call get_repo_context_workflow for the readiness gate and expected output shape.",
        "- Use prompts/get collect_repo_context when you want a guided repo_context collection workflow.",
        "- Pass a compact repo_context object into build_agent_brief or build_context_bundle.",
        "- Read repoFit.targetMap from build_agent_brief for grouped files, symbols, locations, commands, tests, and runtime targets.",
        "- Do not require the user to connect GitHub inside Memexai when you already have repo MCP access.",
        "",
        f"Tools: {tool_names}",
        f"Prompts: {prompt_names}",
        "",
        "Common flow:",
        "1. Call get_mcp_session to confirm effective scopes and safe next calls.",
        "2. Read context://agent-quickstart or call get_agent_quickstart.",
        "3. Read context://brain-sync-contract or call get_brain_sync_contract when syncing an external personal brain.",
        "4. Pull export_brain_digest or context://brain-digest when the user wants external-brain sync.",
        "5. Call list_projects or read context://projects to identify explicit project scopes.",
        "6. Call get_project_context_map when the task maps to a project; otherwise broaden to the full library intentionally.",
        "7. If the user asks for a new workstream, call create_project with project:write.",
        "8. If the user gives a playlist for a project, call link_youtube_playlist_capture_source with capture:write.",
        "9. Preview playlist sync with sync_capture_source max_jobs=0, then queue only after explicit confirmation.",
        "10. Call list_video_library or read context://library.",
        "11. Call list_context_categories or read context://categories.",
        "12. Call list_capture_sources or read context://capture-sources when you need to understand standing YouTube inputs.",
        "13. Call list_workflow_runs or read context://workflows when following long-running platform work.",
        "14. Use search_video_concepts with retrieval_mode=hybrid for source reports, concepts, report sections, aliases, tools, methods, pitfalls, and timestamp refs. Pass project_id/project_slug when scoped.",
        "15. Call get_video_knowledge_map or read context://video-map/{videoId} for candidate videos before pulling transcript clips.",
        "16. Use search_video_moments with retrieval_mode=hybrid for timestamp evidence, or retrieval_mode=semantic/keyword for narrower follow-up. Pass youtube_video_id/video_id when the user asks about one known video. Inspect accessScope/accessReason on returned clips, library videos, and video context.",
        "17. Use search_transcript_text for exact phrases, names, acronyms, and product terms without embedding/LLM spend. Pass youtube_video_id/video_id for known-video questions.",
        "18. Use get_transcript_window for direct evidence around a returned timestamp before pulling broader context.",
        "19. Use get_video_context/include_transcript only when the map, searches, and transcript window are insufficient.",
        "20. Use get_repo_context_workflow or context://repo-context-workflow when you need the repo collection flow.",
        "21. Use get_repo_context_contract or context://repo-context-contract when you need the repo_context schema.",
        "22. Optional: use prompts/get collect_repo_context to gather validated repo_context with the agent's own repo tools.",
        "23. Call validate_repo_context and follow readiness.suggestedAgentNextSteps before implementation planning.",
        "24. Use build_agent_brief for product specs, implementation plans, and agent prompts.",
        "25. Use add_context_note or upsert_personal_concept for durable personalized takeaways.",
    ]
    if full:
        lines.extend(
            [
                "",
                "Ingestion flow:",
                "- queue_youtube_ingestion requires ingest:write.",
                "- Single-video and Shorts URLs can be queued directly.",
                "- Playlist and channel URLs require allow_bulk=true after explicit user approval.",
                "- Use list_workflow_runs, get_workflow_run, list_ingestion_jobs, or get_ingestion_job to check progress before assuming new context is searchable.",
                "",
                "Resource URIs:",
                "- context://agent-quickstart: machine-readable first steps for connected agents.",
                "- context://brain-sync-contract: contract for syncing compact saved-video knowledge into an external personal brain.",
                "- context://brain-digest: compact incremental digest for external personal brains.",
                "- context://projects: explicit user project scopes for saved videos.",
                "- context://project/{projectId}: project-scoped video/context map.",
                "- context://library: indexed channels and saved videos.",
                "- context://repo-context-contract: schema for caller-supplied repo_context.",
                "- context://repo-context-workflow: readiness gate and expected output for caller-supplied repo_context collection.",
                "- context://capture-sources: standing YouTube inputs such as a dedicated playlist.",
                "- context://categories: source labels, facets, and personal concepts.",
                "- context://notes: recent overlay notes.",
                "- context://workflows: recent durable platform workflow runs.",
                "- context://workflow/{workflowInstanceId}: status, steps, and artifacts for one workflow run.",
                "- context://video/{videoId}: transcript-derived context for one saved video.",
                "",
                "Recommended repo_context shape:",
                "- discover the full contract with get_repo_context_contract or context://repo-context-contract",
                "- source: agent-mcp",
                "- repo: owner/name or local project name",
                "- files: relevant paths",
                "- locations: compact path, symbol, route, or line anchors",
                "- entrypoints: routes, workers, jobs, scripts, pages, or handlers",
                "- symbols: relevant functions, classes, components, workflows, tools, or tests",
                "- modules: relevant modules",
                "- features: feature areas that could benefit from saved-video knowledge",
                "- dependencies: key frameworks, services, APIs, models, or libraries",
                "- commands: verified dev, test, build, migration, or deploy commands",
                "- tests: relevant test files, suites, evals, or verification gates",
                "- deployment: runtime, queue, database, or hosting facts",
                "- active_changes: dirty worktree, branch, PR, or user changes to preserve",
                "- constraints: important architecture, deployment, product, or user constraints",
                "",
                "Useful docs:",
                f"- {base_url}/mcp.json",
                f"- {base_url}/llms.txt",
                f"- {base_url}/llms-full.txt",
            ]
        )
    return "\n".join(lines) + "\n"


@app.get("/llms.txt")
async def llms_txt_endpoint(request: Request):
    """Public concise agent-readable guide."""
    return Response(content=_llms_text(_public_base_url(request)), media_type="text/plain")


@app.get("/llms-full.txt")
async def llms_full_txt_endpoint(request: Request):
    """Public detailed agent-readable guide."""
    return Response(
        content=_llms_text(_public_base_url(request), full=True), media_type="text/plain"
    )


@app.get("/mcp.json")
async def mcp_manifest_endpoint(request: Request):
    """Public MCP discovery manifest for agents."""
    return _public_mcp_manifest(_public_base_url(request))


@app.get("/.well-known/mcp.json")
async def well_known_mcp_manifest_endpoint(request: Request):
    """Well-known MCP discovery manifest alias."""
    return _public_mcp_manifest(_public_base_url(request))


@app.get("/.well-known/oauth-protected-resource")
async def oauth_protected_resource_endpoint(request: Request):
    """OAuth protected-resource metadata for MCP clients."""
    return protected_resource_metadata(_public_base_url(request))


@app.get("/.well-known/oauth-protected-resource/mcp")
async def oauth_protected_resource_mcp_endpoint(request: Request):
    """OAuth protected-resource metadata scoped to the MCP endpoint path."""
    return protected_resource_metadata(_public_base_url(request))


@app.get("/.well-known/oauth-authorization-server")
async def oauth_authorization_server_endpoint(request: Request):
    """OAuth authorization-server metadata for native MCP onboarding."""
    return authorization_server_metadata(_public_base_url(request))


@app.get("/.well-known/openid-configuration")
async def openid_configuration_endpoint(request: Request):
    """OIDC discovery alias for MCP clients that probe both discovery paths."""
    return authorization_server_metadata(_public_base_url(request))


@app.post("/oauth/register")
async def oauth_client_registration_endpoint(
    registration: McpOAuthClientRegistrationRequest,
):
    """Dynamically register a public OAuth client for an MCP agent."""
    if not is_supabase_mode():
        raise HTTPException(status_code=404, detail="MCP OAuth is only available in hosted mode")

    try:
        return register_oauth_client(get_supabase(), registration.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/oauth/authorize")
async def oauth_authorize_endpoint(request: Request):
    """Send OAuth users to the Memexai app approval screen."""
    if not is_supabase_mode():
        raise HTTPException(status_code=404, detail="MCP OAuth is only available in hosted mode")

    params = dict(request.query_params)
    try:
        validate_authorization_request(get_supabase(), params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    app_base_url = get_public_app_url(_public_base_url(request))
    return RedirectResponse(f"{app_base_url}/mcp/authorize?{urlencode(params)}", status_code=302)


@app.post("/oauth/token")
async def oauth_token_endpoint(request: Request):
    """Exchange an OAuth authorization code for a Memexai MCP bearer token."""
    if not is_supabase_mode():
        raise HTTPException(status_code=404, detail="MCP OAuth is only available in hosted mode")

    try:
        payload = parse_oauth_token_body(request.headers.get("content-type"), await request.body())
        return exchange_authorization_code(get_supabase(), payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Authenticated endpoints
# ---------------------------------------------------------------------------


async def get_request_user(authorization: str | None = Header(None)) -> dict:
    """Return the authenticated user, or a local pseudo-user in no-auth mode."""
    auth_mode = get_auth_mode()
    if auth_mode == NO_AUTH:
        return {"sub": LOCAL_USER_ID}
    if auth_mode == SUPABASE_AUTH:
        return await get_current_user(authorization)
    raise HTTPException(status_code=500, detail="Invalid auth configuration")


async def get_mcp_request_user(authorization: str | None = Header(None)) -> dict:
    """Authenticate MCP requests with either app auth or a dedicated MCP token."""
    auth_mode = get_auth_mode()
    if auth_mode == NO_AUTH:
        return {"sub": LOCAL_USER_ID}
    if auth_mode != SUPABASE_AUTH:
        raise HTTPException(status_code=500, detail="Invalid auth configuration")

    if authorization and authorization.startswith(f"Bearer {MCP_AUTH_PREFIX}_"):
        if is_supabase_mode():
            token_user = authenticate_mcp_token(get_supabase(), authorization)
            if token_user:
                return token_user
        raise HTTPException(status_code=401, detail="Invalid MCP token")

    return await get_current_user(authorization)


async def resolve_mcp_request_user(authorization: str | None) -> dict | None:
    """Return an MCP user or None so /mcp can emit an OAuth challenge."""
    auth_mode = get_auth_mode()
    if auth_mode == NO_AUTH:
        return {"sub": LOCAL_USER_ID}
    if auth_mode != SUPABASE_AUTH:
        raise HTTPException(status_code=500, detail="Invalid auth configuration")

    if authorization and authorization.startswith(f"Bearer {MCP_AUTH_PREFIX}_"):
        if is_supabase_mode():
            return authenticate_mcp_token(get_supabase(), authorization)
        return None

    if authorization:
        try:
            return await get_current_user(authorization)
        except HTTPException:
            return None

    return None


def mcp_oauth_challenge(request: Request, error: str | None = None) -> Response:
    """Build an MCP OAuth challenge response for desktop agent clients."""
    metadata_url = f"{_public_base_url(request)}/.well-known/oauth-protected-resource/mcp"
    parts = [
        'Bearer realm="memexai-mcp"',
        f'resource_metadata="{metadata_url}"',
        'scope="context:read overlay:write"',
    ]
    if error:
        parts.append(f'error="{error}"')
    return Response(status_code=401, headers={"WWW-Authenticate": ", ".join(parts)})


def require_internal_workflow_secret(provided_secret: str | None) -> None:
    """Require the Cloudflare Workflow shared secret for internal-only routes."""
    expected_secret = get_workflow_internal_secret()
    if not expected_secret:
        raise HTTPException(
            status_code=404,
            detail="Internal workflow endpoint is not configured",
        )
    if not provided_secret or not hmac.compare_digest(provided_secret, expected_secret):
        raise HTTPException(status_code=401, detail="Invalid workflow secret")


def schedule_hosted_ingestion_job(
    background_tasks: BackgroundTasks,
    job: dict,
    source: str = "hosted-api",
) -> dict:
    """Dispatch a hosted ingestion job to local background work or Cloudflare Queues."""
    try:
        return dispatch_ingestion_job(
            job,
            background_tasks=background_tasks,
            processor=process_hosted_ingestion_job,
            source=source,
        )
    except Exception as exc:  # noqa: BLE001 - dispatch failures should be durable.
        job_id = job.get("id")
        if is_supabase_mode() and isinstance(job_id, str):
            try:
                supabase = get_supabase()
                update_ingestion_job(
                    supabase,
                    job_id,
                    status="failed",
                    error=str(exc),
                    last_message=f"Dispatch failed: {str(exc)}",
                    **failed_ingestion_fields(job),
                )
                record_ingestion_job_event(
                    supabase,
                    job_id,
                    "error",
                    f"Dispatch failed: {str(exc)}",
                    reason="dispatch_failed",
                )
            except Exception as job_err:  # noqa: BLE001
                print(f"[WARN] Failed to mark ingestion dispatch failed: {job_err}")
        raise


def resolve_search_execution(
    user_id: str,
    limit: int,
    x_api_key: str | None = None,
) -> tuple[object | None, str | None, bool]:
    """Resolve search dependencies and enforce hosted search limits."""
    supabase = None
    used_own_key = bool(x_api_key)
    api_key = x_api_key

    if is_supabase_mode():
        supabase = get_supabase()
        profile = get_user_profile(supabase, user_id)
        api_key, used_own_key = resolve_api_key(profile, x_api_key)
        billing = resolve_user_entitlements(supabase, user_id, profile)
        entitlements = billing["entitlements"]
        period_usage = billing["usage"]

        max_search_results = int(entitlements["maxSearchResults"])
        if limit > max_search_results:
            raise HTTPException(
                status_code=400,
                detail=f"{entitlements['planKey'].title()} searches can return up to {max_search_results} clips.",
            )

        if not check_search_quota(profile, used_own_key, entitlements, period_usage):
            raise HTTPException(
                status_code=429,
                detail=(
                    f"{entitlements['planKey'].title()} monthly search limit reached. "
                    "Upgrade or wait for the next billing period to unlock more hosted searches."
                ),
            )
    elif not x_api_key:
        api_key, used_own_key = resolve_api_key()

    return supabase, api_key, used_own_key


def search_for_user(
    query: str,
    user_id: str,
    limit: int,
    x_api_key: str | None = None,
    category_filters: dict | None = None,
    retrieval_mode: str = "hybrid",
    project_id: str | None = None,
    project_slug: str | None = None,
    youtube_video_id: str | None = None,
) -> dict:
    """Run a scoped semantic search and log hosted usage when applicable."""
    supabase, api_key, used_own_key = resolve_search_execution(user_id, limit, x_api_key)
    if project_id or project_slug:
        result = search(
            query,
            user_id,
            api_key,
            limit,
            category_filters,
            retrieval_mode,
            project_id,
            project_slug,
            youtube_video_id,
        )
    else:
        result = search(
            query,
            user_id,
            api_key,
            limit,
            category_filters,
            retrieval_mode,
            youtube_video_id=youtube_video_id,
        )

    try:
        if supabase is not None:
            increment_search_usage(supabase, user_id, used_own_key, limit)
    except Exception as usage_err:
        print(f"[WARN] Failed to log search usage: {usage_err}")

    return result


LIBRARY_CACHE_CONTROL = "private, max-age=30, stale-while-revalidate=120"
LIBRARY_ARTIFACT_CACHE_CONTROL = "private, max-age=300, stale-while-revalidate=600"


@app.get("/api/projects")
async def projects_endpoint(
    response: Response,
    limit: int = 50,
    user: dict = Depends(get_request_user),
):
    """List user projects that can scope saved-video context."""
    response.headers["Cache-Control"] = LIBRARY_CACHE_CONTROL
    if not is_supabase_mode():
        return {
            "projects": [],
            "archivedProjects": [],
            "totalProjects": 0,
            "totalArchivedProjects": 0,
            "limit": max(1, min(limit, 100)),
        }
    return list_projects(get_supabase(), user["sub"], limit)


@app.post("/api/projects")
async def create_project_endpoint(
    request: ProjectRequest,
    user: dict = Depends(get_request_user),
):
    """Create a user-owned project scope."""
    if not is_supabase_mode():
        raise HTTPException(status_code=404, detail="Projects are available in hosted mode")
    try:
        project = create_project(
            get_supabase(),
            user["sub"],
            request.name,
            request.description,
            request.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"project": project}


@app.patch("/api/projects/{project_id}")
async def update_project_endpoint(
    project_id: str,
    request: ProjectUpdateRequest,
    user: dict = Depends(get_request_user),
):
    """Update project display/status fields."""
    if not is_supabase_mode():
        raise HTTPException(status_code=404, detail="Projects are available in hosted mode")
    try:
        project = update_project(
            get_supabase(),
            user["sub"],
            project_id,
            name=request.name,
            description=request.description,
            status=request.status,
            metadata=request.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"project": project}


@app.delete("/api/projects/{project_id}")
async def delete_project_endpoint(
    project_id: str,
    user: dict = Depends(get_request_user),
):
    """Delete a project and its memberships without deleting source videos."""
    if not is_supabase_mode():
        raise HTTPException(status_code=404, detail="Projects are available in hosted mode")
    if not delete_project(get_supabase(), user["sub"], project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"deleted": True}


@app.post("/api/projects/{project_id}/videos")
async def add_project_videos_endpoint(
    project_id: str,
    request: ProjectVideosRequest,
    user: dict = Depends(get_request_user),
):
    """Assign existing accessible library videos to a project."""
    if not is_supabase_mode():
        raise HTTPException(status_code=404, detail="Projects are available in hosted mode")
    try:
        return add_videos_to_project(
            get_supabase(),
            user["sub"],
            project_id,
            video_ids=request.video_ids,
            youtube_video_ids=request.youtube_video_ids,
            added_source=request.added_source,
        )
    except ValueError as exc:
        status = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@app.delete("/api/projects/{project_id}/videos/{video_id}")
async def remove_project_video_endpoint(
    project_id: str,
    video_id: str,
    user: dict = Depends(get_request_user),
):
    """Remove one video from a project only."""
    if not is_supabase_mode():
        raise HTTPException(status_code=404, detail="Projects are available in hosted mode")
    if not remove_video_from_project(get_supabase(), user["sub"], project_id, video_id):
        raise HTTPException(status_code=404, detail="Project video not found")
    return {"removed": True}


@app.get("/api/projects/{project_id}/context-map")
async def project_context_map_endpoint(
    project_id: str,
    response: Response,
    detail_level: str = "compact",
    max_chars: int | None = None,
    user: dict = Depends(get_request_user),
):
    """Return a compact project-scoped context map."""
    response.headers["Cache-Control"] = LIBRARY_CACHE_CONTROL
    if not is_supabase_mode():
        raise HTTPException(status_code=404, detail="Projects are available in hosted mode")
    try:
        return build_project_context_map(
            get_supabase(),
            user["sub"],
            project_id=project_id,
            detail_level=detail_level,
            max_chars=max_chars,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/library")
async def library_endpoint(
    response: Response,
    project_id: str | None = None,
    project_slug: str | None = None,
    user: dict = Depends(get_request_user),
):
    """
    Get the authenticated user's indexed videos organized by channel.

    Returns:
        {
            "channels": [{"name": "...", "videoCount": N, "videos": [...]}],
            "totalVideos": N,
            "totalClips": N
        }
    """
    response.headers["Cache-Control"] = LIBRARY_CACHE_CONTROL
    user_id = user["sub"]
    try:
        return get_library(user_id, project_id, project_slug)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/library/graph")
async def library_graph_endpoint(
    response: Response,
    limit: int = 50,
    include_content: bool = False,
    project_id: str | None = None,
    project_slug: str | None = None,
    user: dict = Depends(get_request_user),
):
    """Return the user's inspectable source graph snapshot."""
    response.headers["Cache-Control"] = LIBRARY_CACHE_CONTROL
    if not is_supabase_mode():
        return {
            "version": "memexai-library-source-graph-v1",
            "limit": max(1, min(limit, 100)),
            "accessModel": {
                "scope": "current_user_grants",
                "visibilityGrants": ["user_videos", "user_channels"],
                "sourceTruth": "read_only",
                "provenanceFields": ["accessScope", "accessSource", "accessReason"],
            },
            "videos": [],
            "componentCounts": {
                "videos": 0,
                "channels": 0,
                "sourceLabels": 0,
                "sourceConcepts": 0,
                "sourceEdges": 0,
                "knowledgeArtifacts": 0,
                "transcriptChunksSampled": 0,
                "agentNotes": 0,
                "personalConcepts": 0,
                "reviewFlags": 0,
            },
            "graph": {"nodes": [], "edges": [], "selectedNodeId": None},
            "reviewFlags": [],
            "edgeCaseHandling": [],
            "guidance": "Structured source graph is available in hosted Supabase mode.",
        }

    bounded_limit = max(1, min(limit, 100))
    try:
        graph_kwargs = {
            "include_artifact_content": include_content,
            "include_auxiliary_nodes": False,
            "include_review_flags": False,
        }
        if project_id or project_slug:
            graph_kwargs.update({"project_id": project_id, "project_slug": project_slug})
        return build_library_source_graph(
            get_supabase(),
            user["sub"],
            bounded_limit,
            **graph_kwargs,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/library/artifacts/{artifact_id}")
async def library_artifact_endpoint(
    artifact_id: str,
    response: Response,
    user: dict = Depends(get_request_user),
):
    """Return the full source report content for one accessible library artifact."""
    if not is_supabase_mode():
        raise HTTPException(
            status_code=404, detail="Library artifacts are available in hosted mode"
        )
    artifact = get_library_artifact(get_supabase(), user["sub"], artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found in your library")
    response.headers["Cache-Control"] = LIBRARY_ARTIFACT_CACHE_CONTROL
    return artifact


@app.get("/api/library/components/search")
async def library_components_search_endpoint(
    q: str = "",
    limit: int = 20,
    component_types: str | None = None,
    project_id: str | None = None,
    project_slug: str | None = None,
    user: dict = Depends(get_request_user),
):
    """Keyword-search source graph components without embeddings or an LLM answer."""
    bounded_limit = max(1, min(limit, 50))
    selected_types = (
        [item.strip() for item in component_types.split(",") if item.strip()]
        if component_types
        else None
    )
    if not is_supabase_mode():
        return {
            "query": q.strip(),
            "retrievalMode": "component_keyword",
            "results": [],
            "componentTypes": selected_types or [],
            "accessModel": {
                "scope": "current_user_grants",
                "embeddingUsed": False,
                "llmAnswerUsed": False,
            },
            "retrievalBudget": {
                "embeddingCalls": 0,
                "llmCalls": 0,
                "maxResults": bounded_limit,
                "searchedVideos": 0,
                "returnedResults": 0,
            },
            "guidance": "Component search is available in hosted Supabase mode.",
        }
    try:
        if project_id or project_slug:
            return search_library_components(
                get_supabase(),
                user["sub"],
                q,
                bounded_limit,
                selected_types,
                project_id=project_id,
                project_slug=project_slug,
            )
        return search_library_components(
            get_supabase(),
            user["sub"],
            q,
            bounded_limit,
            selected_types,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/api/video/{video_id}")
async def delete_video_endpoint(video_id: str, user: dict = Depends(get_request_user)):
    """
    Delete a video and all its clips from the database.
    Only works if the user is subscribed to the channel owning this video.

    Args:
        video_id: YouTube video ID to delete

    Returns:
        {"deleted": true/false, ...}
    """
    user_id = user["sub"]
    return delete_video(video_id, user_id)


def format_srt_timestamp(seconds: int) -> str:
    """Convert seconds to SRT timestamp format (HH:MM:SS,mmm)."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d},000"


@app.get("/api/transcript/{video_id}")
async def transcript_endpoint(
    video_id: str,
    format: str = "srt",
    user: dict = Depends(get_request_user),
):
    """
    Download transcript for a video as SRT file.

    Args:
        video_id: YouTube video ID
        format: Output format (currently only 'srt' supported)

    Returns:
        SRT file download
    """
    chunks = get_video_transcript(video_id, user["sub"])

    if not chunks:
        raise HTTPException(status_code=404, detail="Video not found or has no transcript")

    # Build SRT content
    srt_lines = []
    for i, chunk in enumerate(chunks, 1):
        start_ts = format_srt_timestamp(chunk["start_seconds"])
        end_ts = format_srt_timestamp(chunk["end_seconds"])
        text = chunk["content"].strip()

        srt_lines.append(f"{i}")
        srt_lines.append(f"{start_ts} --> {end_ts}")
        srt_lines.append(text)
        srt_lines.append("")  # Blank line between entries

    srt_content = "\n".join(srt_lines)

    # Sanitize filename
    safe_title = video_id  # We don't have title in the transcript response
    filename = f"{safe_title}.srt"

    return Response(
        content=srt_content,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/videos/{video_id}/context")
async def video_context_endpoint(
    video_id: str,
    project_id: str | None = None,
    project_slug: str | None = None,
    user: dict = Depends(get_request_user),
):
    """
    Return source-derived context for a video in the user's library.

    This endpoint is intentionally read-only. Agents can use it as context,
    but source video/transcript/concept records are not mutated through this
    surface.
    """
    if not is_supabase_mode():
        raise HTTPException(
            status_code=404, detail="Structured video context is only available in hosted mode"
        )

    try:
        context = get_video_context(
            get_supabase(),
            user["sub"],
            video_id,
            project_id=project_id,
            project_slug=project_slug,
        )
        if not context:
            raise HTTPException(status_code=404, detail="Video not found in your library")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return context


@app.get("/api/context/notes")
async def context_notes_endpoint(
    limit: int = 50,
    user: dict = Depends(get_request_user),
):
    """List recent notes from the user's writable personal context overlay."""
    if not is_supabase_mode():
        return {"notes": []}

    bounded_limit = max(1, min(limit, 100))
    return {"notes": list_agent_notes(get_supabase(), user["sub"], bounded_limit)}


@app.post("/api/context/notes")
async def create_context_note_endpoint(
    request: AgentNoteRequest,
    user: dict = Depends(get_request_user),
):
    """Create a user-scoped overlay note without modifying source video context."""
    if not request.content.strip():
        raise HTTPException(status_code=400, detail="Note content cannot be empty")
    if request.created_by not in {"user", "agent"}:
        raise HTTPException(status_code=400, detail="created_by must be 'user' or 'agent'")
    if not is_supabase_mode():
        raise HTTPException(
            status_code=404, detail="Context notes are only available in hosted mode"
        )

    note = create_agent_note(
        get_supabase(),
        user["sub"],
        request.content.strip(),
        request.source_refs,
        request.tags,
        request.created_by,
        request.created_by_client,
    )
    return {"note": note}


@app.post("/api/context/personal-concepts")
async def upsert_personal_concept_endpoint(
    request: PersonalConceptRequest,
    user: dict = Depends(get_request_user),
):
    """Create or update a personalized concept in the user's overlay."""
    if not request.name.strip():
        raise HTTPException(status_code=400, detail="Concept name cannot be empty")
    if request.created_by not in {"user", "agent"}:
        raise HTTPException(status_code=400, detail="created_by must be 'user' or 'agent'")
    if request.status not in {"active", "learning", "applied", "ignored", "archived"}:
        raise HTTPException(status_code=400, detail="Invalid concept status")
    if not is_supabase_mode():
        raise HTTPException(
            status_code=404, detail="Personal concepts are only available in hosted mode"
        )

    concept = upsert_personal_concept(
        get_supabase(),
        user["sub"],
        request.name.strip(),
        request.summary.strip(),
        request.source_refs,
        request.status,
        request.created_by,
        request.created_by_client,
    )
    return {"concept": concept}


@app.post("/api/context/bundle")
async def context_bundle_endpoint(
    request: ContextBundleRequest,
    user: dict = Depends(get_request_user),
):
    """
    Build an agent-friendly context bundle.

    `repo_context` is request-supplied so agents with their own repo MCP can
    bring repository context without forcing a hosted GitHub connection first.
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    if not is_supabase_mode():
        raise HTTPException(
            status_code=404, detail="Context bundles are only available in hosted mode"
        )

    bounded_limit = max(1, min(request.limit, 20))
    return build_context_bundle(
        get_supabase(),
        user["sub"],
        request.query.strip(),
        request.repo_context,
        bounded_limit,
        request.category_filters,
    )


@app.post("/api/context/repo-context/validate")
async def validate_repo_context_endpoint(
    request: RepoContextValidationRequest,
    user: dict = Depends(get_request_user),
):
    """Validate caller-supplied repo context without storing it."""
    del user
    return validate_repo_context(request.repo_context)


@app.post("/api/mcp/oauth/approve")
async def approve_mcp_oauth_endpoint(
    request: McpOAuthApproveRequest,
    user: dict = Depends(get_request_user),
):
    """Approve a native MCP OAuth authorization request for the current user."""
    if not is_supabase_mode():
        raise HTTPException(status_code=404, detail="MCP OAuth is only available in hosted mode")

    try:
        redirect_url = create_authorization_redirect(
            get_supabase(),
            user["sub"],
            request.model_dump(exclude_none=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"redirectUrl": redirect_url}


@app.get("/api/youtube/oauth/status")
async def youtube_oauth_status_endpoint(user: dict = Depends(get_request_user)):
    """Return token-safe YouTube OAuth connection status for the current user."""
    if not is_supabase_mode():
        return {
            "connected": False,
            "needsReconnect": False,
            "youtubeReadonlyGranted": False,
            "hasRefreshToken": False,
            "scopes": [],
            "expiresAt": None,
            "connectedAt": None,
            "updatedAt": None,
            "lastError": None,
        }

    return get_youtube_oauth_status(get_supabase(), user["sub"])


@app.post("/api/youtube/oauth/connection")
async def save_youtube_oauth_connection_endpoint(
    request: YoutubeOAuthConnectionRequest,
    user: dict = Depends(get_request_user),
):
    """Store encrypted Google provider tokens for YouTube playlist capture sync."""
    if not is_supabase_mode():
        raise HTTPException(
            status_code=404, detail="YouTube OAuth connections are only available in hosted mode"
        )

    try:
        status = upsert_youtube_oauth_connection(
            get_supabase(),
            user["sub"],
            access_token=request.access_token,
            refresh_token=request.refresh_token,
            expires_in=request.expires_in,
            expires_at=request.expires_at,
            scopes=request.scopes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return status


@app.delete("/api/youtube/oauth/connection")
async def disconnect_youtube_oauth_endpoint(user: dict = Depends(get_request_user)):
    """Remove the current user's stored YouTube OAuth grant."""
    if not is_supabase_mode():
        return {
            "connected": False,
            "needsReconnect": False,
            "youtubeReadonlyGranted": False,
            "hasRefreshToken": False,
            "scopes": [],
            "expiresAt": None,
            "connectedAt": None,
            "updatedAt": None,
            "lastError": None,
        }

    return disconnect_youtube_oauth(get_supabase(), user["sub"])


@app.get("/api/capture/sources")
async def capture_sources_endpoint(
    limit: int = 50,
    user: dict = Depends(get_request_user),
):
    """List standing YouTube capture sources for the current user."""
    if not is_supabase_mode():
        return {"captureSources": []}

    bounded_limit = max(1, min(limit, 100))
    return build_capture_sources_context(get_supabase(), user["sub"], bounded_limit)


@app.post("/api/capture/sources")
async def create_capture_source_endpoint(
    request: CaptureSourceRequest,
    user: dict = Depends(get_request_user),
):
    """Create a user-selected YouTube playlist capture source."""
    if not is_supabase_mode():
        raise HTTPException(
            status_code=404, detail="Capture sources are only available in hosted mode"
        )

    try:
        source = create_playlist_capture_source(
            get_supabase(),
            user["sub"],
            request.playlist_url,
            request.title,
            request.project_id,
            request.created_by,
            request.created_by_client,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"captureSource": source}


@app.delete("/api/capture/sources/{source_id}")
async def delete_capture_source_endpoint(
    source_id: str,
    user: dict = Depends(get_request_user),
):
    """Delete one capture source. Already indexed videos stay in the user's library."""
    if not is_supabase_mode():
        raise HTTPException(
            status_code=404, detail="Capture sources are only available in hosted mode"
        )
    if not delete_capture_source(get_supabase(), user["sub"], source_id):
        raise HTTPException(status_code=404, detail="Capture source not found")
    return {"deleted": True}


@app.patch("/api/capture/sources/{source_id}/project")
async def set_capture_source_project_endpoint(
    source_id: str,
    request: CaptureSourceProjectRequest,
    user: dict = Depends(get_request_user),
):
    """Attach or detach a capture playlist's default project target."""
    if not is_supabase_mode():
        raise HTTPException(
            status_code=404, detail="Capture sources are only available in hosted mode"
        )
    try:
        source = set_capture_source_project(
            get_supabase(),
            user["sub"],
            source_id,
            request.project_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not source:
        raise HTTPException(status_code=404, detail="Capture source not found")
    return {"captureSource": source}


@app.post("/api/capture/sources/{source_id}/sync")
async def sync_capture_source_endpoint(
    source_id: str,
    request: CaptureSourceSyncRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_request_user),
):
    """Manually sync a YouTube capture source and queue bounded ingestion jobs."""
    if not is_supabase_mode():
        raise HTTPException(
            status_code=404, detail="Capture sources are only available in hosted mode"
        )

    try:
        result = run_capture_sync_workflow(
            get_supabase(),
            user["sub"],
            source_id,
            request.max_jobs,
            dispatch_job=lambda job: schedule_hosted_ingestion_job(
                background_tasks,
                job,
                source="capture-sync",
            ),
            trigger="api.capture.sync",
            created_by="user",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return result


@app.post("/internal/workflows/capture-sync")
async def internal_capture_sync_workflow_endpoint(
    request: InternalWorkflowCaptureSyncRequest,
    background_tasks: BackgroundTasks,
    x_memexai_workflow_secret: str | None = Header(None),
):
    """Trigger capture sync from Cloudflare Workflows without impersonating a user."""
    require_internal_workflow_secret(x_memexai_workflow_secret)
    if not is_supabase_mode():
        raise HTTPException(
            status_code=404, detail="Capture workflows are only available in hosted mode"
        )

    user_id = request.user_id.strip()
    source_id = request.capture_source_id.strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    if not source_id:
        raise HTTPException(status_code=400, detail="capture_source_id is required")

    try:
        result = run_capture_sync_workflow(
            get_supabase(),
            user_id,
            source_id,
            request.max_jobs,
            dispatch_job=lambda job: schedule_hosted_ingestion_job(
                background_tasks,
                job,
                source="cloudflare-workflow:capture-sync",
            ),
            trigger="cloudflare.workflow.capture.sync",
            created_by="system",
            created_by_client=request.created_by_client or "cloudflare-workflows",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return result


@app.get("/api/mcp/tokens")
async def mcp_tokens_endpoint(user: dict = Depends(get_request_user)):
    """List active MCP token metadata for the current user."""
    if not is_supabase_mode():
        return {"tokens": []}
    return {"tokens": list_mcp_tokens(get_supabase(), user["sub"])}


@app.post("/api/mcp/tokens")
async def create_mcp_token_endpoint(
    token_request: McpTokenRequest,
    http_request: Request,
    user: dict = Depends(get_request_user),
):
    """Create an MCP bearer token. The raw token is returned once."""
    if not is_supabase_mode():
        raise HTTPException(status_code=404, detail="MCP tokens are only available in hosted mode")

    result = create_mcp_token(
        get_supabase(),
        user["sub"],
        token_request.name,
        token_request.scopes,
    )
    return {
        "token": result["token"],
        "tokenRecord": result["record"],
        "setup": _mcp_agent_setup_bundle(_public_base_url(http_request), result["token"]),
    }


@app.delete("/api/mcp/tokens/{token_id}")
async def revoke_mcp_token_endpoint(token_id: str, user: dict = Depends(get_request_user)):
    """Revoke an MCP token owned by the current user."""
    if not is_supabase_mode():
        raise HTTPException(status_code=404, detail="MCP tokens are only available in hosted mode")

    result = revoke_mcp_token(get_supabase(), user["sub"], token_id)
    if not result["revoked"]:
        raise HTTPException(status_code=404, detail="MCP token not found")
    return result


@app.post("/mcp")
async def mcp_endpoint(
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(None),
):
    """Serve a stateless MCP JSON-RPC endpoint for agent context access."""
    user = await resolve_mcp_request_user(authorization)
    if not user:
        return mcp_oauth_challenge(request, "invalid_token" if authorization else None)

    try:
        payload = await request.json()
    except JSONDecodeError:
        return JSONResponse(parse_error_response(), status_code=200)

    supabase = (
        get_supabase() if is_supabase_mode() and mcp_payload_requires_supabase(payload) else None
    )

    def run_mcp_search(
        query: str,
        limit: int,
        category_filters: dict | None = None,
        retrieval_mode: str = "hybrid",
        project_id: str | None = None,
        project_slug: str | None = None,
        youtube_video_id: str | None = None,
    ) -> dict:
        try:
            if project_id or project_slug:
                return search_for_user(
                    query,
                    user["sub"],
                    limit,
                    category_filters=category_filters,
                    retrieval_mode=retrieval_mode,
                    project_id=project_id,
                    project_slug=project_slug,
                    youtube_video_id=youtube_video_id,
                )
            return search_for_user(
                query,
                user["sub"],
                limit,
                category_filters=category_filters,
                retrieval_mode=retrieval_mode,
                youtube_video_id=youtube_video_id,
            )
        except HTTPException as exc:
            raise ValueError(str(exc.detail)) from exc
        except Exception as exc:
            raise ValueError(f"Search failed: {exc}") from exc

    def run_mcp_transcript_text_search(
        query: str,
        limit: int,
        category_filters: dict | None = None,
        project_id: str | None = None,
        project_slug: str | None = None,
        youtube_video_id: str | None = None,
    ) -> dict:
        try:
            if project_id or project_slug:
                return search_transcript_text(
                    query,
                    user["sub"],
                    limit,
                    category_filters=category_filters,
                    project_id=project_id,
                    project_slug=project_slug,
                    youtube_video_id=youtube_video_id,
                )
            return search_transcript_text(
                query,
                user["sub"],
                limit,
                category_filters=category_filters,
                youtube_video_id=youtube_video_id,
            )
        except Exception as exc:
            raise ValueError(f"Keyword transcript search failed: {exc}") from exc

    def embed_mcp_source_query(query: str) -> list[float]:
        try:
            return get_query_embeddings().embed_query(query)
        except Exception as exc:
            raise ValueError(f"Source knowledge embedding failed: {exc}") from exc

    queued_ingestion_jobs: list[dict] = []
    queued_capture_sync_jobs: list[dict] = []
    loop = asyncio.get_event_loop()
    response, status_code = await loop.run_in_executor(
        None,
        lambda: handle_mcp_request(
            payload,
            user["sub"],
            supabase,
            user.get("scopes"),
            {
                "auth_kind": user.get(
                    "auth", "app_user" if get_auth_mode() != NO_AUTH else "local"
                ),
                "search_video_moments": run_mcp_search,
                "search_transcript_text": run_mcp_transcript_text_search,
                "embed_source_query": embed_mcp_source_query,
                "queued_ingestion_jobs": queued_ingestion_jobs,
                "queued_capture_sync_jobs": queued_capture_sync_jobs,
            },
        ),
    )
    for job in queued_ingestion_jobs:
        schedule_hosted_ingestion_job(background_tasks, job, source="mcp")
    for job in queued_capture_sync_jobs:
        schedule_hosted_ingestion_job(background_tasks, job, source="mcp-capture-sync")

    if response is None:
        return Response(status_code=status_code)
    return JSONResponse(response, status_code=status_code)


@app.post("/api/ingest")
async def ingest_endpoint(
    request: IngestRequest,
    user: dict = Depends(get_request_user),
    x_api_key: str | None = Header(None),
):
    """
    Index a YouTube channel, playlist, or single video.

    Uses Server-Sent Events (SSE) to stream progress to the frontend.
    The frontend displays these messages in a terminal-style log view.

    SSE Format:
        data: Scanning channel for videos...
        data: Found 50 videos in channel
        data: [DONE]
    """
    user_id = user["sub"]

    supabase = None
    used_own_key = False
    api_key = x_api_key
    ingestion_job = None

    if is_supabase_mode():
        supabase = get_supabase()
        profile = get_user_profile(supabase, user_id)
        api_key, used_own_key = resolve_api_key(profile)
        billing = resolve_user_entitlements(supabase, user_id, profile)
        entitlements = billing["entitlements"]
        source_type, _ = detect_url_type(request.url)
        active_jobs = count_active_ingestion_jobs(supabase, user_id)
        if active_jobs >= int(entitlements["maxActiveIngestionJobs"]):
            raise HTTPException(
                status_code=409,
                detail=(
                    "You already have the maximum number of imports running for your plan. "
                    "Wait for one to finish before starting another."
                ),
            )
        digest_depth = normalize_digest_depth(request.digest_depth)
        cost_estimate = build_ingestion_cost_estimate(
            supabase,
            user_id,
            request.url,
            source_type,
            digest_depth=digest_depth,
        )
        ingestion_job = create_ingestion_job(
            supabase,
            user_id,
            request.url,
            source_type,
            cost_estimate,
        )
    elif x_api_key:
        used_own_key = True
    else:
        api_key, used_own_key = resolve_api_key()

    async def generate_events() -> AsyncGenerator[str, None]:
        messages: list[str] = []
        try:
            if supabase is not None and ingestion_job:
                update_ingestion_job(
                    supabase,
                    ingestion_job["id"],
                    status="running",
                    started_at=datetime.now(timezone.utc).isoformat(),
                )

            def run_ingestion():
                yield from ingest_url(
                    request.url,
                    user_id,
                    api_key,
                    used_own_key,
                    normalize_digest_depth(request.digest_depth),
                )

            async for message in stream_sync_generator(run_ingestion):
                messages.append(message)
                if supabase is not None and ingestion_job:
                    try:
                        record_ingestion_job_event(
                            supabase,
                            ingestion_job["id"],
                            classify_ingestion_event_level(message),
                            message,
                            reason=extract_ingestion_event_reason(message),
                        )
                        update_ingestion_job(supabase, ingestion_job["id"], last_message=message)
                    except Exception as job_err:
                        print(f"[WARN] Failed to record ingestion job event: {job_err}")
                yield f"data: {message}\n\n"
                # Small delay for frontend to render each message
                await asyncio.sleep(0.05)

            if supabase is not None and ingestion_job:
                summary = summarize_ingestion_messages(messages)
                update_ingestion_job(
                    supabase,
                    ingestion_job["id"],
                    requested_video_count=summary["requested_video_count"],
                    indexed_video_count=summary["indexed_video_count"],
                    skipped_video_count=summary["skipped_video_count"],
                    failed_video_count=summary["failed_video_count"],
                    status=summary["status"],
                    last_message=messages[-1] if messages else "Complete",
                )

            # Signal completion
            yield "data: [DONE]\n\n"

        except Exception as e:
            if supabase is not None and ingestion_job:
                try:
                    update_ingestion_job(
                        supabase,
                        ingestion_job["id"],
                        status="failed",
                        error=str(e),
                        last_message=f"Error: {str(e)}",
                        **failed_ingestion_fields(ingestion_job),
                    )
                    record_ingestion_job_event(
                        supabase,
                        ingestion_job["id"],
                        "error",
                        f"Error: {str(e)}",
                    )
                except Exception as job_err:
                    print(f"[WARN] Failed to mark ingestion job failed: {job_err}")
            yield f"data: Error: {str(e)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@app.post("/api/search", response_model=None)
async def search_endpoint(
    request: SearchRequest,
    user: dict = Depends(get_request_user),
    x_api_key: str | None = Header(None),
) -> dict:
    """
    Search indexed videos using semantic similarity.

    Returns:
        {
            "answer": "",
            "relevantClips": [...]
        }
    """
    user_id = user["sub"]

    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        # Run the synchronous search in a thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: search_for_user(
                request.query,
                user_id,
                request.limit,
                x_api_key=x_api_key,
                category_filters=request.category_filters,
                retrieval_mode=request.retrieval_mode,
                project_id=request.project_id,
                project_slug=request.project_slug,
            ),
        )
        return result
    except HTTPException:
        raise
    except ValueError as e:
        if "project" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


# ---------------------------------------------------------------------------
# User profile & settings
# ---------------------------------------------------------------------------


@app.get("/api/profile")
async def profile_endpoint(user: dict = Depends(get_request_user)):
    """Get user profile info."""
    if not is_supabase_mode():
        return {
            "id": LOCAL_USER_ID,
            "displayName": "Local User",
            "avatarUrl": "",
            "hasOwnKey": False,
            "apiKeyMode": get_api_key_mode(),
            "hasServerKey": bool(get_server_api_key()),
            "allowUserKeys": allow_user_keys(),
        }

    user_id = user["sub"]
    supabase = get_supabase()
    profile = get_user_profile(supabase, user_id)
    return {
        "id": profile["id"],
        "displayName": profile.get("display_name", "User"),
        "avatarUrl": profile.get("avatar_url", ""),
        "hasOwnKey": bool(profile.get("api_key_enc")),
        "apiKeyMode": get_api_key_mode(),
        "hasServerKey": bool(get_server_api_key()),
        "allowUserKeys": allow_user_keys(),
    }


@app.get("/api/onboarding/status")
async def onboarding_status_endpoint(user: dict = Depends(get_request_user)):
    """Return resumable first-time setup state and activation signals."""
    if not is_supabase_mode():
        return {
            "step": "done",
            "state": {},
            "completedAt": None,
            "skippedAt": None,
            "explicitCompleted": True,
            "explicitSkipped": False,
            "derived": {
                "youtubeConnected": False,
                "hasCaptureSource": False,
                "hasGrantedVideo": False,
                "hasQueuedOrIndexedJob": False,
                "hasMcpToken": False,
                "hasSearchUsage": False,
                "activationComplete": True,
            },
            "nextSteps": [],
        }

    supabase = get_supabase()
    profile = get_user_profile(supabase, user["sub"])
    return build_onboarding_status(supabase, user["sub"], profile)


@app.patch("/api/onboarding/status")
async def update_onboarding_status_endpoint(
    request: OnboardingStatusUpdateRequest,
    user: dict = Depends(get_request_user),
):
    """Persist first-time setup progress without mutating source video context."""
    if not is_supabase_mode():
        return await onboarding_status_endpoint(user)

    try:
        updates = build_onboarding_update(request.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    supabase = get_supabase()
    if updates:
        supabase.table("profiles").update(updates).eq("id", user["sub"]).execute()
    profile = get_user_profile(supabase, user["sub"])
    return build_onboarding_status(supabase, user["sub"], profile)


@app.post("/api/billing/checkout")
async def billing_checkout_endpoint(
    request: BillingCheckoutRequest,
    user: dict = Depends(get_request_user),
):
    """Create a Stripe-hosted Checkout session for a paid subscription."""
    if not is_supabase_mode():
        raise HTTPException(status_code=404, detail="Billing is only available in hosted mode")
    return create_checkout_session(get_supabase(), user, request.lookupKey, request.promoCode)


@app.get("/api/billing/promo/{promo_code}")
async def billing_promo_endpoint(promo_code: str):
    """Describe a promotional trial code so the app can render its offer."""
    if not is_supabase_mode():
        raise HTTPException(status_code=404, detail="Billing is only available in hosted mode")
    promo = describe_promo_trial(promo_code)
    if not promo:
        raise HTTPException(status_code=404, detail="Unknown promo code")
    return promo


@app.post("/api/billing/portal")
async def billing_portal_endpoint(user: dict = Depends(get_request_user)):
    """Create a Stripe-hosted Customer Portal session for billing management."""
    if not is_supabase_mode():
        raise HTTPException(status_code=404, detail="Billing is only available in hosted mode")
    return create_portal_session(get_supabase(), user["sub"])


@app.get("/api/billing/status")
async def billing_status_endpoint(user: dict = Depends(get_request_user)):
    """Return current Stripe billing state and resolved hosted entitlements."""
    if not is_supabase_mode():
        return {
            "planKey": "local",
            "billingStatus": "local",
            "currentPeriodStart": None,
            "currentPeriodEnd": None,
            "cancelAtPeriodEnd": False,
            "entitlements": None,
            "usage": None,
            "hasStripeCustomer": False,
        }

    supabase = get_supabase()
    profile = get_user_profile(supabase, user["sub"])
    billing = resolve_user_entitlements(supabase, user["sub"], profile)
    entitlements = billing["entitlements"]
    billing_profile = billing.get("billingProfile") or {}
    return {
        "planKey": entitlements["planKey"],
        "billingStatus": entitlements["billingStatus"],
        "currentPeriodStart": entitlements["periodStart"],
        "currentPeriodEnd": entitlements["periodEnd"],
        "cancelAtPeriodEnd": bool(billing_profile.get("cancel_at_period_end", False)),
        "entitlements": entitlements,
        "usage": billing["usage"],
        "hasStripeCustomer": bool(billing_profile.get("stripe_customer_id")),
    }


@app.post("/api/billing/webhook")
async def billing_webhook_endpoint(
    request: Request,
    stripe_signature: str | None = Header(None, alias="Stripe-Signature"),
):
    """Receive signed Stripe billing events and update hosted entitlement state."""
    if not is_supabase_mode():
        raise HTTPException(status_code=404, detail="Billing is only available in hosted mode")

    payload = await request.body()
    event = construct_stripe_event(payload, stripe_signature)
    return process_stripe_event(get_supabase(), event)


@app.get("/api/usage")
async def usage_endpoint(user: dict = Depends(get_request_user)):
    """Returns the user's current quota status."""
    if not is_supabase_mode():
        return {
            "plan": "local",
            "planKey": "local",
            "billingStatus": "local",
            "searchesUsedToday": 0,
            "searchLimit": None,
            "searchesUsedThisMonth": 0,
            "searchPeriod": "month",
            "indexesUsedThisMonth": 0,
            "indexLimit": None,
            "indexedVideosUsed": 0,
            "indexedVideoLimit": None,
            "indexedSecondsUsed": 0,
            "indexedSecondsLimit": None,
            "maxImportVideos": None,
            "maxSearchResults": None,
            "hasOwnKey": False,
            "apiKeyMode": get_api_key_mode(),
            "hasServerKey": bool(get_server_api_key()),
            "allowUserKeys": allow_user_keys(),
        }

    user_id = user["sub"]
    supabase = get_supabase()
    profile = get_user_profile(supabase, user_id)
    billing = resolve_user_entitlements(supabase, user_id, profile)
    entitlements = billing["entitlements"]
    period_usage = billing["usage"]
    billing_profile = billing.get("billingProfile") or {}
    has_own_key = bool(profile.get("api_key_enc"))
    searches_used = int(period_usage.get("retrievalCalls", 0) or 0)
    indexed_videos = profile.get("free_indexed_videos_total", 0)
    indexed_seconds = profile.get("free_indexed_seconds_total", 0)
    return {
        "plan": entitlements["planKey"],
        "planKey": entitlements["planKey"],
        "billingStatus": entitlements["billingStatus"],
        "currentPeriodStart": entitlements["periodStart"],
        "currentPeriodEnd": entitlements["periodEnd"],
        "cancelAtPeriodEnd": bool(billing_profile.get("cancel_at_period_end", False)),
        "searchesUsedToday": searches_used,
        "searchLimit": entitlements["monthlyRetrievalCalls"],
        "searchesUsedThisMonth": searches_used,
        "searchPeriod": "month",
        "indexesUsedThisMonth": indexed_videos,
        "indexLimit": entitlements["indexedVideosTotal"],
        "indexedVideosUsed": indexed_videos,
        "indexedVideoLimit": entitlements["indexedVideosTotal"],
        "indexedSecondsUsed": indexed_seconds,
        "indexedSecondsLimit": entitlements["libraryTranscriptSeconds"],
        "monthlyIndexedSecondsUsed": int(period_usage.get("indexedTranscriptSeconds", 0) or 0),
        "monthlyIndexedSecondsLimit": entitlements["monthlyIndexedTranscriptSeconds"],
        "deepIndexedSecondsUsed": int(period_usage.get("deepIndexedTranscriptSeconds", 0) or 0),
        "deepIndexedSecondsLimit": entitlements["deepTranscriptSeconds"],
        "maxImportVideos": entitlements["maxImportVideos"],
        "maxSearchResults": entitlements["maxSearchResults"],
        "maxActiveIngestionJobs": entitlements["maxActiveIngestionJobs"],
        "usagePackSecondsBalance": entitlements["usagePackSecondsBalance"],
        "priorityQueue": entitlements["priorityQueue"],
        "hasOwnKey": has_own_key,
        "apiKeyMode": get_api_key_mode(),
        "hasServerKey": bool(get_server_api_key()),
        "allowUserKeys": allow_user_keys(),
    }


@app.get("/api/ingestion-jobs")
async def ingestion_jobs_endpoint(user: dict = Depends(get_request_user)):
    """List recent durable ingestion jobs for the current user."""
    if not is_supabase_mode():
        return {"jobs": []}

    supabase = get_supabase()
    return {"jobs": list_ingestion_jobs(supabase, user["sub"])}


@app.delete("/api/ingestion-jobs/history")
async def clear_ingestion_jobs_history_endpoint(user: dict = Depends(get_request_user)):
    """Clear settled ingestion jobs for the current user."""
    if not is_supabase_mode():
        return {"deletedCount": 0}

    supabase = get_supabase()
    return {"deletedCount": clear_ingestion_job_history(supabase, user["sub"])}


@app.get("/api/ingestion-jobs/{job_id}")
async def ingestion_job_endpoint(job_id: str, user: dict = Depends(get_request_user)):
    """Fetch one durable ingestion job, scoped to the current user."""
    if not is_supabase_mode():
        raise HTTPException(
            status_code=404, detail="Ingestion jobs are only available in hosted mode"
        )

    supabase = get_supabase()
    job = get_ingestion_job(supabase, user["sub"], job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    return job


@app.get("/api/workflows/definitions")
async def workflow_definitions_endpoint(
    limit: int = 50,
    user: dict = Depends(get_request_user),
):
    """List visible platform workflow definitions."""
    if not is_supabase_mode():
        return {"workflowDefinitions": []}

    bounded_limit = max(1, min(limit, 100))
    return {
        "workflowDefinitions": list_workflow_definitions(get_supabase(), user["sub"], bounded_limit)
    }


@app.get("/api/workflows/instances")
async def workflow_instances_endpoint(
    limit: int = 20,
    user: dict = Depends(get_request_user),
):
    """List recent durable platform workflow instances for the current user."""
    if not is_supabase_mode():
        return {"workflowInstances": []}

    bounded_limit = max(1, min(limit, 50))
    return {
        "workflowInstances": list_workflow_instances(get_supabase(), user["sub"], bounded_limit)
    }


@app.get("/api/workflows/instances/{instance_id}")
async def workflow_instance_endpoint(instance_id: str, user: dict = Depends(get_request_user)):
    """Fetch one workflow instance with step and artifact details."""
    if not is_supabase_mode():
        raise HTTPException(status_code=404, detail="Workflows are only available in hosted mode")

    workflow = get_workflow_instance(get_supabase(), user["sub"], instance_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow instance not found")
    return workflow


@app.put("/api/settings/key")
async def save_api_key(request: ApiKeyRequest, user: dict = Depends(get_request_user)):
    """Save or update the user's Gemini API key."""
    if not allow_user_keys():
        raise HTTPException(
            status_code=403, detail="User API keys are disabled for this deployment"
        )

    if not is_supabase_mode():
        return {"success": True}

    user_id = user["sub"]
    supabase = get_supabase()
    supabase.table("profiles").update({"api_key_enc": encrypt_api_key(request.api_key)}).eq(
        "id", user_id
    ).execute()
    return {"success": True}


@app.delete("/api/settings/key")
async def delete_api_key(user: dict = Depends(get_request_user)):
    """Remove the user's stored Gemini API key."""
    if not allow_user_keys():
        raise HTTPException(
            status_code=403, detail="User API keys are disabled for this deployment"
        )

    if not is_supabase_mode():
        return {"success": True}

    user_id = user["sub"]
    supabase = get_supabase()
    supabase.table("profiles").update({"api_key_enc": None}).eq("id", user_id).execute()
    return {"success": True}


# Run with uvicorn if executed directly
if __name__ == "__main__":
    import io
    import sys

    import uvicorn

    # Fix Windows console encoding for Unicode
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    print("\n" + "=" * 60)
    print("  Memexai Backend")
    print("  YouTube Context Engine")
    print("=" * 60 + "\n")

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8080,
        reload=False,  # Disable to preserve singleton state (restart manually when needed)
        log_level="warning",  # Suppress routine request logs
    )
