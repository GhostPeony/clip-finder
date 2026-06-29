from fastapi.testclient import TestClient

from backend import context


class Result:
    def __init__(self, data):
        self.data = data


class Query:
    def __init__(self, table_name, supabase):
        self.table_name = table_name
        self.supabase = supabase

    def select(self, *args, **kwargs):
        self.supabase.calls.append((self.table_name, "select", args, kwargs))
        return self

    def eq(self, column, value):
        self.supabase.calls.append((self.table_name, "eq", column, value))
        return self

    def in_(self, column, values):
        self.supabase.calls.append((self.table_name, "in", column, values))
        return self

    def match(self, payload):
        self.supabase.calls.append((self.table_name, "match", payload))
        return self

    def maybe_single(self):
        self.supabase.calls.append((self.table_name, "maybe_single"))
        return self

    def order(self, column, desc=False):
        self.supabase.calls.append((self.table_name, "order", column, desc))
        return self

    def limit(self, value):
        self.supabase.calls.append((self.table_name, "limit", value))
        return self

    def or_(self, expression):
        self.supabase.calls.append((self.table_name, "or", expression))
        return self

    def insert(self, payload):
        self.supabase.calls.append((self.table_name, "insert", payload))
        self.supabase.inserted[self.table_name] = payload
        return self

    def upsert(self, payload, **kwargs):
        self.supabase.calls.append((self.table_name, "upsert", payload, kwargs))
        self.supabase.inserted[self.table_name] = payload
        return self

    def execute(self):
        if self.table_name in self.supabase.inserted:
            return Result([{**self.supabase.inserted[self.table_name], "id": "new-row"}])
        return Result(self.supabase.responses.get(self.table_name, []))


class Supabase:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.inserted = {}
        self.calls = []

    def table(self, table_name):
        self.calls.append(("table", table_name))
        return Query(table_name, self)


class RpcQuery:
    def __init__(self, supabase, name, payload):
        self.supabase = supabase
        self.name = name
        self.payload = payload

    def execute(self):
        return Result(self.supabase.rpc_responses.get(self.name, []))


class RpcSupabase(Supabase):
    def __init__(self, responses=None, rpc_responses=None):
        super().__init__(responses)
        self.rpc_responses = rpc_responses or {}
        self.rpc_calls = []

    def rpc(self, name, payload):
        self.rpc_calls.append((name, payload))
        return RpcQuery(self, name, payload)


class MissingIndexedByQuery(Query):
    def __init__(self, table_name, supabase):
        super().__init__(table_name, supabase)
        self.selected_columns = ""
        self.filters = []

    def select(self, *args, **kwargs):
        if args:
            self.selected_columns = str(args[0])
        return super().select(*args, **kwargs)

    def eq(self, column, value):
        self.filters.append((column, value))
        return super().eq(column, value)

    def execute(self):
        if self.table_name == "videos" and (
            "indexed_by" in self.selected_columns
            or any(column == "indexed_by" for column, _value in self.filters)
        ):
            raise Exception("column videos.indexed_by does not exist")
        return super().execute()


class MissingIndexedBySupabase(Supabase):
    def table(self, table_name):
        self.calls.append(("table", table_name))
        return MissingIndexedByQuery(table_name, self)


def test_get_video_context_requires_user_channel_subscription():
    supabase = Supabase(
        {
            "videos": {"id": "video-db", "channel_id": "channel-db", "youtube_video_id": "yt"},
            "user_channels": [],
        }
    )

    assert context.get_video_context(supabase, "user-1", "yt") is None
    assert ("table", "chunks") not in supabase.calls
    assert ("table", "source_concepts") not in supabase.calls


def test_get_video_context_returns_source_context_for_subscribed_user():
    supabase = Supabase(
        {
            "videos": {
                "id": "video-db",
                "channel_id": "channel-db",
                "youtube_video_id": "yt",
                "title": "A Video",
                "thumbnail_url": "thumb",
                "transcript_seconds": 120,
            },
            "user_channels": {"user_id": "user-1"},
            "channels": {"id": "channel-db", "name": "Channel", "youtube_handle": "@channel"},
            "transcript_lines": [
                {"id": "line-1", "content": "hello", "start_seconds": 0, "end_seconds": 2}
            ],
            "chunks": [{"id": "chunk-1", "content": "hello world"}],
            "source_concepts": [{"id": "concept-1", "name": "RLHF"}],
            "source_edges": [{"id": "edge-1", "relation": "explains"}],
            "knowledge_artifacts": [{"id": "artifact-1", "artifact_type": "study_guide"}],
        }
    )

    result = context.get_video_context(supabase, "user-1", "yt")

    assert result["video"]["videoId"] == "yt"
    assert result["video"]["channel"]["name"] == "Channel"
    assert result["video"]["accessScope"] == "channel"
    assert result["video"]["accessSource"] == "channel"
    assert result["video"]["accessReason"] == "Visible through a channel access grant."
    assert result["transcriptLines"][0]["id"] == "line-1"
    assert result["sourceConcepts"][0]["name"] == "RLHF"
    assert ("knowledge_artifacts", "or", "user_id.is.null,user_id.eq.user-1") in supabase.calls


def test_get_video_context_returns_source_context_for_explicit_video_grant():
    supabase = Supabase(
        {
            "videos": {
                "id": "video-db",
                "channel_id": "channel-db",
                "youtube_video_id": "yt",
                "title": "A Shared Video",
                "thumbnail_url": "thumb",
                "transcript_seconds": 120,
            },
            "user_channels": [],
            "user_videos": {"user_id": "user-1", "access_source": "shared_existing"},
            "channels": {"id": "channel-db", "name": "Channel", "youtube_handle": "@channel"},
            "transcript_lines": [],
            "chunks": [],
            "source_concepts": [],
            "source_edges": [],
            "knowledge_artifacts": [],
        }
    )

    result = context.get_video_context(supabase, "user-1", "yt")

    assert result["video"]["videoId"] == "yt"
    assert result["video"]["accessScope"] == "video"
    assert result["video"]["accessSource"] == "shared_existing"
    assert result["video"]["accessReason"] == "Visible through an explicit saved-video grant."
    assert ("user_videos", "select", ("user_id, access_source",), {}) in supabase.calls


def test_get_video_context_marks_channel_and_video_access_when_both_apply():
    supabase = Supabase(
        {
            "videos": {
                "id": "video-db",
                "channel_id": "channel-db",
                "youtube_video_id": "yt",
                "title": "A Saved Channel Video",
                "thumbnail_url": "thumb",
                "transcript_seconds": 120,
            },
            "user_channels": {"user_id": "user-1"},
            "user_videos": {"user_id": "user-1", "access_source": "playlist"},
            "channels": {"id": "channel-db", "name": "Channel", "youtube_handle": "@channel"},
            "transcript_lines": [],
            "chunks": [],
            "source_concepts": [],
            "source_edges": [],
            "knowledge_artifacts": [],
        }
    )

    result = context.get_video_context(supabase, "user-1", "yt")

    assert result["video"]["accessScope"] == "channel_and_video"
    assert result["video"]["accessSource"] == "playlist"
    assert (
        result["video"]["accessReason"]
        == "Visible through channel access and an explicit video grant."
    )


def test_list_video_library_context_groups_recent_videos_by_user_channels():
    supabase = Supabase(
        {
            "user_channels": [{"channel_id": "channel-a"}, {"channel_id": "channel-b"}],
            "channels": [
                {"id": "channel-a", "name": "AI Explained", "youtube_handle": "@ai"},
                {"id": "channel-b", "name": "Model Gym", "youtube_handle": "@gym"},
            ],
            "videos": [
                {
                    "id": "video-db-1",
                    "channel_id": "channel-a",
                    "youtube_video_id": "yt-a",
                    "title": "Reward Models",
                    "thumbnail_url": "thumb-a",
                    "transcript_seconds": 640,
                    "indexed_at": "2026-06-20T12:00:00Z",
                },
                {
                    "id": "video-db-2",
                    "channel_id": "channel-b",
                    "youtube_video_id": "yt-b",
                    "title": "Eval Harnesses",
                    "thumbnail_url": "thumb-b",
                    "transcript_seconds": 480,
                    "indexed_at": "2026-06-19T12:00:00Z",
                },
            ],
        }
    )

    library = context.list_video_library_context(supabase, "user-1", limit=25)

    assert library["totalChannels"] == 2
    assert library["returnedVideos"] == 2
    assert library["channels"][0]["name"] == "AI Explained"
    assert library["channels"][0]["videos"][0]["videoId"] == "yt-a"
    assert library["channels"][0]["videos"][0]["accessScope"] == "channel"
    assert library["channels"][0]["videos"][0]["accessSource"] == "channel"
    assert library["channels"][1]["youtubeHandle"] == "@gym"
    assert library["channels"][1]["returnedVideoCount"] == 1
    assert "get_video_context" in library["guidance"]
    assert ("user_channels", "eq", "user_id", "user-1") in supabase.calls
    assert ("channels", "in", "id", ["channel-a", "channel-b"]) in supabase.calls
    assert ("videos", "in", "channel_id", ["channel-a", "channel-b"]) in supabase.calls
    assert ("videos", "limit", 25) in supabase.calls


def test_list_video_library_context_marks_explicit_video_grants():
    supabase = Supabase(
        {
            "user_channels": [],
            "user_videos": [{"video_id": "video-db-1", "access_source": "shared_existing"}],
            "channels": [{"id": "channel-a", "name": "AI Explained", "youtube_handle": "@ai"}],
            "videos": [
                {
                    "id": "video-db-1",
                    "channel_id": "channel-a",
                    "youtube_video_id": "yt-a",
                    "title": "Reward Models",
                    "thumbnail_url": "thumb-a",
                    "transcript_seconds": 640,
                    "indexed_at": "2026-06-20T12:00:00Z",
                }
            ],
        }
    )

    library = context.list_video_library_context(supabase, "user-1", limit=25)
    video = library["channels"][0]["videos"][0]

    assert video["videoId"] == "yt-a"
    assert video["accessScope"] == "video"
    assert video["accessSource"] == "shared_existing"
    assert video["accessReason"] == "Visible through an explicit saved-video grant."
    assert ("videos", "in", "id", ["video-db-1"]) in supabase.calls


def test_create_agent_note_writes_only_overlay_table():
    supabase = Supabase()

    note = context.create_agent_note(
        supabase,
        "user-1",
        "Use this for the model gym.",
        [{"source_type": "video", "source_id": "yt"}],
        ["ml"],
        created_by_client="hermes",
    )

    assert note["id"] == "new-row"
    assert supabase.inserted["agent_notes"]["user_id"] == "user-1"
    assert supabase.inserted["agent_notes"]["created_by_client"] == "hermes"
    assert all(call[0] not in {"chunks", "source_concepts", "videos"} for call in supabase.calls)


def test_create_agent_note_queues_external_brain_event(monkeypatch):
    supabase = Supabase()
    sync_events = []

    def fake_queue(*args, **kwargs):
        sync_events.append((args, kwargs))
        return {"queuedCount": 1}

    monkeypatch.setattr(context, "queue_brain_sync_event", fake_queue)

    context.create_agent_note(
        supabase,
        "user-1",
        "Use this for the model gym.",
        [{"source_type": "video", "source_id": "yt"}],
        ["ml"],
        created_by_client="hermes",
    )

    args, kwargs = sync_events[0]
    assert args[:3] == (supabase, "user-1", "overlay.note.created")
    assert kwargs["payload"]["noteId"] == "new-row"
    assert kwargs["payload"]["contentPreview"] == "Use this for the model gym."
    assert kwargs["payload"]["createdByClient"] == "hermes"
    assert kwargs["source_ref"] == {"type": "agent_note", "id": "new-row"}
    assert kwargs["idempotency_key"] == "overlay.note.created:new-row"


def test_build_brain_digest_export_returns_compact_user_granted_context():
    source_ref = {
        "source_type": "transcript",
        "youtube_video_id": "yt",
        "start_seconds": 45,
        "end_seconds": 75,
    }
    supabase = Supabase(
        {
            "user_channels": [{"channel_id": "channel-db"}],
            "user_videos": [{"video_id": "video-db", "access_source": "playlist"}],
            "videos": [
                {
                    "id": "video-db",
                    "channel_id": "channel-db",
                    "youtube_video_id": "yt",
                    "title": "Sierra Harness Podcast",
                    "thumbnail_url": "thumb",
                    "transcript_seconds": 3600,
                    "indexed_at": "2026-06-20T12:00:00Z",
                }
            ],
            "channels": [
                {"id": "channel-db", "name": "Product Builders", "youtube_handle": "@builders"}
            ],
            "source_labels": [
                {
                    "id": "label-1",
                    "video_id": "video-db",
                    "label_type": "task_fit",
                    "label": "agent harness",
                    "confidence": 0.93,
                    "source_refs": [source_ref],
                    "created_at": "2026-06-20T12:05:00Z",
                }
            ],
            "source_concepts": [
                {
                    "id": "concept-1",
                    "video_id": "video-db",
                    "concept_type": "method",
                    "name": "Eval harness loop",
                    "summary": "Use product telemetry, simulations, and review loops to improve agents.",
                    "source_refs": [source_ref],
                    "updated_at": "2026-06-20T12:10:00Z",
                }
            ],
            "knowledge_artifacts": [
                {
                    "id": "artifact-1",
                    "video_id": "video-db",
                    "artifact_type": "tldr",
                    "title": "Harness TLDR",
                    "summary": "A compact summary of the operating loop.",
                    "content": "Longer implementation notes that should stay excerpted.",
                    "source_refs": [source_ref],
                    "updated_at": "2026-06-20T12:15:00Z",
                }
            ],
            "agent_notes": [
                {
                    "id": "note-1",
                    "content": "Connect this to the model gym workflow.",
                    "source_refs": [source_ref],
                    "tags": ["model-gym"],
                    "created_by": "agent",
                    "created_by_client": "hermes",
                    "created_at": "2026-06-20T12:20:00Z",
                }
            ],
            "personal_concepts": [
                {
                    "id": "pc-1",
                    "name": "Training gym harness",
                    "summary": "Personal project bridge for eval workflows.",
                    "status": "learning",
                    "source_refs": [source_ref],
                    "updated_at": "2026-06-20T12:25:00Z",
                }
            ],
        }
    )

    export = context.build_brain_digest_export(supabase, "user-1", limit=5)

    assert export["version"] == "memexai-brain-digest-v1"
    assert export["sync"]["nextCursor"]
    assert export["sync"]["objects"] == [
        "artifacts",
        "concepts",
        "labels",
        "notes",
        "personal_concepts",
        "videos",
    ]
    assert export["accessModel"]["scope"] == "current_user_grants"
    assert export["digest"]["videos"][0]["accessScope"] == "channel_and_video"
    assert export["digest"]["videos"][0]["accessSource"] == "playlist"
    assert export["digest"]["sourceLabels"][0]["video"]["videoId"] == "yt"
    assert export["digest"]["sourceConcepts"][0]["name"] == "Eval harness loop"
    assert export["digest"]["knowledgeArtifacts"][0]["contentExcerpt"]
    assert export["digest"]["agentNotes"][0]["createdByClient"] == "hermes"
    assert export["digest"]["personalConcepts"][0]["status"] == "learning"
    assert ("videos", "in", "channel_id", ["channel-db"]) in supabase.calls
    assert ("source_labels", "in", "video_id", ["video-db"]) in supabase.calls
    assert ("knowledge_artifacts", "or", "user_id.is.null,user_id.eq.user-1") in supabase.calls


def test_build_brain_digest_export_honors_notes_only_since_filter():
    supabase = Supabase(
        {
            "agent_notes": [
                {
                    "id": "note-new",
                    "content": "Fresh takeaway for the personal brain.",
                    "created_at": "2026-06-20T13:00:00Z",
                },
                {
                    "id": "note-old",
                    "content": "Already synced.",
                    "created_at": "2026-06-20T12:00:00Z",
                },
            ],
        }
    )

    export = context.build_brain_digest_export(
        supabase,
        "user-1",
        since="2026-06-20T12:30:00Z",
        objects=["notes"],
        limit=10,
    )

    assert export["sync"]["since"] == "2026-06-20T12:30:00Z"
    assert export["sync"]["objects"] == ["notes"]
    assert [note["id"] for note in export["digest"]["agentNotes"]] == ["note-new"]
    assert export["digest"]["videos"] == []
    assert all(call[1] != "source_labels" for call in supabase.calls if call[0] == "table")
    assert all(call[1] != "videos" for call in supabase.calls if call[0] == "table")
    assert ("agent_notes", "eq", "user_id", "user-1") in supabase.calls


def test_build_context_bundle_accepts_agent_supplied_repo_context():
    supabase = Supabase(
        {
            "agent_notes": [{"id": "note-1", "content": "Personal note"}],
            "personal_concepts": [{"id": "pc-1", "name": "Training gym idea"}],
        }
    )
    repo_context = {
        "source": "mcp",
        "repo": "GhostPeony/model-gym",
        "features": ["reward model experiments"],
    }

    bundle = context.build_context_bundle(supabase, "user-1", "apply RLHF", repo_context)

    assert bundle["repoContext"] == repo_context
    assert bundle["personalConcepts"][0]["name"] == "Training gym idea"
    assert "agent-supplied context" in bundle["guidance"]


def test_build_context_bundle_includes_user_scoped_source_knowledge():
    supabase = Supabase(
        {
            "agent_notes": [],
            "personal_concepts": [],
            "user_channels": [{"channel_id": "channel-db"}],
            "videos": [
                {
                    "id": "video-db",
                    "youtube_video_id": "yt",
                    "title": "RLHF lesson",
                    "thumbnail_url": "thumb",
                    "transcript_seconds": 120,
                }
            ],
            "source_concepts": [
                {
                    "id": "concept-1",
                    "video_id": "video-db",
                    "concept_type": "algorithm",
                    "name": "RLHF reward model",
                    "summary": "Preference model for training loops.",
                },
                {
                    "id": "concept-2",
                    "video_id": "video-db",
                    "concept_type": "tool",
                    "name": "Unrelated deployment note",
                    "summary": "Shipping checklist.",
                },
            ],
            "source_edges": [{"id": "edge-1", "video_id": "video-db", "relation": "supports"}],
            "knowledge_artifacts": [
                {
                    "id": "artifact-1",
                    "video_id": "video-db",
                    "artifact_type": "study_guide",
                    "title": "RLHF Study Guide",
                    "summary": "Reward modeling overview.",
                    "content": "Use reward models in eval harnesses.",
                }
            ],
        }
    )

    bundle = context.build_context_bundle(
        supabase,
        "user-1",
        "apply RLHF to my eval harness",
        {"source": "agent-mcp", "repo": "GhostPeony/open-model-gym"},
        limit=8,
    )

    source_context = bundle["sourceContext"]
    assert source_context["videos"][0]["videoId"] == "yt"
    assert [concept["name"] for concept in source_context["sourceConcepts"]] == [
        "RLHF reward model"
    ]
    assert source_context["knowledgeArtifacts"][0]["title"] == "RLHF Study Guide"
    assert source_context["sourceEdges"][0]["relation"] == "supports"
    assert ("videos", "in", "channel_id", ["channel-db"]) in supabase.calls


def test_list_context_categories_groups_source_labels_and_overlay_concepts():
    source_ref = {
        "source_type": "transcript",
        "youtube_video_id": "yt",
        "start_seconds": 30,
        "end_seconds": 75,
    }
    supabase = Supabase(
        {
            "user_channels": [{"channel_id": "channel-db"}],
            "videos": [
                {
                    "id": "video-db",
                    "youtube_video_id": "yt",
                    "title": "Sierra Harness Podcast",
                    "thumbnail_url": "thumb",
                    "transcript_seconds": 120,
                }
            ],
            "source_labels": [
                {
                    "id": "label-1",
                    "video_id": "video-db",
                    "label_type": "task_fit",
                    "label": "eval harness",
                    "confidence": 0.91,
                    "source_refs": [source_ref],
                },
                {
                    "id": "label-2",
                    "video_id": "video-db",
                    "label_type": "domain",
                    "label": "AI product",
                    "confidence": 0.83,
                    "source_refs": [],
                },
            ],
            "source_concepts": [
                {
                    "id": "concept-1",
                    "video_id": "video-db",
                    "concept_type": "method",
                    "name": "Harness-driven product development",
                    "summary": "Use eval harnesses to shape agent behavior.",
                    "source_refs": [source_ref],
                }
            ],
            "knowledge_artifacts": [
                {
                    "id": "artifact-1",
                    "video_id": "video-db",
                    "artifact_type": "study_guide",
                    "title": "Harness Study Guide",
                }
            ],
            "personal_concepts": [
                {
                    "id": "pc-1",
                    "name": "Model gym curriculum",
                    "status": "learning",
                }
            ],
        }
    )

    categories = context.list_context_categories(supabase, "user-1", limit=20)

    assert categories["videoCount"] == 1
    assert categories["sourceLabelCount"] == 2
    assert categories["facets"]["task_fit"] == ["eval harness"]
    assert categories["facets"]["domain"] == ["AI product"]
    assert categories["taxonomy"]["facets"]["task_fit"]["description"]
    assert categories["filterExamples"][0]["task_fit"]
    assert categories["personalConcepts"][0]["name"] == "Model gym curriculum"
    assert categories["categories"][0]["count"] == 1
    assert any(category["label"] == "eval harness" for category in categories["categories"])
    assert ("source_labels", "in", "video_id", ["video-db"]) in supabase.calls
    assert ("personal_concepts", "eq", "user_id", "user-1") in supabase.calls


def test_build_context_bundle_applies_category_filters():
    supabase = Supabase(
        {
            "agent_notes": [],
            "personal_concepts": [],
            "user_channels": [{"channel_id": "channel-db"}],
            "user_videos": [],
            "videos": [
                {
                    "id": "video-match",
                    "channel_id": "channel-db",
                    "youtube_video_id": "yt-match",
                    "title": "Harness lesson",
                    "thumbnail_url": "thumb",
                    "transcript_seconds": 120,
                },
                {
                    "id": "video-other",
                    "channel_id": "channel-db",
                    "youtube_video_id": "yt-other",
                    "title": "Unrelated lesson",
                    "thumbnail_url": "thumb",
                    "transcript_seconds": 90,
                },
            ],
            "source_labels": [
                {
                    "id": "label-1",
                    "video_id": "video-match",
                    "label_type": "task_fit",
                    "label": "product spec",
                    "confidence": 0.9,
                },
                {
                    "id": "label-2",
                    "video_id": "video-other",
                    "label_type": "task_fit",
                    "label": "study guide",
                    "confidence": 0.8,
                },
            ],
            "source_concepts": [
                {
                    "id": "concept-1",
                    "video_id": "video-match",
                    "concept_type": "method",
                    "name": "Harness loop",
                    "summary": "Use source labels to narrow planning.",
                },
                {
                    "id": "concept-2",
                    "video_id": "video-other",
                    "concept_type": "method",
                    "name": "Other loop",
                    "summary": "Should not be included.",
                },
            ],
            "source_edges": [],
            "knowledge_artifacts": [],
        }
    )

    bundle = context.build_context_bundle(
        supabase,
        "user-1",
        "Harness",
        {"repo": "GhostPeony/memexai"},
        limit=8,
        category_filters={"task_fit": ["product spec"]},
    )

    assert bundle["categoryFilters"] == {"task_fit": ["product spec"]}
    assert bundle["sourceContext"]["videos"][0]["videoId"] == "yt-match"
    assert [concept["name"] for concept in bundle["sourceContext"]["sourceConcepts"]] == [
        "Harness loop"
    ]
    assert bundle["sourceContext"]["sourceLabels"][0]["label"] == "product spec"


def test_search_source_knowledge_returns_compact_concepts_and_artifacts():
    source_ref = {
        "source_type": "transcript",
        "youtube_video_id": "yt-match",
        "start_seconds": 30,
        "end_seconds": 75,
    }
    supabase = Supabase(
        {
            "user_channels": [{"channel_id": "channel-db"}],
            "user_videos": [],
            "videos": [
                {
                    "id": "video-match",
                    "channel_id": "channel-db",
                    "youtube_video_id": "yt-match",
                    "title": "Harness lesson",
                    "thumbnail_url": "thumb",
                    "transcript_seconds": 120,
                }
            ],
            "source_labels": [
                {
                    "id": "label-1",
                    "video_id": "video-match",
                    "label_type": "task_fit",
                    "label": "study guide",
                    "confidence": 0.9,
                }
            ],
            "source_concepts": [
                {
                    "id": "concept-1",
                    "video_id": "video-match",
                    "concept_type": "method",
                    "name": "Harness loop",
                    "summary": "Use harness loops to evaluate agent behavior before rollout.",
                    "source_refs": [source_ref],
                }
            ],
            "source_edges": [],
            "knowledge_artifacts": [
                {
                    "id": "artifact-1",
                    "video_id": "video-match",
                    "artifact_type": "study_guide",
                    "title": "Harness Study Guide",
                    "summary": "A study guide for harness-driven product development.",
                    "content": "Harness loop " * 200,
                    "source_refs": [source_ref],
                }
            ],
        }
    )

    result = context.search_source_knowledge(
        supabase,
        "user-1",
        "harness loop",
        limit=5,
        category_filters={"task_fit": ["study guide"]},
        detail_level="compact",
        max_chars=4000,
    )

    assert result["retrievalMode"] == "hybrid"
    assert result["detailLevel"] == "compact"
    assert result["categoryFilters"] == {"task_fit": ["study guide"]}
    assert result["retrievalBudget"]["embeddingCalls"] == 0
    assert result["retrievalPlan"]["fallbackUsed"] is True
    assert result["retrievalBudget"]["llmCalls"] == 0
    assert result["retrievalBudget"]["maxChars"] == 4000
    assert result["retrievalBudget"]["estimatedResponseChars"] <= 4000
    assert {item["resultType"] for item in result["results"]} == {
        "source_concept",
        "knowledge_artifact",
    }
    artifact = next(
        item for item in result["results"] if item["resultType"] == "knowledge_artifact"
    )
    concept = next(item for item in result["results"] if item["resultType"] == "source_concept")
    assert concept["video"]["accessScope"] == "channel"
    assert concept["video"]["accessSource"] == "channel"
    assert artifact["video"]["accessScope"] == "channel"
    assert artifact["video"]["accessSource"] == "channel"
    assert len(artifact["contentExcerpt"]) <= 700
    assert artifact["matchType"] == "artifact_keyword"
    assert artifact["contentExcerptStrategy"] in {"matched_terms", "matched_heading"}
    assert artifact["matchedTerms"] == ["harness", "loop"]
    assert artifact["sourceRefs"][0]["youtube_video_id"] == "yt-match"


def test_search_source_knowledge_returns_query_focused_artifact_excerpt():
    source_ref = {
        "source_type": "transcript",
        "youtube_video_id": "yt-match",
        "start_seconds": 210,
        "end_seconds": 260,
    }
    long_opening = "Opening context about the saved video and general product framing. " * 20
    supabase = Supabase(
        {
            "user_channels": [{"channel_id": "channel-db"}],
            "user_videos": [],
            "videos": [
                {
                    "id": "video-match",
                    "channel_id": "channel-db",
                    "youtube_video_id": "yt-match",
                    "title": "Agent report",
                    "thumbnail_url": "thumb",
                    "transcript_seconds": 600,
                }
            ],
            "source_labels": [],
            "source_concepts": [],
            "source_edges": [],
            "knowledge_artifacts": [
                {
                    "id": "artifact-1",
                    "video_id": "video-match",
                    "artifact_type": "study_guide",
                    "title": "Production Agent Report",
                    "summary": "A source-backed report.",
                    "content": (
                        "# Production Agent Report\n\n"
                        "## Compiled Truth\n\n"
                        f"{long_opening}\n\n"
                        "## Latency Budget Rules\n\n"
                        "- The latency budget section explains that production agents need "
                        "bounded tool calls, predictable retries, and explicit fallback paths. "
                        "This lets an agent retrieve the operational tradeoff without scanning "
                        "the full transcript. (source: 3:30)"
                    ),
                    "source_refs": [source_ref],
                }
            ],
        }
    )

    result = context.search_source_knowledge(
        supabase,
        "user-1",
        "latency budget retry",
        limit=3,
        detail_level="compact",
        max_chars=2500,
    )

    artifact = result["results"][0]
    assert artifact["resultType"] == "knowledge_artifact"
    assert artifact["contentExcerptStart"] > 0
    assert artifact["contentExcerptStrategy"] == "matched_heading"
    assert artifact["matchedTerms"] == ["latency", "budget"]
    assert artifact["matchedHeadings"] == ["Latency Budget Rules"]
    assert "production agents" in artifact["contentExcerpt"]
    assert "bounded tool calls" in artifact["contentExcerpt"]
    assert "Opening context about the saved video" not in artifact["contentExcerpt"]


def test_search_source_knowledge_uses_hybrid_index_rpc_with_aliases_and_next_call():
    source_ref = {
        "source_type": "transcript",
        "youtube_video_id": "yt-harness",
        "start_seconds": 120,
        "end_seconds": 180,
    }
    supabase = RpcSupabase(
        rpc_responses={
            "search_source_knowledge_hybrid": [
                {
                    "id": "index-1",
                    "video_id": "video-db",
                    "source_object_type": "report_section",
                    "source_object_id": "artifact:0:source-report",
                    "section_key": "agent-quick-index",
                    "title": "Agent Quick Index",
                    "body": "Use this section when an agent needs retrieval hints for harness loops.",
                    "aliases": ["retrieval hints", "agent index"],
                    "source_refs": [source_ref],
                    "metadata": {
                        "artifactType": "study_guide",
                        "sectionHeading": "Agent Quick Index",
                        "sectionOrder": 2,
                    },
                    "youtube_video_id": "yt-harness",
                    "video_title": "Harness lesson",
                    "channel_name": "Agent Channel",
                    "thumbnail_url": "thumb",
                    "transcript_seconds": 600,
                    "similarity": 0.81,
                    "keyword_rank": 0.4,
                    "hybrid_score": 0.036,
                    "match_type": "hybrid",
                    "access_scope": "video",
                    "access_source": "playlist",
                    "access_reason": "Visible through an explicit saved-video grant.",
                }
            ]
        }
    )
    embed_calls = []

    result = context.search_source_knowledge(
        supabase,
        "user-1",
        "how do agents find harness loops",
        limit=5,
        retrieval_mode="hybrid",
        embedding_provider=lambda query: embed_calls.append(query) or [0.1, 0.2, 0.3],
    )

    assert embed_calls == ["how do agents find harness loops"]
    assert supabase.rpc_calls[0][0] == "search_source_knowledge_hybrid"
    assert supabase.rpc_calls[0][1]["retrieval_mode"] == "hybrid"
    assert supabase.rpc_calls[0][1]["query_embedding"] == [0.1, 0.2, 0.3]
    assert result["retrievalMode"] == "hybrid"
    assert result["retrievalPlan"]["primary"] == "source_knowledge_index_hybrid_vector_keyword"
    assert result["retrievalBudget"]["embeddingCalls"] == 1
    assert result["retrievalBudget"]["llmCalls"] == 0
    item = result["results"][0]
    assert item["resultType"] == "report_section"
    assert item["aliases"] == ["retrieval hints", "agent index"]
    assert item["sourceRefs"][0]["start_seconds"] == 120
    assert item["video"]["accessScope"] == "video"
    assert item["next_mcp_call"]["name"] == "get_video_knowledge_map"
    assert result["next_mcp_call"]["name"] == "get_video_knowledge_map"


def test_search_source_knowledge_keyword_mode_avoids_embedding_calls():
    supabase = RpcSupabase(
        rpc_responses={
            "search_source_knowledge_hybrid": [
                {
                    "id": "index-1",
                    "video_id": "video-db",
                    "source_object_type": "source_concept",
                    "source_object_id": "concept:0:rlhf",
                    "section_key": "",
                    "title": "RLHF",
                    "body": "Human feedback is converted into model-facing evaluation signal.",
                    "aliases": ["reward modeling"],
                    "source_refs": [],
                    "metadata": {"conceptType": "method"},
                    "youtube_video_id": "yt-rlhf",
                    "video_title": "RLHF Lesson",
                    "channel_name": "AI Channel",
                    "match_type": "title_alias_keyword",
                    "keyword_rank": 0.7,
                    "hybrid_score": 0.02,
                    "access_scope": "channel",
                    "access_source": "channel",
                    "access_reason": "Visible through a channel access grant.",
                }
            ]
        }
    )

    result = context.search_source_knowledge(
        supabase,
        "user-1",
        "reward modeling",
        limit=3,
        retrieval_mode="keyword",
        embedding_provider=lambda _query: (_ for _ in ()).throw(
            AssertionError("keyword mode should not embed")
        ),
    )

    assert supabase.rpc_calls[0][1]["query_embedding"] is None
    assert supabase.rpc_calls[0][1]["retrieval_mode"] == "keyword"
    assert result["retrievalMode"] == "keyword"
    assert result["retrievalBudget"]["embeddingCalls"] == 0
    assert result["results"][0]["name"] == "RLHF"
    assert result["results"][0]["conceptType"] == "method"


def test_search_source_knowledge_keyword_mode_falls_back_when_index_is_empty():
    source_ref = {
        "source_type": "transcript",
        "youtube_video_id": "yt-synthetic",
        "start_seconds": 90,
        "end_seconds": 140,
    }
    supabase = RpcSupabase(
        responses={
            "user_channels": [{"channel_id": "channel-db"}],
            "user_videos": [],
            "videos": [
                {
                    "id": "video-synthetic",
                    "channel_id": "channel-db",
                    "youtube_video_id": "yt-synthetic",
                    "title": "Synthetic Data Lesson",
                    "thumbnail_url": "thumb",
                    "transcript_seconds": 1800,
                }
            ],
            "source_labels": [],
            "source_concepts": [
                {
                    "id": "concept-synthetic",
                    "video_id": "video-synthetic",
                    "concept_type": "method",
                    "name": "Synthetic Data",
                    "summary": "Synthetic data is used to expand post-training coverage.",
                    "source_refs": [source_ref],
                }
            ],
            "source_edges": [],
            "knowledge_artifacts": [],
        },
        rpc_responses={"search_source_knowledge_hybrid": []},
    )

    result = context.search_source_knowledge(
        supabase,
        "user-1",
        "synthetic data",
        limit=3,
        retrieval_mode="keyword",
        embedding_provider=lambda _query: (_ for _ in ()).throw(
            AssertionError("keyword mode should not embed")
        ),
    )

    assert supabase.rpc_calls[0][1]["query_embedding"] is None
    assert supabase.rpc_calls[0][1]["retrieval_mode"] == "keyword"
    assert result["retrievalMode"] == "keyword"
    assert result["retrievalPlan"]["fallbackUsed"] is True
    assert "keyword search returned no matches" in result["retrievalPlan"]["fallbackReason"]
    assert result["retrievalBudget"]["embeddingCalls"] == 0
    assert result["results"][0]["resultType"] == "source_concept"
    assert result["results"][0]["name"] == "Synthetic Data"
    assert result["results"][0]["sourceRefs"][0]["start_seconds"] == 90


def test_build_video_knowledge_map_returns_sections_and_timestamp_refs():
    source_ref = {
        "source_type": "transcript",
        "youtube_video_id": "yt-map",
        "start_seconds": 210,
        "end_seconds": 260,
    }
    supabase = Supabase(
        {
            "videos": {
                "id": "video-map",
                "channel_id": "channel-db",
                "youtube_video_id": "yt-map",
                "title": "Agent harness map",
                "thumbnail_url": "thumb",
                "transcript_seconds": 600,
            },
            "user_channels": {"user_id": "user-1"},
            "channels": {"id": "channel-db", "name": "Agent Channel"},
            "transcript_lines": [],
            "chunks": [],
            "source_edges": [],
            "source_concepts": [
                {
                    "id": "concept-1",
                    "video_id": "video-map",
                    "concept_type": "claim",
                    "name": "Verification catches drift",
                    "summary": "Verification catches drift before rollout.",
                    "source_refs": [source_ref],
                }
            ],
            "knowledge_artifacts": [
                {
                    "id": "artifact-1",
                    "video_id": "video-map",
                    "artifact_type": "study_guide",
                    "title": "Source Report: Agent harness map",
                    "summary": "Report summary.",
                    "content": (
                        "# Agent harness map\n\n"
                        "## Compiled Truth\n\n"
                        "Harnesses make reliability inspectable. (source: 3:30)\n\n"
                        "## Decisions\n\n"
                        "- Add a verify step before release. (source: 3:30)"
                    ),
                    "source_refs": [source_ref],
                }
            ],
            "source_knowledge_index": [
                {
                    "id": "section-1",
                    "video_id": "video-map",
                    "source_object_type": "report_section",
                    "source_object_id": "artifact:0",
                    "section_key": "compiled-truth",
                    "title": "Compiled Truth",
                    "body": "Harnesses make reliability inspectable.",
                    "aliases": ["main takeaways"],
                    "source_refs": [source_ref],
                    "metadata": {"sectionOrder": 0, "sectionHeading": "Compiled Truth"},
                }
            ],
        }
    )

    result = context.build_video_knowledge_map(
        supabase,
        "user-1",
        "yt-map",
        detail_level="compact",
        max_chars=5000,
    )

    assert result["found"] is True
    assert result["video"]["videoId"] == "yt-map"
    assert result["reportSections"][0]["title"] == "Compiled Truth"
    assert result["claims"][0]["name"] == "Verification catches drift"
    assert result["timestampRefs"][0]["start_seconds"] == 210
    assert result["next_mcp_call"]["name"] == "search_video_moments"
    assert result["fallback_mcp_call"]["arguments"]["include_transcript"] is True


def test_build_library_source_graph_exposes_components_and_review_flags():
    source_ref = {
        "source_type": "transcript",
        "youtube_video_id": "yt-a",
        "start_seconds": 30,
        "end_seconds": 75,
    }
    supabase = Supabase(
        {
            "user_channels": [{"channel_id": "channel-db"}],
            "user_videos": [{"video_id": "video-a", "access_source": "playlist"}],
            "channels": [
                {"id": "channel-db", "name": "Research Channel", "youtube_handle": "@research"}
            ],
            "videos": [
                {
                    "id": "video-a",
                    "channel_id": "channel-db",
                    "youtube_video_id": "yt-a",
                    "title": "Harness lesson",
                    "thumbnail_url": "",
                    "transcript_seconds": 0,
                    "indexed_at": None,
                },
                {
                    "id": "video-b",
                    "channel_id": "channel-db",
                    "youtube_video_id": "yt-b",
                    "title": "Harness follow-up",
                    "thumbnail_url": "thumb-b",
                    "transcript_seconds": 120,
                    "indexed_at": "2026-06-20T12:00:00Z",
                },
            ],
            "source_labels": [
                {
                    "id": "label-1",
                    "video_id": "video-a",
                    "label_type": "task_fit",
                    "label": "agent QA",
                    "confidence": 0.8,
                    "source_refs": [],
                }
            ],
            "source_concepts": [
                {
                    "id": "concept-a",
                    "video_id": "video-a",
                    "concept_type": "claim",
                    "name": "Harness loop",
                    "summary": "Run the harness before every release.",
                    "source_refs": [source_ref],
                },
                {
                    "id": "concept-b",
                    "video_id": "video-b",
                    "concept_type": "claim",
                    "name": "Harness loop",
                    "summary": "Run the harness only for risky releases.",
                    "source_refs": [
                        {
                            **source_ref,
                            "youtube_video_id": "yt-b",
                            "start_seconds": 80,
                            "end_seconds": 120,
                        }
                    ],
                },
            ],
            "source_edges": [
                {
                    "id": "edge-1",
                    "video_id": "video-b",
                    "relation": "contrasts_with",
                    "from_ref": {"name": "Harness loop"},
                    "to_ref": {"name": "Release policy"},
                    "evidence_refs": [source_ref],
                }
            ],
            "knowledge_artifacts": [
                {
                    "id": "artifact-1",
                    "video_id": "video-b",
                    "artifact_type": "tldr",
                    "title": "Harness TLDR",
                    "summary": "A compact harness summary.",
                    "content": "Run evaluation loops before release. " * 80,
                    "source_refs": [source_ref],
                }
            ],
            "chunks": [
                {
                    "id": "chunk-a",
                    "video_id": "video-a",
                    "content": "Run the harness before every release with a clear timestamped reason.",
                    "start_seconds": 30,
                    "end_seconds": 75,
                },
                {
                    "id": "chunk-1",
                    "video_id": "video-b",
                    "content": "Harness loops reveal quality risks.",
                    "start_seconds": 80,
                    "end_seconds": 120,
                },
            ],
            "agent_notes": [
                {
                    "id": "note-1",
                    "content": "Use this for release readiness.",
                    "source_refs": [source_ref],
                    "tags": ["release"],
                    "created_by_client": "hermes",
                    "created_at": "2026-06-20T12:30:00Z",
                }
            ],
            "personal_concepts": [
                {
                    "id": "pc-1",
                    "name": "Release harness",
                    "summary": "My reusable QA loop.",
                    "status": "learning",
                    "source_refs": [source_ref],
                    "updated_at": "2026-06-20T12:35:00Z",
                }
            ],
        }
    )

    graph = context.build_library_source_graph(supabase, "user-1", limit=10)

    assert graph["version"] == "memexai-library-source-graph-v1"
    assert graph["accessModel"]["scope"] == "current_user_grants"
    assert graph["componentCounts"]["videos"] == 2
    assert graph["componentCounts"]["sourceConcepts"] == 2
    assert {node["type"] for node in graph["graph"]["nodes"]} >= {
        "video",
        "source_concept",
        "source_label",
        "knowledge_artifact",
        "transcript_chunk",
        "agent_note",
        "personal_concept",
    }
    flag_types = {flag["type"] for flag in graph["reviewFlags"]}
    assert "missing_transcript" in flag_types
    assert "missing_thumbnail" in flag_types
    assert "weak_evidence_refs" in flag_types
    assert "potential_conflict" in flag_types
    assert any("Conflicting information" in item["edgeCase"] for item in graph["edgeCaseHandling"])
    concept_node = next(
        node for node in graph["graph"]["nodes"] if node["id"] == "concept:concept-a"
    )
    assert concept_node["sourceRefs"][0]["quote"].startswith("Run the harness before")
    artifact_node = next(
        node for node in graph["graph"]["nodes"] if node["id"] == "artifact:artifact-1"
    )
    assert artifact_node["content"] == "Run evaluation loops before release. " * 80
    assert artifact_node["metadata"]["contentChars"] > 220


def test_build_library_source_graph_includes_legacy_indexed_by_rows():
    supabase = Supabase(
        {
            "user_channels": [],
            "user_videos": [],
            "channels": [{"id": "channel-db", "name": "Legacy Channel"}],
            "videos": [
                {
                    "id": "video-legacy",
                    "channel_id": "channel-db",
                    "youtube_video_id": "yt-legacy",
                    "title": "Legacy indexed video",
                    "thumbnail_url": "thumb",
                    "transcript_seconds": 180,
                    "indexed_at": "2026-06-20T12:00:00Z",
                    "indexed_by": "user-1",
                }
            ],
            "chunks": [
                {
                    "id": "chunk-1",
                    "video_id": "video-legacy",
                    "content": "Legacy transcript content still belongs in the graph.",
                    "start_seconds": 0,
                    "end_seconds": 60,
                }
            ],
            "source_labels": [],
            "source_concepts": [],
            "source_edges": [],
            "knowledge_artifacts": [],
            "agent_notes": [],
            "personal_concepts": [],
        }
    )

    graph = context.build_library_source_graph(supabase, "user-1", limit=10)

    assert graph["componentCounts"]["videos"] == 1
    assert graph["componentCounts"]["transcriptChunksSampled"] == 1
    assert graph["videos"][0]["accessScope"] == "user_library"
    assert graph["videos"][0]["accessSource"] == "legacy_indexed_by"
    assert any(node["id"] == "video:yt-legacy" for node in graph["graph"]["nodes"])


def test_build_library_source_graph_handles_missing_legacy_indexed_by_column():
    supabase = MissingIndexedBySupabase(
        {
            "user_channels": [],
            "user_videos": [{"video_id": "video-saved", "access_source": "ingest"}],
            "channels": [{"id": "channel-db", "name": "Saved Channel"}],
            "videos": [
                {
                    "id": "video-saved",
                    "channel_id": "channel-db",
                    "youtube_video_id": "yt-saved",
                    "title": "Saved video",
                    "thumbnail_url": "thumb",
                    "transcript_seconds": 180,
                    "indexed_at": "2026-06-20T12:00:00Z",
                }
            ],
            "chunks": [
                {
                    "id": "chunk-1",
                    "video_id": "video-saved",
                    "content": "Saved transcript content should still be available.",
                    "start_seconds": 0,
                    "end_seconds": 60,
                }
            ],
            "source_labels": [],
            "source_concepts": [],
            "source_edges": [],
            "knowledge_artifacts": [],
            "agent_notes": [],
            "personal_concepts": [],
        }
    )

    graph = context.build_library_source_graph(supabase, "user-1", limit=10)

    assert graph["componentCounts"]["videos"] == 1
    assert graph["componentCounts"]["transcriptChunksSampled"] == 1
    assert graph["videos"][0]["accessScope"] == "video"
    assert graph["videos"][0]["accessSource"] == "ingest"
    assert any(node["id"] == "video:yt-saved" for node in graph["graph"]["nodes"])


def test_search_library_components_matches_without_embedding_or_llm():
    source_ref = {
        "source_type": "transcript",
        "youtube_video_id": "yt-a",
        "start_seconds": 30,
        "end_seconds": 75,
    }
    supabase = Supabase(
        {
            "user_channels": [{"channel_id": "channel-db"}],
            "channels": [{"id": "channel-db", "name": "Research Channel"}],
            "videos": [
                {
                    "id": "video-a",
                    "channel_id": "channel-db",
                    "youtube_video_id": "yt-a",
                    "title": "Harness lesson",
                    "thumbnail_url": "thumb",
                    "transcript_seconds": 120,
                    "indexed_at": "2026-06-20T12:00:00Z",
                }
            ],
            "source_labels": [],
            "source_concepts": [
                {
                    "id": "concept-a",
                    "video_id": "video-a",
                    "concept_type": "method",
                    "name": "Harness loop",
                    "summary": "Harness loops improve agent QA.",
                    "source_refs": [source_ref],
                }
            ],
            "source_edges": [],
            "knowledge_artifacts": [
                {
                    "id": "artifact-1",
                    "video_id": "video-a",
                    "artifact_type": "study_guide",
                    "title": "Harness Study Guide",
                    "summary": "QA with harness loops.",
                    "content": "Harness loop " * 40,
                    "source_refs": [source_ref],
                }
            ],
            "chunks": [
                {
                    "id": "chunk-1",
                    "video_id": "video-a",
                    "content": "Harness loop quality checks appear here.",
                    "start_seconds": 30,
                    "end_seconds": 75,
                }
            ],
        }
    )

    result = context.search_library_components(supabase, "user-1", "harness loop", limit=10)

    assert result["retrievalMode"] == "component_keyword"
    assert result["accessModel"]["embeddingUsed"] is False
    assert result["accessModel"]["llmAnswerUsed"] is False
    assert result["retrievalBudget"]["embeddingCalls"] == 0
    assert result["retrievalBudget"]["llmCalls"] == 0
    assert {item["resultType"] for item in result["results"]} >= {
        "video",
        "source_concept",
        "knowledge_artifact",
        "transcript_chunk",
    }
    concept = next(item for item in result["results"] if item["resultType"] == "source_concept")
    assert concept["video"]["videoId"] == "yt-a"
    assert concept["sourceRefs"][0]["start_seconds"] == 30

    video_result = context.search_library_components(
        supabase,
        "user-1",
        "yt-a",
        limit=10,
        component_types=["video"],
    )

    assert video_result["results"][0]["resultType"] == "video"
    assert video_result["results"][0]["video"]["videoId"] == "yt-a"
    assert video_result["results"][0]["metadata"]["youtubeVideoId"] == "yt-a"


def test_library_graph_endpoint_uses_hosted_source_graph(monkeypatch):
    from backend import server

    monkeypatch.setenv("SEARCHTUBE_AUTH_MODE", "none")
    monkeypatch.setattr(server, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(server, "get_supabase", lambda: object())
    monkeypatch.setattr(
        server,
        "build_library_source_graph",
        lambda supabase, user_id, limit, **kwargs: {
            "userId": user_id,
            "limit": limit,
            "kwargs": kwargs,
            "graph": {"nodes": [], "edges": []},
        },
    )

    client = TestClient(server.app)
    response = client.get("/api/library/graph?limit=999")

    assert response.status_code == 200
    assert response.json() == {
        "userId": "local",
        "limit": 100,
        "kwargs": {
            "include_artifact_content": False,
            "include_auxiliary_nodes": False,
            "include_review_flags": False,
        },
        "graph": {"nodes": [], "edges": []},
    }


def test_library_artifact_endpoint_returns_user_gated_full_report(monkeypatch):
    from backend import server

    monkeypatch.setenv("SEARCHTUBE_AUTH_MODE", "none")
    monkeypatch.setattr(server, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(server, "get_supabase", lambda: object())
    calls = []

    def fake_get_artifact(supabase, user_id, artifact_id):
        calls.append((supabase, user_id, artifact_id))
        return {
            "id": "artifact:artifact-1",
            "type": "knowledge_artifact",
            "label": "Source report",
            "content": "Full source report body",
        }

    monkeypatch.setattr(server, "get_library_artifact", fake_get_artifact)

    client = TestClient(server.app)
    response = client.get("/api/library/artifacts/artifact-1")

    assert response.status_code == 200
    assert response.headers["cache-control"].startswith("private")
    assert response.json()["content"] == "Full source report body"
    assert calls[0][1:] == ("local", "artifact-1")


def test_get_library_artifact_requires_access_to_artifact_video():
    supabase = Supabase(
        {
            "knowledge_artifacts": {
                "id": "artifact-1",
                "video_id": "video-db",
                "artifact_type": "source_report",
                "title": "Source report",
                "summary": "Short shell",
                "content": "Full source report body",
                "source_refs": [],
                "metadata": {},
            },
            "videos": {
                "id": "video-db",
                "channel_id": "channel-db",
                "youtube_video_id": "yt",
                "title": "Source video",
                "thumbnail_url": "thumb",
                "transcript_seconds": 120,
            },
            "user_channels": [],
            "user_videos": [],
        }
    )

    assert context.get_library_artifact(supabase, "user-1", "artifact-1") is None
    assert ("table", "chunks") not in supabase.calls


def test_get_library_artifact_returns_full_content_for_explicit_video_grant():
    supabase = Supabase(
        {
            "knowledge_artifacts": {
                "id": "artifact-1",
                "video_id": "video-db",
                "artifact_type": "source_report",
                "title": "Source report",
                "summary": "Short shell",
                "content": "Full source report body",
                "source_refs": [
                    {
                        "source_type": "transcript",
                        "youtube_video_id": "yt",
                        "start_seconds": 30,
                        "end_seconds": 75,
                    }
                ],
                "metadata": {"reportKind": "tldr"},
            },
            "videos": {
                "id": "video-db",
                "channel_id": "channel-db",
                "youtube_video_id": "yt",
                "title": "Source video",
                "thumbnail_url": "thumb",
                "transcript_seconds": 120,
            },
            "user_channels": [],
            "user_videos": {"user_id": "user-1", "access_source": "playlist"},
            "channels": {"id": "channel-db", "name": "Channel"},
            "chunks": [
                {
                    "id": "chunk-1",
                    "video_id": "video-db",
                    "content": "Timestamp evidence from the transcript.",
                    "start_seconds": 0,
                    "end_seconds": 60,
                }
            ],
        }
    )

    artifact = context.get_library_artifact(supabase, "user-1", "artifact:artifact-1")

    assert artifact["id"] == "artifact:artifact-1"
    assert artifact["content"] == "Full source report body"
    assert artifact["video"]["videoId"] == "yt"
    assert artifact["sourceRefs"][0]["quote"] == "Timestamp evidence from the transcript."
    assert artifact["metadata"]["contentChars"] == len("Full source report body")
    assert artifact["metadata"]["reportKind"] == "tldr"


def test_library_components_search_endpoint_uses_keyword_component_search(monkeypatch):
    from backend import server

    monkeypatch.setenv("SEARCHTUBE_AUTH_MODE", "none")
    monkeypatch.setattr(server, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(server, "get_supabase", lambda: object())
    calls = []

    def fake_search(supabase, user_id, query, limit, component_types):
        calls.append((supabase, user_id, query, limit, component_types))
        return {"query": query, "results": [{"resultType": "source_concept"}]}

    monkeypatch.setattr(server, "search_library_components", fake_search)

    client = TestClient(server.app)
    response = client.get(
        "/api/library/components/search?q=harness&limit=999&component_types=source_concept,video"
    )

    assert response.status_code == 200
    assert response.json()["results"][0]["resultType"] == "source_concept"
    assert calls[0][1:] == ("local", "harness", 50, ["source_concept", "video"])


def test_build_agent_brief_creates_actionable_repo_aware_context():
    source_ref = {
        "source_type": "transcript",
        "youtube_video_id": "yt",
        "start_seconds": 30,
        "end_seconds": 75,
    }
    supabase = Supabase(
        {
            "agent_notes": [{"id": "note-1", "content": "Connect this to eval harnesses."}],
            "personal_concepts": [{"id": "pc-1", "name": "Model gym curriculum"}],
            "user_channels": [{"channel_id": "channel-db"}],
            "videos": [
                {
                    "id": "video-db",
                    "youtube_video_id": "yt",
                    "title": "RLHF lesson",
                    "thumbnail_url": "thumb",
                    "transcript_seconds": 120,
                }
            ],
            "source_concepts": [
                {
                    "id": "concept-1",
                    "video_id": "video-db",
                    "concept_type": "algorithm",
                    "name": "Reward model",
                    "summary": "A learned scorer for preference data.",
                    "source_refs": [source_ref],
                }
            ],
            "source_edges": [],
            "knowledge_artifacts": [
                {
                    "id": "artifact-1",
                    "video_id": "video-db",
                    "artifact_type": "study_guide",
                    "title": "RLHF Study Guide",
                    "summary": "Reward modeling overview.",
                    "content": "Use reward models in evaluation loops.",
                    "source_refs": [source_ref],
                }
            ],
        }
    )

    brief = context.build_agent_brief(
        supabase,
        "user-1",
        "apply reward models",
        {
            "source": "agent-mcp",
            "repo": "GhostPeony/open-model-gym",
            "branch": "feature/evals",
            "files": ["backend/evals.py"],
            "locations": ["backend/evals.py:42 run_eval_suite"],
            "entrypoints": ["POST /api/evals/run"],
            "symbols": ["run_eval_suite"],
            "features": ["evaluation harness"],
            "dependencies": ["Supabase"],
            "commands": ["python -m pytest tests/test_evals.py -q"],
            "tests": ["tests/test_evals.py"],
            "deployment": ["Cloudflare Workers"],
            "active_changes": ["preserve eval dashboard wiring"],
            "constraints": ["source context is read-only"],
            "open_questions": ["Should reward scoring run async?"],
        },
        limit=8,
    )

    assert brief["title"] == "Agent Brief: apply reward models"
    assert brief["repoFit"]["provided"] is True
    assert brief["repoFit"]["candidateTouchpoints"][:2] == [
        "GhostPeony/open-model-gym",
        "evaluation harness",
    ]
    assert "python -m pytest tests/test_evals.py -q" in brief["repoFit"]["candidateTouchpoints"]
    assert "tests/test_evals.py" in brief["repoFit"]["candidateTouchpoints"]
    assert "run_eval_suite" in brief["repoFit"]["candidateTouchpoints"]
    assert "backend/evals.py:42 run_eval_suite" in brief["repoFit"]["candidateTouchpoints"]
    assert brief["repoFit"]["targetMap"] == {
        "repo": "GhostPeony/open-model-gym",
        "branch": "feature/evals",
        "features": ["evaluation harness"],
        "modules": [],
        "symbols": ["run_eval_suite"],
        "locations": ["backend/evals.py:42 run_eval_suite"],
        "files": ["backend/evals.py"],
        "entrypoints": ["POST /api/evals/run"],
        "dependencies": ["Supabase"],
        "commands": ["python -m pytest tests/test_evals.py -q"],
        "tests": ["tests/test_evals.py"],
        "deployment": ["Cloudflare Workers"],
        "activeChanges": ["preserve eval dashboard wiring"],
        "constraints": ["source context is read-only"],
        "openQuestions": ["Should reward scoring run async?"],
        "implementationTargets": [
            "backend/evals.py:42 run_eval_suite",
            "run_eval_suite",
            "backend/evals.py",
            "POST /api/evals/run",
            "evaluation harness",
        ],
        "verificationTargets": [
            "python -m pytest tests/test_evals.py -q",
            "tests/test_evals.py",
        ],
        "runtimeTargets": ["Supabase", "Cloudflare Workers"],
    }
    assert brief["repoContextValidation"]["readiness"]["level"] == "implementation_ready"
    assert brief["repoContextValidation"]["readiness"]["readyForImplementationBrief"] is True
    assert brief["repoContextValidation"]["next_mcp_call"]["name"] == "build_agent_brief"
    assert brief["suggestedNextActions"][0].startswith("Repo context is implementation-ready")
    assert brief["keyConcepts"][0]["name"] == "Reward model"
    assert "Reward model" in brief["implementationGuidance"][0]
    assert brief["personalOverlay"]["notes"][0]["id"] == "note-1"
    assert brief["citations"] == [source_ref]
    assert all(call[0] != "agent_notes" or call[1] != "insert" for call in supabase.calls)


def test_build_agent_brief_prefers_indexed_source_knowledge_when_available():
    source_ref = {
        "source_type": "transcript",
        "youtube_video_id": "yt-terminal-rl",
        "start_seconds": 120,
        "end_seconds": 180,
    }
    supabase = RpcSupabase(
        responses={
            "agent_notes": [],
            "personal_concepts": [],
            "user_channels": [{"channel_id": "channel-db"}],
            "user_videos": [],
            "videos": [
                {
                    "id": "video-db",
                    "channel_id": "channel-db",
                    "youtube_video_id": "yt-terminal-rl",
                    "title": "Older agent lesson",
                    "thumbnail_url": "thumb",
                    "transcript_seconds": 900,
                }
            ],
            "source_concepts": [
                {
                    "id": "legacy-concept",
                    "video_id": "video-db",
                    "concept_type": "claim",
                    "name": "Generic Agent Journey",
                    "summary": "A broad agent journey framing.",
                    "source_refs": [source_ref],
                }
            ],
            "source_edges": [],
            "knowledge_artifacts": [],
        },
        rpc_responses={
            "search_source_knowledge_hybrid": [
                {
                    "id": "index-terminal-rl",
                    "video_id": "video-db",
                    "source_object_type": "source_concept",
                    "source_object_id": "concept:terminal-rl",
                    "section_key": "",
                    "title": "Terminal RL Harness",
                    "body": "Use verifiable reward tests and release gates to train coding agents.",
                    "aliases": ["RLVR", "eval gates"],
                    "source_refs": [source_ref],
                    "metadata": {"conceptType": "method"},
                    "youtube_video_id": "yt-terminal-rl",
                    "video_title": "Terminal RL Lesson",
                    "channel_name": "AI Channel",
                    "similarity": 0.84,
                    "keyword_rank": 0.5,
                    "hybrid_score": 0.04,
                    "match_type": "hybrid",
                    "access_scope": "video",
                    "access_source": "ingest",
                    "access_reason": "Visible through an explicit saved-video grant.",
                }
            ]
        },
    )
    embed_calls = []

    brief = context.build_agent_brief(
        supabase,
        "user-1",
        "apply agent reliability to BashGym",
        {
            "source": "agent-mcp",
            "repo": "Ghostwork/BashGym",
            "features": ["terminal RL", "verifiable rewards", "release gates"],
            "symbols": ["dppo_launcher"],
            "constraints": ["source context is read-only"],
        },
        limit=5,
        embedding_provider=lambda query: embed_calls.append(query) or [0.1, 0.2, 0.3],
    )

    assert "terminal RL" in embed_calls[0]
    assert supabase.rpc_calls[0][0] == "search_source_knowledge_hybrid"
    assert brief["sourceRetrieval"]["usedSourceKnowledgeIndex"] is True
    assert brief["sourceRetrieval"]["embeddingCalls"] == 1
    assert brief["keyConcepts"][0]["name"] == "Terminal RL Harness"
    assert brief["keyConcepts"][0]["type"] == "method"
    assert "Terminal RL Harness" in brief["implementationGuidance"][0]
    assert brief["citations"] == [source_ref]


def test_build_agent_brief_prompts_more_repo_inspection_when_context_is_partial():
    source_ref = {
        "source_type": "transcript",
        "youtube_video_id": "yt",
        "start_seconds": 30,
        "end_seconds": 75,
    }
    supabase = Supabase(
        {
            "agent_notes": [],
            "personal_concepts": [],
            "user_channels": [{"channel_id": "channel-db"}],
            "videos": [
                {
                    "id": "video-db",
                    "youtube_video_id": "yt",
                    "title": "RLHF lesson",
                    "thumbnail_url": "thumb",
                    "transcript_seconds": 120,
                }
            ],
            "source_concepts": [
                {
                    "id": "concept-1",
                    "video_id": "video-db",
                    "concept_type": "method",
                    "name": "Harness loop",
                    "summary": "Use an eval loop before rollout.",
                    "source_refs": [source_ref],
                }
            ],
            "source_edges": [],
            "knowledge_artifacts": [],
        }
    )

    brief = context.build_agent_brief(
        supabase,
        "user-1",
        "apply harness ideas",
        {
            "source": "agent-mcp",
            "repo": "GhostPeony/open-model-gym",
            "features": ["evaluation harness"],
            "constraints": ["source context is read-only"],
        },
        limit=8,
    )

    assert brief["repoContextValidation"]["readiness"]["level"] == "partial"
    assert brief["repoContextValidation"]["readiness"]["readyForImplementationBrief"] is False
    assert brief["repoContextValidation"]["next_mcp_call"]["name"] == "validate_repo_context"
    assert brief["suggestedNextActions"][0].startswith(
        "Improve repo_context before implementation planning"
    )
    assert "filesystem/GitHub/code-index MCP" in brief["suggestedNextActions"][0]


def test_context_note_endpoint_rejects_source_like_created_by(monkeypatch):
    from backend.server import app

    monkeypatch.setenv("SEARCHTUBE_AUTH_MODE", "none")
    client = TestClient(app)
    response = client.post(
        "/api/context/notes",
        json={"content": "bad", "created_by": "system"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "created_by must be 'user' or 'agent'"


def test_context_bundle_endpoint_accepts_repo_context_from_agent_mcp(monkeypatch):
    from backend import server

    monkeypatch.setenv("SEARCHTUBE_AUTH_MODE", "none")
    monkeypatch.setattr(server, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(server, "get_supabase", lambda: object())

    def fake_bundle(supabase, user_id, query, repo_context, limit, category_filters=None):
        return {
            "query": query,
            "userId": user_id,
            "repoContext": repo_context,
            "categoryFilters": category_filters,
            "limit": limit,
        }

    monkeypatch.setattr(server, "build_context_bundle", fake_bundle)

    client = TestClient(server.app)
    response = client.post(
        "/api/context/bundle",
        json={
            "query": "apply this to my trainer",
            "repo_context": {
                "source": "mcp",
                "repo": "GhostPeony/open-model-gym",
                "features": ["evaluation harness"],
            },
            "category_filters": {"task_fit": ["product spec"]},
            "limit": 999,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["userId"] == "local"
    assert data["repoContext"]["source"] == "mcp"
    assert data["repoContext"]["features"] == ["evaluation harness"]
    assert data["categoryFilters"] == {"task_fit": ["product spec"]}
    assert data["limit"] == 20
