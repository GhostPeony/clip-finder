import json

from backend import queue_consumer
from backend.queue_consumer import (
    CloudflarePullQueueClient,
    QueueConsumerError,
    check_consumer_configuration,
    consume_once,
    main,
    normalize_queue_message_body,
    process_ingestion_queue_message,
    supervised_consume_once,
)


def _message(job_id="job-1", lease_id="lease-1"):
    return {
        "lease_id": lease_id,
        "body": {
            "type": "ingestion_job.process",
            "version": 1,
            "source": "mcp",
            "job": {
                "id": job_id,
                "user_id": "user-1",
                "source_url": "https://www.youtube.com/watch?v=uCKhOmth2ms",
                "source_type": "video",
                "status": "queued",
            },
        },
    }


class FakeClient:
    def __init__(self, messages):
        self.messages = messages
        self.ack_calls = []

    def pull_messages(self, batch_size, visibility_timeout_ms):
        self.pull_args = (batch_size, visibility_timeout_ms)
        return self.messages

    def acknowledge(self, ack_lease_ids, retry_lease_ids):
        self.ack_calls.append((ack_lease_ids, retry_lease_ids))
        return {"success": True}


class BrokenClient:
    def pull_messages(self, batch_size, visibility_timeout_ms):
        del batch_size, visibility_timeout_ms
        raise RuntimeError("queue unavailable")


def test_normalize_queue_message_body_accepts_json_and_nested_body():
    body = normalize_queue_message_body(json.dumps({"body": _message()["body"]}))

    assert body["type"] == "ingestion_job.process"
    assert body["job"]["id"] == "job-1"


def test_process_ingestion_queue_message_validates_and_processes_job():
    processed = []

    result = process_ingestion_queue_message(
        _message(),
        processor=lambda job: processed.append(job) or {"status": "completed"},
    )

    assert result == {"status": "completed"}
    assert processed[0]["id"] == "job-1"


def test_process_ingestion_queue_message_rejects_unknown_type():
    bad_message = _message()
    bad_message["body"]["type"] = "unknown"

    try:
        process_ingestion_queue_message(bad_message)
    except QueueConsumerError as exc:
        assert "Unsupported" in str(exc)
    else:
        raise AssertionError("expected unsupported queue message to fail")


def test_consume_once_acks_successes_and_retries_failures():
    client = FakeClient([_message("job-1", "lease-1"), _message("job-2", "lease-2")])

    def processor(job):
        if job["id"] == "job-2":
            raise RuntimeError("boom")
        return {"ok": True}

    summary = consume_once(
        client,
        processor=processor,
        batch_size=2,
        visibility_timeout_ms=6000,
    )

    assert summary == {"pulled": 2, "acked": 1, "retried": 1}
    assert client.pull_args == (2, 6000)
    assert client.ack_calls == [(["lease-1"], ["lease-2"])]


def test_consume_once_skips_ack_when_queue_is_empty():
    client = FakeClient([])

    summary = consume_once(client, processor=lambda job: job)

    assert summary == {"pulled": 0, "acked": 0, "retried": 0}
    assert client.ack_calls == []


def test_supervised_consume_once_reports_infrastructure_failures():
    result = supervised_consume_once(BrokenClient())

    assert result == {
        "ok": False,
        "summary": {"pulled": 0, "acked": 0, "retried": 0},
        "error": "queue unavailable",
    }


def test_queue_consumer_healthcheck_validates_config_without_network(monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_INGESTION_QUEUE_API_URL", raising=False)
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "account-1")
    monkeypatch.setenv("CLOUDFLARE_INGESTION_QUEUE_ID", "queue-1")
    monkeypatch.setenv("CLOUDFLARE_QUEUES_API_TOKEN", "secret-token")

    result = check_consumer_configuration()

    assert result == {
        "ok": True,
        "pullUrlConfigured": True,
        "ackUrlConfigured": True,
        "apiTokenConfigured": True,
    }


def test_queue_consumer_healthcheck_cli_returns_clean_failure(monkeypatch, capsys):
    monkeypatch.delenv("CLOUDFLARE_INGESTION_QUEUE_API_URL", raising=False)
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("CLOUDFLARE_INGESTION_QUEUE_ID", raising=False)
    monkeypatch.delenv("CLOUDFLARE_QUEUES_API_TOKEN", raising=False)

    exit_code = main(["--healthcheck"])

    assert exit_code == 1
    assert "Queue consumer configuration invalid" in capsys.readouterr().out


def test_pull_client_uses_cloudflare_pull_and_ack_endpoints(monkeypatch):
    requests = []
    fake_token = "token"  # noqa: S105 - unit-test placeholder, not a real credential.

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(self.payload).encode("utf-8")

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        if request.full_url.endswith("/pull"):
            return Response(
                {
                    "success": True,
                    "result": {"messages": [_message()]},
                }
            )
        return Response({"success": True})

    monkeypatch.setattr(queue_consumer.urllib.request, "urlopen", fake_urlopen)
    client = CloudflarePullQueueClient(
        pull_url="https://queue.example/messages/pull",
        ack_url="https://queue.example/messages/ack",
        api_token=fake_token,
    )

    messages = client.pull_messages(batch_size=50, visibility_timeout_ms=6000)
    ack = client.acknowledge(["lease-1"], [])

    assert messages[0]["lease_id"] == "lease-1"
    assert ack == {"success": True}
    pull_request = requests[0][0]
    ack_request = requests[1][0]
    assert pull_request.headers["Authorization"] == "Bearer token"
    assert json.loads(pull_request.data.decode("utf-8")) == {
        "batch_size": 50,
        "visibility_timeout_ms": 6000,
    }
    assert json.loads(ack_request.data.decode("utf-8")) == {
        "acks": [{"lease_id": "lease-1"}],
        "retries": [],
    }
