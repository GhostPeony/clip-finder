from scripts.local_sidecar_digest import (
    build_schema_sql,
    digest_to_records,
    records_to_sql,
    unwrap_mcp_payload,
)


def sample_digest():
    return {
        "version": "memexai-brain-digest-v1",
        "userId": "user-1",
        "sync": {"nextCursor": "cursor-2"},
        "digest": {
            "videos": [
                {
                    "id": "video-row-1",
                    "objectType": "video",
                    "videoId": "abc123",
                    "title": "Agent Plans",
                    "youtubeUrl": "https://www.youtube.com/watch?v=abc123",
                    "accessScope": "video",
                    "accessSource": "ingest",
                    "accessReason": "Visible through an explicit saved-video grant.",
                    "indexedAt": "2026-06-22T12:00:00Z",
                }
            ],
            "sourceLabels": [
                {
                    "objectType": "source_label",
                    "labelType": "tool",
                    "label": "MCP",
                    "video": {"videoId": "abc123"},
                    "updated_at": "2026-06-22T12:01:00Z",
                }
            ],
            "sourceConcepts": [
                {
                    "id": "concept-1",
                    "objectType": "source_concept",
                    "conceptType": "method",
                    "name": "Plan first",
                    "summary": "Write a bounded plan.",
                    "video": {"videoId": "abc123"},
                    "updated_at": "2026-06-22T12:02:00Z",
                }
            ],
            "knowledgeArtifacts": [],
            "agentNotes": [
                {
                    "id": "note-1",
                    "objectType": "agent_note",
                    "content": "Use O'Brien's fixture.",
                    "created_at": "2026-06-22T12:03:00Z",
                }
            ],
            "personalConcepts": [],
        },
    }


def test_digest_to_records_normalizes_compact_digest():
    records = digest_to_records(sample_digest())

    assert [record.object_type for record in records] == [
        "video",
        "source_label",
        "source_concept",
        "agent_note",
    ]
    assert records[0].video_id == "abc123"
    assert records[0].title == "Agent Plans"
    assert records[1].record_id == "source_label:abc123:tool:MCP:0"
    assert records[2].summary == "Write a bounded plan."
    assert records[3].user_id == "user-1"


def test_unwrap_mcp_payload_accepts_tool_response_text():
    wrapped = {
        "jsonrpc": "2.0",
        "id": "local-sidecar-export",
        "result": {
            "content": [{"type": "text", "text": '{"digest": {"videos": []}}'}],
            "isError": False,
        },
    }

    assert unwrap_mcp_payload(wrapped) == {"digest": {"videos": []}}


def test_schema_sql_uses_pgvector_and_read_models():
    schema = build_schema_sql("sidecar")

    assert "CREATE EXTENSION IF NOT EXISTS vector" in schema
    assert "embedding VECTOR(768)" in schema
    assert 'CREATE OR REPLACE VIEW "sidecar".videos' in schema
    assert 'CREATE OR REPLACE VIEW "sidecar".source_context' in schema


def test_records_to_sql_upserts_and_escapes_values():
    records = digest_to_records(sample_digest())
    sql = records_to_sql(records, "sidecar")

    assert 'INSERT INTO "sidecar".mirror_records' in sql
    assert "ON CONFLICT (object_type, record_id) DO UPDATE SET" in sql
    assert "Use O''Brien''s fixture." in sql
    assert "'source_concept'" in sql
