"""Smoke-test hosted-mode wiring without printing secret values.

This script checks the local FastAPI app in Supabase mode, verifies that the
linked Supabase schema exposes the tables used by the agent/MCP path, and probes
whether Google OAuth is enabled for an interactive sign-in attempt.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

from dotenv import load_dotenv
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env.local"
LOCAL_REDIRECT = "http://localhost:3000"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCHEMA_CHECKS = [
    ("profiles", "onboarding_step"),
    ("mcp_tokens", "user_id"),
    ("mcp_oauth_clients", "client_id"),
    ("mcp_oauth_authorization_codes", "code_hash"),
    ("source_labels", "id"),
    ("transcript_lines", "id"),
    ("user_videos", "user_id"),
    ("workflow_instances", "id"),
    ("youtube_capture_sources", "id"),
    ("youtube_oauth_connections", "user_id"),
]


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


def _print_check(check: Check) -> None:
    status = "ok" if check.ok else "fail"
    print(f"  [{status}] {check.name}: {check.detail}")


def check_public_api() -> list[Check]:
    from backend.server import app

    client = TestClient(app)
    checks: list[Check] = []

    health = client.get("/")
    checks.append(Check("health", health.status_code == 200, f"HTTP {health.status_code}"))

    config = client.get("/api/config")
    config_json = config.json() if config.status_code == 200 else {}
    checks.append(
        Check(
            "public config",
            config.status_code == 200
            and config_json.get("storage") == "supabase"
            and config_json.get("authMode") == "supabase",
            f"HTTP {config.status_code}; storage={config_json.get('storage')}; auth={config_json.get('authMode')}",
        )
    )

    manifest = client.get("/mcp.json")
    manifest_json = manifest.json() if manifest.status_code == 200 else {}
    tool_names = {tool.get("name") for tool in manifest_json.get("tools", [])}
    checks.append(
        Check(
            "MCP manifest",
            manifest.status_code == 200
            and "get_mcp_session" in tool_names
            and "build_agent_brief" in tool_names,
            f"HTTP {manifest.status_code}; tools={len(tool_names)}",
        )
    )

    llms = client.get("/llms.txt")
    checks.append(
        Check(
            "agent guide",
            llms.status_code == 200 and "repoFit.targetMap" in llms.text,
            f"HTTP {llms.status_code}",
        )
    )
    return checks


def check_supabase_schema() -> list[Check]:
    from backend.db import get_supabase

    supabase = get_supabase()
    checks = []
    for table_name, select_column in SCHEMA_CHECKS:
        try:
            supabase.table(table_name).select(select_column).limit(1).execute()
            checks.append(Check(f"schema {table_name}", True, "select ok"))
        except Exception as exc:  # pragma: no cover - detail is useful in live smoke output.
            checks.append(Check(f"schema {table_name}", False, type(exc).__name__))
    return checks


def check_google_oauth_provider(base_url: str) -> Check:
    if not base_url:
        return Check("Google OAuth provider", False, "VITE_SUPABASE_URL is missing")

    authorize_url = (
        f"{base_url.rstrip('/')}/auth/v1/authorize"
        f"?provider=google&redirect_to={quote(LOCAL_REDIRECT, safe='')}"
    )
    opener = build_opener(NoRedirect)
    try:
        response = opener.open(Request(authorize_url, method="GET"), timeout=10)
        location = response.headers.get("location", "")
        return Check(
            "Google OAuth provider",
            response.status in {302, 303} and bool(location),
            f"HTTP {response.status}",
        )
    except HTTPError as exc:
        location = exc.headers.get("location", "")
        if exc.code in {302, 303} and location:
            return Check("Google OAuth provider", True, f"redirect HTTP {exc.code}")
        body = exc.read(500).decode("utf-8", errors="replace")
        try:
            payload = json.loads(body)
            message = payload.get("msg") or payload.get("message") or payload.get("error") or body
        except json.JSONDecodeError:
            message = body
        return Check("Google OAuth provider", False, f"HTTP {exc.code}: {message}")
    except (TimeoutError, URLError) as exc:
        return Check("Google OAuth provider", False, type(exc).__name__)


def main() -> int:
    load_dotenv(ENV_FILE)
    print("Hosted-mode smoke test")
    print(f"Env file: {ENV_FILE if ENV_FILE.exists() else 'not found'}")

    all_checks: list[Check] = []
    print("\nLocal FastAPI public surfaces")
    public_checks = check_public_api()
    for check in public_checks:
        _print_check(check)
    all_checks.extend(public_checks)

    print("\nLinked Supabase schema")
    schema_checks = check_supabase_schema()
    for check in schema_checks:
        _print_check(check)
    all_checks.extend(schema_checks)

    print("\nSupabase auth provider")
    auth_check = check_google_oauth_provider(os.getenv("VITE_SUPABASE_URL", ""))
    _print_check(auth_check)
    all_checks.append(auth_check)

    failures = [check for check in all_checks if not check.ok]
    if failures:
        print("\nHosted-mode smoke failed:")
        for failure in failures:
            print(f"  - {failure.name}: {failure.detail}")
        return 1

    print("\nHosted-mode smoke passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
