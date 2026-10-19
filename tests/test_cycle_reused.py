"""P1 inbox-to-feedback scenario, with only the workspace boundary adapted."""
from datetime import date, datetime, timedelta
import json
from research_engine import workspace as cloud
from research_engine.workspace import context, events, write_json
from research_engine.market_data import _bar
from research_engine.processor import process_one
from research_engine.review_cycle import advance_reviews, load_feedback
from research_engine.__main__ import discussion

def submit(root, key, operation, inputs, clock):
    path = root / f"inbox/{key}.json"
    write_json(path, {"version": 1, "operation": operation, "inputs": inputs})
    receipt = process_one(root, path, clock)
    assert receipt["status"] == "succeeded", receipt
    return receipt

def test_new_judgement_inbox_to_automatic_result_to_next_research(tmp_path, monkeypatch):
    created = datetime.fromisoformat("2026-10-02T05:00:00+08:00")
    identity = {"symbol": "QQQ", "venue": "US", "currency": "USD", "return_kind": "provider_adjusted_etf_price"}
    check = {**identity, "claim": "TEST ONLY: QQQ window return >= 1%", "history_key": "nasdaq",
             "metric": "close_return_pct", "start": "2026-10-01", "end": "2026-10-05", "operator": "gte", "threshold": 1}
    submit(tmp_path, "test-only-create", "save_decision", {
        "reference": "test-only-judgement", "asset": "nasdaq", "record_kind": "research",
        "conclusion": "TEST ONLY: future QQQ proxy test, no account operation.", "review_at": "2026-10-06",
        "review_spec": json.dumps({"kind": "market", "checks": [check],
            "mechanisms": ["TEST ONLY: momentum hypothesis, correlation is not causation"]})}, created)
    original = (tmp_path / "data/events/test-only-judgement.json").read_bytes()
    assert context(tmp_path, created)["review_queue"][0]["status"] == "pending"
    assert advance_reviews(tmp_path, created, {"histories": {}})["written"] == 0
    history = {**identity, "source_url": "test-only://prices", "bars": []}
    for day, price in (("2026-10-01", 100), ("2026-10-02", 99), ("2026-10-05", 98)):
        history["bars"].append(_bar(date.fromisoformat(day), (price, price, price, price), price, identity))
    bundle = {"histories": {"nasdaq": history}, "record_path": "test-only-input"}
    early = datetime.fromisoformat("2026-10-06T04:05:00+08:00")
    assert advance_reviews(tmp_path, early, bundle)["awaiting_evaluation"] == 1
    mature = early+timedelta(minutes=20)
    # Exercise the exact scheduled operation, with only the free fetch mocked.
    import research_engine.market_data as data
    monkeypatch.setattr(data, "load_bundle", lambda *args: bundle)
    report = cloud.apply_operation(tmp_path, {"operation": "research_refresh"}, mature)
    assert report["completed"] == 1
    assert not context(tmp_path, mature)["review_queue"]
    feedback = load_feedback(tmp_path, "nasdaq")["recent_completed"][0]
    assert feedback["verdict"] == "refuted" and feedback["refuted"] and feedback["errors"] and feedback["next_hypotheses"]
    assert discussion(tmp_path, "nasdaq", mature)["current_research"]["review_feedback"]["recent_completed"][0] == feedback
    assert advance_reviews(tmp_path, mature+timedelta(days=1), bundle)["written"] == 0
    assert (tmp_path / "data/events/test-only-judgement.json").read_bytes() == original
    assert {e["type"] for e in events(tmp_path)} == {"discussion_decision", "review_completion"}
    cloud.save_decision(tmp_path, {"reference": "test-only-next-judgement", "asset": "nasdaq",
                                  "note": "TEST ONLY: revised thesis", "supersedes": "test-only-judgement"}, mature)
    context(tmp_path, mature)
    assert load_feedback(tmp_path, "nasdaq")["recent_completed"][0] == feedback
