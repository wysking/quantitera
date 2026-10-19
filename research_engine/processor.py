"""Process immutable requests created by the GitHub plugin; publish machine-readable receipts."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile

from research_engine.workspace import apply_operation, now, read_json, write_json

OPERATIONS = {"save_decision", "record_review", "classify_decision", "record_evidence", "research_refresh", "status"}
FIELDS = {"reference", "asset", "note", "assets", "subjects", "topics", "aliases", "horizon", "status", "confidence", "question",
          "facts", "user_hypotheses", "model_inference", "conclusion", "invalidation", "review_at", "supersedes", "related_ids",
          "source_refs", "review_id", "target_id", "record_kind", "review_spec", "review_result", "evidence"}


class RequestFileError(ValueError):
    """A single request cannot be trusted; the existing ledger is untouched."""

    def __init__(self, message, digest=None):
        super().__init__(message)
        self.digest = digest


def validate_request(payload: object) -> dict:
    if not isinstance(payload, dict) or set(payload) != {"version", "operation", "inputs"}:
        raise ValueError("请求必须包含且仅包含version、operation、inputs")
    if type(payload["version"]) is not int or payload["version"] != 1:
        raise ValueError("不支持的请求版本")
    op = payload["operation"]
    if not isinstance(op, str) or op not in OPERATIONS:
        raise ValueError("不支持的操作")
    inputs = payload["inputs"]
    if not isinstance(inputs, dict) or set(inputs) - FIELDS:
        raise ValueError("inputs字段无效")
    for name, value in inputs.items():
        if name in {"confirmed", "refresh", "enabled"}:
            if type(value) is not bool:
                raise ValueError(f"{name}须为JSON布尔值")
        elif not isinstance(value, str):
            raise ValueError(f"{name}须为字符串")
    for field, operation in (("review_spec", "save_decision"), ("review_result", "record_review"), ("evidence", "record_evidence")):
        if field in inputs and op != operation:
            raise ValueError(f"{field} only supports {operation}")
    return dict(inputs, operation=op)


def process_one(root: Path, path: Path, clock: datetime) -> dict:
    root, path = root.resolve(), path.absolute()
    if path.parent != root / "inbox" or path.is_symlink():
        raise RequestFileError("仅支持inbox中的普通JSON请求")
    request_id = path.stem
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}", request_id):
        raise RequestFileError("请求文件名须为3—64位字母、数字、横线或下划线")
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    receipt_path = root / "outbox" / f"{request_id}.json"
    old = read_json(receipt_path)
    if old:
        if old.get("request_sha256") != digest:
            raise RequestFileError("已处理的请求被修改；请使用新编号，不会重放或覆盖旧回执", digest)
        return old
    receipt = {"request_id": request_id, "request_sha256": digest, "processed_at": clock.isoformat(),
        "status": "rejected", "operation": None}
    # All validation and view generation happen in a disposable copy. A rejected
    # snapshot or failed export cannot leave a partial trade in the real ledger.
    with tempfile.TemporaryDirectory(prefix="quant-request-") as temporary:
        stage = Path(temporary)
        try:
            if len(raw) > 80000:
                raise ValueError("请求超过80KB限制")
            payload = json.loads(raw)
            inputs = validate_request(payload)
            receipt["operation"] = inputs["operation"]
            for relative in ("data", "inputs", "config"):
                if (root / relative).exists():
                    shutil.copytree(root / relative, stage / relative)
            result = apply_operation(stage, inputs, clock, record_id=f"request-{request_id}")
            receipt.update(status="succeeded", result={
                "event_id": result.get("id") if isinstance(result, dict) else None,
                "review_feedback_path": "exports/current_state.json", "review_queue_path": "exports/review_queue.json",
                "mechanisms_path": "exports/mechanisms.json", "execution_allowed": False})
        except (ValueError, TypeError, KeyError, OSError, ArithmeticError) as exc:
            receipt["error"] = str(exc)[:1000]
        if receipt["status"] == "succeeded":
            # File system failures here abort the whole job, before git publishes.
            for relative in ("data/events", "exports"):
                if (stage / relative).exists():
                    shutil.copytree(stage / relative, root / relative, dirs_exist_ok=True)
    write_json(receipt_path, receipt)
    return receipt


def process_pending(root: Path, clock: datetime | None = None) -> list[dict]:
    clock = clock or now()
    receipts = []
    for index, path in enumerate(sorted((root / "inbox").glob("*.json"))):
        try:
            receipts.append(process_one(root, path, clock + timedelta(microseconds=index)))
        except RequestFileError as exc:
            # Preserve any prior success receipt. Never read through symlinks,
            # and do not swallow disk/ledger integrity failures as file errors.
            identity = hashlib.sha256(json.dumps([path.name, exc.digest, str(exc)],
                                                ensure_ascii=False).encode()).hexdigest()
            relative = f"outbox/file_errors/{identity}.json"
            receipt = read_json(root / relative)
            if not receipt:
                receipt = {"request_id": path.stem, "request_sha256": exc.digest,
                    "processed_at": (clock + timedelta(microseconds=index)).isoformat(),
                    "status": "rejected", "operation": None, "error": str(exc),
                    "error_path": relative}
                write_json(root / relative, receipt)
            receipts.append(receipt)
    if not receipts:
        # An empty dispatch is useful for verifying the deployment.
        apply_operation(root, {"operation": "status"}, clock)
    return receipts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    receipts = process_pending(args.root.resolve())
    print(f"Checked {len(receipts)} request receipts. See outbox for individual results.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
