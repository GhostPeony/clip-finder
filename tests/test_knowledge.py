import re
from pathlib import Path
from types import SimpleNamespace

from backend import ingest, knowledge


class Result:
    def __init__(self, data=None):
        self.data = data if data is not None else []


class Query:
    def __init__(self, table_name, supabase):
        self.table_name = table_name
        self.supabase = supabase
        self.action = None

    def insert(self, payload):
        self.action = "insert"
        self.supabase.inserts.append((self.table_name, payload))
        return self

    def update(self, payload):
        self.action = "update"
        self.supabase.updates.append((self.table_name, payload))
        return self

    def delete(self):
        self.action = "delete"
        self.supabase.deletes.append(self.table_name)
        return self

    def select(self, *args, **kwargs):
        self.action = "select"
        self.supabase.calls.append((self.table_name, "select", args, kwargs))
        return self

    def eq(self, column, value):
        self.supabase.calls.append((self.table_name, "eq", column, value))
        return self

    def match(self, payload):
        self.supabase.calls.append((self.table_name, "match", payload))
        return self

    def maybe_single(self):
        self.supabase.calls.append((self.table_name, "maybe_single"))
        return self

    def limit(self, count):
        self.supabase.calls.append((self.table_name, "limit", count))
        return self

    def order(self, column, desc=False):
        self.supabase.calls.append((self.table_name, "order", column, desc))
        return self

    def single(self):
        self.supabase.calls.append((self.table_name, "single"))
        return self

    def execute(self):
        if self.action == "select" and self.table_name in self.supabase.select_results:
            return Result(self.supabase.select_results[self.table_name])
        if self.action == "delete":
            return Result([])
        if self.action == "insert" and self.table_name == "videos":
            return Result([{"id": "video-db-id"}])
        if self.action == "select" and self.table_name == "channels":
            return Result({"total_videos": 2})
        return Result([])


class Supabase:
    def __init__(self):
        self.inserts = []
        self.updates = []
        self.deletes = []
        self.calls = []
        self.select_results = {}

    def table(self, table_name):
        self.calls.append(("table", table_name))
        return Query(table_name, self)


def test_extract_source_knowledge_normalizes_llm_json(monkeypatch):
    captured = {}

    class FakeLlm:
        def invoke(self, prompt):
            captured["prompt"] = prompt
            return SimpleNamespace(
                content="""```json
                {
                  "tldr": "The video explains reward models and why evaluation loops matter.",
                  "study_guide": {
                    "title": "Reward Model Study Guide",
                    "summary": "A compact path through the lesson.",
                    "compiled_truth": [
                      {
                        "name": "Reward models need measured feedback loops",
                        "summary": "The lesson treats preference data, scoring, and eval checks as one operating system rather than separate research artifacts. It starts from the practical need to convert subjective judgments into repeatable measurement, then explains why the reward model only becomes useful when it is connected to a harness that can catch regressions and reward hacking.",
                        "why_it_matters": "An agent can use this as the controlling interpretation of the video before deciding whether to fetch transcript evidence.",
                        "source_refs": [{"clip_index": 0}]
                      }
                    ],
                    "agent_index": [
                      {
                        "name": "claim: preference data supports reward models",
                        "summary": "Start here when an agent needs the argument for reward-model training data and the reason comparisons matter. This entry points directly to the portion where preference data is connected to the learned scorer.",
                        "retrieval_hint": "Use this when a downstream agent asks why preference data belongs in an evaluation loop or how human judgment is converted into a model-facing score.",
                        "query": "preference data reward model support",
                        "source_refs": [{"clip_index": 1}]
                      }
                    ],
                    "themes": ["Evaluation loops turn subjective preference signals into operational checks."],
                    "people": [
                      {
                        "name": "Evaluation lead",
                        "role": "owner",
                        "summary": "Owns the harness that turns model behavior into measurable review.",
                        "source_refs": [{"clip_index": 0}]
                      }
                    ],
                    "organizations": [
                      {
                        "name": "AI Channel",
                        "summary": "Frames reward modeling as an engineering practice instead of a pure research idea."
                      }
                    ],
                    "tools": [
                      {
                        "name": "Eval harness",
                        "summary": "The system where feedback becomes regression checks.",
                        "source_refs": [{"clip_index": 1}]
                      }
                    ],
                    "claims": [
                      {
                        "claim": "Preference data supports the reward model.",
                        "why_it_matters": "Agents can retrieve this instead of reading the full transcript.",
                        "source_refs": [{"clip_index": 1}]
                      }
                    ],
                    "decisions": [
                      {
                        "decision": "Map reward feedback into the eval harness.",
                        "source_refs": [{"clip_index": 1}]
                      }
                    ],
                    "timeline": [
                      {
                        "time": "1:00",
                        "summary": "Preference data is connected to the reward model.",
                        "source_refs": [{"clip_index": 1}]
                      }
                    ],
                    "sections": [
                      {
                        "heading": "Core idea",
                        "bullets": [
                          {
                            "summary": "Use preference data to train a reward model.",
                            "source_refs": [{"clip_index": 0}]
                          }
                        ]
                      }
                    ],
                    "action_items": ["Map reward feedback into your eval harness."],
                    "open_questions": ["Where can reward hacking appear?"]
                  },
                  "labels": [
                    {
                      "label_type": "task_fit",
                      "label": "eval harness",
                      "confidence": 0.92,
                      "source_refs": [{"clip_index": 1}]
                    },
                    {
                      "label_type": "unsupported",
                      "label": "falls back to topic",
                      "confidence": 9
                    }
                  ],
                  "concepts": [
                    {
                      "name": "Reward model",
                      "concept_type": "algorithm",
                      "summary": "A learned scorer trained from preference labels.",
                      "source_refs": [{"clip_index": 0, "quote": "train a reward model"}]
                    },
                    {
                      "name": "Unsupported type falls back",
                      "concept_type": "made_up",
                      "summary": "Still kept as a concept.",
                      "source_refs": [{"start_seconds": 60, "end_seconds": 90}]
                    }
                  ],
                  "edges": [
                    {
                      "from": "Preference data",
                      "to": "Reward model",
                      "relation": "supports",
                      "evidence_refs": [{"clip_index": 1}]
                    }
                  ]
                }
                ```"""
            )

    monkeypatch.setattr(knowledge, "_get_llm", lambda api_key, max_output_tokens=2048: FakeLlm())
    monkeypatch.setattr(knowledge, "get_llm_model", lambda: "test-model")

    chunks = [
        {
            "text": "We train a reward model from comparisons.",
            "start_seconds": 0,
            "end_seconds": 50,
        },
        {
            "text": "Preference data supports the reward model.",
            "start_seconds": 60,
            "end_seconds": 90,
        },
    ]

    result = knowledge.extract_source_knowledge("yt123", "RLHF Lesson", "AI Channel", chunks, "k")

    assert "RLHF Lesson" in captured["prompt"]
    assert "gbrain-style entity page" in captured["prompt"]
    assert "Do not make agents scan the transcript" in captured["prompt"]
    assert "Source report target for this 1m 30s video: 400-900 words" in captured["prompt"]
    assert "same analysis contract to every indexed video" in captured["prompt"]
    assert "Transcript duration estimate: 1m 30s" in captured["prompt"]
    assert "paragraph-level notes" in captured["prompt"]
    assert "Do not write placeholder bullets" in captured["prompt"]
    assert "short named objects" not in captured["prompt"]
    guide_content = result["artifacts"][1]["content"]
    assert "Compiled Truth" in guide_content
    assert "Agent Quick Index" in guide_content
    assert "Key Themes" in guide_content
    assert "People" in guide_content
    assert "Organizations" in guide_content
    assert "Tools and Systems" in guide_content
    assert "Claims" in guide_content
    assert "Decisions" in guide_content
    assert "Timeline" in guide_content
    assert "Open Questions" in guide_content
    assert "controlling interpretation of the video" in guide_content
    assert "downstream agent asks why preference data belongs" in guide_content
    assert "source: 1:00" in guide_content
    assert result["concepts"][0]["concept_type"] == "algorithm"
    assert result["concepts"][0]["source_refs"][0]["start_seconds"] == 0
    assert result["concepts"][1]["concept_type"] == "concept"
    assert result["labels"][0]["label_type"] == "task_fit"
    assert result["labels"][0]["label"] == "eval harness"
    assert result["labels"][0]["confidence"] == 0.92
    assert result["labels"][0]["source_refs"][0]["start_seconds"] == 60
    assert result["labels"][1]["label_type"] == "topic"
    assert result["labels"][1]["confidence"] == 1.0
    assert result["edges"][0]["relation"] == "supports"
    assert result["edges"][0]["evidence_refs"][0]["end_seconds"] == 90
    assert {artifact["artifact_type"] for artifact in result["artifacts"]} == {
        "tldr",
        "study_guide",
    }
    assert result["artifacts"][1]["title"].startswith("Source Report:")
    assert result["artifacts"][1]["metadata"]["display_artifact_type"] == "source_report"
    assert "Action Items" in guide_content
    assert len(result["artifacts"][1]["source_refs"]) > 1


def test_extract_source_knowledge_infers_timestamp_refs_when_model_omits_them(monkeypatch):
    class FakeLlm:
        def invoke(self, prompt):
            return SimpleNamespace(
                content="""{
                  "tldr": "The video explains how synthetic data helps model teams test rare cases.",
                  "study_guide": {
                    "title": "Synthetic Data Field Guide",
                    "summary": "The speaker breaks down when generated records are useful and where they need validation.",
                    "compiled_truth": [
                      "Synthetic data creates rare fraud examples for evaluation sets."
                    ],
                    "sections": [
                      {
                        "heading": "Validation",
                        "bullets": [
                          "Validate synthetic data against real distribution drift."
                        ]
                      }
                    ],
                    "action_items": [
                      "Audit generated records before training the fraud model."
                    ]
                  },
                  "labels": [
                    {"label_type": "topic", "label": "synthetic data"}
                  ],
                  "concepts": [
                    {
                      "name": "Synthetic data",
                      "concept_type": "method",
                      "summary": "Generated records expand rare fraud cases."
                    }
                  ],
                  "edges": [
                    {
                      "from": "Synthetic data",
                      "to": "Fraud model",
                      "relation": "supports"
                    }
                  ]
                }"""
            )

    monkeypatch.setattr(knowledge, "_get_llm", lambda api_key, max_output_tokens=2048: FakeLlm())
    monkeypatch.setattr(knowledge, "get_llm_model", lambda: "test-model")

    chunks = [
        {
            "text": "Synthetic data creates rare fraud examples for evaluation sets and stress tests.",
            "start_seconds": 120,
            "end_seconds": 180,
        },
        {
            "text": "Validate synthetic data against real distribution drift before training.",
            "start_seconds": 300,
            "end_seconds": 360,
        },
    ]

    result = knowledge.extract_source_knowledge(
        "yt-synthetic",
        "Why use synthetic data?",
        "Data Channel",
        chunks,
        "k",
    )

    concept = result["concepts"][0]
    label = result["labels"][0]
    edge = result["edges"][0]
    report = result["artifacts"][1]

    assert concept["source_refs"][0]["start_seconds"] == 120
    assert concept["metadata"]["source_ref_fallback"] == knowledge.SOURCE_REF_FALLBACK_VERSION
    assert label["source_refs"][0]["start_seconds"] == 120
    assert label["metadata"]["source_ref_fallback"] == knowledge.SOURCE_REF_FALLBACK_VERSION
    assert edge["evidence_refs"][0]["start_seconds"] == 120
    assert edge["metadata"]["source_ref_fallback"] == knowledge.SOURCE_REF_FALLBACK_VERSION
    assert (
        "Validate synthetic data against real distribution drift. (source: 5:00)"
        in report["content"]
    )
    assert any(ref.get("start_seconds") == 300 for ref in report["source_refs"])


def test_extraction_prompt_is_universal_not_ai_only(monkeypatch):
    captured = {}

    class FakeLlm:
        def invoke(self, prompt):
            captured["prompt"] = prompt
            return SimpleNamespace(
                content='{"tldr":"Summary","study_guide":{},"labels":[],"concepts":[],"edges":[]}'
            )

    monkeypatch.setattr(knowledge, "_get_llm", lambda api_key, max_output_tokens=2048: FakeLlm())

    knowledge.extract_source_knowledge(
        "cook123",
        "How to Bake Sourdough",
        "Kitchen Lessons",
        [
            {
                "text": "Feed the starter before mixing the dough.",
                "start_seconds": 0,
                "end_seconds": 30,
            }
        ],
        "k",
    )

    prompt = captured["prompt"]
    assert "cooking, repairs, history, music, sports, health, business, science, AI" in prompt
    assert "learn, decide, teach, troubleshoot, create, practice, buy, plan, build" in prompt
    assert "product spec, agent prompt, or implementation plan" not in prompt
    assert "for an AI agent" not in prompt


def test_store_video_knowledge_writes_source_tables_only(monkeypatch):
    supabase = Supabase()
    monkeypatch.setattr(
        knowledge,
        "extract_source_knowledge",
        lambda **_kwargs: {
            "concepts": [
                {
                    "concept_type": "method",
                    "name": "Eval loop",
                    "summary": "Repeated measurement loop.",
                    "source_refs": [{"source_type": "transcript", "start_seconds": 0}],
                    "metadata": {"extraction_version": "test"},
                }
            ],
            "labels": [
                {
                    "label_type": "task_fit",
                    "label": "eval harness",
                    "confidence": 0.91,
                    "source_refs": [{"source_type": "transcript", "start_seconds": 0}],
                    "metadata": {"extraction_version": "test"},
                }
            ],
            "edges": [
                {
                    "relation": "implements",
                    "from_ref": {"source_type": "source_concept", "name": "Eval loop"},
                    "to_ref": {"source_type": "source_concept", "name": "Training gym"},
                    "evidence_refs": [{"source_type": "transcript", "start_seconds": 0}],
                    "metadata": {"extraction_version": "test"},
                }
            ],
            "artifacts": [
                {
                    "artifact_type": "study_guide",
                    "title": "Source Report",
                    "summary": "Summary",
                    "content": "# Source Report",
                    "source_refs": [{"source_type": "video"}],
                    "metadata": {"extraction_version": "test"},
                }
            ],
        },
    )

    counts = knowledge.store_video_knowledge(
        supabase,
        "video-db-id",
        "yt123",
        "Title",
        "Channel",
        [{"text": "hello", "start_seconds": 0, "end_seconds": 60}],
        "key",
    )

    inserts = {table: payload for table, payload in supabase.inserts}
    assert counts == {
        "transcript_lines": 1,
        "source_concepts": 1,
        "source_labels": 1,
        "source_edges": 1,
        "knowledge_artifacts": 1,
    }
    assert inserts["transcript_lines"][0]["metadata"]["granularity"] == "chunk"
    assert inserts["source_concepts"][0]["name"] == "Eval loop"
    assert inserts["source_labels"][0]["label"] == "eval harness"
    assert inserts["knowledge_artifacts"][0]["created_by"] == "system"
    assert "agent_notes" not in inserts
    assert "personal_concepts" not in inserts


def test_store_video_knowledge_queues_published_event_for_user(monkeypatch):
    supabase = Supabase()
    sync_events = []
    monkeypatch.setattr(
        knowledge,
        "extract_source_knowledge",
        lambda **_kwargs: {
            "concepts": [
                {
                    "concept_type": "method",
                    "name": "Practice loop",
                    "summary": "Repeat and measure the lesson.",
                    "source_refs": [{"source_type": "transcript", "start_seconds": 0}],
                    "metadata": {"extraction_version": "test"},
                }
            ],
            "labels": [],
            "edges": [],
            "artifacts": [],
        },
    )
    monkeypatch.setattr(
        knowledge,
        "queue_brain_sync_event",
        lambda *args, **kwargs: sync_events.append((args, kwargs)) or {"queuedCount": 1},
    )

    counts = knowledge.store_video_knowledge(
        supabase,
        "video-db-id",
        "yt123",
        "Title",
        "Channel",
        [{"text": "hello", "start_seconds": 0, "end_seconds": 60}],
        "key",
        published_for_user_id="user-1",
    )

    assert counts["source_concepts"] == 1
    event_args, event_kwargs = sync_events[0]
    assert event_args[:3] == (supabase, "user-1", "knowledge.published")
    assert event_kwargs["payload"]["videoDbId"] == "video-db-id"
    assert event_kwargs["payload"]["videoId"] == "yt123"
    assert event_kwargs["payload"]["counts"]["source_concepts"] == 1
    assert event_kwargs["source_ref"] == {
        "type": "youtube_video",
        "video_db_id": "video-db-id",
        "video_id": "yt123",
    }
    assert event_kwargs["idempotency_key"] == "knowledge.published:video-db-id:standard"


def test_build_source_knowledge_index_rows_includes_concepts_reports_and_sections():
    source_ref = {
        "source_type": "transcript",
        "youtube_video_id": "yt123",
        "start_seconds": 120,
        "end_seconds": 180,
    }
    row_groups = {
        "source_concepts": [
            {
                "concept_type": "method",
                "name": "Harness loop",
                "summary": "Evaluate agent behavior with a repeatable verification loop.",
                "source_refs": [source_ref],
                "metadata": {"aliases": ["agent harness"]},
            }
        ],
        "knowledge_artifacts": [
            {
                "artifact_type": "study_guide",
                "title": "Source Report: Reliable agents",
                "summary": "A one-page report about reliable agent harnesses.",
                "content": (
                    "# Reliable agents\n\n"
                    "## Compiled Truth\n\n"
                    "The video argues that reliability comes from harnesses, not prompts. "
                    "(source: 2:00)\n\n"
                    "## Decisions\n\n"
                    "- Add a verification step before rollout. (source: 2:00)"
                ),
                "source_refs": [source_ref],
                "metadata": {"display_artifact_type": "source_report"},
            }
        ],
    }

    rows = knowledge.build_source_knowledge_index_rows(
        "video-db-id",
        row_groups,
        youtube_video_id="yt123",
        title="Reliable agents",
    )

    row_types = {row["source_object_type"] for row in rows}
    assert row_types == {"source_concept", "knowledge_artifact", "report_section"}
    concept = next(row for row in rows if row["source_object_type"] == "source_concept")
    section = next(row for row in rows if row["source_object_type"] == "report_section")
    assert concept["title"] == "Harness loop"
    assert "agent harness" in concept["aliases"]
    assert "method" in concept["aliases"]
    assert section["title"] == "Compiled Truth"
    assert "main takeaways" in section["aliases"]
    assert section["source_refs"][0]["start_seconds"] == 120
    assert section["embedding"] is None
    assert section["index_version"] == knowledge.SOURCE_KNOWLEDGE_INDEX_VERSION


def test_store_video_knowledge_indexes_keyword_rows_when_embedding_fails(monkeypatch):
    supabase = Supabase()
    source_ref = {
        "source_type": "transcript",
        "youtube_video_id": "yt123",
        "start_seconds": 60,
        "end_seconds": 120,
    }

    monkeypatch.setattr(
        knowledge,
        "extract_source_knowledge",
        lambda **_kwargs: {
            "concepts": [
                {
                    "concept_type": "claim",
                    "name": "Verification catches drift",
                    "summary": "A verification step catches agent drift before users see it.",
                    "source_refs": [source_ref],
                    "metadata": {"extraction_version": "test"},
                }
            ],
            "labels": [],
            "edges": [],
            "artifacts": [
                {
                    "artifact_type": "study_guide",
                    "title": "Source Report: Verification",
                    "summary": "Report summary.",
                    "content": (
                        "# Verification\n\n"
                        "## Claims\n\n"
                        "- Verification catches drift before release. (source: 1:00)"
                    ),
                    "source_refs": [source_ref],
                    "metadata": {"display_artifact_type": "source_report"},
                }
            ],
        },
    )
    monkeypatch.setattr(
        knowledge,
        "_get_source_index_embeddings",
        lambda _api_key=None: (_ for _ in ()).throw(RuntimeError("embedding unavailable")),
    )

    counts = knowledge.store_video_knowledge(
        supabase,
        "video-db-id",
        "yt123",
        "Verification",
        "Agent Channel",
        [{"text": "verification catches drift", "start_seconds": 60, "end_seconds": 120}],
        "key",
    )

    inserts = {table: payload for table, payload in supabase.inserts}
    assert counts["source_concepts"] == 1
    assert "source_knowledge_index" in inserts
    index_rows = inserts["source_knowledge_index"]
    assert {row["source_object_type"] for row in index_rows} == {
        "source_concept",
        "knowledge_artifact",
        "report_section",
    }
    assert all(row["embedding"] is None for row in index_rows)
    assert all(row["metadata"]["embeddingStatus"] == "failed" for row in index_rows)


def test_store_video_knowledge_none_depth_skips_llm_and_keeps_transcript_lines(monkeypatch):
    supabase = Supabase()
    monkeypatch.setattr(
        knowledge,
        "extract_source_knowledge",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("none depth should not call the LLM extractor")
        ),
    )

    counts = knowledge.store_video_knowledge(
        supabase,
        "video-db-id",
        "yt123",
        "Title",
        "Channel",
        [{"text": "hello", "start_seconds": 0, "end_seconds": 60}],
        "key",
        digest_depth="none",
    )

    inserts = {table: payload for table, payload in supabase.inserts}
    assert counts == {
        "transcript_lines": 1,
        "source_concepts": 0,
        "source_labels": 0,
        "source_edges": 0,
        "knowledge_artifacts": 0,
    }
    assert "transcript_lines" in inserts
    assert "source_concepts" not in inserts
    assert "knowledge_artifacts" not in inserts


def test_refresh_existing_video_source_knowledge_keeps_existing_rows_when_extraction_is_empty(
    monkeypatch,
):
    supabase = Supabase()
    supabase.select_results["chunks"] = [
        {
            "content": "The speaker explains that agent harnesses need verification.",
            "start_seconds": 0,
            "end_seconds": 60,
        }
    ]
    extraction_calls = []

    def empty_extraction(**kwargs):
        extraction_calls.append(kwargs)
        return {"concepts": [], "labels": [], "edges": [], "artifacts": []}

    monkeypatch.setattr(knowledge, "extract_source_knowledge", empty_extraction)

    result = knowledge.refresh_existing_video_source_knowledge(
        supabase,
        {
            "id": "video-db-id",
            "youtube_video_id": "yt123",
            "title": "Building reliable agent harnesses",
            "channel_name": "Harnesses in AI",
        },
        api_key="key",
    )

    assert result == {
        "refreshed": False,
        "reason": "extraction_not_publishable",
        "counts": {
            "source_concepts": 0,
            "source_labels": 0,
            "source_edges": 0,
            "knowledge_artifacts": 0,
        },
    }
    assert extraction_calls[0]["digest_depth"] == "standard"
    assert supabase.deletes == []
    assert supabase.inserts == []


def test_refresh_existing_video_source_knowledge_replaces_generated_rows_after_valid_report(
    monkeypatch,
):
    supabase = Supabase()
    supabase.select_results["chunks"] = [
        {
            "content": "The agent harness verifies whether the task was actually completed.",
            "start_seconds": 300,
            "end_seconds": 360,
        }
    ]
    long_report = (
        "# Source Report\n\n"
        + (
            "The video frames agent reliability as an engineering harness problem, "
            "where verification, tool boundaries, context control, and completion checks "
            "matter more than a clever prompt. "
        )
        * 8
        + "(source: 5:00)"
    )
    extraction_calls = []

    def valid_extraction(**kwargs):
        extraction_calls.append(kwargs)
        return {
            "concepts": [
                {
                    "concept_type": "method",
                    "name": "Verification step",
                    "summary": "Checks whether the agent completed the requested task.",
                    "source_refs": [
                        {
                            "source_type": "transcript",
                            "youtube_video_id": "yt123",
                            "start_seconds": 300,
                            "end_seconds": 360,
                        }
                    ],
                    "metadata": {"extraction_version": "test"},
                }
            ],
            "labels": [],
            "edges": [],
            "artifacts": [
                {
                    "artifact_type": "study_guide",
                    "title": "Source Report: Building reliable agent harnesses",
                    "summary": "A source-backed report on reliability harnesses.",
                    "content": long_report,
                    "source_refs": [
                        {
                            "source_type": "transcript",
                            "youtube_video_id": "yt123",
                            "start_seconds": 300,
                            "end_seconds": 360,
                        }
                    ],
                    "metadata": {
                        "display_artifact_type": "source_report",
                        "extraction_version": "test",
                    },
                }
            ],
        }

    monkeypatch.setattr(knowledge, "extract_source_knowledge", valid_extraction)

    result = knowledge.refresh_existing_video_source_knowledge(
        supabase,
        {
            "id": "video-db-id",
            "youtube_video_id": "yt123",
            "title": "Building reliable agent harnesses",
            "channel_name": "Harnesses in AI",
        },
        api_key="key",
        published_for_user_id="user-1",
    )

    inserts = {table: payload for table, payload in supabase.inserts}
    assert result["refreshed"] is True
    assert result["counts"] == {
        "transcript_lines": 0,
        "source_concepts": 1,
        "source_labels": 0,
        "source_edges": 0,
        "knowledge_artifacts": 1,
    }
    assert extraction_calls[0]["title"] == "Building reliable agent harnesses"
    assert extraction_calls[0]["digest_depth"] == "standard"
    assert supabase.deletes == [
        "source_concepts",
        "source_labels",
        "source_edges",
        "knowledge_artifacts",
        "source_knowledge_index",
    ]
    assert "transcript_lines" not in inserts
    assert inserts["source_concepts"][0]["name"] == "Verification step"
    assert inserts["knowledge_artifacts"][0]["content"] == long_report


def test_basic_digest_depth_limits_artifacts_and_edges(monkeypatch):
    captured = {}

    class FakeLlm:
        def invoke(self, prompt):
            captured["prompt"] = prompt
            return SimpleNamespace(
                content="""
                {
                  "tldr": "Compact summary.",
                  "study_guide": {
                    "title": "Should be ignored",
                    "summary": "Ignore this at basic depth."
                  },
                  "labels": [{"label_type": "topic", "label": "testing"}],
                  "concepts": [{"name": "Loop", "concept_type": "method", "summary": "Loop."}],
                  "edges": [{
                    "from": "Loop",
                    "to": "Harness",
                    "relation": "implements"
                  }]
                }
                """
            )

    monkeypatch.setattr(knowledge, "_get_llm", lambda api_key, max_output_tokens=2048: FakeLlm())

    result = knowledge.extract_source_knowledge(
        "yt123",
        "Title",
        "Channel",
        [{"text": "hello", "start_seconds": 0, "end_seconds": 60}],
        "key",
        digest_depth="basic",
    )

    assert "Digest depth: basic" in captured["prompt"]
    assert "Do not create a source report for basic depth" in captured["prompt"]
    assert result["edges"] == []
    assert [artifact["artifact_type"] for artifact in result["artifacts"]] == ["tldr"]


def test_index_video_to_pg_invokes_failure_safe_knowledge_storage(monkeypatch):
    supabase = Supabase()
    calls = []

    class FakeEmbeddings:
        def embed_documents(self, texts):
            return [[0.1, 0.2] for _text in texts]

    def fail_store_video_knowledge(*args):
        calls.append(args)
        raise RuntimeError("knowledge tables not migrated")

    monkeypatch.setattr(ingest, "get_embeddings", lambda api_key: FakeEmbeddings())
    monkeypatch.setattr(ingest, "store_video_knowledge", fail_store_video_knowledge)

    chunks = [{"text": "transcript", "start_seconds": 0, "end_seconds": 60}]
    count = ingest.index_video_to_pg(
        supabase,
        "yt123",
        "Title",
        "Channel",
        "channel-db-id",
        chunks,
        60,
        "key",
    )

    inserts = {table: payload for table, payload in supabase.inserts}
    assert count == 1
    assert inserts["chunks"][0]["content"] == "transcript"
    assert calls[0][1:6] == ("video-db-id", "yt123", "Title", "Channel", chunks)
    assert len(supabase.updates) == 1
    assert supabase.updates[0][0] == "channels"
    assert supabase.updates[0][1]["total_videos"] == 3
    assert "indexed_at" in supabase.updates[0][1]


def test_grant_user_video_access_links_existing_video_without_embedding(monkeypatch):
    supabase = Supabase()
    increments = []

    monkeypatch.setattr(
        ingest,
        "get_user_profile",
        lambda supabase, user_id: {
            "free_indexed_videos_total": 0,
            "free_indexed_seconds_total": 0,
        },
    )
    monkeypatch.setattr(ingest, "check_index_quota", lambda profile, count, seconds=0: True)
    monkeypatch.setattr(
        ingest,
        "increment_index_usage",
        lambda supabase, user_id, video_count, used_own_key, transcript_seconds=0: (
            increments.append((user_id, video_count, used_own_key, transcript_seconds))
        ),
    )

    message = ingest.grant_user_video_access(
        supabase,
        "user-2",
        {"id": "video-db-id", "transcript_seconds": 420},
        used_own_key=False,
        access_source="shared_existing",
        source_url="https://www.youtube.com/watch?v=yt123",
    )

    inserts = {table: payload for table, payload in supabase.inserts}
    assert message is None
    assert inserts["user_videos"]["user_id"] == "user-2"
    assert inserts["user_videos"]["video_id"] == "video-db-id"
    assert inserts["user_videos"]["access_source"] == "shared_existing"
    assert increments == [("user-2", 1, False, 420)]


def test_user_video_access_sources_match_database_constraint():
    migration_sql = Path("backend/supabase/migrations/010_user_video_access.sql").read_text()
    constraint = re.search(
        r"CHECK\s*\(\s*access_source\s+IN\s*\((.*?)\)\s*\)",
        migration_sql,
        flags=re.DOTALL,
    )

    assert constraint is not None
    assert ingest.USER_VIDEO_ACCESS_SOURCES == frozenset(
        re.findall(r"'([^']+)'", constraint.group(1))
    )


def test_grant_user_video_access_rejects_unknown_access_source():
    supabase = Supabase()

    try:
        ingest.grant_user_video_access(
            supabase,
            "user-2",
            {"id": "video-db-id"},
            access_source="single_video",
        )
    except ValueError as exc:
        assert "Unsupported user_videos access_source" in str(exc)
    else:
        raise AssertionError("unsupported access_source should fail before Supabase insert")

    assert not supabase.inserts


def test_ingest_single_video_reuses_existing_canonical_video(monkeypatch):
    grant_calls = []

    monkeypatch.setattr(ingest, "get_supabase", lambda: object())
    monkeypatch.setattr(
        ingest,
        "get_indexed_video_pg",
        lambda supabase, video_id: {
            "id": "video-db-id",
            "channel_id": "channel-db-id",
            "youtube_video_id": video_id,
            "transcript_seconds": 300,
        },
    )
    monkeypatch.setattr(
        ingest,
        "grant_user_video_access",
        lambda supabase, user_id, video, used_own_key=False, access_source="shared_existing", source_url=None, charge_usage=True: (
            grant_calls.append((user_id, video["id"], access_source, source_url, charge_usage))
            or None
        ),
    )
    monkeypatch.setattr(
        ingest,
        "fetch_video_metadata",
        lambda video_id: (_ for _ in ()).throw(
            AssertionError("metadata should not be fetched for a reused video")
        ),
    )
    monkeypatch.setattr(
        ingest,
        "fetch_transcript_chunks",
        lambda video_id: (_ for _ in ()).throw(
            AssertionError("transcript should not be fetched for a reused video")
        ),
    )
    monkeypatch.setattr(
        ingest,
        "get_embeddings",
        lambda api_key=None: (_ for _ in ()).throw(
            AssertionError("embeddings should not be generated for a reused video")
        ),
    )

    messages = list(ingest.ingest_single_video_pg("yt123", "user-2"))

    assert any("Added the existing embeddings to your library" in message for message in messages)
    assert messages[-1] == "Complete!"
    assert grant_calls == [
        (
            "user-2",
            "video-db-id",
            "shared_existing",
            "https://www.youtube.com/watch?v=yt123",
            True,
        )
    ]


def test_ingest_single_video_refreshes_weak_reused_source_knowledge(monkeypatch):
    refresh_calls = []

    monkeypatch.setattr(ingest, "get_supabase", lambda: object())
    monkeypatch.setattr(
        ingest,
        "get_indexed_video_pg",
        lambda supabase, video_id: {
            "id": "video-db-id",
            "channel_id": "channel-db-id",
            "youtube_video_id": video_id,
            "title": "Why use synthetic data?",
            "channel_name": "Data Channel",
            "transcript_seconds": 300,
        },
    )
    monkeypatch.setattr(
        ingest,
        "grant_user_video_access",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        ingest,
        "refresh_existing_video_source_context_if_needed",
        lambda supabase, video, api_key, digest_depth, user_id: (
            refresh_calls.append((video["id"], api_key, digest_depth, user_id))
            or "Updated source report and timestamped topics from the existing transcript (1 reports, 6 topics)."
        ),
    )
    monkeypatch.setattr(
        ingest,
        "fetch_transcript_chunks",
        lambda video_id: (_ for _ in ()).throw(
            AssertionError("reused video refresh should load stored chunks, not fetch YouTube")
        ),
    )
    monkeypatch.setattr(
        ingest,
        "get_embeddings",
        lambda api_key=None: (_ for _ in ()).throw(
            AssertionError("reused video refresh should not generate embeddings")
        ),
    )

    messages = list(ingest.ingest_single_video_pg("yt123", "user-2", api_key="key"))

    assert any("Updated source report and timestamped topics" in message for message in messages)
    assert any("Added the existing embeddings to your library" in message for message in messages)
    assert refresh_calls == [("video-db-id", "key", "standard", "user-2")]


def test_ingest_single_video_new_index_grants_precise_video_access(monkeypatch):
    lookup_count = 0
    grant_calls = []
    usage_calls = []

    def fake_get_indexed_video_pg(supabase, video_id):
        nonlocal lookup_count
        lookup_count += 1
        if lookup_count == 1:
            return None
        return {
            "id": "video-db-id",
            "channel_id": "channel-db-id",
            "youtube_video_id": video_id,
            "transcript_seconds": 60,
        }

    monkeypatch.setattr(ingest, "get_supabase", lambda: object())
    monkeypatch.setattr(ingest, "get_indexed_video_pg", fake_get_indexed_video_pg)
    monkeypatch.setattr(ingest, "fetch_video_metadata", lambda video_id: ("Title", "Channel"))
    monkeypatch.setattr(
        ingest,
        "get_or_create_channel",
        lambda supabase, youtube_handle, channel_name, user_id: {"id": "channel-db-id"},
    )
    monkeypatch.setattr(
        ingest,
        "ensure_user_channel_subscription",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("single-video imports should not grant full channel access")
        ),
    )
    monkeypatch.setattr(
        ingest,
        "get_user_profile",
        lambda supabase, user_id: {
            "free_indexed_videos_total": 0,
            "free_indexed_seconds_total": 0,
        },
    )
    monkeypatch.setattr(ingest, "check_index_quota", lambda profile, count, seconds=0: True)
    monkeypatch.setattr(
        ingest,
        "fetch_transcript_chunks",
        lambda video_id: SimpleNamespace(
            chunks=[{"text": "hello", "start_seconds": 0, "end_seconds": 60}],
            skip_reason=None,
        ),
    )
    monkeypatch.setattr(ingest, "index_video_to_pg", lambda *_args, **_kwargs: 1)

    def fake_grant_user_video_access(
        supabase,
        user_id,
        video,
        used_own_key=False,
        access_source="shared_existing",
        source_url=None,
        charge_usage=True,
    ):
        grant_calls.append((user_id, video["id"], access_source, source_url, charge_usage))
        return None

    monkeypatch.setattr(ingest, "grant_user_video_access", fake_grant_user_video_access)
    monkeypatch.setattr(
        ingest,
        "increment_index_usage",
        lambda supabase, user_id, video_count, used_own_key, transcript_seconds=0: (
            usage_calls.append((user_id, video_count, transcript_seconds))
        ),
    )

    messages = list(ingest.ingest_single_video_pg("yt123", "user-2"))

    assert "Added video to your library" in messages
    assert grant_calls == [
        ("user-2", "video-db-id", "ingest", "https://www.youtube.com/watch?v=yt123", False)
    ]
    assert usage_calls == [("user-2", 1, 60)]


def test_ingest_url_uses_normalized_channel_url(monkeypatch):
    captured = []

    monkeypatch.setattr(
        ingest,
        "ingest_channel_pg",
        lambda channel_url, *_args, **_kwargs: captured.append(channel_url) or iter(["ok"]),
    )

    messages = list(ingest.ingest_url_pg("youtube.com/@SomeChannel/videos", "user-1"))

    assert messages[0] == "Detected URL type: CHANNEL"
    assert messages[1] == "ok"
    assert captured == ["https://youtube.com/@SomeChannel/videos"]
