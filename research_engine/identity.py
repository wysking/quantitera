"""Additive identity views; a proxy never becomes a holding or a NAV.

The existing registries remain authoritative for their declared purposes.
Venue aliases describe the same market, not interchangeable instruments.
"""
from datetime import datetime, timezone
import re

from research_engine import calendar

VERSION = "data-identity-v1"
VENUES = {"SSE": "CN", "HKEX": "HK", "NASDAQ": "US"}
INSTRUMENTS = {
    "GLD": ("etf", "US", "USD"), "GC=F": ("continuous_future", "COMEX", "USD"),
    "QQQ": ("etf", "US", "USD"), "SPY": ("etf", "US", "USD"),
    "^NDX": ("index", "US", "USD"), "^GSPC": ("index", "US", "USD"),
    "NDX": ("index", "US", "USD"), "SPX": ("index", "US", "USD"),
    "HSIII": ("index", "HK", "HKD"), "HSTECH": ("index", "HK", "HKD"),
    "^HSI": ("index", "HK", "HKD"), "H30269": ("index", "CN", "CNY"),
}
PRICE_KINDS = {"etf": "etf_exchange_price", "index": "index_points",
               "continuous_future": "continuous_futures_price", "fund": "fund_nav"}


def instrument_spec(symbol):
    if symbol in INSTRUMENTS:
        return INSTRUMENTS[symbol]
    if isinstance(symbol, str) and re.fullmatch(r"\d{6}\.SS", symbol):
        return "etf", "CN", "CNY"
    if isinstance(symbol, str) and re.fullmatch(r"\d{6}", symbol):
        return "fund", "CN", "CNY"
    raise ValueError("unregistered instrument identity")


def require_identity(actual, expected=None):
    """Check the purpose-specific target as well as the instrument's market."""
    instrument, venue, currency = instrument_spec(actual.get("symbol"))
    if VENUES.get(actual.get("venue"), actual.get("venue")) != venue or actual.get("currency") != currency:
        raise ValueError("instrument venue/currency mismatch")
    kind = actual.get("return_kind")
    price_kind = "money_market_income" if kind == "money_market_income_index" else PRICE_KINDS[instrument]
    if actual.get("price_kind", price_kind) != price_kind:
        raise ValueError("instrument price kind mismatch")
    allowed = {"not_applicable_quote"}
    if instrument == "index":
        allowed.add("price_index")
    elif instrument == "etf":
        allowed.update({"provider_adjusted_etf_price", "unadjusted_proxy_price_return"})
    elif instrument == "continuous_future":
        allowed.add("continuous_futures_price_return")
    elif instrument == "fund":
        allowed.update({"fund_nav_dividend_reinvested", "money_market_income_index"})
    if kind not in allowed:
        raise ValueError("instrument return kind mismatch")
    if expected and any(actual.get(k) != expected.get(k) for k in ("symbol", "venue", "currency", "return_kind")):
        raise ValueError("purpose-specific research identity mismatch")
    return instrument, price_kind


def _stamp(value):
    if value is None:
        return None
    return calendar.aware(datetime.fromisoformat(value)).astimezone(timezone.utc).isoformat()


def data_identity(record, *, market_as_of=None, available_at=None, vintage_status=None):
    instrument, price_kind = require_identity(record)
    vintage = vintage_status or record.get("vintage_status") or "current_revised"
    return {"schema_version": 1, "identity_version": VERSION,
            "instrument": instrument, "symbol": record["symbol"],
            "venue": VENUES.get(record["venue"], record["venue"]), "currency": record["currency"],
            "price_kind": price_kind, "return_kind": record["return_kind"],
            "source": record.get("source"), "source_url": record.get("source_url"),
            "market_as_of": _stamp(market_as_of), "available_at": _stamp(available_at),
            "vintage_status": vintage, "point_in_time_backtest_allowed": False,
            "actual_account_return": None,
            "relationship_to_holding": "distinct source instrument; no fund NAV or account return substitution"}
