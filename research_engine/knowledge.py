from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Iterable

from research_engine.reviews import is_review_due, legacy_review_due_at

VALID_STATUSES = {"active", "unresolved", "superseded", "expired", "archived"}
VALID_HORIZONS = {"intraday", "short_term", "event_window", "cycle", "structural", "unspecified"}
RECORD_KINDS = {"constraint", "baseline_plan", "execution_plan", "research", "workflow", "account_context", "unclassified"}
SYSTEM_MARKERS = ("架构", "检索", "工作流", "workflow", "知识库", "schema_version", "latest.json", "data/events")


def _list(value: object, *, lowercase: bool = True) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        values = value
    elif isinstance(value, str):
        text = value.strip()
        if text.startswith("["):
            values = json.loads(text)
        else:
            values = [part.strip() for part in text.split(",")]
    else:
        raise ValueError("列表字段必须是JSON数组或逗号分隔字符串")
    if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
        raise ValueError("列表字段必须包含字符串")
    result = []
    for item in values:
        item = item.strip()
        if lowercase:
            item = item.lower()
        if item and item not in result:
            result.append(item)
    return result


def _event_text(event: dict) -> str:
    return " ".join(str(event.get(k) or "") for k in ("title", "question", "note", "conclusion")).lower()


def _is_system_record(event: dict, text: str) -> bool:
    return str(event.get("asset") or "").strip().lower() == "all" and any(marker in text for marker in SYSTEM_MARKERS)


def infer_assets(event: dict) -> list[str]:
    # Subjects are explicitly supplied by each workspace, never inferred from holdings.
    return _list(event.get("assets")) or [str(event.get("asset") or "all").strip().lower()]


def infer_topics(event: dict) -> list[str]:
    explicit = _list(event.get("topics") or event.get("tags"))
    if explicit:
        return explicit
    text = _event_text(event)
    if _is_system_record(event, text):
        rules = {
            "workflow": ("架构", "工作流", "workflow", "知识库", "schema_version", "latest.json", "data/events"),
            "retrieval": ("检索", "retrieval"),
            "migration": ("迁移", "migration"),
            "review_queue": ("复盘", "review_queue"),
        }
        return [topic for topic, words in rules.items() if any(word in text for word in words)] or ["workflow"]
    rules = {
        "drawdown": ("回撤", "腰斩", "跌幅"),
        "valuation": ("估值", "pe", "pb"),
        "market_structure": ("市场结构", "诈骗", "收割", "高β", "高beta"),
        "earnings_quality": ("盈利", "现金流", "roic"),
        "dca": ("定投",),
        "macro": ("宏观", "利率", "通胀", "fomc"),
        "workflow": ("架构", "检索", "工作流", "workflow"),
    }
    return [topic for topic, words in rules.items() if any(word in text for word in words)] or ["general"]


def normalize_decision(event: dict) -> dict:
    note = str(event.get("note") or "").strip()
    recorded = str(event.get("recorded_at") or "")
    result = {
        "schema_version": 3,
        "id": event["id"],
        "recorded_at": recorded,
        "decision_date": str(event.get("decision_date") or recorded[:10]),
        "type": "knowledge_decision",
        "assets": infer_assets(event),
        "subjects": _list(event.get("subjects")),
        "topics": infer_topics(event),
        "aliases": _list(event.get("aliases")),
        "horizon": str(event.get("horizon") or event.get("time_horizon") or "unspecified"),
        "status": {"advisory_only": "active"}.get(str(event.get("status") or "active"),
                                                     str(event.get("status") or "active")),
        "confidence": str(event.get("confidence") or "working"),
        "record_kind": str(event.get("record_kind") or "unclassified"),
        "question": str(event.get("question") or ""),
        "facts": str(event.get("facts") or ""),
        "user_hypotheses": str(event.get("user_hypotheses") or ""),
        "model_inference": str(event.get("model_inference") or ""),
        "conclusion": str(event.get("conclusion") or note),
        "invalidation": str(event.get("invalidation") or ""),
        "review_at": event.get("review_at"),
        "supersedes": _list(event.get("supersedes"), lowercase=False),
        "related_ids": _list(event.get("related_ids"), lowercase=False),
        "source_refs": _list(event.get("source_refs"), lowercase=False),
        "execution_status": str(event.get("execution_status") or "not_confirmed"),
        "legacy_note": note if event.get("schema_version") != 3 else "",
    }
    if event.get("review_spec"):
        result["review_spec"] = event["review_spec"]
    if result["status"] not in VALID_STATUSES:
        result["original_status"] = result["status"]
        result["normalization_issues"] = ["unknown_status"]
        result["status"] = "invalid"
    if result["horizon"] not in VALID_HORIZONS:
        result["horizon"] = "unspecified"
    if result["record_kind"] not in RECORD_KINDS:
        result["record_kind"] = "unclassified"
    return result


def build_knowledge_views(root: Path, all_events: Iterable[dict], generated_at: str) -> dict:
    all_events = list(all_events)
    decisions = [normalize_decision(e) for e in all_events if e.get("type") == "discussion_decision"]
    event_ids = {item["id"] for item in decisions}
    decisions.sort(key=lambda x: (x["decision_date"], x["recorded_at"], x["id"]))
    by_id = {item["id"]: item for item in decisions}
    annotations = sorted((e for e in all_events if e.get("type") == "knowledge_annotation"),
                         key=lambda e: (e["recorded_at"], e["id"]))
    for annotation in annotations:
        item = by_id.get(annotation["target_id"])
        if item is None:
            continue
        item.setdefault("annotations", []).append(annotation)
        if annotation.get("status"):
            item["status"] = annotation["status"]
        if annotation.get("record_kind"):
            item["record_kind"] = annotation["record_kind"]
    superseded_assets: dict[str, set[str]] = defaultdict(set)
    for newer in decisions:
        for old_id in newer["supersedes"]:
            older = by_id.get(old_id)
            if older is None:
                continue
            overlap = set(older["assets"]) & set(newer["assets"])
            if "all" in newer["assets"]:
                overlap = set(older["assets"])
            superseded_assets[old_id].update(overlap)
    for item in decisions:
        item["active_assets"] = [asset for asset in item["assets"]
                                 if asset not in superseded_assets[item["id"]]]
        if not item["active_assets"] and item["status"] in {"active", "unresolved"}:
            item["status"] = "superseded"

    reviews = sorted((e for e in all_events if e.get("type") == "review_completion"),
                     key=lambda e: (e.get("recorded_at", ""), e["id"]))
    for item in decisions:
        related_reviews = [e for e in reviews if (e.get("decision_id") or e["review_id"]) == item["id"]]
        if related_reviews:
            item["reviews"] = related_reviews

    details = root / "exports/knowledge"
    details.mkdir(parents=True, exist_ok=True)
    for item in decisions:
        (details / f'{item["id"]}.json').write_text(
            json.dumps(item, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )

    index = [{
        "id": item["id"], "decision_date": item["decision_date"], "assets": item["assets"],
        "active_assets": item["active_assets"],
        "subjects": item["subjects"], "topics": item["topics"], "aliases": item["aliases"],
        "horizon": item["horizon"], "status": item["status"], "confidence": item["confidence"],
        "record_kind": item["record_kind"],
        "review_at": item["review_at"], "supersedes": item["supersedes"],
        "execution_status": item["execution_status"],
        "summary": item["conclusion"][:280],
        "source_kind": item.get("source_kind", "discussion_decision"),
        "detail_path": f'exports/knowledge/{item["id"]}.json',
    } for item in decisions]

    by_asset = defaultdict(list)
    for item in reversed(index):
        if item["status"] in {"active", "unresolved"}:
            for asset in item["active_assets"]:
                by_asset[asset].append(item)
    current_state = {
        asset: {"active_decisions": items[:20], "count": len(items),
                "truncated": len(items) > 20, "overflow_path": "exports/retrieval_index.json",
                "groups": {kind: [item["id"] for item in items if item["record_kind"] == kind]
                           for kind in sorted({item["record_kind"] for item in items})}}
        for asset, items in sorted(by_asset.items())
    }
    clock = datetime.fromisoformat(generated_at)
    review_queue = [{
        "id": item["id"], "decision_id": item["id"],
        "source": item.get("source_kind", "discussion_decision"),
        "review_at": item["review_at"], "decision_date": item["decision_date"],
        "assets": item["active_assets"], "topics": item["topics"],
        "status": "due" if is_review_due(str(item["review_at"]), clock) else "pending",
        "detail_path": item["detail_path"],
    } for item in index if item["review_at"] and item["status"] in {"active", "unresolved"}]
    completed = [e for e in reviews if e.get("status", "reviewed") == "reviewed"]
    completed_ids = {e["review_id"] for e in completed}
    latest_reviews = {e["review_id"]: e for e in reviews}
    review_targets = {item["id"]: item for item in review_queue}
    review_queue = [item for item in review_queue if item["id"] not in completed_ids]
    for item in review_queue:
        review = latest_reviews.get(item["id"])
        if review and review.get("status") == "awaiting_evaluation":
            item.update(status="awaiting_evaluation", latest_review_id=review["id"],
                        evidence_gaps=review.get("learning", {}).get("evidence_gaps", []),
                        detail_path=f"data/events/{review['id']}.json",
                        original_detail_path=item.get("detail_path"), needs_chatgpt=True)
    review_queue.sort(key=lambda x: (
        0 if x["status"] in {"due", "awaiting_evaluation"} else 1,
        x.get("review_at") or x.get("decision_date") or "9999-12-31",
        x["id"],
    ))

    from research_engine.review_cycle import feedback_for
    feedback_reviews = [{**e, "decision_id": e.get("decision_id") or
        review_targets.get(e["review_id"], {}).get("decision_id") or e["review_id"], "assets": e.get("assets") or
        by_id.get(e.get("decision_id") or e["review_id"], {}).get("assets") or
        review_targets.get(e["review_id"], {}).get("assets", [])} for e in reviews]
    feedback_assets = set(current_state)
    for review in feedback_reviews:
        feedback_assets.update(review.get("assets", []))
    for asset in sorted(feedback_assets):
        state = current_state.setdefault(asset, {"active_decisions": [], "count": 0,
            "truncated": False, "overflow_path": "exports/retrieval_index.json", "groups": {}})
        state["review_feedback"] = feedback_for(asset, feedback_reviews, decisions)

    manifest = {
        "schema_version": 3, "generated_at": generated_at,
        "counts": {"decisions": len(event_ids), "legacy_history": len(decisions) - len(event_ids), "knowledge_records": len(index), "active_assets": sum(bool(s["count"]) for s in current_state.values()), "reviews": len(review_queue)},
        "paths": {
            "retrieval_index": "exports/retrieval_index.json",
            "current_state": "exports/current_state.json",
            "review_queue": "exports/review_queue.json",
            "details": "exports/knowledge/<decision_id>.json",
            "reviews": "exports/reviews.json",
            "mechanisms": "exports/mechanisms.json",
        },
    }
    payloads = {
        "exports/retrieval_index.json": {"schema_version": 3, "generated_at": generated_at, "items": index},
        "exports/current_state.json": {"schema_version": 3, "generated_at": generated_at, "assets": current_state},
        "exports/review_queue.json": {"schema_version": 3, "generated_at": generated_at, "items": review_queue},
        "exports/manifest.json": manifest,
        "exports/reviews.json": {"schema_version": 2, "generated_at": generated_at, "items": reviews},
    }
    for path, value in payloads.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return {"manifest": manifest, "index": index, "current_state": current_state, "review_queue": review_queue}
