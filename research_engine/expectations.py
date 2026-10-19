"""Source-backed prior comparisons, never inferred from subsequent gold prices."""

from research_engine.evidence import stamp

VERSION = "gold-prior-expectation-v2"
EVENT_IDENTITY = ("event_id", "metric", "unit", "horizon", "observation_period")
SOURCE_CONFLICTS = {"conflicting_event_sources", "conflicting_prior_sources"}


def event_groups(records):
    """One comparable original event per declared target; retain every source ID."""
    groups = {}
    for event in (r for r in records if r["kind"] == "event"):
        comparable = (event["vintage_status"] == "original"
                      and event["published_at"] and event["status"] == "available")
        identity = ("original", *(event[k] for k in EVENT_IDENTITY)) if comparable else (
            "non_comparable", event["record_id"])
        groups.setdefault(identity, []).append(event)
    return list(groups.values())


def compare(records):
    results = []
    for group in event_groups(records):
        group = sorted(group, key=lambda r: (stamp(r["available_at"]), r["record_id"]))
        event = group[0]
        event_records = [r["record_id"] for r in group]
        result = {
            "event_id": event["event_id"],
            "event_record_id": event["record_id"],
            "event_record_ids": event_records,
            "event_identity": {k: event[k] for k in EVENT_IDENTITY},
            "status": "unknown",
            "surprise": None,
            "comparison_value": None,
            "expectation_record_id": None,
            "expectation_kind": None,
            "supporting_evidence": event_records,
            "counter_evidence": [],
            "missing_evidence": [],
            "alternative_explanations": ["事件后价格变动可能包含其他同时发生的信息"],
            "causal_status": "not_identified",
            "priced_in_status": "unknown",
        }
        if (
            event["vintage_status"] != "original"
            or not event["published_at"]
            or event["status"] != "available"
        ):
            result["missing_evidence"] = [
                "available_original_event_publication_required"
            ]
            results.append(result)
            continue
        # Two incompatible original values or release times cannot both be the
        # same event. Null remains missing, never a replacement for an actual.
        if len({(r["value"], stamp(r["published_at"])) for r in group}) != 1:
            result.update(status="conflicting_event_sources",
                          supporting_evidence=[], counter_evidence=event_records,
                          missing_evidence=["original_event_values_or_publication_times_conflict"])
            results.append(result)
            continue
        priors = [
            r
            for r in records
            if r["kind"] == "expectation" and r["event_id"] == event["event_id"]
        ]
        eligible = [
            r
            for r in priors
            if r["status"] == "available"
            and r["published_at"]
            and r["vintage_status"] == "original"
            and stamp(r["available_at"]) < stamp(event["published_at"])
            and stamp(r["expectation_cutoff_at"]) < stamp(event["published_at"])
            and all(
                r[k] == event[k]
                for k in ("metric", "unit", "horizon", "observation_period")
            )
        ]
        if not eligible:
            result["missing_evidence"] = [
                "prior_known_before_event_with_matching_target_unit_horizon"
            ]
        elif (
            len(
                {(r["expectation_kind"], r["population"], r["value"]) for r in eligible}
            )
            != 1
        ):
            result.update(
                status="conflicting_prior_sources",
                counter_evidence=[r["record_id"] for r in eligible],
                missing_evidence=["source_selection_requires_review; no averaging"],
            )
        else:
            prior = eligible[0]
            result.update(
                expectation_record_id=prior["record_id"],
                expectation_kind=prior["expectation_kind"],
                supporting_evidence=[r["record_id"] for r in eligible] + event_records,
            )
            if event["value"] is None or prior["value"] is None:
                result["missing_evidence"] = ["numeric_event_or_expectation_missing"]
            elif prior["expectation_kind"] == "market_implied":
                result["missing_evidence"] = [
                    "market_implied_instrument_and_model_not_registered_in_P1"
                ]
            else:
                difference = event["value"] - prior["value"]
                result.update(
                    comparison_value=difference,
                    unit=event["unit"],
                    status="provided_source_comparison",
                    source_verification=prior["source_verification"],
                )
                if prior["expectation_kind"] == "survey_consensus":
                    result["surprise"] = difference
                    result["priced_in_status"] = (
                        "consistent_with_prior_expectation_not_proven_priced_in"
                        if difference == 0
                        else "unknown"
                    )
                else:
                    result["comparison_label"] = {
                        "company_guidance": "difference_from_company_guidance",
                        "analyst_view": "difference_from_single_view",
                        "model_projection": "difference_from_own_model",
                    }[prior["expectation_kind"]]
        results.append(result)
    return {
        "expectation_policy_version": VERSION,
        "status": "conflicting_sources" if any(e["status"] in SOURCE_CONFLICTS for e in results)
        else "provided_source_comparisons"
        if any(e["comparison_value"] is not None for e in results)
        else "unknown",
        "events": results,
        "event_identity_fields": list(EVENT_IDENTITY),
        "surprise": None,
        "missing_evidence": sorted({m for e in results for m in e["missing_evidence"]})
        if results
        else ["no_recorded_event_and_prior_expectation"],
        "predictive_rule_eligible": False,
        "probability_up": None,
    }
