"""Bounded immutable source records; ledger capture prevents backdated expectations."""

from datetime import date, datetime, timezone
from math import isfinite
from urllib.parse import urlsplit
import json
import re

from research_engine import calendar
from research_engine.market_data import digest

VERSION = "economic-evidence-v1"
HORIZONS = {"short", "medium", "structural"}
KINDS = {"event", "expectation", "mechanism_evidence"}
EXPECTATION_KINDS = {
    "survey_consensus",
    "market_implied",
    "company_guidance",
    "analyst_view",
    "model_projection",
}
COMMON = {
    "schema_version",
    "asset",
    "kind",
    "fact_id",
    "metric",
    "unit",
    "value",
    "horizon",
    "observation_period",
    "published_at",
    "source_captured_at",
    "available_at",
    "expires_at",
    "source_url",
    "source_excerpt",
    "vintage_status",
    "revision_of",
}
EXTRAS = {
    "event": {"event_id"},
    "expectation": {
        "event_id",
        "expectation_kind",
        "population",
        "expectation_cutoff_at",
    },
    "mechanism_evidence": {
        "mechanism_id",
        "evidence_role",
        "counter_evidence",
        "alternative_explanations",
    },
}


def stamp(value):
    return calendar.aware(datetime.fromisoformat(value)).astimezone(timezone.utc)


def text(value, field, limit=2000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{field} must be nonempty text, at most {limit} characters")
    return value.strip()


def key(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_-]{2,79}", value
    ):
        raise ValueError("invalid evidence identifier")
    return value


def finite(value):
    if value is not None and (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
    ):
        raise ValueError("evidence value must be a finite number or null")
    return value


def validate(value, clock):
    calendar.aware(clock)
    if not isinstance(value, dict) or value.get("kind") not in KINDS:
        raise ValueError("unsupported economic evidence kind")
    kind = value["kind"]
    required = COMMON - {"expires_at", "revision_of"}
    if (
        set(value) - (COMMON | EXTRAS[kind])
        or required - set(value)
        or EXTRAS[kind] - set(value)
    ):
        raise ValueError("incomplete/unsupported shadow evidence fields")
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != 1
        or not isinstance(value["asset"], str) or not value["asset"].strip()
    ):
        raise ValueError("shadow evidence requires schema 1 and explicit asset identity")
    if value["horizon"] not in HORIZONS or value["vintage_status"] not in {
        "original",
        "revised",
        "unknown",
    }:
        raise ValueError("unsupported evidence horizon/vintage")
    output = dict(value, fact_id=key(value["fact_id"]), value=finite(value["value"]))
    for field in ("metric", "unit", "observation_period", "source_excerpt"):
        output[field] = text(
            value[field], field, 4000 if field == "source_excerpt" else 200
        )
    url = urlsplit(text(value["source_url"], "source_url"))
    if url.scheme != "https" or not url.hostname or url.username or url.password:
        raise ValueError("source must be an HTTPS reference without credentials")
    for field in ("published_at", "source_captured_at", "available_at", "expires_at"):
        output[field] = stamp(value[field]).isoformat() if value.get(field) else None
    if not output["source_captured_at"] or not output["available_at"]:
        raise ValueError("capture and conservative availability are required")
    if stamp(output["source_captured_at"]) > clock:
        raise ValueError("future source capture cannot be recorded")
    if output["published_at"] and (
        stamp(output["published_at"]) > clock
        or stamp(output["available_at"]) < stamp(output["published_at"])
    ):
        raise ValueError("publication/availability order is invalid")
    if output["expires_at"] and stamp(output["expires_at"]) < stamp(
        output["available_at"]
    ):
        raise ValueError("expiry precedes availability")
    period = output["observation_period"]
    try:
        observed = date.fromisoformat(
            period + "-01" if re.fullmatch(r"\d{4}-\d{2}", period) else period
        )
    except ValueError as exc:
        raise ValueError("observation_period requires YYYY-MM or YYYY-MM-DD") from exc
    if kind != "expectation" and observed > clock.date():
        raise ValueError("future observations are not facts")
    if kind in {"expectation", "event"}:
        output["event_id"] = key(value["event_id"])
    if kind == "expectation":
        if value["expectation_kind"] not in EXPECTATION_KINDS:
            raise ValueError("unsupported expectation kind")
        output["population"] = text(value["population"], "population", 300)
        output["expectation_cutoff_at"] = stamp(
            value["expectation_cutoff_at"]
        ).isoformat()
        if stamp(output["expectation_cutoff_at"]) > stamp(output["source_captured_at"]):
            raise ValueError("expectation cutoff cannot follow source capture")
        if output["published_at"] and stamp(output["expectation_cutoff_at"]) > stamp(
            output["published_at"]
        ):
            raise ValueError("expectation cutoff cannot follow its publication")
    if kind == "mechanism_evidence":
        if not isinstance(value["mechanism_id"], str) or not value["mechanism_id"].strip() or value["evidence_role"] not in {
            "supporting",
            "counter",
            "context",
        }:
            raise ValueError("unsupported mechanism or evidence role")
        for field in ("counter_evidence", "alternative_explanations"):
            if not isinstance(value[field], list) or len(value[field]) > 12:
                raise ValueError("counter/alternative evidence must be bounded lists")
            output[field] = [text(item, field, 600) for item in value[field]]
    output["revision_of"] = (
        key(value["revision_of"]) if value.get("revision_of") else None
    )
    if bool(output["revision_of"]) != (output["vintage_status"] == "revised"):
        raise ValueError(
            "revised evidence requires revision_of; originals cannot supersede silently"
        )
    output["evidence_contract_version"] = VERSION
    output["content_hash"] = digest(
        {k: v for k, v in output.items() if k != "content_hash"}
    )
    output["content_hash_kind"] = "provided_evidence_payload_not_downloaded_page"
    output["source_verification"] = (
        "provided_source_reference; content not fetched by this operation"
    )
    return output


def record(root, inputs, clock):
    from research_engine.workspace import append_event, events, identifier

    raw = inputs.get("evidence", "")
    if len(raw.encode()) > 24000:
        raise ValueError("shadow evidence exceeds 24KB")
    value = validate(json.loads(raw), clock)
    if value["revision_of"]:
        previous = next(
            (e for e in events(root) if e["id"] == value["revision_of"]), None
        )
        if (
            not previous
            or previous.get("type") != "economic_evidence"
            or stamp(previous["recorded_at"]) > clock
        ):
            raise ValueError("revision must reference an existing known shadow record")
        if any(
            previous["evidence"].get(k) != value.get(k)
            for k in ("kind", "asset", "event_id", "metric", "unit")
        ):
            raise ValueError("revision source identity mismatch")
    return append_event(
        root,
        {
            "id": identifier(inputs.get("reference", "")),
            "type": "economic_evidence",
            "schema_version": 1,
            "asset": value["asset"],
            "evidence": value,
            "execution_allowed": False,
        },
        clock,
    )


def visible_records(root, clock):
    from research_engine.workspace import events

    output = []
    for event in events(root):
        if (
            event.get("type") != "economic_evidence"
            or stamp(event["recorded_at"]) > clock
        ):
            continue
        # Recheck raw contracts and hashes without trusting an edited archive.
        value = event["evidence"]
        raw = {k: v for k, v in value.items() if k in COMMON | EXTRAS[value["kind"]]}
        checked = validate(raw, clock)
        if checked != value:
            raise ValueError("shadow evidence archive/hash changed")
        known = max(
            stamp(value["available_at"]),
            stamp(value["source_captured_at"]),
            stamp(event["recorded_at"]),
        )
        if known > clock:
            continue
        status = (
            "expired"
            if value["expires_at"] and stamp(value["expires_at"]) < clock
            else "available"
        )
        output.append(
            {
                **value,
                "record_id": event["id"],
                "first_seen_at": event["recorded_at"],
                "available_at": known.isoformat(),
                "status": status,
                "point_in_time_backtest_allowed": False,
            }
        )
    return sorted(output, key=lambda e: (e["available_at"], e["record_id"]))
