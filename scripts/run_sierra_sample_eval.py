"""Run the offline Sierra podcast sample eval against agent-facing context helpers."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "eval" / "fixtures" / "sierra_harness_podcast.json"
DEFAULT_USER_ID = "sierra-eval-user"
VIDEO_DB_ID = "sierra-video-db"
CHANNEL_DB_ID = "sierra-channel-db"


class Result:
    def __init__(self, data: Any):
        self.data = data


class MemoryQuery:
    def __init__(self, store: "MemorySupabase", table_name: str):
        self.store = store
        self.table_name = table_name
        self.action: str | None = None
        self.payload: Any = None
        self.filters: list[tuple[str, str, Any]] = []
        self.limit_value: int | None = None
        self.order_field: str | None = None
        self.order_desc = False
        self.single = False
        self.upsert_conflict: list[str] = []

    def select(self, *args: Any, **kwargs: Any) -> "MemoryQuery":
        del args, kwargs
        self.action = self.action or "select"
        return self

    def eq(self, column: str, value: Any) -> "MemoryQuery":
        self.filters.append(("eq", column, value))
        return self

    def match(self, values: dict[str, Any]) -> "MemoryQuery":
        for column, value in values.items():
            self.eq(column, value)
        return self

    def in_(self, column: str, values: list[Any]) -> "MemoryQuery":
        self.filters.append(("in", column, values))
        return self

    def or_(self, expression: str) -> "MemoryQuery":
        self.filters.append(("or", "", expression))
        return self

    def order(self, column: str, desc: bool = False) -> "MemoryQuery":
        self.order_field = column
        self.order_desc = desc
        return self

    def limit(self, value: int) -> "MemoryQuery":
        self.limit_value = value
        return self

    def maybe_single(self) -> "MemoryQuery":
        self.single = True
        return self

    def insert(self, payload: Any) -> "MemoryQuery":
        self.action = "insert"
        self.payload = payload
        return self

    def upsert(self, payload: dict, on_conflict: str | None = None) -> "MemoryQuery":
        self.action = "upsert"
        self.payload = payload
        self.upsert_conflict = [part.strip() for part in (on_conflict or "").split(",") if part]
        return self

    def execute(self) -> Result:
        self.store.calls.append((self.table_name, self.action or "select", deepcopy(self.payload)))
        if self.action == "insert":
            rows = self.payload if isinstance(self.payload, list) else [self.payload]
            inserted = []
            for row in rows:
                inserted.append(self.store.insert_row(self.table_name, row))
            return Result(inserted if isinstance(self.payload, list) else inserted[0])

        if self.action == "upsert":
            return Result(
                self.store.upsert_row(self.table_name, self.payload, self.upsert_conflict)
            )

        rows = [deepcopy(row) for row in self.store.tables.get(self.table_name, [])]
        rows = self._apply_filters(rows)
        if self.order_field:
            rows.sort(
                key=lambda row: (row.get(self.order_field) is None, row.get(self.order_field)),
                reverse=self.order_desc,
            )
        if self.limit_value is not None:
            rows = rows[: self.limit_value]
        if self.single:
            return Result(rows[0] if rows else None)
        return Result(rows)

    def _apply_filters(self, rows: list[dict]) -> list[dict]:
        filtered = rows
        for op, column, value in self.filters:
            if op == "eq":
                filtered = [row for row in filtered if row.get(column) == value]
            elif op == "in":
                allowed = set(value)
                filtered = [row for row in filtered if row.get(column) in allowed]
            elif op == "or" and self.table_name == "knowledge_artifacts":
                # The production helper requests "user_id is null or user_id equals current user".
                filtered = [
                    row
                    for row in filtered
                    if row.get("user_id") is None
                    or "user_id.eq." + str(row.get("user_id")) in value
                ]
        return filtered


class MemorySupabase:
    def __init__(self, tables: dict[str, list[dict]]):
        self.tables = deepcopy(tables)
        self.calls: list[tuple[str, str, Any]] = []

    def table(self, table_name: str) -> MemoryQuery:
        self.tables.setdefault(table_name, [])
        return MemoryQuery(self, table_name)

    def insert_row(self, table_name: str, row: dict) -> dict:
        stored = deepcopy(row)
        stored.setdefault("id", f"{table_name}-{len(self.tables[table_name]) + 1}")
        self.tables[table_name].append(stored)
        return deepcopy(stored)

    def upsert_row(self, table_name: str, row: dict, conflict_keys: list[str]) -> dict:
        stored = deepcopy(row)
        if conflict_keys:
            for index, existing in enumerate(self.tables[table_name]):
                if all(existing.get(key) == stored.get(key) for key in conflict_keys):
                    self.tables[table_name][index] = {**existing, **stored}
                    return deepcopy(self.tables[table_name][index])
        stored.setdefault("id", f"{table_name}-{len(self.tables[table_name]) + 1}")
        self.tables[table_name].append(stored)
        return deepcopy(stored)


def load_fixture(path: Path = FIXTURE_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_sample_tables(fixture: dict, user_id: str = DEFAULT_USER_ID) -> dict[str, list[dict]]:
    video = fixture["video"]
    source_refs = [
        {
            "source_type": "transcript",
            "youtube_video_id": video["youtubeVideoId"],
            "start_seconds": 180,
            "end_seconds": 260,
        },
        {
            "source_type": "transcript",
            "youtube_video_id": video["youtubeVideoId"],
            "start_seconds": 980,
            "end_seconds": 1080,
        },
    ]
    source_labels = []
    for expected in fixture["expectedLabels"]:
        for label in expected["labels"]:
            source_labels.append(
                {
                    "id": f"label-{len(source_labels) + 1}",
                    "video_id": VIDEO_DB_ID,
                    "label_type": expected["label_type"],
                    "label": label,
                    "confidence": 0.92,
                    "source_refs": source_refs[:1],
                    "metadata": {"fixture": fixture["name"]},
                }
            )

    return {
        "channels": [
            {
                "id": CHANNEL_DB_ID,
                "name": video["source"],
                "youtube_handle": None,
            }
        ],
        "videos": [
            {
                "id": VIDEO_DB_ID,
                "channel_id": CHANNEL_DB_ID,
                "youtube_video_id": video["youtubeVideoId"],
                "title": video["title"],
                "thumbnail_url": "",
                "transcript_seconds": 4200,
                "indexed_at": "2026-06-22T00:00:00Z",
            }
        ],
        "user_channels": [],
        "user_videos": [
            {
                "id": "grant-1",
                "user_id": user_id,
                "video_id": VIDEO_DB_ID,
                "grant_source": "sierra_sample_eval",
            }
        ],
        "source_labels": source_labels,
        "source_concepts": [
            {
                "id": "concept-1",
                "video_id": VIDEO_DB_ID,
                "concept_type": "method",
                "name": "Sierra-style harness loop",
                "summary": (
                    "Use inspectable workflow steps, evaluation feedback, and product constraints "
                    "to iterate production AI agent behavior."
                ),
                "source_refs": source_refs,
                "metadata": {"fixture": fixture["name"]},
            },
            {
                "id": "concept-2",
                "video_id": VIDEO_DB_ID,
                "concept_type": "implementation_note",
                "name": "Workflow orchestration for agent context",
                "summary": (
                    "Keep source context read-only while allowing agents to request briefs, "
                    "poll workflow handles, and write personal overlay notes."
                ),
                "source_refs": source_refs[:1],
                "metadata": {"fixture": fixture["name"]},
            },
            {
                "id": "concept-3",
                "video_id": VIDEO_DB_ID,
                "concept_type": "pitfall",
                "name": "Latency and cost control",
                "summary": (
                    "Production agent systems need bounded steps, retries, and evaluation gates "
                    "so cost and latency do not sprawl."
                ),
                "source_refs": source_refs[1:],
                "metadata": {"fixture": fixture["name"]},
            },
        ],
        "source_edges": [
            {
                "id": "edge-1",
                "video_id": VIDEO_DB_ID,
                "relation": "supports",
                "from_ref": {"source_type": "source_concept", "name": "Sierra-style harness loop"},
                "to_ref": {
                    "source_type": "source_concept",
                    "name": "Workflow orchestration for agent context",
                },
                "evidence_refs": source_refs,
                "metadata": {"fixture": fixture["name"]},
            }
        ],
        "knowledge_artifacts": [
            {
                "id": "artifact-1",
                "user_id": None,
                "video_id": VIDEO_DB_ID,
                "artifact_type": "tldr",
                "title": "TLDR: Sierra agent harness podcast",
                "summary": (
                    "The sample turns the Sierra podcast into reusable context for workflow "
                    "orchestration, MCP access, eval loops, and agent-ready specs."
                ),
                "content": (
                    "Use this source to evaluate whether Memexai can move from video "
                    "ingestion to actionable, cited agent context."
                ),
                "source_refs": source_refs,
                "metadata": {"fixture": fixture["name"]},
            },
            {
                "id": "artifact-2",
                "user_id": None,
                "video_id": VIDEO_DB_ID,
                "artifact_type": "study_guide",
                "title": "Study Guide: Sierra-style agent harnesses",
                "summary": (
                    "A study guide for applying production agent harness ideas to Memexai."
                ),
                "content": "\n".join(
                    [
                        "# Sierra-style agent harnesses",
                        "",
                        "## Core ideas",
                        "- Keep source knowledge read-only and provenance-backed.",
                        "- Make workflow steps inspectable, retryable, and easy to evaluate.",
                        "- Use repo context from the calling agent instead of forcing a hosted repo connection.",
                        "",
                        "## Action items",
                        "- Gate ingestion cost before bulk submissions.",
                        "- Publish workflow handles for long-running work.",
                        "- Add eval checks for categorization and brief quality.",
                    ]
                ),
                "source_refs": source_refs,
                "metadata": {"fixture": fixture["name"]},
            },
        ],
        "agent_notes": [
            {
                "id": "note-1",
                "user_id": user_id,
                "content": "Connect Sierra harness lessons to workflow orchestration evals.",
                "source_refs": source_refs[:1],
                "tags": ["sierra", "eval"],
                "created_by": "agent",
            }
        ],
        "personal_concepts": [
            {
                "id": "personal-concept-1",
                "user_id": user_id,
                "name": "Sierra-style harness loop",
                "summary": "Personalized shorthand for eval-driven agent workflow iteration.",
                "source_refs": source_refs[:1],
                "status": "learning",
                "created_by": "agent",
            }
        ],
        "transcript_lines": [],
        "chunks": [],
    }


def run_offline_eval(fixture_path: Path = FIXTURE_PATH, user_id: str = DEFAULT_USER_ID) -> dict:
    root_text = str(ROOT)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)

    from backend import context

    fixture = load_fixture(fixture_path)
    tables = build_sample_tables(fixture, user_id)
    supabase = MemorySupabase(tables)
    source_counts_before = _source_table_counts(supabase)

    categories = context.list_context_categories(supabase, user_id, limit=100)
    video_context = context.get_video_context(supabase, user_id, fixture["video"]["youtubeVideoId"])
    bundle = context.build_context_bundle(
        supabase,
        user_id,
        fixture["mcpWorkflow"][-1]["arguments"]["query"],
        fixture["repoContext"],
        limit=8,
        category_filters=fixture["categoryFilters"],
    )
    brief = context.build_agent_brief(
        supabase,
        user_id,
        fixture["mcpWorkflow"][-1]["arguments"]["query"],
        fixture["repoContext"],
        limit=8,
        category_filters=fixture["mcpWorkflow"][-1]["arguments"]["category_filters"],
    )
    note = context.create_agent_note(
        supabase,
        user_id,
        "Use the Sierra sample as the baseline for workflow orchestration evals.",
        source_refs=brief["citations"][:1],
        tags=["sierra", "workflow"],
        created_by="agent",
        created_by_client="sierra-sample-eval",
    )
    personal_concept = context.upsert_personal_concept(
        supabase,
        user_id,
        "Sierra-style harness loop",
        "A personalized frame for eval-driven workflow orchestration.",
        source_refs=brief["citations"][:1],
        status="learning",
        created_by="agent",
        created_by_client="sierra-sample-eval",
    )
    source_counts_after = _source_table_counts(supabase)

    checks = [
        _check(
            "canonical_video_access_grant",
            bool(tables["user_videos"]) and not tables["user_channels"],
            "Sample uses user_videos access instead of duplicating canonical video rows.",
        ),
        _check(
            "category_discovery",
            _has_required_categories(categories),
            "Categories expose Sierra, agent architecture, implementation plan, and production pattern labels.",
        ),
        _check(
            "study_guide_artifact",
            any(
                artifact.get("artifact_type") == "study_guide"
                for artifact in (video_context or {}).get("knowledgeArtifacts", [])
            ),
            "Video context includes a study guide artifact.",
        ),
        _check(
            "filtered_context_bundle",
            bundle["sourceContext"]["videos"]
            and bundle["sourceContext"]["videos"][0]["videoId"]
            == fixture["video"]["youtubeVideoId"]
            and bundle["categoryFilters"] == fixture["categoryFilters"],
            "Context bundle returns the Sierra video under category filters.",
        ),
        _check(
            "repo_aware_agent_brief",
            brief["repoFit"]["provided"]
            and bool(brief["implementationGuidance"])
            and bool(brief["citations"])
            and "workflow orchestration" in brief["repoFit"]["candidateTouchpoints"],
            "Agent brief includes repo fit, implementation guidance, and citations.",
        ),
        _check(
            "overlay_writes_do_not_mutate_source_context",
            source_counts_before == source_counts_after
            and note["created_by"] == "agent"
            and personal_concept["name"] == "Sierra-style harness loop",
            "Overlay note/concept writes leave source tables unchanged.",
        ),
    ]

    return {
        "fixture": fixture["name"],
        "video": fixture["video"],
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
        "categoryFacets": categories["facets"],
        "studyGuide": _study_guide_summary(video_context),
        "contextBundle": {
            "videoIds": [video["videoId"] for video in bundle["sourceContext"]["videos"]],
            "categoryFilters": bundle["categoryFilters"],
            "sourceLabelCount": len(bundle["sourceContext"]["sourceLabels"]),
            "conceptCount": len(bundle["sourceContext"]["sourceConcepts"]),
        },
        "agentBrief": {
            "title": brief["title"],
            "repoFit": brief["repoFit"],
            "implementationGuidance": brief["implementationGuidance"],
            "citationCount": len(brief["citations"]),
        },
        "overlay": {
            "note": note,
            "personalConcept": personal_concept,
        },
    }


def _source_table_counts(supabase: MemorySupabase) -> dict[str, int]:
    return {
        table_name: len(supabase.tables.get(table_name, []))
        for table_name in (
            "videos",
            "transcript_lines",
            "chunks",
            "source_labels",
            "source_concepts",
            "source_edges",
            "knowledge_artifacts",
        )
    }


def _has_required_categories(categories: dict) -> bool:
    facets = categories.get("facets", {})
    return (
        "Sierra" in facets.get("entity", [])
        and "agent architecture" in facets.get("topic", [])
        and "implementation plan" in facets.get("task_fit", [])
        and "production pattern" in facets.get("maturity", [])
    )


def _study_guide_summary(video_context: dict | None) -> dict:
    if not video_context:
        return {"present": False}
    artifact = next(
        (
            item
            for item in video_context.get("knowledgeArtifacts", [])
            if item.get("artifact_type") == "study_guide"
        ),
        None,
    )
    if not artifact:
        return {"present": False}
    return {
        "present": True,
        "title": artifact.get("title"),
        "summary": artifact.get("summary"),
        "sourceRefs": artifact.get("source_refs", []),
    }


def _check(name: str, passed: bool, detail: str) -> dict:
    return {"name": name, "passed": bool(passed), "detail": detail}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=FIXTURE_PATH)
    parser.add_argument("--user-id", default=DEFAULT_USER_ID)
    parser.add_argument("--pretty", action="store_true", help="Print indented JSON.")
    args = parser.parse_args()

    report = run_offline_eval(args.fixture, args.user_id)
    indent = 2 if args.pretty else None
    print(json.dumps(report, indent=indent, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
