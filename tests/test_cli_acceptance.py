"""Acceptance through the real CLI, blank template and persisted synthetic inputs."""
import json
from pathlib import Path
import subprocess
import sys

from research_engine.workspace import read_json, write_json
from tests.test_economic_reused import evidence


REPO = Path(__file__).resolve().parents[1]
CREATED = "2026-10-02T08:00:00+08:00"
MATURE = "2026-10-06T12:00:00+08:00"


def cli(root, command, clock=CREATED, *extra):
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "research_engine", command,
         "--workspace", str(root), "--as-of", clock, *extra],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(result.stdout)


def request(root, key, operation, **inputs):
    write_json(root / f"inbox/{key}.json", {
        "version": 1, "operation": operation, "inputs": inputs})


def queue(root):
    return {item["id"]: item for item in read_json(root / "exports/review_queue.json")["items"]}


def prices(root, missing_middle=False):
    # Entirely synthetic prices; timestamps follow registered US sessions.
    bars = [{"date": day, "open": price, "high": price, "low": price, "close": price,
             "adjusted_close": price, "close_at": f"{day}T16:00:00-04:00",
             "available_at": f"{day}T16:15:00-04:00"}
            for day, price in (("2026-10-01", 100), ("2026-10-02", 99), ("2026-10-05", 98))
            if not (missing_middle and day == "2026-10-02")]
    write_json(root / "inputs/market.json", {"histories": {"synthetic-proxy": {
        "symbol": "QQQ", "venue": "US", "currency": "USD",
        "return_kind": "provider_adjusted_etf_price",
        "source_url": "https://example.org/synthetic-prices", "bars": bars}}})


def test_blank_cli_batch_to_mature_result_and_next_research(tmp_path):
    root = tmp_path / "private-workspace"
    cli(root, "init")
    assert cli(root, "refresh")["review_cycle"]["discovered"] == 0
    # An external personal model can supply a judgement without importing its code
    # or changing its parameters. This file is synthetic and remains private.
    model = root / "models/personal.json"
    write_json(model, {"synthetic_only": True, "score": 0.6, "weights": [0.4, 0.6]})
    original_model = model.read_bytes()
    check = {"claim": "SYNTHETIC proxy return >= 1%", "history_key": "synthetic-proxy",
             "symbol": "QQQ", "venue": "US", "currency": "USD",
             "return_kind": "provider_adjusted_etf_price", "metric": "close_return_pct",
             "start": "2026-10-01", "end": "2026-10-05", "operator": "gte", "threshold": 1}
    request(root, "001-market", "save_decision", reference="synthetic-market", asset="nasdaq",
            conclusion="SYNTHETIC future proxy observation", record_kind="research",
            model_inference=json.dumps({"source": "models/personal.json", "score": 0.6}),
            review_at="2026-10-06", review_spec=json.dumps({"kind": "market", "checks": [check],
                "mechanisms": ["SYNTHETIC liquidity transmission still needs independent evidence"]}))
    request(root, "002-policy", "save_decision", reference="synthetic-policy", asset="gold",
            conclusion="SYNTHETIC budget constraint", record_kind="constraint", review_at="2026-10-06",
            invalidation="SYNTHETIC external eligibility changes",
            review_spec=json.dumps({"kind": "policy", "milestones": [
                {"date": "2026-10-06", "condition": "SYNTHETIC confirm eligibility"}]}))
    request(root, "003-research", "save_decision", reference="synthetic-research", asset="hsiii",
            conclusion="SYNTHETIC macro transmission hypothesis", record_kind="research",
            review_at="2026-10-06", review_spec=json.dumps({"kind": "research",
                "evidence_gaps": ["SYNTHETIC primary release missing"],
                "competing_explanations": ["SYNTHETIC demand weakness"]}))
    write_json(root / "config/research.json", {"mechanisms": {"nasdaq": {"synthetic-channel": {
        "hypothesis": "SYNTHETIC cheaper funding may support investment", "horizon": "medium",
        "alternative_explanations": ["SYNTHETIC demand may weaken"],
        "invalidation": "SYNTHETIC investment does not respond",
        "next_observation": "SYNTHETIC comparable primary disclosure"}}}})
    for index, role in enumerate(("supporting", "counter"), 4):
        value = evidence("mechanism_evidence", asset="nasdaq", mechanism_id="synthetic-channel",
            fact_id=f"synthetic-{role}", metric=f"synthetic-{role}", evidence_role=role,
            observation_period="2026-10-01", published_at="2026-10-01T10:00:00Z",
            source_captured_at="2026-10-01T11:00:00Z", available_at="2026-10-01T10:00:00Z",
            counter_evidence=["SYNTHETIC source objection"],
            alternative_explanations=["SYNTHETIC alternative channel"])
        request(root, f"00{index}-evidence", "record_evidence", reference=f"synthetic-{role}",
                evidence=json.dumps(value))
    cli(root, "refresh")
    assert all(read_json(path)["status"] == "succeeded" for path in (root / "outbox").glob("*.json"))
    assert len(queue(root)) == 3  # All accepted requests must be visible in this same refresh.
    assert {task["status"] for task in queue(root).values()} == {"pending"}
    card = read_json(root / "exports/mechanisms.json")["assets"]["nasdaq"]["economic_mechanisms"][0]
    assert card["supporting_evidence"] and card["counter_evidence"]
    assert "SYNTHETIC source objection" in card["provided_counter_text"]
    original = (root / "data/events/synthetic-market.json").read_bytes()

    prices(root)
    early = cli(root, "refresh", "2026-10-06T04:05:00+08:00")["review_cycle"]
    assert early["discovered"] == 3 and early["awaiting_evaluation"] == 3 and early["completed"] == 0
    pending = read_json(root / queue(root)["synthetic-market"]["detail_path"])
    assert pending["checks"][0]["reason"] == "result_not_mature"
    prices(root, missing_middle=True)
    assert cli(root, "refresh", MATURE)["review_cycle"]["completed"] == 0
    pending = read_json(root / queue(root)["synthetic-market"]["detail_path"])
    assert pending["checks"][0]["missing_sessions"] == ["2026-10-02"]
    assert cli(root, "refresh", MATURE)["review_cycle"]["written"] == 0
    prices(root)
    assert cli(root, "refresh", MATURE)["review_cycle"]["completed"] == 1
    assert set(queue(root)) == {"synthetic-policy", "synthetic-research"}
    policy = read_json(root / queue(root)["synthetic-policy"]["detail_path"])
    assert not policy["checks"] and policy["policy_checks"][1]["status"] == "review_window_reached"
    packet = cli(root, "discuss", MATURE, "--asset", "nasdaq")
    feedback = packet["current_research"]["review_feedback"]["recent_completed"][0]
    assert feedback["verdict"] == "refuted" and feedback["refuted"]
    assert feedback["errors"] and feedback["mechanisms"] and feedback["next_hypotheses"]
    result = read_json(root / feedback["detail_path"])
    assert abs(result["checks"][0]["value"] + 2) < 1e-8
    assert result["original"]["conclusion"] == "SYNTHETIC future proxy observation"
    assert result["checks"][0]["window_sha256"] and result["checks"][0]["input_path"] == "inputs/market.json"
    assert packet["economic_research"]["evidence"][0]["source_excerpt"]
    for asset in ("gold", "hsiii"):
        pending = cli(root, "discuss", MATURE, "--asset", asset)["current_research"]["review_feedback"]
        assert pending["awaiting_evaluation"][0]["evidence_gaps"]
        assert not pending["recent_completed"]
    frozen = {path.name: path.read_bytes() for path in (root / "data/events").glob("*.json")}
    assert cli(root, "refresh", MATURE)["review_cycle"]["written"] == 0
    assert {path.name: path.read_bytes() for path in (root / "data/events").glob("*.json")} == frozen
    assert (root / "data/events/synthetic-market.json").read_bytes() == original
    next_check = {**check, "start": "2026-10-06", "end": "2026-10-07"}
    request(root, "006-next-judgement", "save_decision", reference="synthetic-next", asset="nasdaq",
            conclusion="SYNTHETIC revised explanation after: " + feedback["errors"][0],
            user_hypotheses=feedback["next_hypotheses"][0], supersedes="synthetic-market",
            related_ids='["synthetic-market"]', review_at="2026-10-08",
            review_spec=json.dumps({"kind": "market", "checks": [next_check]}))
    cli(root, "process", MATURE)
    assert queue(root)["synthetic-next"]["status"] == "pending"
    packet = cli(root, "discuss", MATURE, "--asset", "nasdaq")
    assert packet["current_research"]["review_feedback"]["recent_completed"][0] == feedback
    assert model.read_bytes() == original_model and packet["execution_allowed"] is False


def test_review_feedback_uses_instant_order_across_timezones(tmp_path):
    cli(tmp_path, "init")
    request(tmp_path, "001-create", "save_decision", reference="synthetic-macro", asset="gold",
            conclusion="SYNTHETIC needs research", review_at="2026-10-06",
            review_spec='{"kind":"research"}')
    cli(tmp_path, "refresh", MATURE)
    request(tmp_path, "002-reviewed", "record_review", reference="synthetic-reviewed", review_id="synthetic-macro",
            facts="SYNTHETIC primary evidence compared", conclusion="SYNTHETIC scoped evaluation",
            source_refs='["https://example.org/synthetic-source"]',
            review_result='{"supported":["SYNTHETIC scoped support"],"next_hypotheses":["SYNTHETIC next test"]}')
    # 05:00 UTC is later than 12:00 UTC+8. ISO text order gives the wrong answer.
    later = "2026-10-06T05:00:00+00:00"
    cli(tmp_path, "refresh", later)
    assert read_json(tmp_path / "outbox/002-reviewed.json")["status"] == "succeeded"
    assert not queue(tmp_path)
    feedback = cli(tmp_path, "discuss", later, "--asset", "gold")["current_research"]["review_feedback"]
    assert len(feedback["recent_completed"]) == 1 and not feedback["awaiting_evaluation"]
    assert feedback["recent_completed"][0]["event_id"] == "synthetic-reviewed"


def test_discussion_includes_global_feedback_for_a_new_subject(tmp_path):
    cli(tmp_path, "init")
    request(tmp_path, "001-create", "save_decision", reference="synthetic-global", asset="all",
            conclusion="SYNTHETIC common evidence lesson", review_at="2026-10-06",
            review_spec='{"kind":"research"}')
    cli(tmp_path, "refresh", MATURE)
    packet = cli(tmp_path, "discuss", MATURE, "--asset", "gold")
    assert packet["global_research"]["review_feedback"]["awaiting_evaluation"][0]["decision_id"] == "synthetic-global"
    request(tmp_path, "002-reviewed", "record_review", reference="synthetic-global-reviewed", review_id="synthetic-global",
            facts="SYNTHETIC source checked", conclusion="SYNTHETIC scoped common lesson",
            source_refs='["https://example.org/synthetic-source"]',
            review_result='{"errors":["SYNTHETIC common error"]}')
    later = "2026-10-06T13:00:00+08:00"
    cli(tmp_path, "process", later)
    packet = cli(tmp_path, "discuss", later, "--asset", "gold")
    assert packet["global_research"]["review_feedback"]["recent_completed"][0]["errors"]
