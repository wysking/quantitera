"""Synthetic external provider for the public contract tests, with no personal code."""
from datetime import date
from research_engine.market_data import _bar


def provide(root, clock, operation, **kwargs):
    if operation == "history":
        return [{"id": "synthetic-external", "type": "discussion_decision", "asset": "alpha",
            "recorded_at": "2026-10-02T08:00:00+08:00", "conclusion": "SYNTHETIC external judgement",
            "review_at": "2026-10-06", "source_kind": "external_history",
            "origin": {"path": "external:synthetic-source", "read_only": True},
            "review_spec": {"kind": "market", "checks": [{"claim": "SYNTHETIC >=1%", "history_key": "alpha",
                "symbol": "QQQ", "venue": "US", "currency": "USD", "return_kind": "provider_adjusted_etf_price",
                "metric": "close_return_pct", "start": "2026-10-01", "end": "2026-10-05", "operator": "gte", "threshold": 1}]}}]
    if operation == "snapshot":
        return {"status": "available", "source": {"revision": "synthetic-revision"},
            "account": {"synthetic_only": True},
            "assets": {key: {"economic_mechanisms": []} for key in ("alpha", "beta", "unmodeled")}}
    if operation == "market_data":
        identity = {"symbol": "QQQ", "venue": "US", "currency": "USD", "return_kind": "provider_adjusted_etf_price"}
        return {"record_path": "external:synthetic-prices", "histories": {"alpha": {**identity,
            "bars": [_bar(date.fromisoformat(day), (value, value, value, value), value, identity)
                     for day, value in (("2026-10-01", 100), ("2026-10-02", 101), ("2026-10-05", 102))]}}}
    if operation == "asset_model":
        asset = kwargs["asset"]
        return {"status": "not_registered" if asset == "unmodeled" else "available", "value": {"alpha": 2, "beta": 3}.get(asset)}
    if operation == "portfolio_model":
        assets = kwargs["assets"]
        return {"status": "available", "assets_seen": sorted(assets),
                "value": sum(model["value"] for model in assets.values() if model["value"] is not None)}
    raise ValueError(operation)
