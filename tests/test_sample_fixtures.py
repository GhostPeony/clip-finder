import json
from pathlib import Path

from backend.category_taxonomy import CATEGORY_FACETS, normalize_category_filters
from backend.repo_context import validate_repo_context

ROOT = Path(__file__).resolve().parents[1]
SIERRA_FIXTURE = ROOT / "eval" / "fixtures" / "sierra_harness_podcast.json"
UNIVERSAL_RETRIEVAL_FIXTURE = ROOT / "eval" / "fixtures" / "universal_video_retrieval.json"


def _load_fixture() -> dict:
    return json.loads(SIERRA_FIXTURE.read_text(encoding="utf-8"))


def _load_universal_fixture() -> dict:
    return json.loads(UNIVERSAL_RETRIEVAL_FIXTURE.read_text(encoding="utf-8"))


def test_sierra_sample_fixture_targets_user_supplied_video():
    fixture = _load_fixture()

    assert fixture["video"]["youtubeVideoId"] == "uCKhOmth2ms"
    assert fixture["video"]["url"] == "https://www.youtube.com/watch?v=uCKhOmth2ms"
    assert "Sierra" in fixture["video"]["title"]
    assert "transcript text" in fixture["video"]["notes"]
    assert {"ingestion", "study guide quality", "repo-aware agent brief"}.issubset(
        set(fixture["coverage"])
    )


def test_sierra_sample_fixture_uses_known_category_facets():
    fixture = _load_fixture()

    for expected_label in fixture["expectedLabels"]:
        assert expected_label["label_type"] in CATEGORY_FACETS
        assert expected_label["labels"]

    assert normalize_category_filters(fixture["categoryFilters"]) == fixture["categoryFilters"]
    for query in fixture["retrievalQueries"]:
        assert normalize_category_filters(query["category_filters"]) == query["category_filters"]


def test_sierra_sample_fixture_repo_context_matches_agent_contract():
    fixture = _load_fixture()

    validation = validate_repo_context(fixture["repoContext"])

    assert validation["valid"] is True
    assert validation["normalized"]["source"] == "agent-mcp"
    assert validation["normalized"]["repo"] == "GhostPeony/memexai"
    assert "workflow orchestration" in validation["normalized"]["features"]
    assert "backend/context.py:734 build_agent_brief" in validation["normalized"]["locations"]
    assert "POST /mcp" in validation["normalized"]["entrypoints"]
    assert "build_agent_brief" in validation["normalized"]["symbols"]
    assert "npm test -- --run" in validation["normalized"]["commands"]
    assert "tests/test_mcp_adapter.py" in validation["normalized"]["tests"]
    assert validation["readiness"]["level"] == "implementation_ready"
    assert validation["readiness"]["readyForImplementationBrief"] is True


def test_sierra_sample_fixture_covers_required_mcp_workflow():
    fixture = _load_fixture()
    workflow_tools = {step["tool"]: step for step in fixture["mcpWorkflow"]}
    overlay_tools = {step["tool"]: step for step in fixture["overlayChecks"]}

    assert {
        "queue_youtube_ingestion",
        "get_ingestion_job",
        "list_context_categories",
        "search_video_concepts",
        "search_video_moments",
        "build_agent_brief",
    }.issubset(workflow_tools)
    assert workflow_tools["queue_youtube_ingestion"]["requiredScope"] == "ingest:write"
    assert workflow_tools["search_video_concepts"]["arguments"]["detail_level"] == "compact"
    assert workflow_tools["search_video_concepts"]["arguments"]["max_chars"] == 6000
    assert workflow_tools["search_video_moments"]["arguments"]["retrieval_mode"] == "hybrid"
    assert "category_filters" in workflow_tools["search_video_moments"]["arguments"]
    assert "repo_context" in workflow_tools["build_agent_brief"]["arguments"]
    assert {"add_context_note", "upsert_personal_concept"} == set(overlay_tools)


def test_universal_retrieval_fixture_covers_non_ai_youtube_topics():
    fixture = _load_universal_fixture()

    domains = {document["domain"] for document in fixture["documents"]}
    query_text = " ".join(query["query"] for query in fixture["queries"])

    assert fixture["name"] == "universal_video_retrieval"
    assert {"cooking", "home repair", "history", "music", "fitness", "buying research"}.issubset(
        domains
    )
    assert "AI/ML" in domains
    assert len(fixture["queries"]) >= 7
    assert "sourdough" in query_text
    assert "faucet" in query_text
    assert "Meiji" in query_text
    assert all(query["expected"] for query in fixture["queries"])
