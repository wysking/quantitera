"""Small workspace boundary extracted from the existing immutable ledger API."""
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re
from research_engine.knowledge import build_knowledge_views, RECORD_KINDS
UTC8 = timezone(timedelta(hours=8))
def now() -> datetime:
    return datetime.now(UTC8)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, indent=2, default=str, allow_nan=False) + "\n"
    temp = path.with_suffix(".tmp")
    temp.write_text(text, encoding="utf-8", newline="\n")
    temp.replace(path)


def read_json(path: Path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,79}", value):
        raise ValueError("记录编号须为3—80位字母、数字、横线或下划线")
    return value


def events(root: Path) -> list[dict]:
    return [read_json(p) for p in sorted((root / "data/events").glob("*.json"))]


def append_event(root: Path, event: dict, clock: datetime) -> dict:
    key = identifier(event["id"])
    path = root / "data/events" / f"{key}.json"
    previous = read_json(path)
    if previous:
        if {k: v for k, v in previous.items() if k != "recorded_at"} == event:
            return previous
        raise ValueError("编号已存在但内容不同；不会覆盖原记录")
    event = dict(event, recorded_at=clock.isoformat())
    write_json(path, event)
    return event


def save_decision(root: Path, inputs: dict, clock: datetime) -> dict:
    from research_engine.review_cycle import parse_spec
    review_spec = parse_spec(inputs.get("review_spec"))
    from research_engine.knowledge import RECORD_KINDS, VALID_HORIZONS, VALID_STATUSES, _list
    for field, choices, default in (("status", VALID_STATUSES, "active"),
                                   ("horizon", VALID_HORIZONS, "unspecified"),
                                   ("record_kind", RECORD_KINDS, "unclassified")):
        if inputs.get(field, default) not in choices:
            raise ValueError(f"讨论{field}无效")
    for field in ("assets", "subjects", "topics", "aliases", "supersedes", "related_ids", "source_refs"):
        _list(inputs.get(field))
    asset = inputs.get("asset", "all")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", asset):
        raise ValueError("asset must be an explicit workspace subject identifier")
    note = str(inputs.get("note", "")).strip()
    conclusion = str(inputs.get("conclusion", "")).strip()
    if not (note or conclusion) or len(note) > 12000 or len(conclusion) > 12000:
        raise ValueError("讨论结论不能为空，单字段最多12000字符")
    event = {
        "id": identifier(inputs.get("reference", "")), "type": "discussion_decision",
        "schema_version": 3, "asset": asset, "assets": inputs.get("assets", ""),
        "subjects": inputs.get("subjects", ""), "topics": inputs.get("topics", ""),
        "aliases": inputs.get("aliases", ""), "horizon": inputs.get("horizon", "unspecified"),
        "record_kind": inputs.get("record_kind", "unclassified"),
        "status": inputs.get("status", "active"), "confidence": inputs.get("confidence", "working"),
        "question": inputs.get("question", ""), "facts": inputs.get("facts", ""),
        "user_hypotheses": inputs.get("user_hypotheses", ""),
        "model_inference": inputs.get("model_inference", ""),
        "conclusion": conclusion or note, "invalidation": inputs.get("invalidation", ""),
        "review_at": inputs.get("review_at") or None,
        "supersedes": inputs.get("supersedes", ""), "related_ids": inputs.get("related_ids", ""),
        "source_refs": inputs.get("source_refs", ""), "note": note,
        "execution_status": "not_confirmed",
    }
    if review_spec:
        if not event["review_at"]:
            raise ValueError("登记验证条件必须填写review_at")
        event["review_spec"] = review_spec
    return append_event(root, event, clock)


def evidence_refs(value: str) -> list[str]:
    refs = json.loads(value or "[]")
    if not isinstance(refs, list) or not refs or any(not isinstance(x, str) or not x.strip() for x in refs):
        raise ValueError("source_refs须为非空JSON字符串数组，注明可追溯证据")
    return refs


def record_review(root: Path, inputs: dict, clock: datetime) -> dict:
    from research_engine.review_cycle import parse_result, review_metadata
    key = identifier(inputs.get("reference", ""))
    review_id = str(inputs.get("review_id", ""))
    if not re.fullmatch(r"[A-Za-z0-9_-]{3,200}", review_id):
        raise ValueError("复盘编号无效")
    facts, conclusion = (str(inputs.get(field, "")).strip() for field in ("facts", "conclusion"))
    if not facts or not conclusion or max(len(facts), len(conclusion)) > 12000:
        raise ValueError("完成复盘必须提供事实与结论，单字段最多12000字符")
    status = inputs.get("status", "reviewed")
    if status not in {"reviewed", "awaiting_evaluation"}:
        raise ValueError("复盘状态须为reviewed或awaiting_evaluation")
    learning = parse_result(inputs.get("review_result"))
    if status == "awaiting_evaluation" and (not learning or not learning["evidence_gaps"]):
        raise ValueError("待评价复盘必须列明evidence_gaps")
    event = {"id": key, "type": "review_completion", "review_id": review_id,
             "facts": facts, "conclusion": conclusion,
             "source_refs": evidence_refs(inputs.get("source_refs", "")),
             "note": str(inputs.get("note", ""))[:4000], "status": status,
             "execution_status": "not_inferred"}
    if learning is not None:
        event["learning"] = learning
    previous = read_json(root / "data/events" / f"{key}.json")
    if previous:
        if any(previous.get(k) != v for k, v in event.items()):
            raise ValueError("编号已存在但内容不同；不会覆盖原记录")
        return previous
    target = next((item for item in context(root, clock)["review_queue"] if item["id"] == review_id), None)
    if target is None:
        raise ValueError("待复盘事项不存在或已完成；不能重复关闭")
    if target["status"] not in {"due", "awaiting_evaluation"}:
        raise ValueError("复盘窗口尚未成熟，不能提前完成")
    event.update(review_metadata(root, target))
    if not event["original"]:
        raise ValueError("找不到原始判断，不能完成复盘")
    return append_event(root, event, clock)


def classify_decision(root: Path, inputs: dict, clock: datetime) -> dict:
    key, target = identifier(inputs.get("reference", "")), identifier(inputs.get("target_id", ""))
    kind, status = str(inputs.get("record_kind", "")), str(inputs.get("status", ""))
    if kind and kind not in RECORD_KINDS:
        raise ValueError("未知记录类别")
    if status not in {"", "archived", "expired"} or not (kind or status):
        raise ValueError("整理只支持分类、归档或标记过期，不得复活已替代记录")
    note = str(inputs.get("note", "")).strip()
    if not note or len(note) > 4000:
        raise ValueError("整理必须说明依据，最多4000字符")
    event = {"id": key, "type": "knowledge_annotation", "target_id": target,
             "record_kind": kind, "status": status, "note": note,
             "source_refs": evidence_refs(inputs.get("source_refs", ""))}
    if (root / "data/events" / f"{key}.json").exists():
        return append_event(root, event, clock)
    context(root, clock)
    if not (root / "exports/knowledge" / f"{target}.json").exists():
        raise ValueError("找不到要整理的原始结论")
    return append_event(root, event, clock)


def context(root, clock):
    from research_engine.calendar import aware
    from research_engine.integration import history
    aware(clock)
    combined = {}
    for event in [*history(root, clock), *events(root)]:
        if event["id"] in combined and combined[event["id"]] != event:
            raise ValueError("workspace/provider event identity collision")
        combined[event["id"]] = event
    known = [e for e in combined.values() if datetime.fromisoformat(e["recorded_at"]) <= clock]
    return build_knowledge_views(root, known, clock.isoformat())


def apply_operation(root, inputs, clock, record_id=None):
    from research_engine.review_cycle import advance_reviews
    from research_engine.evidence import record
    operation = inputs["operation"]
    handlers = {
        "save_decision": lambda: save_decision(root, inputs, clock),
        "record_review": lambda: record_review(root, inputs, clock),
        "classify_decision": lambda: classify_decision(root, inputs, clock),
        "record_evidence": lambda: record(root, inputs, clock),
        "research_refresh": lambda: advance_reviews(root, clock),
        "status": lambda: None,
    }
    if operation not in handlers:
        raise ValueError("unsupported research operation")
    result = handlers[operation]()
    context(root, clock)
    from research_engine.mechanisms import export
    export(root, clock)
    from research_engine.integration import export as export_workspace
    export_workspace(root, clock)
    return result
