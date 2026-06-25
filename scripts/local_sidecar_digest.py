"""Export/import compact Memexai brain digests for a local pgvector sidecar.

This prototype is intentionally bounded:

- Hosted Supabase remains canonical.
- The local sidecar stores read-only mirror rows from export_brain_digest.
- The generated SQL never deletes rows; it creates schema and upserts compact JSONB payloads.
- User-owned model spend should flow through stored BYOK API keys in hosted mode, or through the
  user's own local agent/model runner. Hosted Memexai cannot spend a user's Codex/ChatGPT
  subscription from our servers.

Typical flow:

    python scripts/local_sidecar_digest.py pull --endpoint http://localhost:8080/mcp \
      --token "$MEMEXAI_MCP_TOKEN" --output brain.jsonl
    python scripts/local_sidecar_digest.py sql brain.jsonl --schema-sql --output sidecar_import.sql
    psql "$LOCAL_SIDECAR_DATABASE_URL" -f sidecar_import.sql
"""

# ruff: noqa: S608

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

DEFAULT_MCP_ENDPOINT = "https://api.memexai.xyz/mcp"
DEFAULT_SCHEMA = "memexai_sidecar"
DIGEST_COLLECTIONS = {
    "videos": "video",
    "sourceLabels": "source_label",
    "sourceConcepts": "source_concept",
    "knowledgeArtifacts": "knowledge_artifact",
    "agentNotes": "agent_note",
    "personalConcepts": "personal_concept",
}


@dataclass(frozen=True)
class SidecarRecord:
    """A normalized local mirror row emitted as JSONL and SQL."""

    object_type: str
    record_id: str
    payload: dict[str, Any]
    user_id: str | None = None
    video_id: str | None = None
    title: str | None = None
    summary: str | None = None
    updated_at: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "objectType": self.object_type,
            "recordId": self.record_id,
            "userId": self.user_id,
            "videoId": self.video_id,
            "title": self.title,
            "summary": self.summary,
            "updatedAt": self.updated_at,
            "payload": self.payload,
        }


def build_schema_sql(schema: str = DEFAULT_SCHEMA) -> str:
    """Return an idempotent local Postgres/pgvector schema for compact digest rows."""
    quoted_schema = quote_ident(schema)
    return f"""-- Memexai local sidecar prototype schema.
-- Apply to a user-owned local Postgres with pgvector installed.
-- This schema is a read-only mirror target for compact MCP digest rows.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS {quoted_schema};

CREATE TABLE IF NOT EXISTS {quoted_schema}.mirror_records (
    object_type TEXT NOT NULL,
    record_id TEXT NOT NULL,
    user_id TEXT,
    video_id TEXT,
    title TEXT,
    summary TEXT,
    updated_at TIMESTAMPTZ,
    payload JSONB NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    search_vector TSVECTOR GENERATED ALWAYS AS (
        to_tsvector(
            'english',
            COALESCE(title, '') || ' ' ||
            COALESCE(summary, '') || ' ' ||
            COALESCE(payload->>'label', '') || ' ' ||
            COALESCE(payload->>'name', '') || ' ' ||
            COALESCE(payload->>'contentExcerpt', '') || ' ' ||
            COALESCE(payload->>'content', '')
        )
    ) STORED,
    embedding VECTOR(768),
    PRIMARY KEY (object_type, record_id)
);

CREATE INDEX IF NOT EXISTS mirror_records_object_type_idx
    ON {quoted_schema}.mirror_records(object_type);
CREATE INDEX IF NOT EXISTS mirror_records_video_id_idx
    ON {quoted_schema}.mirror_records(video_id);
CREATE INDEX IF NOT EXISTS mirror_records_updated_at_idx
    ON {quoted_schema}.mirror_records(updated_at DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS mirror_records_payload_idx
    ON {quoted_schema}.mirror_records USING gin (payload);
CREATE INDEX IF NOT EXISTS mirror_records_search_idx
    ON {quoted_schema}.mirror_records USING gin (search_vector);

CREATE INDEX IF NOT EXISTS mirror_records_embedding_hnsw_idx
    ON {quoted_schema}.mirror_records
    USING hnsw (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL;

CREATE OR REPLACE VIEW {quoted_schema}.videos AS
SELECT
    record_id,
    video_id AS youtube_video_id,
    title,
    payload->>'youtubeUrl' AS youtube_url,
    payload->'channel' AS channel,
    payload->>'accessScope' AS access_scope,
    payload->>'accessSource' AS access_source,
    payload->>'accessReason' AS access_reason,
    updated_at,
    payload
FROM {quoted_schema}.mirror_records
WHERE object_type = 'video';

CREATE OR REPLACE VIEW {quoted_schema}.source_context AS
SELECT *
FROM {quoted_schema}.mirror_records
WHERE object_type IN ('source_label', 'source_concept', 'knowledge_artifact');

CREATE OR REPLACE VIEW {quoted_schema}.personal_overlay AS
SELECT *
FROM {quoted_schema}.mirror_records
WHERE object_type IN ('agent_note', 'personal_concept');

CREATE TABLE IF NOT EXISTS {quoted_schema}.sync_state (
    sync_name TEXT PRIMARY KEY,
    next_cursor TEXT,
    last_digest JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


def digest_to_records(digest_payload: dict[str, Any]) -> list[SidecarRecord]:
    """Normalize an export_brain_digest payload into sidecar records."""
    structured = unwrap_mcp_payload(digest_payload)
    user_id = _optional_string(structured.get("userId"))
    digest = structured.get("digest")
    if not isinstance(digest, dict):
        raise ValueError("Expected an export_brain_digest payload with a digest object")

    records: list[SidecarRecord] = []
    for collection_name, object_type in DIGEST_COLLECTIONS.items():
        rows = digest.get(collection_name, [])
        if not isinstance(rows, list):
            continue
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            records.append(_record_from_digest_row(object_type, row, user_id, index))
    return records


def unwrap_mcp_payload(value: dict[str, Any]) -> dict[str, Any]:
    """Accept raw digest JSON or a JSON-RPC tools/call response."""
    if "digest" in value:
        return value

    result = value.get("result")
    if isinstance(result, dict):
        structured = result.get("structuredContent")
        if isinstance(structured, dict) and "digest" in structured:
            return structured
        content = result.get("content")
        if isinstance(content, list) and content:
            text = content[0].get("text") if isinstance(content[0], dict) else None
            if isinstance(text, str):
                parsed = json.loads(text)
                if isinstance(parsed, dict) and "digest" in parsed:
                    return parsed

    raise ValueError("Could not find a digest payload in the supplied JSON")


def records_from_jsonl(path: Path) -> list[SidecarRecord]:
    """Read normalized JSONL records from disk."""
    records: list[SidecarRecord] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSONL") from exc
        if not isinstance(raw, dict):
            raise ValueError(f"{path}:{line_number}: JSONL row must be an object")
        records.append(record_from_json(raw, line_number=line_number, source=path))
    return records


def record_from_json(
    value: dict[str, Any],
    *,
    line_number: int | None = None,
    source: Path | None = None,
) -> SidecarRecord:
    prefix = f"{source}:{line_number}: " if source and line_number else ""
    payload = value.get("payload")
    if not isinstance(payload, dict):
        raise ValueError(f"{prefix}payload must be an object")

    object_type = _required_string(value, "objectType", prefix)
    record_id = _required_string(value, "recordId", prefix)
    return SidecarRecord(
        object_type=object_type,
        record_id=record_id,
        payload=payload,
        user_id=_optional_string(value.get("userId")),
        video_id=_optional_string(value.get("videoId")),
        title=_optional_string(value.get("title")),
        summary=_optional_string(value.get("summary")),
        updated_at=_optional_string(value.get("updatedAt")),
    )


def records_to_sql(records: Iterable[SidecarRecord], schema: str = DEFAULT_SCHEMA) -> str:
    """Return idempotent upsert SQL for normalized JSONL records."""
    table = f"{quote_ident(schema)}.mirror_records"
    statements = []
    for record in records:
        statements.append(
            "INSERT INTO "
            f"{table} (object_type, record_id, user_id, video_id, title, summary, updated_at, payload)\n"
            "VALUES ("
            + ", ".join(
                [
                    sql_literal(record.object_type),
                    sql_literal(record.record_id),
                    sql_literal(record.user_id),
                    sql_literal(record.video_id),
                    sql_literal(record.title),
                    sql_literal(record.summary),
                    sql_timestamptz(record.updated_at),
                    sql_jsonb(record.payload),
                ]
            )
            + ")\n"
            "ON CONFLICT (object_type, record_id) DO UPDATE SET\n"
            "    user_id = EXCLUDED.user_id,\n"
            "    video_id = EXCLUDED.video_id,\n"
            "    title = EXCLUDED.title,\n"
            "    summary = EXCLUDED.summary,\n"
            "    updated_at = EXCLUDED.updated_at,\n"
            "    payload = EXCLUDED.payload,\n"
            "    imported_at = NOW();"
        )
    return "\n\n".join(statements)


def build_sync_state_sql(
    digest_payload: dict[str, Any],
    *,
    schema: str = DEFAULT_SCHEMA,
    sync_name: str = "hosted_mcp",
) -> str:
    structured = unwrap_mcp_payload(digest_payload)
    sync = structured.get("sync") if isinstance(structured.get("sync"), dict) else {}
    next_cursor = sync.get("nextCursor") if isinstance(sync, dict) else None
    table = f"{quote_ident(schema)}.sync_state"
    summary = {
        "version": structured.get("version"),
        "detailLevel": structured.get("detailLevel"),
        "sync": sync,
        "exportBudget": structured.get("exportBudget"),
        "accessModel": structured.get("accessModel"),
    }
    return (
        f"INSERT INTO {table} (sync_name, next_cursor, last_digest)\n"
        f"VALUES ({sql_literal(sync_name)}, {sql_literal(_optional_string(next_cursor))}, "
        f"{sql_jsonb(summary)})\n"
        "ON CONFLICT (sync_name) DO UPDATE SET\n"
        "    next_cursor = EXCLUDED.next_cursor,\n"
        "    last_digest = EXCLUDED.last_digest,\n"
        "    updated_at = NOW();"
    )


def pull_digest(
    *,
    endpoint: str,
    token: str,
    cursor: str | None = None,
    since: str | None = None,
    objects: list[str] | None = None,
    limit: int = 20,
    detail_level: str = "compact",
    max_chars: int = 12000,
) -> dict[str, Any]:
    """Call hosted MCP export_brain_digest and return the structured digest payload."""
    arguments: dict[str, Any] = {
        "limit": limit,
        "detail_level": detail_level,
        "max_chars": max_chars,
    }
    if cursor:
        arguments["cursor"] = cursor
    if since:
        arguments["since"] = since
    if objects:
        arguments["objects"] = objects

    request_body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "local-sidecar-export",
            "method": "tools/call",
            "params": {"name": "export_brain_digest", "arguments": arguments},
        }
    ).encode("utf-8")
    request = Request(
        endpoint,
        data=request_body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=60) as response:  # noqa: S310 - user-supplied MCP endpoint.
        raw = json.loads(response.read().decode("utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("MCP response must be a JSON object")
    if "error" in raw:
        raise RuntimeError(f"MCP export_brain_digest failed: {raw['error']}")
    return unwrap_mcp_payload(raw)


def write_jsonl(records: Iterable[SidecarRecord], output: Path | None) -> None:
    lines = [json.dumps(record.to_json(), ensure_ascii=False, sort_keys=True) for record in records]
    text = "\n".join(lines)
    if text:
        text += "\n"
    write_text(text, output)


def write_text(text: str, output: Path | None) -> None:
    if output:
        output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


def quote_ident(value: str) -> str:
    if not value:
        raise ValueError("SQL identifier cannot be empty")
    return '"' + value.replace('"', '""') + '"'


def sql_literal(value: str | None) -> str:
    if value is None:
        return "NULL"
    return "'" + value.replace("'", "''") + "'"


def sql_timestamptz(value: str | None) -> str:
    if not value:
        return "NULL"
    return f"{sql_literal(value)}::timestamptz"


def sql_jsonb(value: dict[str, Any] | list[Any]) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{sql_literal(encoded)}::jsonb"


def _record_from_digest_row(
    object_type: str,
    row: dict[str, Any],
    user_id: str | None,
    index: int,
) -> SidecarRecord:
    record_id = _optional_string(row.get("id")) or _fallback_record_id(object_type, row, index)
    video = row.get("video") if isinstance(row.get("video"), dict) else {}
    video_id = _optional_string(row.get("videoId")) or _optional_string(video.get("videoId"))
    title = _title_for_row(object_type, row)
    summary = _summary_for_row(object_type, row)
    updated_at = (
        _optional_string(row.get("updated_at"))
        or _optional_string(row.get("updatedAt"))
        or _optional_string(row.get("indexedAt"))
        or _optional_string(row.get("created_at"))
    )
    return SidecarRecord(
        object_type=object_type,
        record_id=record_id,
        payload=row,
        user_id=user_id,
        video_id=video_id,
        title=title,
        summary=summary,
        updated_at=updated_at,
    )


def _title_for_row(object_type: str, row: dict[str, Any]) -> str | None:
    if object_type == "video":
        return _optional_string(row.get("title"))
    if object_type == "source_label":
        label_type = _optional_string(row.get("labelType"))
        label = _optional_string(row.get("label"))
        if label_type and label:
            return f"{label_type}: {label}"
        return label
    return (
        _optional_string(row.get("title"))
        or _optional_string(row.get("name"))
        or _optional_string(row.get("label"))
    )


def _summary_for_row(object_type: str, row: dict[str, Any]) -> str | None:
    if object_type == "agent_note":
        return _optional_string(row.get("content"))
    return (
        _optional_string(row.get("summary"))
        or _optional_string(row.get("contentExcerpt"))
        or _optional_string(row.get("accessReason"))
    )


def _fallback_record_id(object_type: str, row: dict[str, Any], index: int) -> str:
    video = row.get("video") if isinstance(row.get("video"), dict) else {}
    pieces = [
        object_type,
        _optional_string(row.get("videoId")) or _optional_string(video.get("videoId")) or "global",
        _optional_string(row.get("labelType")),
        _optional_string(row.get("label")),
        _optional_string(row.get("name")),
        _optional_string(row.get("title")),
        str(index),
    ]
    return ":".join(piece for piece in pieces if piece)


def _required_string(value: dict[str, Any], key: str, prefix: str = "") -> str:
    raw = value.get(key)
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{prefix}{key} must be a non-empty string")
    return raw.strip()


def _optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _load_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return raw


def _split_csv(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        result.extend(part.strip() for part in value.split(",") if part.strip())
    return result


def cmd_schema(args: argparse.Namespace) -> int:
    write_text(build_schema_sql(args.schema), args.output)
    return 0


def cmd_jsonl(args: argparse.Namespace) -> int:
    records: list[SidecarRecord] = []
    for input_path in args.input:
        records.extend(digest_to_records(_load_json(input_path)))
    write_jsonl(records, args.output)
    return 0


def cmd_sql(args: argparse.Namespace) -> int:
    records: list[SidecarRecord] = []
    for input_path in args.input:
        records.extend(records_from_jsonl(input_path))
    parts = []
    if args.schema_sql:
        parts.append(build_schema_sql(args.schema))
    parts.append(records_to_sql(records, args.schema))
    if args.digest:
        parts.append(build_sync_state_sql(_load_json(args.digest), schema=args.schema))
    write_text("\n\n".join(part for part in parts if part).rstrip() + "\n", args.output)
    return 0


def cmd_pull(args: argparse.Namespace) -> int:
    token = args.token or os.getenv("MEMEXAI_MCP_TOKEN", "").strip()
    if not token:
        print("--token or MEMEXAI_MCP_TOKEN is required", file=sys.stderr)
        return 2
    digest = pull_digest(
        endpoint=args.endpoint,
        token=token,
        cursor=args.cursor,
        since=args.since,
        objects=_split_csv(args.objects),
        limit=args.limit,
        detail_level=args.detail_level,
        max_chars=args.max_chars,
    )
    if args.raw_json:
        write_text(json.dumps(digest, ensure_ascii=False, indent=2) + "\n", args.output)
    else:
        write_jsonl(digest_to_records(digest), args.output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    schema_parser = subparsers.add_parser("schema", help="Print local sidecar schema SQL.")
    schema_parser.add_argument("--schema", default=DEFAULT_SCHEMA, help="Postgres schema name.")
    schema_parser.add_argument("--output", type=Path, help="Write SQL to this file.")
    schema_parser.set_defaults(func=cmd_schema)

    jsonl_parser = subparsers.add_parser(
        "jsonl",
        help="Convert export_brain_digest JSON or JSON-RPC responses into compact JSONL.",
    )
    jsonl_parser.add_argument("input", nargs="+", type=Path, help="Digest JSON file(s).")
    jsonl_parser.add_argument("--output", type=Path, help="Write JSONL to this file.")
    jsonl_parser.set_defaults(func=cmd_jsonl)

    sql_parser = subparsers.add_parser("sql", help="Convert compact JSONL into upsert SQL.")
    sql_parser.add_argument("input", nargs="+", type=Path, help="Digest JSONL file(s).")
    sql_parser.add_argument("--schema", default=DEFAULT_SCHEMA, help="Postgres schema name.")
    sql_parser.add_argument(
        "--schema-sql",
        action="store_true",
        help="Prepend CREATE EXTENSION/SCHEMA/TABLE/VIEW statements.",
    )
    sql_parser.add_argument(
        "--digest",
        type=Path,
        help="Optional raw digest JSON file used to update sync_state.next_cursor.",
    )
    sql_parser.add_argument("--output", type=Path, help="Write SQL to this file.")
    sql_parser.set_defaults(func=cmd_sql)

    pull_parser = subparsers.add_parser(
        "pull",
        help="Call export_brain_digest over MCP and write compact JSONL by default.",
    )
    pull_parser.add_argument(
        "--endpoint",
        default=os.getenv("MEMEXAI_MCP_URL", DEFAULT_MCP_ENDPOINT),
        help="MCP endpoint URL.",
    )
    pull_parser.add_argument("--token", help="MCP bearer token; defaults to env var.")
    pull_parser.add_argument("--cursor", help="Previous sync cursor.")
    pull_parser.add_argument("--since", help="Optional ISO timestamp lower bound.")
    pull_parser.add_argument(
        "--objects",
        action="append",
        default=[],
        help="Object list or comma-separated values: videos,concepts,artifacts,notes.",
    )
    pull_parser.add_argument("--limit", type=int, default=20, help="Digest page limit.")
    pull_parser.add_argument(
        "--detail-level",
        choices=["compact", "standard", "deep"],
        default="compact",
        help="MCP digest detail level.",
    )
    pull_parser.add_argument("--max-chars", type=int, default=12000, help="Digest budget.")
    pull_parser.add_argument(
        "--raw-json",
        action="store_true",
        help="Write the raw digest JSON instead of normalized JSONL.",
    )
    pull_parser.add_argument("--output", type=Path, help="Write output to this file.")
    pull_parser.set_defaults(func=cmd_pull)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        print(f"local_sidecar_digest: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
