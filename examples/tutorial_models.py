"""SYNTHETIC local provider copied into the tutorial workspace, never a strategy for live use."""
from research_engine.market_data import digest, history_view
from research_engine.workspace import read_json


def provide(workspace, clock, operation, **kwargs):
    assets = read_json(workspace / "config/tutorial_assets.json", {})
    market = read_json(workspace / "inputs/market.json", {"histories": {}})
    if operation == "history":
        return []
    if operation == "market_data":
        return None  # The normal inputs/market.json loader supplies the data.
    if operation == "snapshot":
        return {"example_only": True, "source": {"input_revision": digest([assets, market])},
                "assets": {asset: {"label": spec["label"], "market_data": "inputs/market.json",
                                   "model_definition": spec.get("model")}
                           for asset, spec in assets.items()}}
    if operation == "asset_model":
        asset = kwargs["asset"]
        spec = assets.get(asset, {})
        model = spec.get("model")
        if not model:
            return {"status": "not_registered", "reason": "No model configured for this asset"}
        view = history_view(market["histories"].get(spec["history_key"]), clock,
                            min_observations=model["lookback_bars"])
        result = {"status": view["status"], "example_only": True, "model_version": model["version"],
                  "market_as_of": view.get("market_as_of"), "source_path": "inputs/market.json"}
        if view["status"] != "ok":
            return result
        bars = view["bars"][-model["lookback_bars"]:]
        change = bars[-1]["adjusted_close"] / bars[0]["adjusted_close"] - 1
        feedback = kwargs["research_context"]["asset_feedback"].get("recent_completed", [])
        return {**result, "status": "available", "observed_change": change,
                "research_signal": "positive" if change > 0 else "non_positive",
                "feedback_effect": "manual_recheck_required" if any(r.get("verdict") == "refuted" for r in feedback)
                                   else "read_before_next_judgement",
                "meaning": "Toy observation, not an investment forecast, allocation or order"}
    if operation == "portfolio_model":
        models = kwargs["assets"]
        return {"status": "research_only", "example_only": True, "assets_received": sorted(models),
                "model_statuses": {asset: model["status"] for asset, model in models.items()},
                "requires_recheck": [asset for asset, model in models.items()
                                     if model.get("feedback_effect") == "manual_recheck_required"],
                "meaning": "All-asset research coverage; no portfolio weights or trade instructions"}
    raise ValueError("unsupported tutorial operation: " + operation)
