import json
import sys
from pathlib import Path

from scripts.evaluate_source_knowledge_discoverability import (
    DEFAULT_FIXTURE,
    evaluate_fixture,
    main,
)

SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "evaluate_source_knowledge_discoverability.py"
)


def test_source_knowledge_discoverability_fixture_shape():
    fixture = json.loads(Path(DEFAULT_FIXTURE).read_text(encoding="utf-8"))

    assert fixture["name"] == "source_knowledge_discoverability"
    assert fixture["sourceKnowledge"]
    assert {row["resultType"] for row in fixture["sourceKnowledge"]} >= {
        "source_concept",
        "report_section",
    }
    assert all(row["sourceRefs"] for row in fixture["sourceKnowledge"])
    assert {query["id"] for query in fixture["queries"]} == {
        "completion_check",
        "hidden_variables",
        "context_compressor",
        "typed_tools",
        "pricing_unit",
    }


def test_source_knowledge_discoverability_eval_passes_initial_bar():
    fixture = json.loads(Path(DEFAULT_FIXTURE).read_text(encoding="utf-8"))

    report = evaluate_fixture(fixture)

    assert report["passed"] is True
    assert report["metrics"]["objectRecallAt5"] >= 0.85
    assert report["metrics"]["videoRecallAt5"] >= 0.9
    assert report["metrics"]["timestampHitRate"] >= 0.75
    assert report["metrics"]["transcriptAvoidanceRate"] == 1.0
    assert report["metrics"]["averageResponseBytes"] < 2500


def test_source_knowledge_discoverability_cli_outputs_report(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [str(SCRIPT)])

    exit_code = main()
    report = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert report["passed"] is True
    assert report["fixture"] == "source_knowledge_discoverability"
