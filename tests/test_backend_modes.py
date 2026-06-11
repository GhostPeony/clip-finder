import importlib

from fastapi.testclient import TestClient


def test_backend_server_importable_from_package():
    module = importlib.import_module("backend.server")

    assert module.app.title == "SearchTube API"


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


def test_ingestion_jobs_endpoint_is_empty_in_local_mode(monkeypatch):
    monkeypatch.setenv("SEARCHTUBE_STORAGE", "local")
    monkeypatch.setenv("SEARCHTUBE_AUTH_MODE", "none")

    from backend.server import app

    client = TestClient(app)
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


def test_storage_dispatch_uses_local_ingestion(monkeypatch):
    from backend import storage

    monkeypatch.setenv("SEARCHTUBE_STORAGE", "local")
    monkeypatch.setattr(
        storage,
        "ingest_url_local",
        lambda url, api_key=None: iter([f"local:{url}:{api_key}"]),
    )

    assert list(storage.ingest_url("https://youtu.be/dQw4w9WgXcQ", api_key="key")) == [
        "local:https://youtu.be/dQw4w9WgXcQ:key"
    ]


def test_supabase_search_groups_nearby_duplicate_chunks():
    # Dedupe logic is shared by both storage modes via clip_selection.
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
