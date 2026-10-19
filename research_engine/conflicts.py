"""Data first, horizons second, mechanisms last. Never adds a directional score."""

from research_engine.market_data import digest
from research_engine.expectations import SOURCE_CONFLICTS

VERSION = "gold-shadow-conflict-v2"


def diagnose(facts, mechanisms, technical, expectations, errors):
    grouped = {}
    for fact in facts:
        grouped.setdefault(fact["fact_id"], []).append(fact)
        grouped.setdefault(
            "datum:" + digest([fact["metric"], fact["observation_period"]]), []
        ).append(fact)
    duplicates, conflicts = {}, []
    for key, group in grouped.items():
        signatures = {
            digest(
                {k: f.get(k) for k in ("metric", "value", "unit", "observation_period")}
            )
            for f in group
        }
        if len(signatures) > 1:
            conflicts.append(key)
        elif len(group) > 1:
            duplicates[key] = [f["evidence_id"] for f in group]
    usable = [m for m in mechanisms if m["status"] == "research_only"]
    data_missing = technical["status"] not in {"ok", "not_supplied"} or not usable
    source_conflicts = [e for e in expectations["events"] if e["status"] in SOURCE_CONFLICTS]
    conflict_records = sorted({record for e in source_conflicts
                              for record in e["counter_evidence"] + e["event_record_ids"]})
    labels = []
    if conflicts or data_missing or source_conflicts:
        labels.append("data_conflict")
    else:
        long_support = any(
            m["horizon"] == "structural" and m["supporting_evidence"] for m in usable
        )
        if long_support and technical["direction"] == "negative":
            labels.append("horizon_mismatch")
        if any(
            (m["counter_evidence"] and technical["direction"] == "positive")
            or (
                m["supporting_evidence"]
                and m["horizon"] != "structural"
                and technical["direction"] == "negative"
            )
            or (m["supporting_evidence"] and m["counter_evidence"])
            for m in usable
        ):
            labels.append("mechanism_disagreement")
        if any(
            e["priced_in_status"].startswith("consistent_with_prior")
            for e in expectations["events"]
        ):
            labels.append("prior_expectation_consistency_hypothesis")
    if not expectations["events"] or any(
        e["status"] == "unknown" or e["status"] in SOURCE_CONFLICTS for e in expectations["events"]
    ):
        labels.append("unresolved")
    if not labels:
        labels = ["no_observed_direction_conflict"]
    return {
        "conflict_policy_version": VERSION,
        "status": labels[0],
        "labels": labels,
        "hypothesis": "先核对资料与期限，再保留竞争机制；分歧不能证明市场错误定价",
        "supporting_evidence": sorted(
            {f["evidence_id"] for f in facts if f["status"] in {"ok", "available"}}
        ),
        "counter_evidence": conflicts + conflict_records,
        "source_conflicts": [{k: e[k] for k in
                              ("event_id", "event_record_ids", "status", "counter_evidence")}
                             for e in source_conflicts],
        "missing_evidence": errors + expectations["missing_evidence"],
        "alternative_explanations": [
            "信息时滞",
            "未观察到的其他买卖方",
            "同时发生的政策或流动性变化",
        ],
        "next_observation": "核实新披露、事前预期及直接数量/持仓资料",
        "expiry": None,
        "duplicate_fact_groups": duplicates,
        "independent_votes": None,
        "price_reused_as_expectation": False,
        "causal_effect": None,
        "direction_score": None,
    }
