"""QuantItera CLI. All mutable state belongs to an explicit private workspace."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil

from research_engine.workspace import apply_operation, context, now, read_json


def initialize(root):
    template = Path(__file__).with_name("workspace_template")
    if root.exists() and any(root.iterdir()):
        raise ValueError("workspace must be a new or empty directory")
    root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(template, root, dirs_exist_ok=True)
    for name in ("data/events", "inputs", "inbox", "outbox", "exports"):
        (root / name).mkdir(parents=True, exist_ok=True)
        (root / name / ".gitkeep").touch()
    return {"workspace": str(root), "status": "initialized", "execution_allowed": False}


def discussion(root, asset, clock):
    apply_operation(root, {"operation": "status"}, clock)
    states = read_json(root / "exports/current_state.json")["assets"]
    state = states.get(asset, {})
    mechanisms = read_json(root / "exports/mechanisms.json")["assets"].get(asset, {})
    return {"asset": asset, "current_research": state,
            "global_research": states.get("all", {}) if asset != "all" else {},
            "economic_research": mechanisms,
            "workspace_research": read_json(root / "exports/workspace.json", {}).get("assets", {}).get(asset, {}),
            "research_instructions": [
                "Read asset and global_research completed reviews and unresolved evidence before making a new judgement.",
                "Explain supported/refuted parts, errors, evidence gaps, surviving mechanisms and new hypotheses.",
                "Compare prior expectations, source timestamps, horizons, counter-evidence and competing explanations.",
                "Check workspace model/data timestamps and missing capabilities; proxies are not account returns.",
                "Save the resulting judgement with review_at and explicit review_spec; do not infer personal trades.",
            ], "execution_allowed": False}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="quantitera")
    parser.add_argument("command", choices=("init", "refresh", "process", "status", "discuss", "workspace", "model", "portfolio"))
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--asset")
    parser.add_argument("--as-of", help="Timezone-aware clock, for reproducible research/tests")
    args = parser.parse_args(argv)
    root = args.workspace.resolve()
    clock = datetime.fromisoformat(args.as_of) if args.as_of else now()
    if clock.utcoffset() is None:
        parser.error("--as-of requires a timezone")
    if args.command == "init":
        result = initialize(root)
    else:
        if not (root / "config/research.json").is_file():
            parser.error("workspace is not initialized")
        if args.command in {"refresh", "process"}:
            from research_engine.processor import process_pending
            receipts = process_pending(root, clock)
            result = apply_operation(root, {"operation": "research_refresh" if args.command == "refresh" else "status"}, clock)
            result = {"requests_checked": len(receipts), "review_cycle": result, "execution_allowed": False}
        elif args.command == "discuss":
            if not args.asset:
                parser.error("discuss requires --asset")
            result = discussion(root, args.asset, clock)
        elif args.command in {"workspace", "model", "portfolio"}:
            from research_engine import integration
            apply_operation(root, {"operation": "status"}, clock)
            if args.command == "model" and not args.asset:
                parser.error("model requires --asset")
            result = (integration.model(root, args.asset, clock) if args.command == "model" else
                      integration.portfolio(root, clock) if args.command == "portfolio" else
                      integration.export(root, clock))
        else:
            apply_operation(root, {"operation": "status"}, clock)
            result = {"state_path": "exports/current_state.json", "execution_allowed": False}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
