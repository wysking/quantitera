"""V6 synthetic source, prior and time regressions. No private fixtures."""
from datetime import datetime, timedelta, timezone
import json
import pytest
from research_engine.evidence import record, validate, visible_records
from research_engine.expectations import compare
CLOCK = datetime(2026, 10, 2, 10, tzinfo=timezone.utc)

@pytest.fixture
def root(tmp_path):
    return tmp_path

def evidence(kind="expectation", **changes):
    result = {
        "schema_version": 1,
        "asset": "gold",
        "kind": kind,
        "fact_id": "test-fact-01",
        "metric": "policy_rate",
        "unit": "percentage_points",
        "value": 3.0,
        "horizon": "medium",
        "observation_period": "2026-10",
        "published_at": (CLOCK - timedelta(hours=2)).isoformat(),
        "source_captured_at": (CLOCK - timedelta(hours=1)).isoformat(),
        "available_at": (CLOCK - timedelta(hours=2)).isoformat(),
        "source_url": "https://example.org/original-source",
        "source_excerpt": "Test-only declared source, not production evidence",
        "vintage_status": "original",
    }
    if kind == "expectation":
        result.update(
            event_id="test-event-01",
            expectation_kind="survey_consensus",
            population="test survey",
            expectation_cutoff_at=(CLOCK - timedelta(hours=3)).isoformat(),
        )
    elif kind == "event":
        result["event_id"] = "test-event-01"
    else:
        result.update(
            mechanism_id="reserve_demand",
            evidence_role="supporting",
            counter_evidence=[],
            alternative_explanations=[],
        )
    result.update(changes)
    return result


def save(root, reference, value, clock=CLOCK):
    return record(root, {"reference": reference, "evidence": json.dumps(value)}, clock)


def event_and_prior(root, kind="survey_consensus", value=3.0):
    save(root, "prior-record-01", evidence(expectation_kind=kind))
    released = CLOCK + timedelta(hours=1)
    event = evidence(
        "event",
        value=value,
        published_at=released.isoformat(),
        available_at=released.isoformat(),
        source_captured_at=(released + timedelta(minutes=1)).isoformat(),
    )
    save(root, "event-record-01", event, released + timedelta(minutes=2))
    return released + timedelta(minutes=3)


@pytest.mark.parametrize(
    "field",
    [
        "source_url",
        "source_excerpt",
        "fact_id",
        "unit",
        "population",
        "published_at",
        "available_at",
    ],
)
def test_required_fields_not_synthesized(field):
    value = evidence()
    value.pop(field)
    with pytest.raises(ValueError):
        validate(value, CLOCK)


@pytest.mark.parametrize(
    "published,value",
    [(None, None), (None, 0.0), ((CLOCK - timedelta(hours=2)).isoformat(), 0.0)],
)
def test_unknown_is_distinct_from_zero_and_not_a_forecast(published, value):
    item = validate(evidence(published_at=published, value=value), CLOCK)
    assert item["value"] is value or item["value"] == value
    assert item["published_at"] == published


def test_capture_is_ledger_time_not_client_claim_and_actual_publication_unknown_stays_null(
    root,
):
    save(root, "late-claimed-prior", evidence(published_at=None))
    item = visible_records(root, CLOCK)[0]
    assert (
        item["first_seen_at"] == CLOCK.isoformat()
        and item["available_at"] == CLOCK.isoformat()
    )
    assert item["published_at"] is None


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_availability_exact_minute_boundary(root, offset):
    bound = CLOCK + timedelta(minutes=2)
    save(root, "embargo-source-01", evidence(available_at=bound.isoformat()))
    assert bool(visible_records(root, bound + timedelta(minutes=offset))) == (
        offset >= 0
    )


def test_prior_known_before_event_permits_only_source_comparison(root):
    end = event_and_prior(root, value=3.25)
    report = compare(visible_records(root, end))
    assert report["events"][0]["surprise"] == 0.25
    assert report["events"][0]["causal_status"] == "not_identified"
    assert report["events"][0]["priced_in_status"] == "unknown"
    assert not report["predictive_rule_eligible"] and report["probability_up"] is None


@pytest.mark.parametrize(
    "kind", ["company_guidance", "analyst_view", "model_projection"]
)
def test_guidance_and_single_views_are_not_market_surprises(root, kind):
    end = event_and_prior(root, kind=kind, value=4.0)
    item = compare(visible_records(root, end))["events"][0]
    assert item["surprise"] is None and item["comparison_value"] == 1.0


def test_implied_expectation_without_registered_instrument_and_method_stays_unknown(
    root,
):
    end = event_and_prior(root, kind="market_implied", value=4.0)
    item = compare(visible_records(root, end))["events"][0]
    assert item["surprise"] is None and item["comparison_value"] is None
    assert "not_registered" in item["missing_evidence"][0]


def test_equal_expectation_supports_hypothesis_not_proof_of_pricing(root):
    end = event_and_prior(root)
    item = compare(visible_records(root, end))["events"][0]
    assert item["surprise"] == 0 and "not_proven_priced_in" in item["priced_in_status"]


@pytest.mark.parametrize(
    "field,change",
    [
        ("unit", "bps"),
        ("metric", "inflation"),
        ("horizon", "short"),
        ("observation_period", "2026-09"),
    ],
)
def test_targets_units_and_horizons_cannot_be_substituted(root, field, change):
    end = event_and_prior(root)
    # A separate event preserves the first record, but has a mismatched target.
    value = evidence(
        "event",
        **{field: change},
        published_at=(end - timedelta(minutes=2)).isoformat(),
        available_at=(end - timedelta(minutes=2)).isoformat(),
        source_captured_at=end.isoformat(),
    )
    save(root, "mismatched-event", value, end)
    item = compare(visible_records(root, end))["events"][-1]
    assert item["surprise"] is None


def test_after_event_backfill_and_revision_do_not_create_original_surprise(root):
    released = CLOCK - timedelta(minutes=1)
    value = evidence(
        "event", published_at=released.isoformat(), available_at=released.isoformat()
    )
    save(root, "original-event", value)
    save(root, "late-prior", evidence())
    assert compare(visible_records(root, CLOCK))["events"][0]["surprise"] is None
    original = (root / "data/events/original-event.json").read_bytes()
    save(
        root,
        "revised-event",
        dict(value, value=4.0, revision_of="original-event", vintage_status="revised"),
    )
    assert (root / "data/events/original-event.json").read_bytes() == original
    assert all(
        e["surprise"] is None for e in compare(visible_records(root, CLOCK))["events"]
    )


def test_conflicting_prior_sources_are_not_averaged(root):
    save(root, "other-prior", evidence(value=4.0))
    end = event_and_prior(root)
    item = compare(visible_records(root, end))["events"][0]
    assert item["status"] == "conflicting_prior_sources" and item["surprise"] is None


def test_expired_evidence_is_not_current(root):
    save(root, "expired-prior", evidence(expires_at=CLOCK.isoformat()))
    item = visible_records(root, CLOCK + timedelta(seconds=1))[0]
    assert item["status"] == "expired"
