from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER_SOURCE = ROOT / "workers" / "orchestrator" / "src" / "index.ts"
WRANGLER_CONFIG = ROOT / "workers" / "orchestrator" / "wrangler.toml"
WORKER_README = ROOT / "workers" / "orchestrator" / "README.md"


def test_cloudflare_orchestrator_worker_defines_durable_workflows():
    source = WORKER_SOURCE.read_text(encoding="utf-8")

    assert "WorkflowEntrypoint" in source
    assert "class CapturePlaylistSyncWorkflow" in source
    assert "class VideoIngestionWorkflow" in source
    assert "validate capture sync payload" in source
    assert "run hosted capture sync" in source
    assert "send ingestion queue message" in source
    assert "/internal/workflows/capture-sync" in source
    assert "X-Memexai-Workflow-Secret" in source
    assert "ORCHESTRATOR_SHARED_SECRET" in source
    assert "INGESTION_QUEUE.send(message)" in source


def test_cloudflare_orchestrator_wrangler_config_has_bindings_without_secrets():
    config = WRANGLER_CONFIG.read_text(encoding="utf-8")

    assert 'name = "memexai-orchestrator"' in config
    assert 'binding = "CAPTURE_SYNC_WORKFLOW"' in config
    assert 'class_name = "CapturePlaylistSyncWorkflow"' in config
    assert 'binding = "VIDEO_INGESTION_WORKFLOW"' in config
    assert 'class_name = "VideoIngestionWorkflow"' in config
    assert 'binding = "INGESTION_QUEUE"' in config
    assert 'queue = "memexai-ingestion"' in config
    assert "MEMEXAI_WORKFLOW_SECRET" not in config
    assert "ORCHESTRATOR_SHARED_SECRET" not in config


def test_cloudflare_orchestrator_readme_documents_secret_mapping():
    readme = WORKER_README.read_text(encoding="utf-8")

    assert "WORKFLOW_INTERNAL_SECRET" in readme
    assert "MEMEXAI_WORKFLOW_SECRET" in readme
    assert "ORCHESTRATOR_SHARED_SECRET" in readme
    assert "npx wrangler deploy -c workers/orchestrator/wrangler.toml" in readme
