from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_queue_consumer_dockerfile_runs_packaged_worker_with_healthcheck():
    dockerfile = (ROOT / "Dockerfile.queue-consumer").read_text(encoding="utf-8")

    assert "FROM python:3.12-slim" in dockerfile
    assert "COPY backend/ ./backend/" in dockerfile
    assert "python -m backend.queue_consumer --healthcheck" in dockerfile
    assert 'CMD ["python", "-m", "backend.queue_consumer"]' in dockerfile


def test_docker_compose_has_queue_consumer_profile_and_cloudflare_env():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "queue-consumer:" in compose
    assert "dockerfile: Dockerfile.queue-consumer" in compose
    assert "- queue" in compose
    assert "CLOUDFLARE_INGESTION_QUEUE_ID" in compose
    assert "CLOUDFLARE_QUEUES_API_TOKEN" in compose
    assert "INGESTION_QUEUE_MAX_CONSECUTIVE_ERRORS" in compose


def test_production_env_example_documents_queue_and_workflow_runtime_env():
    env_example = (ROOT / ".env.production.example").read_text(encoding="utf-8")

    assert "INGESTION_DISPATCH_MODE=cloudflare_queue" in env_example
    assert "CLOUDFLARE_ACCOUNT_ID=your-cloudflare-account-id" in env_example
    assert "CLOUDFLARE_INGESTION_QUEUE_ID=your-cloudflare-queue-id" in env_example
    assert "CLOUDFLARE_QUEUES_API_TOKEN=your-cloudflare-queues-token" in env_example
    assert "WORKFLOW_INTERNAL_SECRET=replace-with-a-long-random-secret" in env_example


def test_hosted_readiness_checks_queue_env_when_queue_mode_is_enabled():
    script = (ROOT / "scripts" / "check_hosted_readiness.py").read_text(encoding="utf-8")

    assert "QUEUE_BACKEND" in script
    assert 'ingestion_dispatch_mode == "cloudflare_queue"' in script
    assert "CLOUDFLARE_QUEUES_API_TOKEN" in script
