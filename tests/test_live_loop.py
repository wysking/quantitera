"""Public integration contract uses synthetic data and synthetic provider hooks."""
import json
import pytest

from research_engine import integration
from research_engine.__main__ import discussion, initialize
from research_engine.processor import process_one
from research_engine.workspace import apply_operation, events, read_json, write_json
from tests.test_workspace_provider import CLOCK, configured


def test_formal_research_discovers_due_results_before_loading_feedback(tmp_path):
    configured(tmp_path)
    packet = discussion(tmp_path, "alpha", CLOCK)
    assert packet["current_research"]["review_feedback"]["recent_completed"][0]["verdict"] == "supported"
    assert integration.model(tmp_path, "alpha", CLOCK)["feedback_seen"]["asset_feedback"] == packet["current_research"]["review_feedback"]
    assert not integration.model(tmp_path, "beta", CLOCK)["feedback_seen"]["asset_feedback"].get("recent_completed")
    assert len(events(tmp_path)) == 1


def test_old_model_is_marked_stale_when_feedback_changes_without_source_change(tmp_path):
    configured(tmp_path)
    integration.portfolio(tmp_path, CLOCK)
    assert read_json(tmp_path / "exports/manifest.json")["model_feedback_matches_workspace"]
    discussion(tmp_path, "alpha", CLOCK)
    manifest = read_json(tmp_path / "exports/manifest.json")
    assert manifest["model_source_matches_workspace"] and not manifest["model_feedback_matches_workspace"]
    result = integration.portfolio(tmp_path, CLOCK)
    assert result["feedback_seen"]["alpha"]["asset_feedback"]["recent_completed"]
    assert read_json(tmp_path / "exports/manifest.json")["model_feedback_matches_workspace"]


def test_research_evidence_keeps_complex_review_pending_without_blocking_price_checks(tmp_path):
    configured(tmp_path)
    config = read_json(tmp_path / "config/research.json")
    config["provider_capabilities"] = ["review_evidence"]
    write_json(tmp_path / "config/research.json", config)
    apply_operation(tmp_path, {"operation": "save_decision", "reference": "synthetic-complex", "asset": "beta",
        "conclusion": "SYNTHETIC economic mechanism", "review_at": "2026-10-06"}, CLOCK)
    cycle = apply_operation(tmp_path, {"operation": "research_refresh"}, CLOCK)
    assert cycle["completed"] == 1 and cycle["awaiting_evaluation"] == 1
    review = next(e for e in events(tmp_path) if e.get("review_id") == "synthetic-complex")
    assert review["verdict"] == "not_evaluated" and review["research_evidence"]
    assert "SYNTHETIC competing channel" in review["learning"]["competing_explanations"]
    assert apply_operation(tmp_path, {"operation": "research_refresh"}, CLOCK)["written"] == 0


def test_candidate_validation_is_owned_by_provider_and_rejection_is_atomic(tmp_path):
    configured(tmp_path)
    config = read_json(tmp_path / "config/research.json")
    config["provider_capabilities"] = ["factor_candidates"]
    write_json(tmp_path / "config/research.json", config)
    path = tmp_path / "inbox/synthetic-candidate.json"
    payload = {"version": 1, "operation": "save_decision", "inputs": {"reference": "synthetic-hypothesis",
        "asset": "beta", "conclusion": "SYNTHETIC new mechanism", "factor_candidates": '[{"candidate_id":"bad"}]'}}
    write_json(path, payload)
    assert process_one(tmp_path, path, CLOCK)["status"] == "rejected"
    assert not events(tmp_path)
    path = tmp_path / "inbox/synthetic-valid-candidate.json"
    payload["inputs"]["factor_candidates"] = '[{"candidate_id":"synthetic-candidate"}]'
    write_json(path, payload)
    assert process_one(tmp_path, path, CLOCK)["status"] == "succeeded"
    assert events(tmp_path)[0]["factor_candidates"][0]["candidate_id"] == "synthetic-candidate"


def test_blank_workspace_has_no_implicit_factor_system(tmp_path):
    initialize(tmp_path)
    with pytest.raises(ValueError, match="no configured"):
        apply_operation(tmp_path, {"operation": "save_decision", "reference": "synthetic-hypothesis", "asset": "alpha",
            "conclusion": "SYNTHETIC", "factor_candidates": '[{"candidate_id":"synthetic-candidate"}]'}, CLOCK)
    assert not events(tmp_path)


def test_forward_observations_do_not_hide_human_learning_and_keep_external_paths():
    from research_engine.review_cycle import feedback_for
    reviews = [{"id": "synthetic-human", "review_id": "synthetic-human", "assets": ["alpha"],
        "recorded_at": CLOCK.isoformat(), "conclusion": "SYNTHETIC learned error"}]
    reviews += [{"id": f"synthetic-forward-{n}", "review_id": f"synthetic-forward-{n}", "assets": ["alpha"],
        "recorded_at": CLOCK.isoformat(), "review_kind": "forward_observation", "verdict": "observed_only",
        "origin": {"path": "external:synthetic-frozen-outcome"}} for n in range(12)]
    result = feedback_for("alpha", reviews, [])
    assert len(result["recent_completed"]) == 1 and result["counts"]["forward_observations"] == 12
    assert len(result["forward_observations"]) == 5
    assert result["forward_observations"][0]["detail_path"] == "external:synthetic-frozen-outcome"
    assert not feedback_for("beta", reviews, [])["recent_completed"]


def test_review_candidate_definition_is_immutable_on_replay(tmp_path):
    configured(tmp_path)
    config = read_json(tmp_path / "config/research.json")
    config["provider_capabilities"] = ["factor_candidates"]
    write_json(tmp_path / "config/research.json", config)
    apply_operation(tmp_path, {"operation": "save_decision", "reference": "synthetic-research", "asset": "beta",
        "conclusion": "SYNTHETIC research", "review_at": "2026-10-06"}, CLOCK)
    request = {"operation": "record_review", "reference": "synthetic-reviewed", "review_id": "synthetic-research",
        "facts": "SYNTHETIC facts", "conclusion": "SYNTHETIC review", "source_refs": '["synthetic:source"]',
        "factor_candidates": '[{"candidate_id":"synthetic-candidate"}]'}
    first = apply_operation(tmp_path, request, CLOCK)
    assert apply_operation(tmp_path, request, CLOCK) == first
    request.pop("factor_candidates")
    with pytest.raises(ValueError, match="编号已存在"):
        apply_operation(tmp_path, request, CLOCK)
