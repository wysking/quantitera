"""V6 price identity/window checks; no account, model or data provider adapters."""
from datetime import date, datetime, timedelta
import hashlib
import json
from math import isfinite
from research_engine import calendar
from research_engine.identity import data_identity, require_identity
INSTRUMENT_SUSPENSIONS = {}
def price_session(spec, day):
    return calendar.is_session(spec["venue"], day) and day.isoformat() not in INSTRUMENT_SUSPENSIONS.get(spec["symbol"], {})


def price_sessions(spec, start, end):
    return [day for day in calendar.sessions(spec["venue"], start, end) if price_session(spec, day)]


def latest_price_session(spec, clock):
    day = calendar.latest_completed(spec["venue"], clock)
    for _ in range(25):
        if price_session(spec, day) and calendar.available_at(spec["venue"], day) <= clock:
            return day
        day -= timedelta(days=1)
    raise ValueError("no completed registered instrument session")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def positive(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not isfinite(value) or value <= 0:
        raise ValueError("invalid non-positive/non-finite price")
    return float(value)


def _bar(day, values, adjusted, spec):
    op, high, low, close = map(positive, values)
    if not low <= min(op, close) <= max(op, close) <= high:
        raise ValueError("inconsistent OHLC")
    return {"date": day.isoformat(), "open": op, "high": high, "low": low, "close": close,
            "adjusted_close": positive(adjusted),
            "close_at": calendar.session_times(spec["venue"], day)[1].isoformat(),
            "available_at": calendar.available_at(spec["venue"], day).isoformat()}


def history_view(history, clock, min_observations=61):
    """Recheck persisted histories every time; only known-at-clock bars participate."""
    calendar.aware(clock)
    if not history:
        return {"status": "missing", "bars": [], "reason": "history missing", "gap_dates": []}
    try:
        require_identity(history)
        venue = history["venue"]
        expected = latest_price_session(history, clock).isoformat()
        bars, seen = [], set()
        previous = ""
        for bar in history.get("bars", []):
            day = date.fromisoformat(bar["date"])
            if bar["date"] in seen or bar["date"] <= previous:
                raise ValueError("duplicate/out-of-order history date")
            seen.add(bar["date"])
            previous = bar["date"]
            if not price_session(history, day):
                raise ValueError("history contains a closed session")
            actual = datetime.fromisoformat(bar["available_at"])
            close_at = datetime.fromisoformat(bar["close_at"])
            if (calendar.aware(actual) < calendar.available_at(venue, day) or
                    calendar.aware(close_at) != calendar.session_times(venue, day)[1] or actual < close_at):
                raise ValueError("history availability precedes completed session")
            if actual > clock:
                continue
            values = [bar[k] for k in ("open", "high", "low", "close")]
            _bar(day, values, bar["adjusted_close"], history)
            bars.append(bar)
        gaps = []
        if bars:
            days = {b["date"] for b in bars}
            gaps = [d.isoformat() for d in price_sessions(history, date.fromisoformat(bars[0]["date"]),
                      date.fromisoformat(bars[-1]["date"])) if d.isoformat() not in days]
        status = ("missing" if not bars else "stale" if bars[-1]["date"] < expected else
                  "insufficient" if len(bars) < min_observations else "partial" if gaps else "ok")
        identity = data_identity(history, market_as_of=bars[-1]["close_at"] if bars else None,
                                 available_at=bars[-1]["available_at"] if bars else None)
        return {"status": status, "bars": bars, "expected_completed_session": expected,
                "data_identity": identity,
                "market_as_of": bars[-1]["close_at"] if bars else None, "gap_dates": gaps,
                "observations": len(bars), "reason": history.get("error"),
                "registered_suspensions": INSTRUMENT_SUSPENSIONS.get(history["symbol"], {})}
    except (ValueError, KeyError, TypeError, OverflowError) as exc:
        return {"status": "unsupported_calendar" if "unsupported_calendar" in str(exc) else "malformed",
                "bars": [], "reason": str(exc), "gap_dates": []}


def load_bundle(root, clock):
    from research_engine.workspace import read_json
    from research_engine.integration import call
    bundle = read_json(root / "inputs/market.json", {"histories": {}})
    external = call(root, clock, "market_data")
    if external is not None:
        histories = {key: {**value, "input_path": value.get("input_path") or external.get("record_path")}
                     for key, value in external.get("histories", {}).items()}
        histories.update({key: {**value, "input_path": value.get("input_path") or "inputs/market.json"}
                          for key, value in bundle.get("histories", {}).items()})
        bundle = {**external, **bundle,
                  "histories": histories}
    generated = bundle.get("generated_at")
    if generated and calendar.aware(datetime.fromisoformat(generated)) > clock:
        raise ValueError("market input is newer than the research clock")
    return {**bundle, "record_path": bundle.get("record_path") or "inputs/market.json"}
