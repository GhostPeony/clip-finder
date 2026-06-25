import json
import sys
from pathlib import Path

from scripts.evaluate_context_report_lift import DEFAULT_FIXTURE, evaluate_fixture, main

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_context_report_lift.py"


def test_context_report_lift_fixture_models_report_vs_transcript():
    fixture = json.loads(Path(DEFAULT_FIXTURE).read_text(encoding="utf-8"))

    assert fixture["name"] == "video_context_report_lift"
    assert fixture["rawTranscriptChunks"]
    assert fixture["memexaiContext"]["sourceConcepts"]
    assert fixture["memexaiContext"]["reportSections"]
    assert {query["id"] for query in fixture["queries"]} == {
        "production_agent_shape",
        "latency_cost_controls",
        "eval_harness_lessons",
    }


def test_context_report_lift_eval_passes_agent_navigation_gate():
    fixture = json.loads(Path(DEFAULT_FIXTURE).read_text(encoding="utf-8"))

    report = evaluate_fixture(fixture)

    assert report["passed"] is True
    assert report["metrics"]["memexaiCoverageAt3"] == 1.0
    assert report["metrics"]["memexaiTimestampRefRate"] == 1.0
    assert report["metrics"]["charReduction"] >= 0.25
    assert (
        report["metrics"]["avgMemexaiCharsToCover"] < report["metrics"]["avgTranscriptCharsToCover"]
    )


def test_context_report_lift_cli_outputs_report(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [str(SCRIPT)])

    exit_code = main()
    report = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert report["passed"] is True
    assert report["fixture"] == "video_context_report_lift"
