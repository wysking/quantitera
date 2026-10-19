"""Optional private workspace entry point. No account or model is built in."""
from importlib import import_module
import re


def call(root, clock, operation, **kwargs):
    from research_engine.workspace import read_json
    config = read_json(root / "config/research.json", {})
    entry = config.get("provider")
    if not entry:
        return None
    if not isinstance(entry, str) or not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*", entry):
        raise ValueError("provider must be an explicitly configured module:function")
    module, function = entry.split(":")
    return getattr(import_module(module), function)(root, clock, operation, **kwargs)


def history(root, clock):
    records = call(root, clock, "history") or []
    if not isinstance(records, list):
        raise ValueError("provider history must return an event list")
    return records


def export(root, clock):
    from research_engine.workspace import read_json, write_json
    snapshot = call(root, clock, "snapshot")
    if snapshot is None:
        return {"status": "not_configured", "execution_allowed": False}
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("assets"), dict):
        raise ValueError("provider snapshot requires an assets mapping")
    snapshot = {**snapshot, "generated_at": clock.isoformat(), "execution_allowed": False}
    write_json(root / "exports/workspace.json", snapshot)
    manifest = read_json(root / "exports/manifest.json", {})
    manifest.setdefault("paths", {})["workspace"] = "exports/workspace.json"
    previous = read_json(root / "exports/portfolio_model.json")
    if previous is not None:
        manifest["paths"]["portfolio_model"] = "exports/portfolio_model.json"
        manifest["model_source_matches_workspace"] = (previous.get("source") == snapshot["source"]
                                                     if snapshot.get("source") else None)
    write_json(root / "exports/manifest.json", manifest)
    return snapshot


def model(root, asset, clock):
    result = call(root, clock, "asset_model", asset=asset)
    if result is None:
        return {"status": "not_configured", "asset": asset, "execution_allowed": False}
    if not isinstance(result, dict):
        raise ValueError("asset model must return a mapping")
    return {**result, "asset": asset, "execution_allowed": False}


def portfolio(root, clock):
    from research_engine.workspace import read_json, write_json
    snapshot = export(root, clock)
    if snapshot.get("status") == "not_configured":
        return snapshot
    models = {asset: model(root, asset, clock) for asset in snapshot["assets"]}
    result = call(root, clock, "portfolio_model", assets=models)
    if not isinstance(result, dict):
        raise ValueError("portfolio model must return a mapping")
    result = {**result, "asset_models": models, "source": snapshot.get("source"),
              "generated_at": clock.isoformat(), "execution_allowed": False}
    write_json(root / "exports/portfolio_model.json", result)
    manifest = read_json(root / "exports/manifest.json", {})
    manifest.setdefault("paths", {})["portfolio_model"] = "exports/portfolio_model.json"
    manifest["model_source_matches_workspace"] = True if snapshot.get("source") else None
    write_json(root / "exports/manifest.json", manifest)
    return result
