"""Due reviews use the existing queue, immutable review events and saved inputs."""
from datetime import date, datetime
import json
from math import isfinite
from pathlib import Path
from zoneinfo import ZoneInfo

from research_engine import calendar
from research_engine.market_data import digest, history_view, price_session, price_sessions
from research_engine.identity import require_identity

LEARNING_FIELDS = ("supported", "refuted", "errors", "evidence_gaps", "mechanisms", "next_hypotheses", "competing_explanations")
KINDS = {"market", "research", "policy"}


def parse_spec(raw):
    """Small, explicit checks; never infer a forecast from a preference or prose."""
    if not raw:
        return None
    spec = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(spec, dict) or spec.get("kind") not in KINDS:
        raise ValueError("review_spec.kind须为market/research/policy")
    if set(spec) - {"kind", "checks", "errors", "evidence_gaps", "mechanisms", "next_hypotheses", "competing_explanations", "milestones"}:
        raise ValueError("review_spec字段无效")
    for field in ("errors", "evidence_gaps", "mechanisms", "next_hypotheses", "competing_explanations"):
        _strings(spec.get(field, []), field)
    checks = spec.get("checks", [])
    if not isinstance(checks, list) or len(checks) > 10:
        raise ValueError("最多登记10项验证条件")
    if spec["kind"] == "market" and not checks:
        raise ValueError("市场判断必须登记验证条件")
    for check in checks:
        if not isinstance(check, dict) or set(check) != {"claim", "history_key", "symbol", "venue", "currency", "return_kind", "metric", "start", "end", "operator", "threshold"}:
            raise ValueError("验证条件须包含完整标的、窗口、指标与阈值")
        require_identity(check)
        if check["metric"] not in {"close_return_pct", "close_level"} or check["operator"] not in {"gte", "lte"}:
            raise ValueError("验证只支持收盘收益/点位及gte/lte")
        if not all(isinstance(check[k], str) and check[k] for k in ("claim", "history_key")):
            raise ValueError("验证条件须有claim和history_key")
        start, end = date.fromisoformat(check["start"]), date.fromisoformat(check["end"])
        if start > end or (end-start).days > 730:
            raise ValueError("验证窗口无效或超过两年")
        if not price_session(check, start) or not price_session(check, end):
            raise ValueError("验证端点必须是已登记交易日")
        if isinstance(check["threshold"], bool) or not isinstance(check["threshold"], (int, float)) or not isfinite(check["threshold"]):
            raise ValueError("阈值必须为有限数字")
    milestones = spec.get("milestones", [])
    if not isinstance(milestones, list) or len(milestones) > 10:
        raise ValueError("政策期限列表无效")
    for item in milestones:
        if not isinstance(item, dict) or set(item) != {"date", "condition"} or not isinstance(item["condition"], str):
            raise ValueError("政策期限须包含date和condition")
        date.fromisoformat(item["date"])
    return spec


def _strings(value, name):
    if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
        raise ValueError(f"{name}须为字符串数组")
    return value


def parse_result(raw):
    if not raw:
        return None
    value = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(value, dict) or set(value) - set(LEARNING_FIELDS):
        raise ValueError("review_result字段无效")
    return {field: _strings(value.get(field, []), field) for field in LEARNING_FIELDS}


def original_for(root, task):
    from research_engine.workspace import read_json
    relative = task.get("original_detail_path") or task["detail_path"]
    original = read_json(root / relative)
    if original:
        original = {k: v for k, v in original.items() if k != "reviews"}
    return original, [relative]


def review_metadata(root, task):
    original, refs = original_for(root, task)
    return {"decision_id": task["decision_id"], "assets": task["assets"],
            "topics": task["topics"], "original": original, "original_source_refs": refs,
            "original_task": {k: task[k] for k in ("id", "decision_id", "source", "review_at", "review_after",
                "decision_date", "assets", "topics", "discussion_dir", "window") if k in task}}


def compare(check, bundle, clock):
    result = {"claim": check["claim"], "condition": check, "status": "insufficient_evidence"}
    history = bundle.get("histories", {}).get(check["history_key"])
    if not history:
        return dict(result, reason="same_instrument_history_missing")
    try:
        require_identity(history, check)
        view = history_view(history, clock, min_observations=1)
        if view["status"] in {"malformed", "unsupported_calendar"}:
            return dict(result, reason=view.get("reason") or view["status"])
        start, end = date.fromisoformat(check["start"]), date.fromisoformat(check["end"])
        if calendar.available_at(check["venue"], end) > clock:
            return dict(result, reason="result_not_mature")
        by_day = {b["date"]: b for b in view["bars"]}
        required = price_sessions(history, start, end)
        missing = [d.isoformat() for d in required if d.isoformat() not in by_day]
        if missing:
            return dict(result, reason="required_sessions_missing", missing_sessions=missing)
        first, last = by_day[check["start"]], by_day[check["end"]]
        # Price levels use raw index/exchange close; ETF returns use adjusted
        # closes and retain their declared return semantics.
        value = (last["adjusted_close"]/first["adjusted_close"]-1)*100 if check["metric"] == "close_return_pct" else last["close"]
        matched = value >= check["threshold"] if check["operator"] == "gte" else value <= check["threshold"]
        return dict(result, status="observed", value=value, condition_met=matched,
                    start_bar=first, end_bar=last, source_url=history.get("source_url"),
                    input_path=history.get("input_path") or bundle.get("record_path"), window_sha256=digest([by_day[d.isoformat()] for d in required]),
                    vintage_status="current_provider_history_not_point_in_time", actual_account_return=None)
    except (ValueError, KeyError, TypeError) as exc:
        return dict(result, reason=str(exc))


def _spec(root, task, original):
    from research_engine.workspace import read_json
    explicit = original.get("review_spec") if original else None
    if explicit:
        return parse_spec(explicit), "original_review_spec"
    policy = original and original.get("record_kind") in {"constraint", "baseline_plan", "execution_plan"}
    return {"kind": "policy" if policy else "research", "checks": [],
            "evidence_gaps": ["原记录未登记机器可判定条件，须通过ChatGPT核对原结论及失效条件。"]}, "unstructured_original"


def assess(root, task, bundle, clock):
    meta = review_metadata(root, task)
    original = meta["original"]
    spec, spec_source = _spec(root, task, original)
    from research_engine.integration import optional
    research_evidence = optional(root, clock, "review_evidence", task=task, original=original) or {}
    if not isinstance(research_evidence, dict):
        raise ValueError("review_evidence must return a mapping")
    learning = {field: list(spec.get(field, [])) for field in LEARNING_FIELDS}
    if spec["kind"] != "market":
        for field in ("evidence_gaps", "mechanisms", "competing_explanations"):
            learning[field].extend(_strings(research_evidence.get(field, []), field))
    if not original:
        learning["evidence_gaps"].append("找不到原始判断，不能完成验证。")
    checks = [compare(check, bundle, clock) for check in spec.get("checks", [])]
    macro = {"status": "not_supplied"}
    for check in checks:
        if check["status"] != "observed":
            learning["evidence_gaps"].append(f"{check['claim']}: {check['reason']}")
        else:
            field = "supported" if check["condition_met"] else "refuted"
            learning[field].append(f"仅此项观测条件{'满足' if check['condition_met'] else '未满足'}：{check['claim']}；{check['condition']['metric']}={check['value']:.6f}；不证明整体经济解释。")
    policy_checks = []
    if spec["kind"] == "policy" and original:
        policy_checks.append({"condition": original.get("invalidation", ""),
                              "status": "recorded_active_not_reconfirmed",
                              "meaning": "队列中的原政策未被明确替代；外部约束与用户当前意愿仍须核实。"})
        for milestone in spec.get("milestones", []):
            reached = date.fromisoformat(milestone["date"]) <= clock.astimezone(ZoneInfo("Asia/Shanghai")).date()
            policy_checks.append({**milestone, "status": "review_window_reached" if reached else "future_window"})
        learning["evidence_gaps"].append("政策检查不使用价格涨跌打分；未确认交易及用户当前意愿不能推断。")
    if spec["kind"] != "market" and not learning["evidence_gaps"]:
        learning["evidence_gaps"].append("机制、政策与竞争解释须由ChatGPT逐项评价，不能由价格相关性关闭。")
    complete = bool(original and checks and spec["kind"] == "market" and not learning["evidence_gaps"])
    verdict = ("supported" if all(c["condition_met"] for c in checks) else
               "refuted" if all(not c["condition_met"] for c in checks) else "mixed") if complete else "not_evaluated"
    if complete and verdict in {"refuted", "mixed"}:
        learning["errors"].extend(learning["refuted"])
        learning["next_hypotheses"].append("用新记录和新的未来窗口检验修订解释；本窗口不重复作为独立样本。")
    status = "reviewed" if complete else "awaiting_evaluation"
    conclusion = (f"已完成登记的客观条件对照：{verdict}。" if complete else
                  "已整理可程序化证据，整体判断仍待评价；请按原条件核对缺口与竞争解释。")
    refs = list(dict.fromkeys([*meta["original_source_refs"], *research_evidence.get("source_refs", []), *([spec_source] if spec_source.startswith("config/") else []),
                              *[c[k] for c in checks for k in ("input_path", "source_url") if c.get(k)],
                              *([bundle["record_path"]] if macro.get("series") and bundle.get("record_path") else []),
                              *[v["source_url"] for v in macro.get("series", {}).values() if v.get("source_url")]]))
    return {**meta, "review_kind": spec["kind"], "review_spec": spec, "spec_source": spec_source,
            "checks": checks, "policy_checks": policy_checks, "macro_context": macro, "research_evidence": research_evidence, "learning": learning,
            "facts": json.dumps({"checks": checks, "policy_checks": policy_checks, "macro_context": macro,
                                 "research_evidence_available": bool(research_evidence)}, ensure_ascii=False, sort_keys=True),
            "conclusion": conclusion, "source_refs": refs, "status": status, "verdict": verdict,
            "execution_status": "not_inferred", "execution_allowed": False, "actual_account_return": None}


def advance_reviews(root, clock, bundle=None):
    from research_engine.workspace import append_event, context, events
    from research_engine.market_data import load_bundle
    queue = context(root, clock)["review_queue"]
    bundle = bundle if bundle is not None else load_bundle(root, clock)
    prior = events(root)
    added = []
    for task in queue:
        if task["status"] not in {"due", "awaiting_evaluation"}:
            continue
        result = assess(root, task, bundle, clock)
        # Meaningful evidence only: no daily event for an unchanged gap and no
        # completed review rerun. First evidence and first mature result freeze.
        semantic = {k: v for k, v in result.items() if k not in {"source_refs", "facts", "checks"}}
        semantic["checks"] = [{k: v for k, v in c.items() if k not in {"input_path", "source_url"}} for c in result["checks"]]
        semantic["macro_context"] = {**result["macro_context"], "series": {
            name: {k: v for k, v in value.items() if k != "retrieved_at"}
            for name, value in result["macro_context"].get("series", {}).items()}}
        signature = digest(semantic)
        if any(e.get("review_id") == task["id"] and e.get("assessment_sha256") == signature for e in prior):
            continue
        event = {"id": "auto-review-" + digest([task["id"], signature])[:32],
                 "type": "review_completion", "review_id": task["id"], "producer": "daily_review_v1",
                 "assessment_sha256": signature, **result}
        added.append(append_event(root, event, clock))
    context(root, clock)
    return {"discovered": sum(t["status"] != "pending" for t in queue), "written": len(added),
            "completed": sum(e["status"] == "reviewed" for e in added),
            "awaiting_evaluation": sum(e["status"] == "awaiting_evaluation" for e in added),
            "event_ids": [e["id"] for e in added]}


def feedback_for(asset, reviews, decisions):
    """Always included in the normal current_state entry, even for old assets."""
    by_id = {d["id"]: d for d in decisions}
    latest = {}
    for event in sorted(reviews, key=lambda e: (datetime.fromisoformat(e["recorded_at"]), e["id"])):
        previous = latest.get(event["review_id"])
        # Queue closure is terminal. A gap snapshot with the same cutoff must
        # not hide the completed result merely because its hash sorts later.
        if (previous and previous.get("status", "reviewed") == "reviewed"
                and event.get("status") == "awaiting_evaluation"):
            continue
        latest[event["review_id"]] = event
    result = {"recent_completed": [], "awaiting_evaluation": [], "forward_observations": [], "detail_path": "exports/reviews.json"}
    for event in sorted(latest.values(), key=lambda e: (datetime.fromisoformat(e["recorded_at"]), e["id"]), reverse=True):
        decision = by_id.get(event.get("decision_id") or event["review_id"], {})
        assets = event.get("assets") or decision.get("assets", [])
        if asset not in assets and "all" not in assets:
            continue
        learning = event.get("learning") or {field: [] for field in LEARNING_FIELDS}
        item = {"review_id": event["review_id"], "event_id": event["id"],
                "decision_id": event.get("decision_id") or event["review_id"],
                "recorded_at": event.get("recorded_at"), "status": event.get("status", "reviewed"),
                "review_kind": event.get("review_kind", "legacy_manual"), "verdict": event.get("verdict", "see_conclusion"),
                "facts": event.get("facts", ""), "conclusion": event.get("conclusion", ""), **learning,
                "source_refs": event.get("source_refs", []), "detail_path": event.get("origin", {}).get("path") or f"data/events/{event['id']}.json"}
        key = ("awaiting_evaluation" if item["status"] == "awaiting_evaluation" else
               "forward_observations" if item["review_kind"] == "forward_observation" else "recent_completed")
        result[key].append(item)
    result["counts"] = {k: len(result[k]) for k in ("recent_completed", "awaiting_evaluation", "forward_observations")}
    for key in ("recent_completed", "awaiting_evaluation", "forward_observations"):
        result[key] = result[key][:5]
    result["usage"] = "研究前读取本反馈及相关原判断；逐项说明支持、反驳、缺口、仍适用机制和新假设。经验不自动修改模型权重、投资政策或交易权限。"
    return result


def load_feedback(root, asset):
    from research_engine.workspace import read_json
    return read_json(root / "exports/current_state.json", {}).get("assets", {}).get(asset, {}).get("review_feedback", {})
