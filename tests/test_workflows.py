from fastapi.testclient import TestClient

from backend.workflows import (
    build_workflow_status_context,
    create_workflow_instance,
    get_workflow_instance,
    list_workflow_definitions,
    list_workflow_instances,
    record_workflow_artifact,
    record_workflow_step,
    update_workflow_instance,
)


class Result:
    def __init__(self, data):
        self.data = data


class Query:
    def __init__(self, table_name, supabase):
        self.table_name = table_name
        self.supabase = supabase
        self.action = None
        self.payload = None
        self.filters = []
        self.single = False

    def select(self, *args, **kwargs):
        self.supabase.calls.append((self.table_name, "select", args, kwargs))
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        self.supabase.calls.append((self.table_name, "eq", column, value))
        return self

    def or_(self, expression):
        self.supabase.calls.append((self.table_name, "or", expression))
        return self

    def order(self, column, desc=False):
        self.supabase.calls.append((self.table_name, "order", column, desc))
        return self

    def limit(self, value):
        self.supabase.calls.append((self.table_name, "limit", value))
        return self

    def maybe_single(self):
        self.single = True
        self.supabase.calls.append((self.table_name, "maybe_single"))
        return self

    def insert(self, payload):
        self.action = "insert"
        self.payload = payload
        self.supabase.calls.append((self.table_name, "insert", payload))
        return self

    def update(self, payload):
        self.action = "update"
        self.payload = payload
        self.supabase.calls.append((self.table_name, "update", payload))
        return self

    def execute(self):
        if self.action == "insert":
            prefix = self.table_name.removeprefix("workflow_").removesuffix("s")
            return Result([{**self.payload, "id": f"{prefix}-1"}])
        if self.action == "update":
            row_id = next((value for column, value in self.filters if column == "id"), "row-1")
            return Result([{**self.payload, "id": row_id}])
        data = self.supabase.responses.get(self.table_name, [])
        if self.single and isinstance(data, list):
            return Result(data[0] if data else None)
        return Result(data)


class Supabase:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []

    def table(self, table_name):
        self.calls.append(("table", table_name))
        return Query(table_name, self)


def test_list_workflow_definitions_includes_global_and_user_definitions():
    supabase = Supabase({"workflow_definitions": [{"key": "video.ingest", "version": 1}]})

    definitions = list_workflow_definitions(supabase, "user-1", limit=999)

    assert definitions == [{"key": "video.ingest", "version": 1}]
    assert ("workflow_definitions", "or", "user_id.is.null,user_id.eq.user-1") in supabase.calls
    assert ("workflow_definitions", "limit", 100) in supabase.calls


def test_create_workflow_instance_inserts_user_scoped_run():
    supabase = Supabase()

    instance = create_workflow_instance(
        supabase,
        "user-1",
        "video.ingest.v1",
        2,
        {"youtube_video_id": "uCKhOmth2ms"},
        trigger="mcp.queue_youtube_ingestion",
        created_by="agent",
        created_by_client="hermes",
    )

    assert instance["id"] == "instance-1"
    assert instance["user_id"] == "user-1"
    assert instance["workflow_key"] == "video.ingest.v1"
    assert instance["workflow_version"] == 2
    assert instance["created_by_client"] == "hermes"
    inserted = [call[2] for call in supabase.calls if call[0] == "workflow_instances"][0]
    assert inserted["input"]["youtube_video_id"] == "uCKhOmth2ms"


def test_update_workflow_instance_sets_completed_at_for_terminal_status():
    supabase = Supabase()

    updated = update_workflow_instance(supabase, "workflow-1", status="completed")

    assert updated["status"] == "completed"
    assert "completed_at" in updated
    assert ("workflow_instances", "eq", "id", "workflow-1") in supabase.calls


def test_record_workflow_step_and_artifact():
    supabase = Supabase()

    step = record_workflow_step(
        supabase,
        "workflow-1",
        "extract_source_knowledge",
        "completed",
        output_ref={"table": "source_concepts"},
        metrics={"concepts": 4},
    )
    artifact = record_workflow_artifact(
        supabase,
        "workflow-1",
        "study_guide",
        "Sierra harness study guide",
        {"sections": []},
        source_refs=[{"videoId": "uCKhOmth2ms"}],
        status="published",
    )

    assert step["id"] == "step-1"
    assert step["completed_at"]
    assert artifact["id"] == "artifact-1"
    assert artifact["status"] == "published"


def test_get_and_list_workflow_instances_scope_to_user():
    supabase = Supabase(
        {
            "workflow_instances": [
                {
                    "id": "workflow-1",
                    "workflow_key": "video.ingest.v1",
                    "status": "running",
                }
            ]
        }
    )

    listed = list_workflow_instances(supabase, "user-1", limit=999)
    fetched = get_workflow_instance(supabase, "user-1", "workflow-1")
    context = build_workflow_status_context(supabase, "user-1", limit=10)

    assert listed[0]["id"] == "workflow-1"
    assert fetched["id"] == "workflow-1"
    assert context["workflowInstances"][0]["status"] == "running"
    assert ("workflow_instances", "eq", "user_id", "user-1") in supabase.calls
    assert ("workflow_instances", "eq", "id", "workflow-1") in supabase.calls


def test_workflow_status_endpoints(monkeypatch):
    from backend import server

    monkeypatch.setenv("SEARCHTUBE_AUTH_MODE", "none")
    monkeypatch.setattr(server, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(server, "get_supabase", lambda: object())
    monkeypatch.setattr(
        server,
        "list_workflow_definitions",
        lambda supabase, user_id, limit: [{"key": "video.ingest.v1", "limit": limit}],
    )
    monkeypatch.setattr(
        server,
        "list_workflow_instances",
        lambda supabase, user_id, limit: [{"id": "workflow-1", "user_id": user_id}],
    )
    monkeypatch.setattr(
        server,
        "get_workflow_instance",
        lambda supabase, user_id, instance_id: {
            "id": instance_id,
            "user_id": user_id,
            "workflow_steps": [{"step_key": "fetch_transcript"}],
        },
    )

    client = TestClient(server.app)

    definitions = client.get("/api/workflows/definitions?limit=999")
    instances = client.get("/api/workflows/instances?limit=999")
    instance = client.get("/api/workflows/instances/workflow-1")

    assert definitions.status_code == 200
    assert definitions.json()["workflowDefinitions"][0]["limit"] == 100
    assert instances.status_code == 200
    assert instances.json()["workflowInstances"][0]["user_id"] == "local"
    assert instance.status_code == 200
    assert instance.json()["workflow_steps"][0]["step_key"] == "fetch_transcript"
