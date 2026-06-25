import json
import sys
from pathlib import Path

from scripts.run_sierra_sample_eval import main, run_offline_eval

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_sierra_sample_eval.py"


def test_sierra_sample_offline_eval_passes_agent_contract():
    report = run_offline_eval()
    checks = {check["name"]: check for check in report["checks"]}

    assert report["passed"] is True
    assert report["video"]["youtubeVideoId"] == "uCKhOmth2ms"
    assert checks["canonical_video_access_grant"]["passed"] is True
    assert checks["category_discovery"]["passed"] is True
    assert checks["study_guide_artifact"]["passed"] is True
    assert checks["filtered_context_bundle"]["passed"] is True
    assert checks["repo_aware_agent_brief"]["passed"] is True
    assert checks["overlay_writes_do_not_mutate_source_context"]["passed"] is True
    assert "Sierra" in report["categoryFacets"]["entity"]
    assert "implementation plan" in report["categoryFacets"]["task_fit"]
    assert report["studyGuide"]["present"] is True
    assert report["contextBundle"]["videoIds"] == ["uCKhOmth2ms"]
    assert report["agentBrief"]["citationCount"] >= 1


def test_sierra_sample_eval_cli_outputs_passed_report(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [str(SCRIPT)])

    exit_code = main()
    report = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert report["passed"] is True
    assert report["fixture"] == "sierra_harness_podcast"
