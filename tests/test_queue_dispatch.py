import json

from backend import queue_dispatch
from backend.config import (
    INGESTION_DISPATCH_BACKGROUND,
    INGESTION_DISPATCH_CLOUDFLARE_QUEUE,
    get_cloudflare_queue_api_url,
    get_ingestion_dispatch_mode,
)
from backend.queue_dispatch import build_ingestion_queue_message, dispatch_ingestion_job


class BackgroundTasks:
    def __init__(self):
        self.tasks = []

    def add_task(self, fn, *args, **kwargs):
        self.tasks.append((fn, args, kwargs))


def test_build_ingestion_queue_message_is_versioned_and_minimal():
    message = build_ingestion_queue_message(
        {
            "id": "job-1",
            "user_id": "user-1",
            "source_url": "https://www.youtube.com/watch?v=uCKhOmth2ms",
            "source_type": "video",
            "status": "queued",
            "extra": "not forwarded",
        },
        source="mcp",
    )

    assert message == {
        "type": "ingestion_job.process",
        "version": 1,
        "source": "mcp",
        "job": {
            "id": "job-1",
            "user_id": "user-1",
            "source_url": "https://www.youtube.com/watch?v=uCKhOmth2ms",
            "source_type": "video",
            "status": "queued",
        },
    }


def test_background_dispatch_schedules_task():
    scheduled = BackgroundTasks()
    processed = []

    result = dispatch_ingestion_job(
        {"id": "job-1"},
        background_tasks=scheduled,
        processor=lambda job: processed.append(job),
        mode=INGESTION_DISPATCH_BACKGROUND,
    )

    assert result == {"mode": "background", "scheduled": True}
    assert len(scheduled.tasks) == 1
    assert processed == []


def test_background_dispatch_can_run_inline_without_background_tasks():
    processed = []

    result = dispatch_ingestion_job(
        {"id": "job-1"},
        processor=lambda job: processed.append(job),
        mode=INGESTION_DISPATCH_BACKGROUND,
    )

    assert result["ran_inline"] is True
    assert processed == [{"id": "job-1"}]


def test_cloudflare_queue_dispatch_publishes_message(monkeypatch):
    published = []

    monkeypatch.setattr(
        queue_dispatch,
        "publish_to_cloudflare_queue",
        lambda message: published.append(message) or {"success": True},
    )

    result = dispatch_ingestion_job(
        {"id": "job-1", "user_id": "user-1", "source_url": "https://youtu.be/x"},
        mode=INGESTION_DISPATCH_CLOUDFLARE_QUEUE,
        source="capture-sync",
    )

    assert result["mode"] == "cloudflare_queue"
    assert result["scheduled"] is True
    assert published[0]["source"] == "capture-sync"
    assert published[0]["job"]["id"] == "job-1"


def test_cloudflare_queue_api_url_can_be_built_from_account_and_queue(monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_INGESTION_QUEUE_API_URL", raising=False)
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "account-1")
    monkeypatch.setenv("CLOUDFLARE_INGESTION_QUEUE_ID", "queue-1")

    assert (
        get_cloudflare_queue_api_url()
        == "https://api.cloudflare.com/client/v4/accounts/account-1/queues/queue-1/messages"
    )


def test_ingestion_dispatch_mode_defaults_to_background(monkeypatch):
    monkeypatch.delenv("INGESTION_DISPATCH_MODE", raising=False)

    assert get_ingestion_dispatch_mode() == "background"


def test_publish_to_cloudflare_queue_uses_http_push_api(monkeypatch):
    requests = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"success":true}'

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return Response()

    monkeypatch.setenv("CLOUDFLARE_INGESTION_QUEUE_API_URL", "https://queue.example/messages")
    monkeypatch.setenv("CLOUDFLARE_QUEUES_API_TOKEN", "secret-token")
    monkeypatch.setattr(queue_dispatch.urllib.request, "urlopen", fake_urlopen)

    response = queue_dispatch.publish_to_cloudflare_queue({"type": "ingestion_job.process"})

    assert response == {"success": True}
    request, timeout = requests[0]
    assert timeout == 15
    assert request.full_url == "https://queue.example/messages"
    assert request.headers["Authorization"] == "Bearer secret-token"
    assert json.loads(request.data.decode("utf-8")) == {"body": {"type": "ingestion_job.process"}}
