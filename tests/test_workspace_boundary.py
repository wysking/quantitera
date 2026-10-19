"""The extracted engine runs with an empty workspace and synthetic inputs only."""
from datetime import timedelta
import json
from pathlib import Path

import pytest

from research_engine.__main__ import discussion, initialize, main
from research_engine.workspace import apply_operation, context, events, read_json, write_json
from research_engine.evidence import record
from research_engine.mechanisms import export
from research_engine.processor import process_one
from research_engine.review_cycle import advance_reviews
from tests.test_economic_reused import CLOCK, evidence, event_and_prior, save


def test_empty_workspace_never_requires_personal_seed_or_models(tmp_path, capsys):
    root = tmp_path / "blank"
    initialize(root)
    assert read_json(root / "config/research.json") == {"schema_version": 1, "mechanisms": {}}
    assert read_json(root / "inputs/market.json") == {"histories": {}}
    assert not events(root)
    assert (root / ".github/workflows/research.yml").is_file()
    assert main(["refresh", "--workspace", str(root), "--as-of", CLOCK.isoformat()]) == 0
    assert read_json(root / "exports/current_state.json")["assets"] == {}
    assert "holdings" not in {p.name for p in root.rglob("*")}
    with pytest.raises(ValueError, match="empty"):
        initialize(root)


@pytest.mark.parametrize("kind", ["policy", "research"])
def test_complex_judgement_keeps_evidence_gaps_and_human_review(tmp_path, kind):
    initialize(tmp_path)
    apply_operation(tmp_path, {"operation": "save_decision", "reference": "synthetic-original", "asset": "demo",
        "record_kind": "constraint" if kind == "policy" else "research", "conclusion": "SYNTHETIC original judgement",
        "review_at": CLOCK.date().isoformat(), "review_spec": json.dumps({"kind": kind,
            "evidence_gaps": ["SYNTHETIC source not yet checked"],
            "mechanisms": ["SYNTHETIC transmission hypothesis"],
            "next_hypotheses": ["SYNTHETIC next observation"]})}, CLOCK)
    result = advance_reviews(tmp_path, CLOCK)
    assert result["awaiting_evaluation"] == 1 and result["completed"] == 0
    task = context(tmp_path, CLOCK)["review_queue"][0]
    assert task["status"] == "awaiting_evaluation" and task["needs_chatgpt"]
    assert advance_reviews(tmp_path, CLOCK + timedelta(days=100))["written"] == 0
    packet = discussion(tmp_path, "demo", CLOCK)
    assert packet["current_research"]["review_feedback"]["awaiting_evaluation"][0]["evidence_gaps"]
    apply_operation(tmp_path, {"operation": "record_review", "reference": "synthetic-reviewed", "review_id": task["id"],
        "facts": "SYNTHETIC evidence checked", "conclusion": "SYNTHETIC scoped review completed",
        "source_refs": '["https://example.org/synthetic-evidence"]', "review_result": json.dumps({
            "supported": ["SYNTHETIC supported part"], "refuted": ["SYNTHETIC refuted part"],
            "errors": ["SYNTHETIC error"], "mechanisms": ["SYNTHETIC surviving mechanism"],
            "next_hypotheses": ["SYNTHETIC new hypothesis"]})}, CLOCK + timedelta(minutes=1))
    assert not context(tmp_path, CLOCK + timedelta(minutes=1))["review_queue"]
    feedback = discussion(tmp_path, "demo", CLOCK + timedelta(minutes=1))["current_research"]["review_feedback"]
    assert feedback["recent_completed"][0]["errors"]
    assert feedback["recent_completed"][0]["next_hypotheses"]


def test_economic_mechanisms_prior_comparison_and_counter_evidence_reach_discussion(tmp_path):
    initialize(tmp_path)
    definition = {"hypothesis": "SYNTHETIC lower input cost may improve cash flow", "horizon": "medium",
        "alternative_explanations": ["SYNTHETIC demand may fall"], "invalidation": "SYNTHETIC cash flow fails to improve",
        "next_observation": "SYNTHETIC next comparable primary disclosure"}
    write_json(tmp_path / "config/research.json", {"mechanisms": {"demo": {"demo-transmission": definition}}})
    for role, value in (("supporting", 1), ("counter", -1)):
        record(tmp_path, {"reference": "synthetic-"+role, "evidence": json.dumps(evidence("mechanism_evidence",
            asset="demo", mechanism_id="demo-transmission", evidence_role=role,
            fact_id="synthetic-fact-"+role, metric="synthetic-cost" if value > 0 else "synthetic-demand",
            value=value, counter_evidence=["SYNTHETIC source objection"],
            alternative_explanations=["SYNTHETIC source alternative"]))}, CLOCK)
    end = event_and_prior(tmp_path, value=3.25)
    packet = discussion(tmp_path, "demo", end)
    card = packet["economic_research"]["economic_mechanisms"][0]
    assert card["supporting_evidence"] and card["counter_evidence"] and card["alternative_explanations"]
    assert card["causal_status"] == "hypothesis_not_identified" and card["forecast"] is None
    assert "SYNTHETIC source objection" in card["provided_counter_text"]
    assert "SYNTHETIC source alternative" in card["alternative_explanations"]
    assert packet["economic_research"]["evidence"][0]["source_excerpt"]
    priors = discussion(tmp_path, "gold", end)["economic_research"]["expectations"]
    assert priors["events"][0]["surprise"] == .25 and priors["probability_up"] is None
    assert packet["execution_allowed"] is False


def test_invalid_request_does_not_partially_save_and_receipt_replay_is_stable(tmp_path):
    initialize(tmp_path)
    path = tmp_path / "inbox/synthetic-bad.json"
    write_json(path, {"version": 1, "operation": "save_decision", "inputs": {
        "reference": "synthetic-bad", "asset": "demo", "note": "SYNTHETIC", "review_spec": "invalid-json"}})
    receipt = process_one(tmp_path, path, CLOCK)
    assert receipt["status"] == "rejected" and not events(tmp_path)
    assert process_one(tmp_path, path, CLOCK + timedelta(hours=1)) == receipt


def test_public_tree_contains_no_private_ledger_or_model_adapters():
    root = Path(__file__).resolve().parents[1]
    assert not any((root / name).exists() for name in ("data", "exports", "inbox", "outbox", "codex", "redlow_strategy"))
    for module in (root / "research_engine").glob("*.py"):
        text = module.read_text(encoding="utf-8")
        assert "from mobile" not in text and "from codex" not in text
        assert "gold_research" not in text and "account_snapshot" not in text
    template = root / "research_engine/workspace_template"
    assert not list(template.rglob("holdings*"))
    assert not list(template.rglob("*trade*.json"))
    assert read_json(template / "config/research.json")["mechanisms"] == {}
