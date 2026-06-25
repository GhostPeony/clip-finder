from fastapi.testclient import TestClient


def test_internal_capture_sync_requires_configured_secret(monkeypatch):
    from backend import server

    monkeypatch.delenv("WORKFLOW_INTERNAL_SECRET", raising=False)

    response = TestClient(server.app).post(
        "/internal/workflows/capture-sync",
        json={"user_id": "user-1", "capture_source_id": "capture-1"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Internal workflow endpoint is not configured"


def test_internal_capture_sync_rejects_bad_secret(monkeypatch):
    from backend import server

    monkeypatch.setenv("WORKFLOW_INTERNAL_SECRET", "correct-secret")

    response = TestClient(server.app).post(
        "/internal/workflows/capture-sync",
        headers={"X-Memexai-Workflow-Secret": "wrong-secret"},
        json={"user_id": "user-1", "capture_source_id": "capture-1"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid workflow secret"


def test_internal_capture_sync_runs_hosted_workflow_and_dispatches_jobs(monkeypatch):
    from backend import server

    dispatched = []
    supabase = object()

    monkeypatch.setenv("WORKFLOW_INTERNAL_SECRET", "correct-secret")
    monkeypatch.setattr(server, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(server, "get_supabase", lambda: supabase)
    monkeypatch.setattr(
        server,
        "schedule_hosted_ingestion_job",
        lambda background_tasks, job, source: {"source": source, "job_id": job["id"]},
    )

    def fake_capture_sync_workflow(
        source_supabase,
        user_id,
        source_id,
        max_jobs,
        dispatch_job,
        trigger,
        created_by,
        created_by_client,
    ):
        assert source_supabase is supabase
        assert user_id == "user-1"
        assert source_id == "capture-1"
        assert max_jobs == 2
        assert trigger == "cloudflare.workflow.capture.sync"
        assert created_by == "system"
        assert created_by_client == "cloudflare-orchestrator"
        dispatched.append(dispatch_job({"id": "job-1", "user_id": user_id}))
        return {
            "workflow_instance_id": "workflow-1",
            "queuedJobCount": 1,
            "workflowInstance": {
                "id": "workflow-1",
                "trigger": trigger,
                "created_by": created_by,
                "created_by_client": created_by_client,
            },
        }

    monkeypatch.setattr(server, "run_capture_sync_workflow", fake_capture_sync_workflow)

    response = TestClient(server.app).post(
        "/internal/workflows/capture-sync",
        headers={"X-Memexai-Workflow-Secret": "correct-secret"},
        json={
            "user_id": "user-1",
            "capture_source_id": "capture-1",
            "max_jobs": 2,
            "created_by_client": "cloudflare-orchestrator",
        },
    )

    assert response.status_code == 200
    assert response.json()["workflow_instance_id"] == "workflow-1"
    assert dispatched == [{"source": "cloudflare-workflow:capture-sync", "job_id": "job-1"}]
