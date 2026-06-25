"""Check whether hosted production-mode configuration is present.

This script intentionally reports only presence/placeholder status and never
prints secret values.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env.local"

REQUIRED_FRONTEND = [
    "VITE_AUTH_MODE",
    "VITE_API_URL",
    "VITE_SUPABASE_URL",
    "VITE_SUPABASE_ANON_KEY",
]

REQUIRED_BACKEND = [
    "SEARCHTUBE_STORAGE",
    "SEARCHTUBE_AUTH_MODE",
    "SEARCHTUBE_API_KEY_MODE",
    "SUPABASE_SERVICE_ROLE_KEY",
    "GEMINI_API_KEY",
    "API_KEY_ENCRYPTION_KEY",
    "MEMEXAI_APP_URL",
]

PRODUCTION_RECOMMENDED = [
    "SEARCHTUBE_ALLOWED_ORIGINS",
    "SUPABASE_JWT_SECRET",
]

QUEUE_BACKEND = [
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_INGESTION_QUEUE_ID",
    "CLOUDFLARE_QUEUES_API_TOKEN",
]

WORKFLOW_BACKEND = [
    "WORKFLOW_INTERNAL_SECRET",
]

PLACEHOLDER_MARKERS = (
    "your-",
    "replace-with",
    "placeholder",
    "example.com",
    "your-project",
)


def load_dotenv_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get_value(name: str, file_values: dict[str, str]) -> str:
    return os.getenv(name, file_values.get(name, "")).strip()


def is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def check_group(title: str, names: list[str], file_values: dict[str, str]) -> list[str]:
    problems: list[str] = []
    print(f"\n{title}")
    for name in names:
        value = get_value(name, file_values)
        if not value:
            print(f"  [missing] {name}")
            problems.append(f"{name} is missing")
        elif is_placeholder(value):
            print(f"  [placeholder] {name}")
            problems.append(f"{name} still has a placeholder value")
        else:
            print(f"  [set] {name}")
    return problems


def check_alternative(
    title: str,
    label: str,
    names: list[str],
    file_values: dict[str, str],
) -> list[str]:
    print(f"\n{title}")
    for name in names:
        value = get_value(name, file_values)
        if value and not is_placeholder(value):
            print(f"  [set] {label} via {name}")
            return []
        if value:
            print(f"  [placeholder] {name}")
        else:
            print(f"  [missing] {name}")
    return [f"{label} is missing"]


def check_recommended_group(title: str, names: list[str], file_values: dict[str, str]) -> list[str]:
    warnings: list[str] = []
    print(f"\n{title}")
    for name in names:
        value = get_value(name, file_values)
        if not value:
            print(f"  [recommended] {name}")
            warnings.append(f"{name} is recommended before production deploy")
        elif is_placeholder(value):
            print(f"  [placeholder] {name}")
            warnings.append(f"{name} still has a placeholder value")
        else:
            print(f"  [set] {name}")
    return warnings


def main() -> int:
    file_values = load_dotenv_file(ENV_FILE)

    print("Hosted production readiness check")
    print(f"Env file: {ENV_FILE if ENV_FILE.exists() else 'not found'}")

    problems = []
    warnings = []
    problems.extend(check_group("Frontend build env", REQUIRED_FRONTEND, file_values))
    problems.extend(check_group("Backend runtime env", REQUIRED_BACKEND, file_values))
    problems.extend(
        check_alternative(
            "Backend Supabase anon key",
            "Supabase anon key",
            ["SUPABASE_ANON_KEY", "VITE_SUPABASE_ANON_KEY"],
            file_values,
        )
    )

    storage = get_value("SEARCHTUBE_STORAGE", file_values)
    auth = get_value("SEARCHTUBE_AUTH_MODE", file_values)
    api_key_mode = get_value("SEARCHTUBE_API_KEY_MODE", file_values)
    vite_auth = get_value("VITE_AUTH_MODE", file_values)
    ingestion_dispatch_mode = get_value("INGESTION_DISPATCH_MODE", file_values) or "background"

    warnings.extend(
        check_recommended_group("Production hardening env", PRODUCTION_RECOMMENDED, file_values)
    )
    if ingestion_dispatch_mode == "cloudflare_queue":
        problems.extend(check_group("Cloudflare queue env", QUEUE_BACKEND, file_values))
    elif ingestion_dispatch_mode not in {"background", "cloudflare_queue"}:
        problems.append("INGESTION_DISPATCH_MODE should be 'background' or 'cloudflare_queue'")

    if get_value("WORKFLOW_INTERNAL_SECRET", file_values):
        problems.extend(check_group("Workflow bridge env", WORKFLOW_BACKEND, file_values))

    expected_values = {
        "SEARCHTUBE_STORAGE": (storage, "supabase"),
        "SEARCHTUBE_AUTH_MODE": (auth, "supabase"),
        "SEARCHTUBE_API_KEY_MODE": (api_key_mode, "server"),
        "VITE_AUTH_MODE": (vite_auth, "supabase"),
    }
    for name, (actual, expected) in expected_values.items():
        if actual and actual != expected:
            problems.append(f"{name} should be {expected!r} for this hosted fork")

    if problems:
        print("\nNot ready:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    if warnings:
        print("\nReady for hosted-mode local smoke testing, with production follow-ups:")
        for warning in warnings:
            print(f"  - {warning}")
        print(
            "  - Complete an interactive Google OAuth sign-in check before calling auth e2e done."
        )
        return 0

    print("\nReady for hosted-mode local smoke testing.")
    print("Manual Google OAuth sign-in verification is still required for auth e2e.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
