from pathlib import Path

from backend import rag

ROOT = Path(__file__).resolve().parents[1]


class Result:
    def __init__(self, data=None):
        self.data = data or []


class RpcQuery:
    def __init__(self, supabase):
        self.supabase = supabase

    def execute(self):
        return Result(self.supabase.rpc_data)


class Supabase:
    def __init__(self, rpc_data=None):
        self.rpc_calls = []
        self.rpc_data = rpc_data or []

    def rpc(self, name, payload):
        self.rpc_calls.append((name, payload))
        return RpcQuery(self)


class SequenceRpcQuery:
    def __init__(self, supabase):
        self.supabase = supabase

    def execute(self):
        index = min(self.supabase.call_index, len(self.supabase.rpc_results) - 1)
        self.supabase.call_index += 1
        return Result(self.supabase.rpc_results[index])


class SequenceSupabase:
    def __init__(self, rpc_results):
        self.rpc_calls = []
        self.rpc_results = rpc_results
        self.call_index = 0

    def rpc(self, name, payload):
        self.rpc_calls.append((name, payload))
        return SequenceRpcQuery(self)


def test_search_pg_passes_normalized_category_filters_to_rpc(monkeypatch):
    supabase = Supabase()

    class FakeEmbeddings:
        def embed_query(self, query):
            return [0.1, 0.2, 0.3]

    monkeypatch.setattr(rag, "get_supabase", lambda: supabase)
    monkeypatch.setattr(rag, "_get_embeddings", lambda api_key=None: FakeEmbeddings())
    monkeypatch.setattr(rag, "generate_answer", lambda query, clips, api_key=None: "")

    result = rag.search_pg(
        "agent harness",
        "user-1",
        api_key="key",
        limit=3,
        category_filters={
            "task-fit": "product spec",
            "tool": ["MCP", "MCP"],
            "unknown": ["ignored"],
        },
        retrieval_mode="semantic",
    )

    assert result["categoryFilters"] == {
        "task_fit": ["product spec"],
        "tool": ["MCP"],
    }
    assert result["retrievalMode"] == "semantic"
    assert supabase.rpc_calls == [
        (
            "search_chunks",
            {
                "query_embedding": [0.1, 0.2, 0.3],
                "match_user_id": "user-1",
                "match_limit": 12,
                "min_start_seconds": 0,
                "category_filters": {
                    "task_fit": ["product spec"],
                    "tool": ["MCP"],
                },
            },
        )
    ]


def test_search_pg_defaults_to_hybrid_rpc_with_scores(monkeypatch):
    supabase = Supabase(
        rpc_data=[
            {
                "youtube_video_id": "yt-hybrid",
                "title": "Harness lesson",
                "channel_name": "Sierra",
                "start_seconds": 120,
                "end_seconds": 180,
                "content": "Harness loops pair eval cases with production traces.",
                "thumbnail_url": "thumb",
                "similarity": 0.81,
                "keyword_rank": 0.42,
                "headline": "<mark>Harness</mark> loops pair eval cases with production traces.",
                "match_type": "hybrid",
                "hybrid_score": 0.032,
                "access_scope": "video",
                "access_source": "playlist",
                "access_reason": "Visible through an explicit saved-video grant.",
            }
        ]
    )

    class FakeEmbeddings:
        def embed_query(self, query):
            return [0.1, 0.2, 0.3]

    monkeypatch.setattr(rag, "get_supabase", lambda: supabase)
    monkeypatch.setattr(rag, "_get_embeddings", lambda api_key=None: FakeEmbeddings())
    monkeypatch.setattr(rag, "generate_answer", lambda query, clips, api_key=None: "answer")

    result = rag.search_pg(
        "harness eval traces",
        "user-1",
        api_key="key",
        limit=2,
        category_filters={"task_fit": ["implementation plan"]},
    )

    assert supabase.rpc_calls == [
        (
            "search_chunks_hybrid",
            {
                "query_embedding": [0.1, 0.2, 0.3],
                "search_query": "harness eval traces",
                "match_user_id": "user-1",
                "match_limit": 8,
                "min_start_seconds": 0,
                "category_filters": {"task_fit": ["implementation plan"]},
            },
        )
    ]
    assert result["retrievalMode"] == "hybrid"
    assert result["retrievalPlan"]["primary"] == "hybrid_vector_keyword_rrf"
    assert result["retrievalBudget"]["embeddingCalls"] == 1
    assert result["retrievalBudget"]["llmCalls"] == 1
    clip = result["relevantClips"][0]
    assert clip["videoId"] == "yt-hybrid"
    assert clip["matchType"] == "hybrid"
    assert clip["hybridScore"] == 0.032
    assert clip["keywordRank"] == 0.42
    assert "Hybrid match" in clip["relevanceReason"]


def test_search_pg_can_scope_results_to_known_youtube_video(monkeypatch):
    supabase = Supabase(
        rpc_data=[
            {
                "youtube_video_id": "other-video",
                "title": "Nearby agent video",
                "channel_name": "AI Channel",
                "start_seconds": 120,
                "end_seconds": 180,
                "content": "Browser agents and MCP tools.",
                "thumbnail_url": "thumb",
                "similarity": 0.91,
            },
            {
                "youtube_video_id": "dwarkesh-video",
                "title": "What does the next training paradigm look like?",
                "channel_name": "Dwarkesh Patel",
                "start_seconds": 196,
                "end_seconds": 259,
                "content": "Computer use needs deterministic replayable simulators.",
                "thumbnail_url": "thumb",
                "similarity": 0.86,
            },
        ]
    )
    answer_calls = []

    class FakeEmbeddings:
        def embed_query(self, query):
            return [0.1, 0.2, 0.3]

    def fake_answer(query, clips, api_key=None):
        answer_calls.append((query, [clip["videoId"] for clip in clips], api_key))
        return "answer"

    monkeypatch.setattr(rag, "get_supabase", lambda: supabase)
    monkeypatch.setattr(rag, "_get_embeddings", lambda api_key=None: FakeEmbeddings())
    monkeypatch.setattr(rag, "generate_answer", fake_answer)

    result = rag.search_pg(
        "computer use",
        "user-1",
        api_key="key",
        limit=3,
        youtube_video_id="dwarkesh-video",
    )

    assert supabase.rpc_calls[0][1]["match_limit"] == 100
    assert [clip["videoId"] for clip in result["relevantClips"]] == ["dwarkesh-video"]
    assert result["videoScope"] == {"scope": "video", "youtubeVideoId": "dwarkesh-video"}
    assert result["retrievalPlan"]["videoScoped"] is True
    assert answer_calls == [("computer use", ["dwarkesh-video"], "key")]


def test_search_pg_keyword_mode_uses_keyword_path_without_embedding(monkeypatch):
    calls = []

    def fake_keyword(query, user_id, limit, category_filters=None, **kwargs):
        calls.append((query, user_id, limit, category_filters, kwargs))
        return {
            "answer": "",
            "relevantClips": [],
            "categoryFilters": category_filters or {},
            "retrievalMode": "keyword",
            "retrievalBudget": {"embeddingCalls": 0, "llmCalls": 0},
        }

    def fail_embeddings(*_args, **_kwargs):
        raise AssertionError("keyword retrieval mode should not embed the query")

    monkeypatch.setattr(rag, "search_transcript_text_pg", fake_keyword)
    monkeypatch.setattr(rag, "_get_embeddings", fail_embeddings)

    result = rag.search_pg(
        "exact term",
        "user-1",
        api_key="key",
        limit=3,
        retrieval_mode="keyword",
    )

    assert calls == [("exact term", "user-1", 3, None, {"youtube_video_id": None})]
    assert result["retrievalMode"] == "keyword"
    assert result["retrievalBudget"]["embeddingCalls"] == 0


def test_search_pg_returns_access_provenance_for_shared_canonical_hits(monkeypatch):
    supabase = Supabase(
        rpc_data=[
            {
                "youtube_video_id": "yt-shared",
                "title": "Sierra Harness Podcast",
                "channel_name": "Max Agency",
                "start_seconds": 180,
                "end_seconds": 240,
                "content": "A harness lets the team test agent behavior before rollout.",
                "thumbnail_url": "thumb",
                "similarity": 0.91,
                "access_scope": "video",
                "access_source": "shared_existing",
                "access_reason": "Visible through an explicit saved-video grant.",
            }
        ]
    )

    class FakeEmbeddings:
        def embed_query(self, query):
            return [0.1, 0.2, 0.3]

    monkeypatch.setattr(rag, "get_supabase", lambda: supabase)
    monkeypatch.setattr(rag, "_get_embeddings", lambda api_key=None: FakeEmbeddings())
    monkeypatch.setattr(rag, "generate_answer", lambda query, clips, api_key=None: "")

    result = rag.search_pg("agent harness", "user-2", api_key="key", limit=1)

    clip = result["relevantClips"][0]
    assert clip["videoId"] == "yt-shared"
    assert clip["accessScope"] == "video"
    assert clip["accessSource"] == "shared_existing"
    assert clip["accessReason"] == "Visible through an explicit saved-video grant."


def test_search_transcript_text_pg_uses_keyword_rpc_without_embeddings(monkeypatch):
    supabase = Supabase(
        rpc_data=[
            {
                "youtube_video_id": "yt-keyword",
                "title": "China, Robotics, & Open-Source AI",
                "channel_name": "Latent Space",
                "start_seconds": 0,
                "end_seconds": 60,
                "content": "Open-source AI and robotics strategy in China.",
                "thumbnail_url": "thumb",
                "keyword_rank": 0.78,
                "headline": "<mark>Open-source AI</mark> and robotics strategy in China.",
                "match_type": "title_keyword",
                "access_scope": "video",
                "access_source": "playlist",
                "access_reason": "Visible through an explicit saved-video grant.",
            }
        ]
    )

    def fail_embeddings(*_args, **_kwargs):
        raise AssertionError("keyword search should not embed the query")

    monkeypatch.setattr(rag, "get_supabase", lambda: supabase)
    monkeypatch.setattr(rag, "_get_embeddings", fail_embeddings)

    result = rag.search_transcript_text_pg(
        "China Robotics Open-Source AI",
        "user-1",
        limit=3,
        category_filters={"topic": ["robotics"]},
    )

    assert supabase.rpc_calls == [
        (
            "search_chunks_keyword",
            {
                "search_query": "China Robotics Open-Source AI",
                "match_user_id": "user-1",
                "match_limit": 12,
                "min_start_seconds": 0,
                "category_filters": {"topic": ["robotics"]},
            },
        )
    ]
    assert result["retrievalMode"] == "keyword"
    assert result["retrievalBudget"]["embeddingCalls"] == 0
    assert result["retrievalBudget"]["llmCalls"] == 0
    clip = result["relevantClips"][0]
    assert clip["videoId"] == "yt-keyword"
    assert clip["keywordRank"] == 0.78
    assert clip["matchType"] == "title_keyword"
    assert clip["accessSource"] == "playlist"


def test_search_transcript_text_pg_can_scope_results_to_known_youtube_video(monkeypatch):
    supabase = Supabase(
        rpc_data=[
            {
                "youtube_video_id": "other-video",
                "title": "The best AI agents are simpler than you think",
                "channel_name": "LangChain",
                "start_seconds": 1213,
                "end_seconds": 1281,
                "content": "Agents browsing websites with tools.",
                "thumbnail_url": "thumb",
                "keyword_rank": 0.92,
                "match_type": "transcript_keyword",
            },
            {
                "youtube_video_id": "dwarkesh-video",
                "title": "What does the next training paradigm look like?",
                "channel_name": "Dwarkesh Patel",
                "start_seconds": 144,
                "end_seconds": 212,
                "content": "Why has progress on computer use been slower?",
                "thumbnail_url": "thumb",
                "keyword_rank": 0.8,
                "match_type": "transcript_keyword",
            },
        ]
    )

    def fail_embeddings(*_args, **_kwargs):
        raise AssertionError("keyword search should not embed the query")

    monkeypatch.setattr(rag, "get_supabase", lambda: supabase)
    monkeypatch.setattr(rag, "_get_embeddings", fail_embeddings)

    result = rag.search_transcript_text_pg(
        "computer use",
        "user-1",
        limit=3,
        youtube_video_id="dwarkesh-video",
    )

    assert supabase.rpc_calls[0][1]["match_limit"] == 100
    assert [clip["videoId"] for clip in result["relevantClips"]] == ["dwarkesh-video"]
    assert result["videoScope"] == {"scope": "video", "youtubeVideoId": "dwarkesh-video"}
    assert result["retrievalPlan"]["videoScoped"] is True


def test_search_transcript_text_pg_retries_shorter_keyword_query_without_embeddings(monkeypatch):
    supabase = SequenceSupabase(
        [
            [],
            [
                {
                    "youtube_video_id": "yt-openai",
                    "title": "Sam Altman: How OpenAI Wins",
                    "channel_name": "Alex Kantrowitz",
                    "start_seconds": 1697,
                    "end_seconds": 1730,
                    "content": "Infrastructure and compute commitments for OpenAI buildout.",
                    "thumbnail_url": "thumb",
                    "keyword_rank": 0.51,
                    "headline": "<mark>Infrastructure</mark> and compute commitments.",
                    "match_type": "transcript_keyword",
                    "access_scope": "video",
                    "access_source": "legacy_import",
                    "access_reason": "Visible through an explicit saved-video grant.",
                }
            ],
        ]
    )

    def fail_embeddings(*_args, **_kwargs):
        raise AssertionError("keyword fallback should not embed the query")

    monkeypatch.setattr(rag, "get_supabase", lambda: supabase)
    monkeypatch.setattr(rag, "_get_embeddings", fail_embeddings)

    result = rag.search_transcript_text_pg(
        "OpenAI infrastructure compute spend",
        "user-1",
        limit=5,
    )

    assert [call[1]["search_query"] for call in supabase.rpc_calls] == [
        "OpenAI infrastructure compute spend",
        "OpenAI infrastructure compute",
    ]
    assert result["retrievalPlan"]["fallbackQuery"] == "OpenAI infrastructure compute"
    assert result["relevantClips"][0]["videoId"] == "yt-openai"
    assert result["retrievalBudget"]["embeddingCalls"] == 0


def test_search_access_provenance_migration_keeps_user_grant_gate():
    sql = (
        ROOT / "backend" / "supabase" / "migrations" / "012_search_access_provenance.sql"
    ).read_text(encoding="utf-8")

    assert "access_scope TEXT" in sql
    assert "access_source TEXT" in sql
    assert "access_reason TEXT" in sql
    assert "DROP FUNCTION IF EXISTS search_chunks(VECTOR(768), UUID, INT, INT);" in sql
    assert "DROP FUNCTION IF EXISTS search_chunks(VECTOR(768), UUID, INT, INT, JSONB);" in sql
    assert "FROM user_channels uc" in sql
    assert "FROM user_videos uv" in sql
    assert "COALESCE(channel_access.has_access, FALSE)" in sql
    assert "OR video_access.access_source IS NOT NULL" in sql


def test_keyword_search_migration_keeps_user_grant_gate_and_fts_indexes():
    sql = (
        ROOT / "backend" / "supabase" / "migrations" / "014_keyword_transcript_search.sql"
    ).read_text(encoding="utf-8")

    assert "CREATE INDEX IF NOT EXISTS chunks_content_fts_idx" in sql
    assert "CREATE INDEX IF NOT EXISTS videos_title_fts_idx" in sql
    assert "CREATE OR REPLACE FUNCTION search_chunks_keyword" in sql
    assert "websearch_to_tsquery('english'" in sql
    assert "numnode(query.tsq) > 0" in sql
    assert "keyword_rank FLOAT" in sql
    assert "match_type TEXT" in sql
    assert "FROM user_channels uc" in sql
    assert "FROM user_videos uv" in sql
    assert "OR video_access.access_source IS NOT NULL" in sql
    assert "jsonb_each(COALESCE(category_filters" in sql


def test_hybrid_search_migration_fuses_vector_keyword_and_keeps_user_gate():
    sql = (
        ROOT / "backend" / "supabase" / "migrations" / "015_hybrid_transcript_search.sql"
    ).read_text(encoding="utf-8")

    assert "CREATE OR REPLACE FUNCTION search_chunks_hybrid" in sql
    assert "RETURNS TABLE" in sql
    assert "keyword_rank FLOAT" in sql
    assert "hybrid_score FLOAT" in sql
    assert "vector_ranked AS" in sql
    assert "keyword_ranked AS" in sql
    assert "1.0 / (60 + vr.vector_position)" in sql
    assert "1.0 / (60 + kr.keyword_position)" in sql
    assert "FROM user_channels uc" in sql
    assert "FROM user_videos uv" in sql
    assert "OR video_access.access_source IS NOT NULL" in sql
    assert "jsonb_each(COALESCE(category_filters" in sql


def test_ingestion_job_cost_estimate_migration_adds_jsonb_column():
    sql = (
        ROOT / "backend" / "supabase" / "migrations" / "016_ingestion_job_cost_estimate.sql"
    ).read_text(encoding="utf-8")

    assert "ALTER TABLE ingestion_jobs" in sql
    assert "ADD COLUMN IF NOT EXISTS cost_estimate JSONB NOT NULL DEFAULT '{}'::jsonb" in sql


def test_context_rls_migration_allows_explicit_video_grants():
    sql = (
        ROOT / "backend" / "supabase" / "migrations" / "013_context_rls_user_video_grants.sql"
    ).read_text(encoding="utf-8")

    for policy_name in (
        "transcript_lines_select",
        "source_concepts_select",
        "source_edges_select",
        "knowledge_artifacts_select",
        "source_labels_select",
    ):
        assert f"DROP POLICY IF EXISTS {policy_name}" in sql
        assert f"CREATE POLICY {policy_name}" in sql

    assert sql.count("FROM user_channels uc") == 5
    assert sql.count("FROM user_videos uv") == 5
    assert "uv.video_id = v.id" in sql
