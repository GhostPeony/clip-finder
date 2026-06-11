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
    "SEARCHTUBE_ALLOWED_ORIGINS",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_JWT_SECRET",
    "API_KEY_ENCRYPTION_KEY",
    "GEMINI_API_KEY",
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


def main() -> int:
    file_values = load_dotenv_file(ENV_FILE)

    print("Hosted production readiness check")
    print(f"Env file: {ENV_FILE if ENV_FILE.exists() else 'not found'}")

    problems = []
    problems.extend(check_group("Frontend build env", REQUIRED_FRONTEND, file_values))
    problems.extend(check_group("Backend runtime env", REQUIRED_BACKEND, file_values))

    storage = get_value("SEARCHTUBE_STORAGE", file_values)
    auth = get_value("SEARCHTUBE_AUTH_MODE", file_values)
    api_key_mode = get_value("SEARCHTUBE_API_KEY_MODE", file_values)
    vite_auth = get_value("VITE_AUTH_MODE", file_values)

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

    print("\nReady for hosted-mode local smoke testing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
