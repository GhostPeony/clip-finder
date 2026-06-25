from backend import ingestion_costs
from backend.ingestion_costs import build_ingestion_cost_estimate


class Result:
    def __init__(self, data):
        self.data = data


class Query:
    def __init__(self, table_name, supabase):
        self.table_name = table_name
        self.supabase = supabase
        self.in_filter = None

    def select(self, payload):
        self.supabase.calls.append((self.table_name, "select", payload))
        return self

    def in_(self, column, values):
        self.in_filter = (column, values)
        self.supabase.calls.append((self.table_name, "in", column, values))
        return self

    def execute(self):
        rows = self.supabase.responses.get(self.table_name, [])
        if self.in_filter:
            column, values = self.in_filter
            values = set(values)
            rows = [row for row in rows if row.get(column) in values]
        return Result(rows)


class Supabase:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []

    def table(self, table_name):
        self.calls.append(("table", table_name))
        return Query(table_name, self)


def test_video_estimate_detects_already_indexed_canonical_video(monkeypatch):
    monkeypatch.setattr(ingestion_costs, "get_free_max_import_videos", lambda: 25)
    supabase = Supabase({"videos": [{"youtube_video_id": "uCKhOmth2ms"}]})

    estimate = build_ingestion_cost_estimate(
        supabase,
        "user-1",
        "https://www.youtube.com/watch?v=uCKhOmth2ms",
        "video",
    )

    assert estimate["discoveredVideos"] == 1
    assert estimate["alreadyIndexedVideos"] == 1
    assert estimate["alreadyIndexedVideoIds"] == ["uCKhOmth2ms"]
    assert estimate["videosToEmbed"] == 0
    assert estimate["digestDepth"] == "standard"
    assert estimate["estimatedDigestInputTokens"] == 0
    assert estimate["estimatedDigestOutputTokenBudget"] == 0
    assert estimate["estimatedModelCostUsd"]["totalStandardUpperBoundUsd"] == 0
    assert "source_backed_report" in estimate["generationPolicy"]["ingestionGenerated"]
    assert estimate["riskLevel"] == "low"
    assert "embedding compute" in estimate["guidance"]
    assert ("videos", "in", "youtube_video_id", ["uCKhOmth2ms"]) in supabase.calls


def test_playlist_estimate_without_discovery_is_capped_and_marked_estimated(monkeypatch):
    monkeypatch.setattr(ingestion_costs, "get_free_max_import_videos", lambda: 7)

    estimate = build_ingestion_cost_estimate(
        None,
        "user-1",
        "https://www.youtube.com/playlist?list=PL12345678901",
        "playlist",
    )

    assert estimate["discoveredVideos"] == 7
    assert estimate["discoveredVideosEstimated"] is True
    assert estimate["videosToEmbed"] == 7
    assert estimate["maxVideosThisRun"] == 7
    assert estimate["estimatedEmbeddingTokens"] == 25200
    assert estimate["estimatedDigestLlmCalls"] == 7
    assert estimate["estimatedDigestInputTokens"] == 39900
    assert estimate["estimatedDigestOutputTokenBudget"] == 43008
    assert estimate["estimatedModelCostUsd"]["embeddingStandardUsd"] == 0.00378
    assert estimate["estimatedModelCostUsd"]["digestInputUsd"] == 0.009975
    assert estimate["estimatedModelCostUsd"]["digestOutputBudgetUsd"] == 0.064512
    assert estimate["estimatedModelCostUsd"]["totalStandardUpperBoundUsd"] == 0.078267
    assert estimate["assumptions"]["pricing"]["source"].startswith("https://ai.google.dev")
    assert (
        "custom_report_for_current_user_goal"
        in estimate["generationPolicy"]["mcpAgentShouldGenerateOnDemand"]
    )
    assert estimate["riskLevel"] == "high"
    assert "capped by the hosted import limit" in estimate["guidance"]


def test_known_candidate_estimate_dedupes_and_counts_existing_videos(monkeypatch):
    monkeypatch.setattr(ingestion_costs, "get_free_max_import_videos", lambda: 5)
    supabase = Supabase({"videos": [{"youtube_video_id": "video-b"}]})

    estimate = build_ingestion_cost_estimate(
        supabase,
        "user-1",
        "https://www.youtube.com/playlist?list=PL12345678901",
        "playlist",
        ["video-a", "video-b", "video-a", "video-c"],
    )

    assert estimate["discoveredVideos"] == 3
    assert estimate["discoveredVideosEstimated"] is False
    assert estimate["alreadyIndexedVideos"] == 1
    assert estimate["alreadyIndexedVideoIds"] == ["video-b"]
    assert estimate["videosToEmbed"] == 2
    assert estimate["estimatedTranscriptSeconds"] == 1800
    assert estimate["estimatedModelCostUsd"]["totalStandardUpperBoundUsd"] > 0
    assert estimate["riskLevel"] == "medium"


def test_none_digest_depth_removes_digest_llm_call_estimate(monkeypatch):
    monkeypatch.setattr(ingestion_costs, "get_free_max_import_videos", lambda: 25)

    estimate = build_ingestion_cost_estimate(
        None,
        "user-1",
        "https://www.youtube.com/watch?v=uCKhOmth2ms",
        "video",
        digest_depth="none",
    )

    assert estimate["digestDepth"] == "none"
    assert estimate["estimatedDigestLlmCalls"] == 0
    assert estimate["estimatedDigestInputTokens"] == 0
    assert estimate["estimatedDigestOutputTokenBudget"] == 0
    assert "source_backed_report" not in estimate["generationPolicy"]["ingestionGenerated"]
    assert "without LLM source-knowledge extraction" in estimate["guidance"]


def test_deep_digest_estimate_reflects_larger_report_budget(monkeypatch):
    monkeypatch.setattr(ingestion_costs, "get_free_max_import_videos", lambda: 25)

    estimate = build_ingestion_cost_estimate(
        None,
        "user-1",
        "https://www.youtube.com/watch?v=uCKhOmth2ms",
        "video",
        digest_depth="deep",
    )

    assert estimate["digestDepth"] == "deep"
    assert estimate["estimatedDigestInputTokens"] == 8700
    assert estimate["estimatedDigestOutputTokenBudget"] == 12288
    assert estimate["estimatedModelCostUsd"]["totalStandardUpperBoundUsd"] == 0.021147
    assert estimate["generationPolicy"]["recommendedDefault"].startswith(
        "standard_for_all_indexed_videos"
    )
