"""V6 mechanism cards with workspace definitions instead of private asset models."""
from research_engine.market_data import digest
def mechanism_cards(facts, definitions):
    cards = []
    for name, (
        hypothesis,
        horizon,
        alternatives,
        invalidation,
        next_observation,
    ) in definitions.items():
        for actual_horizon in sorted(
            {horizon} | {f["horizon"] for f in facts if f.get("mechanism_id") == name}
        ):
            source = [
                f
                for f in facts
                if f.get("mechanism_id") == name and f["horizon"] == actual_horizon
            ]
            usable = [f for f in source if f["status"] in {"ok", "available"}]
            # Repeated sources/IDs describe one datum, not additional confidence.
            unique = {}
            for fact in usable:
                signature = digest(
                    {
                        k: fact.get(k)
                        for k in (
                            "metric",
                            "value",
                            "unit",
                            "observation_period",
                            "evidence_role",
                        )
                    }
                )
                unique.setdefault(signature, fact)
            usable = list(unique.values())
            cards.append(
                {
                    "mechanism_id": name,
                    "mechanism_card_id": name + "-" + actual_horizon,
                    "hypothesis": hypothesis,
                    "horizon": actual_horizon,
                    "status": "research_only" if usable else "unknown",
                    "causal_status": "hypothesis_not_identified",
                    "supporting_evidence": [
                        f["evidence_id"]
                        for f in usable
                        if f["evidence_role"] == "supporting"
                    ],
                    "counter_evidence": [
                        f["evidence_id"]
                        for f in usable
                        if f["evidence_role"] == "counter"
                    ],
                    "context_evidence": [
                        f["evidence_id"]
                        for f in usable
                        if f["evidence_role"] == "context"
                    ],
                    "missing_evidence": (
                        ["independent channel identification", "prior expectations"]
                        if usable
                        else ["available source for this mechanism"]
                    ),
                    "alternative_explanations": alternatives,
                    "invalidation": invalidation,
                    "next_observation": next_observation,
                    "expiry": None,
                    "forecast": None,
                    "source_refs": sorted({f["source_url"] for f in usable}),
                }
            )
    return cards


def export(root, clock):
    from research_engine.workspace import read_json, write_json
    from research_engine.evidence import visible_records
    from research_engine.expectations import compare
    from research_engine.conflicts import diagnose
    from research_engine.review_cycle import load_feedback
    config = read_json(root / "config/research.json", {"mechanisms": {}})
    records = visible_records(root, clock)
    assets = set(config.get("mechanisms", {})) | {r["asset"] for r in records}
    assets.update(read_json(root / "exports/current_state.json", {}).get("assets", {}))
    reports = {}
    for asset in sorted(assets):
        selected = [{**r, "evidence_id": r["record_id"]} for r in records if r["asset"] == asset]
        definitions = {name: (d["hypothesis"], d["horizon"], d["alternative_explanations"],
                              d["invalidation"], d["next_observation"])
                       for name, d in config.get("mechanisms", {}).get(asset, {}).items()}
        cards = mechanism_cards(selected, definitions)
        prior = compare(selected)
        technical = {"status": "not_supplied", "direction": None}
        reports[asset] = {"economic_mechanisms": cards, "expectations": prior,
                          "conflicts": diagnose(selected, cards, technical, prior, []),
                          "review_feedback": load_feedback(root, asset),
                          "causal_status": "not_identified", "execution_allowed": False}
    value = {"schema_version": 1, "generated_at": clock.isoformat(), "assets": reports,
             "source_verification": "provided references; not independently downloaded", "execution_allowed": False}
    write_json(root / "exports/mechanisms.json", value)
    return value
