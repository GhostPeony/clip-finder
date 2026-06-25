import json
from pathlib import Path

from scripts.evaluate_video_retrieval import DEFAULT_FIXTURE, evaluate_fixture


def test_video_retrieval_fixture_covers_legacy_and_sierra_queries():
    fixture = json.loads(Path(DEFAULT_FIXTURE).read_text(encoding="utf-8"))

    corpora = {query["corpus"] for query in fixture["queries"]}
    ids = {query["id"] for query in fixture["queries"]}

    assert fixture["name"] == "video_retrieval_queries"
    assert {"legacy_chroma", "sierra_sample"} == corpora
    assert "legacy_china_open_source_ai" in ids
    assert "legacy_mold_toxicity" in ids
    assert "sierra_agent_workflow_design" in ids
    assert all(query["expectedVideoIds"] for query in fixture["queries"])


def test_video_retrieval_eval_passes_offline_baseline():
    fixture = json.loads(Path(DEFAULT_FIXTURE).read_text(encoding="utf-8"))

    report = evaluate_fixture(fixture)

    assert report["metrics"]["recallAt5"] >= 0.8
    assert report["metrics"]["mrr"] >= 0.75
    assert report["metrics"]["wrongTopVideoRate"] <= 0.25
    result_by_id = {result["id"]: result for result in report["results"]}
    assert "b0iJZS9HgJA" in result_by_id["legacy_china_open_source_ai"]["topVideoIds"]
    assert "uCKhOmth2ms" in result_by_id["sierra_latency_cost_tradeoffs"]["topVideoIds"]
