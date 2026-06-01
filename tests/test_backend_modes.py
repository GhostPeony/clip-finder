import importlib

from fastapi.testclient import TestClient


def test_backend_server_importable_from_package():
    module = importlib.import_module("backend.server")

    assert module.app.title == "SearchTube API"


def test_config_endpoint_defaults_to_local_mode(monkeypatch):
    monkeypatch.delenv("SEARCHTUBE_STORAGE", raising=False)
    monkeypatch.delenv("SEARCHTUBE_AUTH_MODE", raising=False)

    from backend.server import app

    client = TestClient(app)
    response = client.get("/api/config")

    assert response.status_code == 200
    assert response.json()["storage"] == "local"
    assert response.json()["authMode"] == "none"


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
    from backend.rag import _is_near_existing_clip

    existing = [{
        "videoId": "abc123",
        "startSeconds": 180,
        "endSeconds": 240,
    }]

    assert _is_near_existing_clip({
        "youtube_video_id": "abc123",
        "start_seconds": 220,
        "end_seconds": 280,
    }, existing)
    assert not _is_near_existing_clip({
        "youtube_video_id": "abc123",
        "start_seconds": 420,
        "end_seconds": 480,
    }, existing)
