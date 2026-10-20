"""Reproducible synthetic reports. Never run against an existing personal workspace."""
import argparse
from datetime import date, datetime
import json
from pathlib import Path

from research_engine.__main__ import initialize
from research_engine.market_data import _bar
from research_engine.performance import export
from research_engine.workspace import apply_operation, write_json


def run_demo(root):
    initialize(root)
    issued = datetime.fromisoformat("2026-01-01T12:00:00+08:00")
    mature = datetime.fromisoformat("2026-01-06T12:00:00+08:00")
    histories = {}
    for asset, symbol, final in (("alpha", "QQQ", 102), ("beta", "SPY", 98)):
        identity = {"symbol": symbol, "venue": "US", "currency": "USD", "return_kind": "provider_adjusted_etf_price"}
        check = {**identity, "claim": "SYNTHETIC >=1%", "history_key": "synthetic-"+asset, "metric": "close_return_pct",
            "start": "2026-01-02", "end": "2026-01-05", "operator": "gte", "threshold": 1}
        apply_operation(root, {"operation": "save_decision", "reference": "synthetic-"+asset, "asset": asset,
            "record_kind": "research", "conclusion": "SYNTHETIC example only; not a real market forecast",
            "review_at": "2026-01-06", "review_spec": json.dumps({"kind": "market", "checks": [check]})}, issued)
        histories["synthetic-"+asset] = {**identity, "source_url": "https://example.com/synthetic-only",
            "bars": [_bar(date.fromisoformat(day), (value, value, value, value), value, identity)
                     for day, value in (("2026-01-02", 100), ("2026-01-05", final))]}
    write_json(root / "inputs/market.json", {"histories": histories})
    apply_operation(root, {"operation": "research_refresh"}, mature)
    source = ["synthetic:example-only"]
    values = [{"date": day, "value": amount, "currency": "CNY", "timing": "end_of_day", "complete_account": True,
               "source_refs": source} for day, amount in (("2026-01-03", 1000), ("2026-01-04", 1595), ("2026-01-05", 1395))]
    flows = [{"date": day, "value": amount, "currency": "CNY", "kind": kind, "timing": "end_of_day", "source_refs": source}
             for day, amount, kind in (("2026-01-04", 500, "deposit"), ("2026-01-05", 200, "withdrawal"))]
    write_json(root / "inputs/live_performance.json", {"base_currency": "CNY", "valuations": values, "cash_flows": flows,
        "coverage": {"start": "2026-01-03", "end": "2026-01-05", "external_flows_complete": True, "costs_complete": True, "source_refs": source},
        "fees": [{"date": "2026-01-04", "value": 5, "currency": "CNY", "included_in_valuation": True, "source_refs": source}],
        "valuation_calendar": "calendar_day", "risk_free": {"currency": "CNY", "annual_rate": .02,
            "start": "2026-01-03", "end": "2026-01-05", "source_refs": source},
        "benchmarks": [{"name": "SYNTHETIC total-return benchmark", "return_kind": "total_return", "source_refs": source,
            "values": [{"date": day, "value": value, "currency": "CNY"} for day, value in (("2026-01-03", 100), ("2026-01-05", 104))]}],
        "trades": [{"id": "synthetic-trade-alpha", "asset": "alpha", "status": "reported_executed"}],
        "trade_links": [{"trade_id": "synthetic-trade-alpha", "decision_id": "synthetic-alpha", "source_refs": source}]})
    write_json(root / "config/performance.json", {"example_only": True, "sharing": {"research": True, "live": True,
        "topics": ["示例资产 A", "示例资产 B"]}})
    return export(root, mature)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True, help="New, empty synthetic workspace only")
    args = parser.parse_args()
    print(json.dumps(run_demo(args.workspace.resolve()), ensure_ascii=False, indent=2))
