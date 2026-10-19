from datetime import datetime
import json
import pytest

from research_engine.__main__ import initialize, discussion, main
from research_engine import integration
from research_engine.processor import process_one
from research_engine.workspace import apply_operation, events, read_json, write_json

CLOCK = datetime.fromisoformat("2026-10-06T12:00:00+08:00")


def configured(root):
    initialize(root)
    write_json(root / "config/research.json", {"schema_version": 1, "mechanisms": {}, "provider": "tests.workspace_provider:provide"})


def test_blank_workspace_does_not_require_provider(tmp_path, capsys):
    initialize(tmp_path)
    for command in ("workspace", "model", "portfolio"):
        assert main([command, "--workspace", str(tmp_path), "--asset", "alpha"]) == 0
        assert json.loads(capsys.readouterr().out)["status"] == "not_configured"
    assert not (tmp_path / "exports/workspace.json").exists()


def test_external_history_and_prices_use_existing_review_cycle_without_copying_ledger(tmp_path):
    configured(tmp_path)
    result = apply_operation(tmp_path, {"operation": "research_refresh"}, CLOCK)
    assert result["completed"] == 1
    assert [e["type"] for e in events(tmp_path)] == ["review_completion"]
    detail = read_json(tmp_path / "exports/knowledge/synthetic-external.json")
    assert detail["source_kind"] == "external_history" and detail["origin"]["read_only"]
    packet = discussion(tmp_path, "alpha", CLOCK)
    assert packet["workspace_research"] == {"economic_mechanisms": []}
    review = packet["current_research"]["review_feedback"]["recent_completed"][0]
    assert review["verdict"] == "supported"
    assert "external:synthetic-prices" in review["source_refs"]
    assert apply_operation(tmp_path, {"operation": "research_refresh"}, CLOCK)["written"] == 0


def test_all_asset_models_are_passed_to_the_private_portfolio_model(tmp_path):
    configured(tmp_path)
    apply_operation(tmp_path, {"operation": "status"}, CLOCK)
    result = integration.portfolio(tmp_path, CLOCK)
    assert result["value"] == 5 and result["assets_seen"] == ["alpha", "beta", "unmodeled"]
    assert result["asset_models"]["unmodeled"]["status"] == "not_registered"
    assert result["execution_allowed"] is False
    assert read_json(tmp_path / "exports/portfolio_model.json") == result
    discussion(tmp_path, "alpha", CLOCK)
    manifest = read_json(tmp_path / "exports/manifest.json")
    assert manifest["paths"]["portfolio_model"] and manifest["model_source_matches_workspace"]


def test_external_identity_collision_is_rejected_atomically(tmp_path):
    configured(tmp_path)
    path = tmp_path / "inbox/synthetic-collision.json"
    write_json(path, {"version": 1, "operation": "save_decision", "inputs": {
        "reference": "synthetic-external", "asset": "alpha", "conclusion": "SYNTHETIC conflicting record"}})
    receipt = process_one(tmp_path, path, CLOCK)
    assert receipt["status"] == "rejected" and "collision" in receipt["error"] and not events(tmp_path)


def test_staged_request_can_use_provider_and_replay_without_external_writes(tmp_path):
    configured(tmp_path)
    path = tmp_path / "inbox/synthetic-new.json"
    write_json(path, {"version": 1, "operation": "save_decision", "inputs": {
        "reference": "synthetic-new", "asset": "beta", "conclusion": "SYNTHETIC new research",
        "review_at": "2026-10-07", "review_spec": '{"kind":"research"}'}})
    receipt = process_one(tmp_path, path, CLOCK)
    assert receipt["status"] == "succeeded" and len(events(tmp_path)) == 1
    assert len(read_json(tmp_path / "exports/retrieval_index.json")["items"]) == 2
    assert process_one(tmp_path, path, CLOCK) == receipt


def test_provider_is_an_explicit_import_not_a_command(tmp_path):
    initialize(tmp_path)
    write_json(tmp_path / "config/research.json", {"provider": "python -c arbitrary_command"})
    with pytest.raises(ValueError, match="module:function"):
        integration.call(tmp_path, CLOCK, "snapshot")


def test_external_and_local_market_inputs_keep_their_own_provenance(tmp_path):
    from research_engine.market_data import load_bundle
    configured(tmp_path)
    write_json(tmp_path / "inputs/market.json", {"histories": {"beta": {"bars": []}}})
    bundle = load_bundle(tmp_path, CLOCK)
    assert bundle["histories"]["alpha"]["input_path"] == "external:synthetic-prices"
    assert bundle["histories"]["beta"]["input_path"] == "inputs/market.json"
