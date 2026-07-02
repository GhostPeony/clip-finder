"""OAuth helpers for native MCP client onboarding."""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

try:
    from .mcp_tokens import ALLOWED_MCP_SCOPES, DEFAULT_MCP_SCOPES, create_mcp_token
except ImportError:
    from mcp_tokens import ALLOWED_MCP_SCOPES, DEFAULT_MCP_SCOPES, create_mcp_token

CLIENT_TABLE = "mcp_oauth_clients"
CODE_TABLE = "mcp_oauth_authorization_codes"
AUTH_CODE_TTL_SECONDS = 600
ACCESS_TOKEN_TTL_SECONDS = 30 * 24 * 60 * 60


def authorization_server_metadata(base_url: str) -> dict:
    issuer = base_url.rstrip("/")
    return {
        "issuer": issuer,
        "authorization_endpoint": f"{issuer}/oauth/authorize",
        "token_endpoint": f"{issuer}/oauth/token",
        "registration_endpoint": f"{issuer}/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": ALLOWED_MCP_SCOPES,
    }


def protected_resource_metadata(base_url: str) -> dict:
    server = base_url.rstrip("/")
    return {
        "resource": f"{server}/mcp",
        "authorization_servers": [server],
        "scopes_supported": ALLOWED_MCP_SCOPES,
        "bearer_methods_supported": ["header"],
        "resource_documentation": f"{server}/llms.txt",
    }


def register_oauth_client(supabase: Any, payload: dict) -> dict:
    redirect_uris = payload.get("redirect_uris") or []
    if not isinstance(redirect_uris, list) or not redirect_uris:
        raise ValueError("redirect_uris must include at least one URI")

    clean_redirects = [_validate_redirect_uri(uri) for uri in redirect_uris]
    client_id = f"memexai_mcp_{secrets.token_urlsafe(24)}"
    client_name = _clean_text(payload.get("client_name"), "MCP client", 120)
    row = {
        "client_id": client_id,
        "client_name": client_name,
        "redirect_uris": clean_redirects,
        "client_uri": _clean_optional_url(payload.get("client_uri")),
        "logo_uri": _clean_optional_url(payload.get("logo_uri")),
        "metadata": {
            "token_endpoint_auth_method": payload.get("token_endpoint_auth_method", "none"),
            "grant_types": payload.get("grant_types", ["authorization_code"]),
            "response_types": payload.get("response_types", ["code"]),
        },
    }
    supabase.table(CLIENT_TABLE).insert(row).execute()
    return {
        "client_id": client_id,
        "client_id_issued_at": int(time.time()),
        "client_name": client_name,
        "redirect_uris": clean_redirects,
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }


def validate_authorization_request(supabase: Any, params: dict) -> dict:
    client_id = _required(params, "client_id")
    redirect_uri = _required(params, "redirect_uri")
    response_type = _required(params, "response_type")
    code_challenge = _required(params, "code_challenge")
    code_challenge_method = params.get("code_challenge_method") or "S256"

    if response_type != "code":
        raise ValueError("response_type must be code")
    if code_challenge_method != "S256":
        raise ValueError("code_challenge_method must be S256")

    client = get_oauth_client(supabase, client_id)
    if not client:
        raise ValueError("Unknown OAuth client")
    if redirect_uri not in (client.get("redirect_uris") or []):
        raise ValueError("redirect_uri is not registered for this client")

    return {
        "client": client,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": response_type,
        "scope": _clean_scopes(params.get("scope")),
        "state": params.get("state") or "",
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "resource": params.get("resource"),
    }


def create_authorization_redirect(supabase: Any, user_id: str, params: dict) -> str:
    request = validate_authorization_request(supabase, params)
    raw_code = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=AUTH_CODE_TTL_SECONDS)
    row = {
        "code_hash": _hash_value(raw_code),
        "user_id": user_id,
        "client_id": request["client_id"],
        "redirect_uri": request["redirect_uri"],
        "code_challenge": request["code_challenge"],
        "code_challenge_method": request["code_challenge_method"],
        "scopes": request["scope"],
        "resource": request.get("resource"),
        "expires_at": expires_at.isoformat(),
    }
    supabase.table(CODE_TABLE).insert(row).execute()
    query = {"code": raw_code}
    if request.get("state"):
        query["state"] = request["state"]
    return f"{request['redirect_uri']}?{urlencode(query)}"


def exchange_authorization_code(supabase: Any, payload: dict) -> dict:
    grant_type = _required(payload, "grant_type")
    if grant_type != "authorization_code":
        raise ValueError("grant_type must be authorization_code")

    code = _required(payload, "code")
    client_id = _required(payload, "client_id")
    redirect_uri = _required(payload, "redirect_uri")
    code_verifier = _required(payload, "code_verifier")

    now = datetime.now(timezone.utc)
    code_hash = _hash_value(code)
    # Consume the code atomically before minting: the conditional update claims
    # an unconsumed row exactly once, so concurrent exchanges cannot double-mint.
    consumed = (
        supabase.table(CODE_TABLE)
        .update({"consumed_at": now.isoformat()})
        .eq("code_hash", code_hash)
        .is_("consumed_at", "null")
        .execute()
    )
    record = _first(consumed)
    if not record:
        existing = _first(
            supabase.table(CODE_TABLE)
            .select("consumed_at")
            .eq("code_hash", code_hash)
            .maybe_single()
            .execute()
        )
        if existing:
            raise ValueError("Authorization code already consumed")
        raise ValueError("Invalid authorization code")

    if _is_expired(record.get("expires_at")):
        raise ValueError("Authorization code expired")
    if record.get("client_id") != client_id:
        raise ValueError("client_id does not match authorization code")
    if record.get("redirect_uri") != redirect_uri:
        raise ValueError("redirect_uri does not match authorization code")

    expected_challenge = _pkce_s256(code_verifier)
    if expected_challenge != record.get("code_challenge"):
        raise ValueError("Invalid code_verifier")

    client = get_oauth_client(supabase, client_id) or {}
    expires_at = now + timedelta(seconds=ACCESS_TOKEN_TTL_SECONDS)
    token = create_mcp_token(
        supabase,
        record["user_id"],
        name=client.get("client_name") or "OAuth MCP client",
        scopes=record.get("scopes") or DEFAULT_MCP_SCOPES,
        expires_at=expires_at.isoformat(),
        oauth_client_id=client_id,
    )
    supabase.table(CLIENT_TABLE).update({"last_used_at": now.isoformat()}).eq(
        "client_id", client_id
    ).execute()

    scopes = token["record"].get("scopes") or DEFAULT_MCP_SCOPES
    return {
        "access_token": token["token"],
        "token_type": "Bearer",
        "expires_in": ACCESS_TOKEN_TTL_SECONDS,
        "scope": " ".join(scopes),
    }


def parse_oauth_token_body(content_type: str | None, body: bytes) -> dict:
    content_type = content_type or ""
    if "application/x-www-form-urlencoded" in content_type:
        parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
        return {key: values[-1] if values else "" for key, values in parsed.items()}
    if "application/json" in content_type:
        import json

        return json.loads(body.decode("utf-8"))
    parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


def get_oauth_client(supabase: Any, client_id: str) -> dict | None:
    result = (
        supabase.table(CLIENT_TABLE).select("*").eq("client_id", client_id).maybe_single().execute()
    )
    return _first(result)


def _validate_redirect_uri(uri: str) -> str:
    cleaned = str(uri or "").strip()
    parsed = urlparse(cleaned)
    if parsed.scheme == "https" and parsed.netloc:
        return cleaned
    if parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
        return cleaned
    raise ValueError("redirect_uris must use https or localhost loopback http")


def _clean_optional_url(value: Any) -> str | None:
    if not value:
        return None
    parsed = urlparse(str(value).strip())
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        return None
    return str(value).strip()


def _clean_text(value: Any, fallback: str, max_length: int) -> str:
    cleaned = " ".join(str(value or "").split())[:max_length].strip()
    return cleaned or fallback


def _clean_scopes(value: Any) -> list[str]:
    if isinstance(value, str):
        requested = value.replace(",", " ").split()
    elif isinstance(value, list):
        requested = [str(scope) for scope in value]
    else:
        requested = []
    if not requested:
        return list(DEFAULT_MCP_SCOPES)
    allowed = set(ALLOWED_MCP_SCOPES)
    cleaned = [scope for scope in requested if scope in allowed]
    if not cleaned:
        raise ValueError(
            "invalid_scope: none of the requested scopes are supported "
            f"(supported: {' '.join(ALLOWED_MCP_SCOPES)})"
        )
    return cleaned


def _required(params: dict, name: str) -> str:
    value = params.get(name)
    if value is None or str(value).strip() == "":
        raise ValueError(f"{name} is required")
    return str(value)


def _hash_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _pkce_s256(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _is_expired(value: str | None) -> bool:
    if not value:
        return True
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized) <= datetime.now(timezone.utc)
    except ValueError:
        return True


def _rows(result: Any) -> list[dict]:
    data = getattr(result, "data", None)
    if data is None:
        return []
    if isinstance(data, list):
        return data
    return [data]


def _first(result: Any) -> dict | None:
    rows = _rows(result)
    return rows[0] if rows else None
