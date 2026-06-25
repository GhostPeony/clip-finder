"""Dispatch durable ingestion jobs to a local runner or Cloudflare Queues."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable

try:
    from .config import (
        INGESTION_DISPATCH_BACKGROUND,
        INGESTION_DISPATCH_CLOUDFLARE_QUEUE,
        get_cloudflare_queue_api_token,
        get_cloudflare_queue_api_url,
        get_ingestion_dispatch_mode,
    )
except ImportError:
    from config import (
        INGESTION_DISPATCH_BACKGROUND,
        INGESTION_DISPATCH_CLOUDFLARE_QUEUE,
        get_cloudflare_queue_api_token,
        get_cloudflare_queue_api_url,
        get_ingestion_dispatch_mode,
    )

IngestionProcessor = Callable[[dict], None]


def build_ingestion_queue_message(job: dict, source: str = "hosted-api") -> dict:
    """Build a versioned queue message for a hosted ingestion job."""
    return {
        "type": "ingestion_job.process",
        "version": 1,
        "source": source,
        "job": {
            "id": job.get("id"),
            "user_id": job.get("user_id"),
            "source_url": job.get("source_url"),
            "source_type": job.get("source_type", "unknown"),
            "status": job.get("status", "queued"),
        },
    }


def dispatch_ingestion_job(
    job: dict,
    background_tasks: Any | None = None,
    processor: IngestionProcessor | None = None,
    mode: str | None = None,
    source: str = "hosted-api",
) -> dict:
    """Dispatch a hosted ingestion job using the configured queue mode."""
    dispatch_mode = mode or get_ingestion_dispatch_mode()
    if dispatch_mode == INGESTION_DISPATCH_BACKGROUND:
        if processor is None:
            raise ValueError("processor is required for background ingestion dispatch")
        if background_tasks is not None:
            background_tasks.add_task(processor, job)
            return {"mode": dispatch_mode, "scheduled": True}

        processor(job)
        return {"mode": dispatch_mode, "scheduled": True, "ran_inline": True}

    if dispatch_mode == INGESTION_DISPATCH_CLOUDFLARE_QUEUE:
        message = build_ingestion_queue_message(job, source)
        response = publish_to_cloudflare_queue(message)
        return {"mode": dispatch_mode, "scheduled": True, "providerResponse": response}

    raise ValueError("Unsupported ingestion dispatch mode")


def publish_to_cloudflare_queue(message: dict) -> dict:
    """Publish one message to Cloudflare Queues through the HTTP Push API."""
    api_url = get_cloudflare_queue_api_url()
    api_token = get_cloudflare_queue_api_token()
    payload = json.dumps({"body": message}).encode("utf-8")
    request = urllib.request.Request(
        api_url,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Cloudflare Queue publish failed: HTTP {exc.code} {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cloudflare Queue publish failed: {exc.reason}") from exc

    parsed = json.loads(raw_body or "{}")
    if parsed.get("success") is not True:
        raise RuntimeError(f"Cloudflare Queue publish failed: {parsed}")
    return parsed
