"""Synthetic account arithmetic and research classification; no private inputs."""
from copy import deepcopy
from datetime import datetime
import json
from math import sqrt
from statistics import stdev

import pytest

from research_engine.live_performance import live_portfolio_performance
from research_engine.performance import export, research_performance, shareable
from research_engine.__main__ import initialize, main
from research_engine.workspace import read_json, write_json

CLOCK = datetime.fromisoformat("2026-10-20T12:00:00+08:00")


def account(values=(1000, 1100, 990)):
    return {"base_currency": "CNY", "valuations": [{"date": f"2026-01-0{i+1}", "value": v, "currency": "CNY",
        "complete_account": True, "timing": "end_of_day", "source_refs": ["synthetic:account"]} for i, v in enumerate(values)],
        "coverage": {"start": "2026-01-01", "end": "2026-01-03", "external_flows_complete": True,
            "costs_complete": True, "source_refs": ["synthetic:verified-records"]}, "valuation_calendar": "calendar_day"}


def flow(day, value, kind="deposit"):
    return {"date": day, "value": value, "currency": "CNY", "kind": kind,
            "timing": "end_of_day", "source_refs": ["synthetic:flow"]}


def value(report, metric):
    return report["metrics"][metric]["value"]


def test_deposits_and_withdrawals_are_not_investment_returns():
    data = account((1000, 1600, 1400))
    data["cash_flows"] = [flow("2026-01-02", 500), flow("2026-01-03", 200, "withdrawal")]
    report = live_portfolio_performance(data, CLOCK)
    assert value(report, "cumulative_profit") == pytest.approx(100)
    assert value(report, "time_weighted_return") == pytest.approx(.1)
    assert report["flow_totals"]["deposits"] == 500 and report["flow_totals"]["withdrawals"] == 200
    assert value(report, "investment_principal") is None


def test_deposit_doubling_account_value_has_zero_profit():
    data = account((1000, 2000, 2000))
    data["cash_flows"] = [flow("2026-01-02", 1000)]
    report = live_portfolio_performance(data, CLOCK)
    assert value(report, "cumulative_profit") == 0 and value(report, "time_weighted_return") == 0
    assert value(report, "sharpe_ratio") is None


@pytest.mark.parametrize("included,values", [(False, (1000, 1100, 1100)), (True, (1000, 1090, 1090))])
def test_outside_fees_are_deducted_and_embedded_fees_are_not_deducted_twice(included, values):
    data = account(values)
    data["fees"] = [{"date": "2026-01-02", "value": 10, "currency": "CNY", "included_in_valuation": included,
                     "timing": "end_of_day", "source_refs": ["synthetic:fee"]}]
    report = live_portfolio_performance(data, CLOCK)
    assert value(report, "cumulative_profit") == pytest.approx(90)
    assert value(report, "time_weighted_return") == pytest.approx(.09)


def test_external_dividend_and_internal_transfer_are_not_new_contributions():
    data = account((1000, 980, 980))
    data["cash_flows"] = [flow("2026-01-02", 100, "distribution"), flow("2026-01-02", 500, "internal_transfer")]
    report = live_portfolio_performance(data, CLOCK)
    assert value(report, "cumulative_profit") == pytest.approx(80)
    assert value(report, "time_weighted_return") == pytest.approx(.08)
    assert report["flow_totals"]["deposits"] == 0


def test_native_currency_returns_include_dated_fx_and_missing_fx_is_not_guessed():
    data = account((100, 110, 110))
    for row, rate in zip(data["valuations"], (7, 7.2, 7.2)):
        row.update(currency="USD", fx={"rate": rate, "base_currency": "CNY", "date": row["date"], "source_refs": ["synthetic:fx"]})
    report = live_portfolio_performance(data, CLOCK)
    assert value(report, "time_weighted_return") == pytest.approx(792/700-1)
    del data["valuations"][-1]["fx"]
    assert value(live_portfolio_performance(data, CLOCK), "time_weighted_return") is None


def test_risk_statistics_use_flow_adjusted_wealth_and_explicit_risk_free_rate():
    data = account()
    data["risk_free"] = {"currency": "CNY", "start": "2026-01-01", "end": "2026-01-03", "annual_rate": 0,
                         "source_refs": ["synthetic:rf"]}
    report = live_portfolio_performance(data, CLOCK)
    assert value(report, "time_weighted_return") == pytest.approx(-.01)
    assert value(report, "max_drawdown") == pytest.approx(-.1)
    assert value(report, "annualized_volatility") == pytest.approx(stdev([.1, -.1])*sqrt(365))
    assert value(report, "sharpe_ratio") == pytest.approx(0, abs=1e-12)
    assert value(report, "annualized_return") is None


def test_irregular_snapshots_do_not_produce_daily_drawdown_volatility_or_sharpe():
    data = account((1000, 1100))
    data["valuations"][1]["date"] = "2026-01-03"
    report = live_portfolio_performance(data, CLOCK)
    assert value(report, "time_weighted_return") == pytest.approx(.1)
    assert all(value(report, key) is None for key in ("max_drawdown", "annualized_volatility", "sharpe_ratio"))


def test_money_profit_can_be_known_when_intra_interval_flow_prevents_exact_twr():
    data = account((1000, 1600))
    data["valuations"][1]["date"] = "2026-01-03"
    data["cash_flows"] = [flow("2026-01-02", 500)]
    report = live_portfolio_performance(data, CLOCK)
    assert value(report, "cumulative_profit") == pytest.approx(100)
    assert value(report, "time_weighted_return") is None


def test_unknown_flow_or_cost_coverage_blocks_net_performance_without_inferring_from_trades():
    data = account()
    data["coverage"]["external_flows_complete"] = False
    data["trades"] = [{"id": "synthetic-buy", "side": "buy", "amount_cny": 100, "date": "2026-01-02"}]
    report = live_portfolio_performance(data, CLOCK)
    assert value(report, "cumulative_profit") is None and value(report, "time_weighted_return") is None
    assert report["unlinked_trade_ids"] == ["synthetic-buy"]
    data["coverage"].update(external_flows_complete=True, costs_complete=False)
    report = live_portfolio_performance(data, CLOCK)
    assert value(report, "net_external_flows") == 0 and value(report, "cumulative_profit") is None


def test_annualization_requires_a_year_and_benchmark_requires_matching_total_return():
    data = account((1000, 1210))
    data["valuations"][0]["date"] = "2025-01-01"
    data["valuations"][1]["date"] = "2026-01-01"
    data["coverage"].update(start="2025-01-01", end="2026-01-01")
    benchmark = {"name": "SYNTHETIC total return", "return_kind": "total_return", "source_refs": ["synthetic:benchmark"],
        "values": [{"date": row["date"], "value": v, "currency": "CNY"} for row, v in zip(data["valuations"], (100, 110))]}
    data["benchmarks"] = [benchmark]
    report = live_portfolio_performance(data, CLOCK)
    assert value(report, "annualized_return") == pytest.approx(.21)
    assert report["benchmark_comparisons"][0]["active_return"] == pytest.approx(.11)
    benchmark["return_kind"] = "price_index"
    assert live_portfolio_performance(data, CLOCK)["benchmark_comparisons"][0]["active_return"] is None


def test_trade_correspondence_requires_explicit_matching_record_ids_and_sources():
    data = account()
    data.update(trades=[{"id": "synthetic-trade", "asset": "alpha", "status": "reported_executed"},
                        {"id": "synthetic-void", "asset": "alpha", "status": "voided"}],
        decision_assets={"synthetic-decision": ["alpha"], "synthetic-wrong": ["beta"]},
        trade_links=[{"trade_id": "synthetic-trade", "decision_id": "synthetic-wrong", "source_refs": ["synthetic:link"]}])
    assert not live_portfolio_performance(data, CLOCK)["trade_research_links"]
    data["trade_links"][0]["decision_id"] = "synthetic-decision"
    report = live_portfolio_performance(data, CLOCK)
    assert len(report["trade_research_links"]) == 1 and not report["unlinked_trade_ids"]


def decision(key, kind="research", asset="alpha"):
    return {"id": key, "record_kind": kind, "assets": [asset], "decision_date": "2026-01-01", "review_at": "2026-01-03"}


def test_research_counts_exclude_policies_workflows_and_proxy_observations_and_do_not_infer_verdicts():
    ds = [decision("synthetic-r1"), decision("synthetic-policy", "constraint"), decision("synthetic-workflow", "workflow"),
          decision("synthetic-unknown", "unclassified"), dict(decision("synthetic-forward"), source_kind="v6_forward_observation")]
    rs = [{"id": "synthetic-review", "review_id": "synthetic-r1", "recorded_at": "2026-01-04T12:00:00+08:00",
           "status": "reviewed", "learning": {"supported": ["SYNTHETIC part supported"]}}]
    r = research_performance(ds, rs, {}, CLOCK)
    assert r["counts"]["judgements"] == 1 and r["counts"]["completed_review_tasks"] == 1
    assert r["counts"]["supported"] == 0 and r["counts"]["unscored_completed"] == 1
    assert r["counts"]["supported_parts_reviews"] == 1 and r["policy_checks"]["judgements"] == 1
    assert r["counts"]["unclassified_records"] == 1


def test_completed_review_is_counted_once_and_forward_versions_horizons_remain_separate():
    ds, rs = [decision("synthetic-r1")], []
    rs += [{"id": "synthetic-done", "review_id": "synthetic-r1", "status": "reviewed", "verdict": "refuted", "recorded_at": "2026-01-04T12:00:00+08:00"},
           {"id": "synthetic-gap", "review_id": "synthetic-r1", "status": "awaiting_evaluation", "recorded_at": "2026-01-05T12:00:00+08:00"}]
    for version, horizon in (("v1", "t1"), ("v2", "t5")):
        key = "synthetic-"+version
        ds.append(dict(decision(key), source_kind="v6_forward_observation", legacy_record={"signal": {"model_version": version}, "horizon": horizon}))
        rs.append({"id": key, "review_id": key, "review_kind": "forward_observation", "recorded_at": "2026-01-04T12:00:00+08:00",
            "facts": json.dumps({"status": "matured", "proxy_return": .2, "entry_date": "2026-01-02", "exit_date": "2026-01-03"})})
    r = research_performance(ds, rs, {}, CLOCK)
    assert r["counts"]["refuted"] == 1 and r["counts"]["awaiting_review_tasks"] == 0
    assert len(r["forward_observations"]) == 2 and all(x["forecast_hit_rate"] is None for x in r["forward_observations"])
    assert r["method_improvement"]["status"] == "not_established"


def test_shareable_reports_are_allowlisted_and_opt_out_has_no_account_period(tmp_path):
    initialize(tmp_path)
    write_json(tmp_path / "inputs/live_performance.json", account())
    export(tmp_path, CLOCK)
    report = read_json(tmp_path / "exports/live_portfolio_performance.json")
    report["private_canary"] = "SECRET-FUND-ACCOUNT-BALANCE"
    report["metrics"]["sharpe_ratio"]["source_refs"] = ["SECRET-FUND-ACCOUNT-BALANCE"]
    report["metrics"]["sharpe_ratio"]["reason"] = "SECRET-FUND-ACCOUNT-BALANCE"
    shared = shareable("live_portfolio_performance", report, {"live": True})
    text = json.dumps(shared)
    assert "SECRET" not in text and "1000" not in text and "holdings" not in shared
    assert not shared.get("asset_value_history") and shared["publication"] == "not_published"
    hidden = shareable("live_portfolio_performance", report, {})
    assert not hidden["selected_for_sharing"] and hidden["period"] == {"start": None, "end": None}


def test_blank_workspace_refresh_and_cli_produce_both_reports(tmp_path, capsys):
    initialize(tmp_path)
    assert main(["refresh", "--workspace", str(tmp_path), "--as-of", CLOCK.isoformat()]) == 0
    capsys.readouterr()
    assert main(["performance", "--workspace", str(tmp_path), "--as-of", CLOCK.isoformat()]) == 0
    capsys.readouterr()
    for name in ("research_performance", "live_portfolio_performance"):
        assert (tmp_path / f"exports/{name}.md").exists()
        assert read_json(tmp_path / f"exports/shareable/{name}.json")["publication"] == "not_published"
    report = read_json(tmp_path / "exports/live_portfolio_performance.json")
    assert all(m["value"] is None for m in report["metrics"].values())


def test_legacy_archive_and_review_window_are_one_judgement_with_traceable_alias():
    archive = dict(decision("synthetic-archive"), origin={"path": "synthetic:archive"}, legacy_record={"asset": "alpha", "action": "wait"}, review_at=None)
    window = dict(decision("synthetic-window"), origin={"path": "synthetic:archive"}, legacy_record={"decision": {"asset": "alpha", "action": "wait"}, "window": "t20"})
    reviews = [{"id": "synthetic-review", "review_id": "synthetic-window", "status": "reviewed", "recorded_at": CLOCK.isoformat()}]
    report = research_performance([archive, window], reviews, {}, CLOCK)
    assert report["counts"]["judgements"] == 1 and report["counts"]["reviewed_judgements"] == 1
    assert report["representation_aliases"] == {"synthetic-window": "synthetic-archive"}


def test_retired_unreviewed_deadlines_are_not_reopened_as_due_judgements():
    old = dict(decision("synthetic-retired"), status="superseded")
    report = research_performance([old], [], {}, CLOCK)
    assert report["counts"]["due_or_reviewed_judgements"] == 0
    assert report["counts"]["historical_deadlines_passed_including_retired"] == 1
    assert report["counts"]["unprocessed_due_judgements"] == 0


def test_documented_synthetic_example_runs_the_real_cycle_and_generates_safe_reports(tmp_path):
    from examples.performance_demo import run_demo
    run_demo(tmp_path)
    research = read_json(tmp_path / "exports/research_performance.json")
    actual = read_json(tmp_path / "exports/live_portfolio_performance.json")
    assert research["counts"]["supported"] == 1 and research["counts"]["refuted"] == 1
    assert value(actual, "cumulative_profit") == pytest.approx(95)
    assert value(actual, "time_weighted_return") == pytest.approx(.095)
    assert actual["benchmark_comparisons"][0]["active_return"] == pytest.approx(.055)
    assert "合成示例" in (tmp_path / "exports/shareable/live_portfolio_performance.md").read_text(encoding="utf-8")


def test_unfinished_today_close_and_future_fx_are_not_used_as_real_results():
    data = account()
    early = datetime.fromisoformat("2026-01-03T02:00:00+08:00")
    report = live_portfolio_performance(data, early)
    assert report["period"]["end"] == "2026-01-02"
    assert len(report["asset_value_history"]) == 2
    data["valuations"][-1].update(currency="USD", fx={"rate": 7, "base_currency": "CNY", "date": "2026-01-04", "source_refs": ["synthetic:future-fx"]})
    assert value(live_portfolio_performance(data, CLOCK), "time_weighted_return") is None
