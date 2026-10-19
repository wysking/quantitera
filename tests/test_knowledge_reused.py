"""Unchanged generic knowledge regressions retained from P1."""
import json
from research_engine.knowledge import build_knowledge_views, normalize_decision

def test_views_separate_index_state_details_and_reviews(tmp_path):
    events = [
        {"id": "old-001", "type": "discussion_decision", "asset": "gold", "note": "old",
         "recorded_at": "2026-09-18T10:00:00+08:00"},
        {"id": "new-001", "type": "discussion_decision", "schema_version": 3,
         "assets": ["gold", "nasdaq"], "topics": ["macro"], "aliases": ["议息"],
         "conclusion": "new", "supersedes": ["old-001"], "review_at": "2026-09-19",
         "status": "active", "recorded_at": "2026-09-19T10:00:00+08:00"},
    ]
    views = build_knowledge_views(tmp_path, events, "2026-09-19T17:00:00+08:00")
    assert views["manifest"]["schema_version"] == 3
    assert next(x for x in views["index"] if x["id"] == "old-001")["status"] == "superseded"
    assert views["review_queue"][0]["status"] == "due"
    assert views["review_queue"][0]["source"] == "discussion_decision"
    detail = json.loads((tmp_path / "exports/knowledge/new-001.json").read_text(encoding="utf-8"))
    assert detail["assets"] == ["gold", "nasdaq"]
    assert (tmp_path / "exports/retrieval_index.json").exists()
    assert (tmp_path / "exports/current_state.json").exists()


def test_long_conclusions_only_live_in_details_and_overflow_is_explicit(tmp_path):
    events = [{"id": f"decision-{n}", "type": "discussion_decision", "asset": "gold",
               "note": "A" * 12000, "recorded_at": "2026-09-19T10:00:00+08:00"}
              for n in range(25)]
    views = build_knowledge_views(tmp_path, events, "2026-09-19T17:00:00+08:00")
    assert len(json.dumps(views["index"])) < 30000
    assert all("search_text" not in item for item in views["index"])
    state = views["current_state"]["gold"]
    assert state["truncated"] and state["count"] == 25
    assert len(state["active_decisions"]) == 20
    detail = json.loads((tmp_path / views["index"][0]["detail_path"]).read_text(encoding="utf-8"))
    assert detail["conclusion"] == "A" * 12000


def test_unresolved_review_is_removed_only_after_full_asset_supersession(tmp_path):
    old = {"id": "old-unresolved", "type": "discussion_decision", "assets": ["gold", "nasdaq"],
           "status": "unresolved", "note": "pending", "review_at": "2026-09-18",
           "recorded_at": "2026-09-17T10:00:00+08:00"}
    newer = {"id": "gold-update", "type": "discussion_decision", "assets": ["gold"],
             "note": "gold updated", "supersedes": [old["id"]], "recorded_at": "2026-09-18T10:00:00+08:00"}
    views = build_knowledge_views(tmp_path, [old, newer], "2026-10-01T12:00:00+08:00")
    assert views["review_queue"][0]["assets"] == ["nasdaq"]
    assert next(x for x in views["index"] if x["id"] == old["id"])["status"] == "unresolved"
    newer["assets"] = ["gold", "nasdaq"]
    newer["status"] = "archived"
    views = build_knowledge_views(tmp_path, [old, newer], "2026-10-01T12:00:00+08:00")
    assert not views["review_queue"]
    assert next(x for x in views["index"] if x["id"] == old["id"])["status"] == "superseded"


def test_classification_does_not_remove_other_asset_constraints(tmp_path):
    original = {"id": "gold-constraint", "type": "discussion_decision", "asset": "gold",
                "note": "do not chase", "recorded_at": "2026-09-18T10:00:00+08:00"}
    old_plan = dict(original, id="old-plan", asset="nasdaq", note="old route")
    annotations = [
        {"id": "label-rule", "type": "knowledge_annotation", "target_id": original["id"],
         "record_kind": "constraint", "status": "", "note": "long term", "recorded_at": "2026-10-01T10:00:00+08:00"},
        {"id": "archive-plan", "type": "knowledge_annotation", "target_id": old_plan["id"],
         "record_kind": "baseline_plan", "status": "archived", "note": "replaced route", "recorded_at": "2026-10-01T10:01:00+08:00"},
    ]
    views = build_knowledge_views(tmp_path, [original, old_plan, *annotations], "2026-10-01T12:00:00+08:00")
    assert "nasdaq" not in views["current_state"]
    assert views["current_state"]["gold"]["groups"] == {"constraint": [original["id"]]}
    detail = json.loads((tmp_path / "exports/knowledge/old-plan.json").read_text(encoding="utf-8"))
    assert detail["conclusion"] == old_plan["note"]
    assert detail["annotations"][0]["note"] == "replaced route"


def test_review_completion_is_retrievable_and_does_not_rewrite_forecast(tmp_path):
    original = {"id": "old-review", "type": "discussion_decision", "asset": "gold",
                "note": "hold", "review_at": "2026-09-18", "recorded_at": "2026-09-17T10:00:00+08:00"}
    completion = {"id": "done-review", "type": "review_completion", "review_id": original["id"],
                  "facts": "proxy declined", "conclusion": "reviewed", "recorded_at": "2026-10-01T10:00:00+08:00"}
    views = build_knowledge_views(tmp_path, [original, completion], "2026-10-01T12:00:00+08:00")
    assert views["review_queue"] == []
    assert views["current_state"]["gold"]["active_decisions"][0]["id"] == original["id"]
    assert json.loads((tmp_path / "exports/reviews.json").read_text(encoding="utf-8"))["items"] == [completion]
