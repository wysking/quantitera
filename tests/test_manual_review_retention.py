"""Synthetic regressions for pending human findings and automated gap updates."""
from copy import deepcopy
from datetime import timedelta
import json

from research_engine import integration
from research_engine.review_cycle import LEARNING_FIELDS, feedback_for, latest_reviews
from research_engine.workspace import apply_operation, append_event, context, read_json
from tests.test_workspace_provider import CLOCK, configured


def pending(key, clock, *, manual=False, target="synthetic-target"):
    learning = {field: [] for field in LEARNING_FIELDS}
    learning["evidence_gaps"] = ["SYNTHETIC economic comparison remains missing"]
    if manual:
        learning["errors"] = ["SYNTHETIC timing evidence was insufficient"]
        learning["next_hypotheses"] = ["SYNTHETIC evaluate evidence rather than fear of missing gains"]
    return {"id": key, "type": "review_completion", "review_id": target,
            "decision_id": target, "assets": ["beta"], "recorded_at": clock.isoformat(),
            "status": "awaiting_evaluation", "learning": learning,
            "facts": "SYNTHETIC facts", "conclusion": "SYNTHETIC review",
            "source_refs": ["synthetic:review"],
            **({} if manual else {"producer": "daily_review_v1"})}


def test_automated_gap_does_not_hide_manual_pending_analysis():
    manual = pending("synthetic-human", CLOCK, manual=True)
    auto = pending("synthetic-auto", CLOCK + timedelta(days=1))
    originals = deepcopy([manual, auto])
    selected = latest_reviews([auto, manual])["synthetic-target"]
    assert selected["id"] == manual["id"]
    assert selected["status"] == "awaiting_evaluation"
    assert selected["learning"]["errors"]
    assert [manual, auto] == originals


def test_later_manual_revision_replaces_prior_findings():
    old = pending("synthetic-old", CLOCK, manual=True)
    newer = pending("synthetic-revised", CLOCK + timedelta(days=1), manual=True)
    newer["learning"]["errors"] = []
    newer["learning"]["next_hypotheses"] = ["SYNTHETIC revised assessment"]
    auto = pending("synthetic-auto", CLOCK + timedelta(days=2))
    selected = latest_reviews([old, newer, auto])["synthetic-target"]
    assert selected["id"] == newer["id"]
    assert selected["learning"]["errors"] == []


def test_automatic_updates_and_gap_only_manual_notes_still_advance():
    first = pending("synthetic-first", CLOCK)
    gap_note = pending("synthetic-gap-note", CLOCK + timedelta(hours=1), manual=True)
    gap_note["learning"]["errors"] = []
    gap_note["learning"]["next_hypotheses"] = []
    newer = pending("synthetic-new", CLOCK + timedelta(days=1))
    assert latest_reviews([first, gap_note, newer])["synthetic-target"] == newer


def test_legacy_null_learning_does_not_break_feedback():
    note = pending("synthetic-null", CLOCK, manual=True)
    note["learning"] = None
    assert feedback_for("beta", [note], [])["awaiting_evaluation"][0]["errors"] == []


def test_manual_pending_findings_survive_the_five_item_feedback_limit():
    manual = pending("synthetic-human", CLOCK, manual=True)
    autos = [pending(f"synthetic-auto-{n}", CLOCK + timedelta(days=n + 1),
                     target=f"synthetic-other-{n}") for n in range(8)]
    feedback = feedback_for("beta", [manual, *autos], [])
    assert feedback["counts"]["awaiting_evaluation"] == 9
    assert len(feedback["awaiting_evaluation"]) == 5
    assert feedback["awaiting_evaluation"][0]["event_id"] == manual["id"]
    assert feedback_for("alpha", [manual, *autos], [])["awaiting_evaluation"] == []


def test_queue_feedback_and_model_keep_manual_findings_without_closing_review(tmp_path):
    configured(tmp_path)
    apply_operation(tmp_path, {"operation": "save_decision", "reference": "synthetic-target", "asset": "beta",
        "conclusion": "SYNTHETIC mechanism", "review_at": "2026-10-06",
        "review_spec": json.dumps({"kind": "research"})}, CLOCK)
    manual = apply_operation(tmp_path, {"operation": "record_review", "reference": "synthetic-human",
        "review_id": "synthetic-target", "status": "awaiting_evaluation",
        "facts": "SYNTHETIC facts", "conclusion": "SYNTHETIC evaluated process, incomplete result",
        "source_refs": '["synthetic:review"]',
        "review_result": json.dumps(pending("unused", CLOCK, manual=True)["learning"])}, CLOCK)
    original_path = tmp_path / "data/events/synthetic-human.json"
    original_bytes = original_path.read_bytes()
    later = CLOCK + timedelta(hours=1)
    append_event(tmp_path, pending("synthetic-auto", later), later)
    packet = context(tmp_path, later)
    task = next(row for row in packet["review_queue"] if row["id"] == "synthetic-target")
    assert task["status"] == "awaiting_evaluation"
    assert task["latest_review_id"] == manual["id"]
    model = integration.model(tmp_path, "beta", later)
    feedback = model["feedback_seen"]["asset_feedback"]["awaiting_evaluation"]
    assert next(row for row in feedback if row["review_id"] == task["id"])["event_id"] == manual["id"]
    assert model["value"] == 3 and not model["execution_allowed"]
    assert read_json(tmp_path / "data/events/synthetic-auto.json")["producer"] == "daily_review_v1"
    assert original_path.read_bytes() == original_bytes
