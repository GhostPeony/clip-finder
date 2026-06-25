"""Cloudflare Queue pull consumer for hosted ingestion jobs."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Callable

try:
    from .config import (
        get_cloudflare_queue_ack_api_url,
        get_cloudflare_queue_api_token,
        get_cloudflare_queue_pull_api_url,
    )
    from .hosted_ingestion import process_hosted_ingestion_job
except ImportError:
    from config import (
        get_cloudflare_queue_ack_api_url,
        get_cloudflare_queue_api_token,
        get_cloudflare_queue_pull_api_url,
    )
    from hosted_ingestion import process_hosted_ingestion_job

EXPECTED_INGESTION_MESSAGE_TYPE = "ingestion_job.process"
SUPPORTED_INGESTION_MESSAGE_VERSION = 1
DEFAULT_PULL_BATCH_SIZE = 1
DEFAULT_VISIBILITY_TIMEOUT_MS = 3_600_000
DEFAULT_IDLE_SLEEP_SECONDS = 5.0
DEFAULT_ERROR_SLEEP_SECONDS = 10.0
DEFAULT_MAX_CONSECUTIVE_ERRORS = 10

QueueProcessor = Callable[[dict], Any]


class QueueConsumerError(Exception):
    """Raised when a queue message cannot be consumed safely."""


class CloudflarePullQueueClient:
    """Small HTTP client for Cloudflare Queues pull consumers."""

    def __init__(
        self,
        pull_url: str | None = None,
        ack_url: str | None = None,
        api_token: str | None = None,
    ):
        self.pull_url = pull_url or get_cloudflare_queue_pull_api_url()
        self.ack_url = ack_url or get_cloudflare_queue_ack_api_url()
        self.api_token = api_token or get_cloudflare_queue_api_token()

    def pull_messages(
        self,
        batch_size: int = DEFAULT_PULL_BATCH_SIZE,
        visibility_timeout_ms: int = DEFAULT_VISIBILITY_TIMEOUT_MS,
    ) -> list[dict]:
        """Pull a short-polled message batch from Cloudflare Queues."""
        payload = {
            "batch_size": max(1, min(int(batch_size), 100)),
            "visibility_timeout_ms": max(1, int(visibility_timeout_ms)),
        }
        response = self._post_json(self.pull_url, payload)
        result = response.get("result", {}) if isinstance(response, dict) else {}
        messages = result.get("messages", [])
        return messages if isinstance(messages, list) else []

    def acknowledge(self, ack_lease_ids: list[str], retry_lease_ids: list[str]) -> dict:
        """Acknowledge processed messages and retry failed messages."""
        payload = {
            "acks": [{"lease_id": lease_id} for lease_id in ack_lease_ids],
            "retries": [{"lease_id": lease_id} for lease_id in retry_lease_ids],
        }
        return self._post_json(self.ack_url, payload)

    def _post_json(self, url: str, payload: dict) -> dict:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Cloudflare Queue request failed: HTTP {exc.code} {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Cloudflare Queue request failed: {exc.reason}") from exc

        parsed = json.loads(raw_body or "{}")
        if parsed.get("success") is not True:
            raise RuntimeError(f"Cloudflare Queue request failed: {parsed}")
        return parsed


def process_ingestion_queue_message(
    queue_message: dict,
    processor: QueueProcessor = process_hosted_ingestion_job,
) -> Any:
    """Validate and process one pulled Cloudflare Queue message."""
    envelope = normalize_queue_message_body(queue_message.get("body", queue_message))
    if envelope.get("type") != EXPECTED_INGESTION_MESSAGE_TYPE:
        raise QueueConsumerError("Unsupported queue message type")
    if envelope.get("version") != SUPPORTED_INGESTION_MESSAGE_VERSION:
        raise QueueConsumerError("Unsupported queue message version")

    job = envelope.get("job")
    if not isinstance(job, dict):
        raise QueueConsumerError("Queue message is missing job payload")
    if not isinstance(job.get("id"), str) or not isinstance(job.get("user_id"), str):
        raise QueueConsumerError("Queue message job payload is missing id or user_id")
    if not isinstance(job.get("source_url"), str):
        raise QueueConsumerError("Queue message job payload is missing source_url")

    return processor(job)


def normalize_queue_message_body(body: Any) -> dict:
    """Normalize body variants returned by Cloudflare Queues and manual tests."""
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError as exc:
            raise QueueConsumerError("Queue message body is not valid JSON") from exc

    if not isinstance(body, dict):
        raise QueueConsumerError("Queue message body must be an object")

    nested_body = body.get("body")
    if "type" not in body and isinstance(nested_body, (dict, str)):
        return normalize_queue_message_body(nested_body)
    return body


def consume_once(
    client: CloudflarePullQueueClient | None = None,
    processor: QueueProcessor = process_hosted_ingestion_job,
    batch_size: int = DEFAULT_PULL_BATCH_SIZE,
    visibility_timeout_ms: int = DEFAULT_VISIBILITY_TIMEOUT_MS,
) -> dict:
    """Pull, process, and ack/retry one Cloudflare Queue batch."""
    queue_client = client or CloudflarePullQueueClient()
    messages = queue_client.pull_messages(batch_size, visibility_timeout_ms)
    ack_lease_ids: list[str] = []
    retry_lease_ids: list[str] = []

    for message in messages:
        lease_id = message.get("lease_id")
        if not isinstance(lease_id, str):
            continue
        try:
            process_ingestion_queue_message(message, processor)
            ack_lease_ids.append(lease_id)
        except Exception as exc:  # noqa: BLE001 - queue item should retry on any processing failure.
            print(f"[WARN] Queue message processing failed: {exc}")
            retry_lease_ids.append(lease_id)

    if ack_lease_ids or retry_lease_ids:
        queue_client.acknowledge(ack_lease_ids, retry_lease_ids)

    return {
        "pulled": len(messages),
        "acked": len(ack_lease_ids),
        "retried": len(retry_lease_ids),
    }


def supervised_consume_once(
    client: CloudflarePullQueueClient | None = None,
    processor: QueueProcessor = process_hosted_ingestion_job,
    batch_size: int = DEFAULT_PULL_BATCH_SIZE,
    visibility_timeout_ms: int = DEFAULT_VISIBILITY_TIMEOUT_MS,
) -> dict:
    """Run one consume pass and convert infrastructure failures into a status payload."""
    try:
        return {
            "ok": True,
            "summary": consume_once(client, processor, batch_size, visibility_timeout_ms),
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001 - supervisor loop decides whether to restart.
        return {
            "ok": False,
            "summary": {"pulled": 0, "acked": 0, "retried": 0},
            "error": str(exc),
        }


def check_consumer_configuration() -> dict:
    """Validate queue consumer configuration without making a network request."""
    pull_url = get_cloudflare_queue_pull_api_url()
    ack_url = get_cloudflare_queue_ack_api_url()
    api_token = get_cloudflare_queue_api_token()
    return {
        "ok": True,
        "pullUrlConfigured": bool(pull_url),
        "ackUrlConfigured": bool(ack_url),
        "apiTokenConfigured": bool(api_token),
    }


def run_pull_loop(
    batch_size: int = DEFAULT_PULL_BATCH_SIZE,
    visibility_timeout_ms: int = DEFAULT_VISIBILITY_TIMEOUT_MS,
    idle_sleep_seconds: float = DEFAULT_IDLE_SLEEP_SECONDS,
    error_sleep_seconds: float = DEFAULT_ERROR_SLEEP_SECONDS,
    max_consecutive_errors: int = DEFAULT_MAX_CONSECUTIVE_ERRORS,
    once: bool = False,
    client: CloudflarePullQueueClient | None = None,
) -> None:
    """Run a simple pull-consumer loop for container deployments."""
    queue_client = client or CloudflarePullQueueClient()
    consecutive_errors = 0
    while True:
        result = supervised_consume_once(
            queue_client,
            batch_size=batch_size,
            visibility_timeout_ms=visibility_timeout_ms,
        )
        summary = result["summary"]
        if result["ok"]:
            consecutive_errors = 0
            print(f"[INFO] Queue consume summary: {summary}")
        else:
            consecutive_errors += 1
            print(
                "[WARN] Queue consume failed "
                f"(consecutive_errors={consecutive_errors}): {result['error']}"
            )
            if once or (
                max_consecutive_errors > 0 and consecutive_errors >= max_consecutive_errors
            ):
                raise RuntimeError(result["error"])

        if once:
            return
        if summary["pulled"] == 0:
            sleep_seconds = error_sleep_seconds if not result["ok"] else idle_sleep_seconds
            time.sleep(max(0.1, sleep_seconds))


def _int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        return int(raw_value)
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        return float(raw_value)
    except ValueError:
        return default


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Memexai ingestion queue consumer.")
    parser.add_argument(
        "--healthcheck",
        action="store_true",
        help="Validate configuration and exit without pulling messages.",
    )
    parser.add_argument(
        "--once", action="store_true", help="Pull and process one batch, then exit."
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=_int_env("INGESTION_QUEUE_PULL_BATCH_SIZE", DEFAULT_PULL_BATCH_SIZE),
    )
    parser.add_argument(
        "--visibility-timeout-ms",
        type=int,
        default=_int_env("INGESTION_QUEUE_VISIBILITY_TIMEOUT_MS", DEFAULT_VISIBILITY_TIMEOUT_MS),
    )
    parser.add_argument(
        "--idle-sleep-seconds",
        type=float,
        default=_float_env("INGESTION_QUEUE_IDLE_SLEEP_SECONDS", DEFAULT_IDLE_SLEEP_SECONDS),
    )
    parser.add_argument(
        "--error-sleep-seconds",
        type=float,
        default=_float_env("INGESTION_QUEUE_ERROR_SLEEP_SECONDS", DEFAULT_ERROR_SLEEP_SECONDS),
    )
    parser.add_argument(
        "--max-consecutive-errors",
        type=int,
        default=_int_env(
            "INGESTION_QUEUE_MAX_CONSECUTIVE_ERRORS",
            DEFAULT_MAX_CONSECUTIVE_ERRORS,
        ),
    )
    args = parser.parse_args(argv)
    if args.healthcheck:
        try:
            print(f"[INFO] Queue consumer configuration: {check_consumer_configuration()}")
        except Exception as exc:  # noqa: BLE001 - healthcheck should print a clean error.
            print(f"[ERROR] Queue consumer configuration invalid: {exc}")
            return 1
        return 0

    run_pull_loop(
        batch_size=args.batch_size,
        visibility_timeout_ms=args.visibility_timeout_ms,
        idle_sleep_seconds=args.idle_sleep_seconds,
        error_sleep_seconds=args.error_sleep_seconds,
        max_consecutive_errors=args.max_consecutive_errors,
        once=args.once,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
