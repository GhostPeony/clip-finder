import importlib
from io import BytesIO
from urllib.error import HTTPError


def _readiness_module():
    return importlib.import_module("scripts.check_hosted_readiness")


def _clear_readiness_env(monkeypatch, readiness):
    for name in (
        *readiness.REQUIRED_FRONTEND,
        *readiness.REQUIRED_BACKEND,
        *readiness.PRODUCTION_RECOMMENDED,
        "SUPABASE_ANON_KEY",
        "VITE_SUPABASE_ANON_KEY",
        "API_KEY_ENCRYPTION_KEY",
        "INGESTION_DISPATCH_MODE",
        "WORKFLOW_INTERNAL_SECRET",
        *readiness.QUEUE_BACKEND,
        *readiness.WORKFLOW_BACKEND,
    ):
        monkeypatch.delenv(name, raising=False)


def test_hosted_readiness_accepts_vite_anon_key_for_local_smoke(
    tmp_path,
    monkeypatch,
    capsys,
):
    readiness = _readiness_module()
    _clear_readiness_env(monkeypatch, readiness)
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "\n".join(
            [
                "VITE_AUTH_MODE=supabase",
                "VITE_API_URL=http://localhost:8000",
                "VITE_SUPABASE_URL=https://example.supabase.co",
                "VITE_SUPABASE_ANON_KEY=anon-key",
                "SEARCHTUBE_STORAGE=supabase",
                "SEARCHTUBE_AUTH_MODE=supabase",
                "SEARCHTUBE_API_KEY_MODE=server",
                "SUPABASE_SERVICE_ROLE_KEY=service-role",
                "GEMINI_API_KEY=gemini-key",
                "API_KEY_ENCRYPTION_KEY=encryption-key",
                "MEMEXAI_APP_URL=https://memexai.example",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(readiness, "ENV_FILE", env_file)

    assert readiness.main() == 0
    output = capsys.readouterr().out
    assert "[set] Supabase anon key via VITE_SUPABASE_ANON_KEY" in output
    assert "Ready for hosted-mode local smoke testing" in output
    assert "SUPABASE_JWT_SECRET is recommended before production deploy" in output


def test_hosted_readiness_requires_encryption_key_for_hybrid_mode(
    tmp_path,
    monkeypatch,
):
    readiness = _readiness_module()
    _clear_readiness_env(monkeypatch, readiness)
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "\n".join(
            [
                "VITE_AUTH_MODE=supabase",
                "VITE_API_URL=http://localhost:8000",
                "VITE_SUPABASE_URL=https://example.supabase.co",
                "VITE_SUPABASE_ANON_KEY=anon-key",
                "SEARCHTUBE_STORAGE=supabase",
                "SEARCHTUBE_AUTH_MODE=supabase",
                "SEARCHTUBE_API_KEY_MODE=hybrid",
                "SUPABASE_SERVICE_ROLE_KEY=service-role",
                "GEMINI_API_KEY=gemini-key",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(readiness, "ENV_FILE", env_file)

    assert readiness.main() == 1


def test_hosted_readiness_fails_without_any_anon_key(tmp_path, monkeypatch):
    readiness = _readiness_module()
    _clear_readiness_env(monkeypatch, readiness)
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "\n".join(
            [
                "VITE_AUTH_MODE=supabase",
                "VITE_API_URL=http://localhost:8000",
                "VITE_SUPABASE_URL=https://example.supabase.co",
                "SEARCHTUBE_STORAGE=supabase",
                "SEARCHTUBE_AUTH_MODE=supabase",
                "SEARCHTUBE_API_KEY_MODE=server",
                "SUPABASE_SERVICE_ROLE_KEY=service-role",
                "GEMINI_API_KEY=gemini-key",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(readiness, "ENV_FILE", env_file)

    assert readiness.main() == 1


def test_hosted_smoke_google_oauth_probe_passes_on_redirect(monkeypatch):
    smoke = importlib.import_module("scripts.smoke_hosted_mode")

    class Response:
        status = 302
        headers = {"location": "https://accounts.google.com/o/oauth2/v2/auth"}

    class Opener:
        def open(self, request, timeout):
            return Response()

    monkeypatch.setattr(smoke, "build_opener", lambda *_args: Opener())

    result = smoke.check_google_oauth_provider("https://example.supabase.co/")

    assert result.ok is True
    assert result.name == "Google OAuth provider"


def test_hosted_smoke_schema_checks_cover_ftue_and_mcp_oauth():
    smoke = importlib.import_module("scripts.smoke_hosted_mode")

    assert ("profiles", "onboarding_step") in smoke.SCHEMA_CHECKS
    assert ("mcp_oauth_clients", "client_id") in smoke.SCHEMA_CHECKS
    assert ("mcp_oauth_authorization_codes", "code_hash") in smoke.SCHEMA_CHECKS
    assert ("youtube_oauth_connections", "user_id") in smoke.SCHEMA_CHECKS


def test_hosted_smoke_google_oauth_probe_reports_disabled_provider(monkeypatch):
    smoke = importlib.import_module("scripts.smoke_hosted_mode")

    class Opener:
        def open(self, request, timeout):
            raise HTTPError(
                request.full_url,
                400,
                "Bad Request",
                {},
                BytesIO(b'{"msg":"Unsupported provider: provider is not enabled"}'),
            )

    monkeypatch.setattr(smoke, "build_opener", lambda *_args: Opener())

    result = smoke.check_google_oauth_provider("https://example.supabase.co")

    assert result.ok is False
    assert "Unsupported provider" in result.detail
