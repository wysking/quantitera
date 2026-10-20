"""Run the documented new-user workflow outside the repository's working directory."""
import subprocess

import pytest

from examples.research_demo import NEXT, cli, run_demo
from research_engine.__main__ import initialize
from research_engine.performance import export
from research_engine.workspace import read_json, write_json
from tests.test_performance import CLOCK


@pytest.fixture(scope="module")
def tutorial(tmp_path_factory):
    root = tmp_path_factory.mktemp("new-user") / "workspace"
    return root, run_demo(root)


def test_new_user_economics_archive_validation_feedback_models_and_reports(tutorial):
    root, summary = tutorial
    assert summary["example_only"] and summary["expectation_difference"] == -.25
    card = summary["mechanism_card"]
    assert card["supporting_evidence"] and card["counter_evidence"] and card["alternative_explanations"]
    assert card["causal_status"] == "hypothesis_not_identified" and card["forecast"] is None
    assert summary["maturity_cycle"]["completed"] == 2 and summary["maturity_cycle"]["awaiting_evaluation"] == 1
    assert summary["research_counts"]["judgements"] == 4
    assert summary["research_counts"]["supported"] == summary["research_counts"]["refuted"] == 1
    assert summary["research_counts"]["unscored_completed"] == 1
    assert summary["repeat_review_events_written"] == 0 and summary["original_judgement_unchanged"]
    assert summary["portfolio"]["assets_received"] == ["sample_defensive", "sample_growth"]
    assert summary["portfolio"]["requires_recheck"] == ["sample_growth"]
    assert set(summary["model_versions"].values()) == {"tutorial-v1"}
    packet = read_json(root / "exports/tutorial/next_research.json")
    feedback = packet["current_research"]["review_feedback"]["recent_completed"]
    assert {r["decision_id"] for r in feedback} == {"synthetic-sample_growth", "synthetic-channel"}
    assert any(r["errors"] and r["next_hypotheses"] for r in feedback)
    assert all(read_json(p)["status"] == "succeeded" for p in (root / "outbox").glob("*.json"))
    assert all(m["value"] is None for m in read_json(root / "exports/live_portfolio_performance.json")["metrics"].values())
    assert read_json(root / "exports/shareable/research_performance.json")["status"] == "not_selected"
    assert {r["id"] for r in read_json(root / "exports/review_queue.json")["items"]} == {"synthetic-iteration-2"}
    with pytest.raises(subprocess.CalledProcessError):
        run_demo(root)  # The tutorial must not replace an existing personal workspace.


def test_copied_workspace_provider_and_new_unmodeled_asset_are_independent(tutorial):
    root, _ = tutorial
    assets = read_json(root / "config/tutorial_assets.json")
    assets["sample_unmodeled"] = {"label": "SYNTHETIC new asset", "history_key": "unavailable"}
    write_json(root / "config/tutorial_assets.json", assets)
    result = cli(root, "portfolio", NEXT)
    assert result["assets_received"] == ["sample_defensive", "sample_growth", "sample_unmodeled"]
    assert result["asset_models"]["sample_unmodeled"]["status"] == "not_registered"
    defensive = result["asset_models"]["sample_defensive"]["research_context"]["asset_feedback"]["recent_completed"]
    assert {r["decision_id"] for r in defensive} == {"synthetic-sample_defensive"}
    assert defensive[0]["verdict"] == "supported"
    assert result["execution_allowed"] is False


def test_standalone_performance_rebuilds_changed_mechanism_configuration(tmp_path):
    initialize(tmp_path)
    export(tmp_path, CLOCK)
    write_json(tmp_path / "config/research.json", {"mechanisms": {"sample": {"new-channel": {
        "hypothesis": "SYNTHETIC new hypothesis", "horizon": "medium", "alternative_explanations": [],
        "invalidation": "SYNTHETIC no response", "next_observation": "SYNTHETIC release"}}}})
    export(tmp_path, CLOCK)
    report = read_json(tmp_path / "exports/research_performance.json")
    assert report["mechanism_progress"]["hypotheses"] == 1
    assert report["mechanisms"][0]["mechanism_id"] == "new-channel"
    assert report["mechanisms"][0]["causal_status"] == "hypothesis_not_identified"
