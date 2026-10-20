"""Actual-account arithmetic. Model prices and trades never revalue an account."""
from datetime import date
from math import isfinite, sqrt
from statistics import mean, stdev
from zoneinfo import ZoneInfo

from research_engine import calendar


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError("finite_amount_required")
    return float(value)


def money(record, base):
    value = number(record["value"])
    if record.get("currency") == base:
        return value
    fx = record.get("fx") or {}
    if (fx.get("base_currency") != base or not fx.get("source_refs")
            or date.fromisoformat(fx["date"]) != date.fromisoformat(record["date"])):
        raise ValueError("dated_base_currency_fx_required")
    rate = number(fx["rate"])
    if rate <= 0:
        raise ValueError("positive_fx_rate_required")
    return value * rate


def _missing(code):
    return {"value": None, "status": "missing_data", "reason": code}


def _value(value, **metadata):
    return {"value": value, "status": "available", **metadata}


METRICS = ("investment_principal", "net_external_flows", "cumulative_profit", "time_weighted_return",
           "annualized_return", "max_drawdown", "annualized_volatility", "sharpe_ratio")


def live_portfolio_performance(data, clock):
    base = data.get("base_currency")
    metrics = {key: _missing("complete_account_values_and_external_flows_required") for key in METRICS}
    metrics["investment_principal"] = _missing("documented_invested_principal_since_inception_required")
    metrics["annualized_return"] = _missing("valid_time_weighted_return_and_one_year_required")
    for key in ("max_drawdown", "annualized_volatility"):
        metrics[key] = _missing("complete_flow_adjusted_daily_valuations_required")
    metrics["sharpe_ratio"] = _missing("complete_daily_net_returns_and_risk_free_required")
    result = {"category": "actual_account", "base_currency": base, "metrics": metrics,
        "period": {"start": None, "end": None}, "asset_value_history": [], "flow_totals": None,
        "return_curve": [], "benchmark_comparisons": [], "asset_performance": data.get("asset_performance", []),
        "trade_research_links": [], "unlinked_trade_ids": [], "unresolved_trade_links": [], "data_gaps": [],
        "coverage": data.get("coverage", {}), "cash_flow_records": data.get("cash_flows", []), "fee_records": data.get("fees", []),
        "snapshot_revisions": data.get("snapshot_revisions", []),
        "semantics": ["Account snapshots include only the declared account boundary, not unreported wealth or liabilities.",
            "Holding P&L is not cumulative investment profit. Buys/sells/internal transfers are not external capital flows.",
            "Return intervals run after the first closing valuation through the last close; opening-day flows are embedded in opening value.",
            "Account values must include cash, fund NAV distributions and in-account costs. Do not subtract embedded fees twice.",
            "Returns, backtests, simulations and proxy observations are separate. This is not a GIPS compliance claim."]}
    cutoff = clock.astimezone(ZoneInfo(data.get("valuation_timezone", "Asia/Shanghai"))).date().isoformat()
    raw = []
    for row in data.get("valuations", []):
        try:
            day = date.fromisoformat(row["date"])
            if day.isoformat() <= cutoff:
                if row.get("timing") == "end_of_day":
                    venue = data.get("valuation_calendar")
                    if venue in {"US", "HK", "CN"}:
                        if not calendar.is_session(venue, day) or calendar.available_at(venue, day) > clock:
                            continue
                    elif day.isoformat() == cutoff:
                        continue
                raw.append(row)
        except (ValueError, KeyError, TypeError):
            result["data_gaps"].append({"reason": "valid_valuation_date_required"})
    raw.sort(key=lambda v: v["date"])
    gaps = result["data_gaps"]
    converted = []
    for row in raw:
        try:
            if not base or not row.get("source_refs"):
                raise ValueError("valuation_currency_and_source_required")
            value = money(row, base)
            if value < 0:
                raise ValueError("nonnegative_net_account_value_required")
            converted.append({**row, "base_value": value})
        except (ValueError, KeyError, TypeError) as exc:
            gaps.append({"date": row.get("date"), "reason": str(exc)})
    result["asset_value_history"] = converted
    result["benchmark_comparisons"] = [{"name": b.get("name"), "return_kind": b.get("return_kind"), "status": "missing_data",
        "return": None, "active_return": None, "reason": "verified_live_return_and_comparable_benchmark_required"} for b in data.get("benchmarks", [])]
    _trade_links(result, data)
    if not raw:
        gaps.append({"reason": "actual_account_valuations_missing"})
        return result
    result["period"] = {"start": raw[0]["date"], "end": raw[-1]["date"]}
    if len({r["date"] for r in raw}) != len(raw):
        gaps.append({"reason": "duplicate_valuation_date_requires_explicit_revision"})
    if len(converted) != len(raw) or gaps:
        return result
    if len(raw) < 2:
        gaps.append({"reason": "two_distinct_account_valuations_required"})
        return result
    start, end = raw[0]["date"], raw[-1]["date"]
    coverage = data.get("coverage", {})
    if not (coverage.get("start", "9999") <= start and coverage.get("end", "") >= end
            and coverage.get("external_flows_complete") is True and coverage.get("source_refs")):
        gaps.append({"reason": "complete_external_flow_coverage_required"})
        return result
    if not all(row.get("complete_account") is True for row in raw):
        gaps.append({"reason": "complete_account_including_cash_and_fund_distributions_required"})
        return result
    flows, fees = [], []
    deposits = withdrawals = distributions = 0.0
    try:
        for row in data.get("cash_flows", []):
            if not start < row["date"] <= end:
                continue
            if row.get("kind") == "internal_transfer":
                continue
            if row.get("kind") not in {"deposit", "withdrawal", "distribution"} or not row.get("source_refs"):
                raise ValueError("documented_external_flow_kind_required")
            amount = money(row, base)
            if amount < 0:
                raise ValueError("external_flow_amount_must_be_unsigned")
            if row["kind"] == "deposit":
                deposits += amount
            elif row["kind"] == "withdrawal":
                withdrawals += amount
            else:
                distributions += amount
            flows.append({**row, "signed_value": amount if row["kind"] == "deposit" else -amount})
        for row in data.get("fees", []):
            if not start < row["date"] <= end:
                continue
            if type(row.get("included_in_valuation")) is not bool or not row.get("source_refs"):
                raise ValueError("fee_inclusion_and_source_required")
            amount = money(row, base)
            if amount < 0:
                raise ValueError("nonnegative_fee_required")
            if row["included_in_valuation"] is False:
                fees.append({**row, "base_value": amount})
    except (ValueError, KeyError, TypeError) as exc:
        gaps.append({"reason": str(exc)})
        return result
    net = deposits - withdrawals - distributions
    result["flow_totals"] = {"deposits": deposits, "withdrawals": withdrawals,
        "external_distributions": distributions, "net_external_flows": net,
        "outside_account_fees": sum(f["base_value"] for f in fees), "currency": base}
    metrics["net_external_flows"] = _value(net, currency=base)
    if coverage.get("costs_complete") is not True:
        gaps.append({"reason": "complete_net_cost_coverage_required"})
        return result
    metrics["cumulative_profit"] = _value(converted[-1]["base_value"] - converted[0]["base_value"] - net
        - sum(f["base_value"] for f in fees), currency=base, basis="observed_period_not_since_inception")
    if data.get("opening_invested_principal") is not None and coverage.get("since_inception") is True:
        try:
            metrics["investment_principal"] = _value(number(data["opening_invested_principal"]), currency=base,
                meaning="documented_opening_contributed_capital; not opening_market_value")
        except ValueError:
            pass
    metrics["investment_principal"] = metrics["investment_principal"] if metrics["investment_principal"]["value"] is not None else _missing("documented_invested_principal_since_inception_required")
    dates = {row["date"] for row in raw}
    if any(r["date"] not in dates or r.get("timing") != "end_of_day" for r in flows+fees):
        gaps.append({"reason": "valuation_at_each_flow_and_explicit_end_of_day_timing_required"})
        return result
    if any(row.get("timing") != "end_of_day" for row in raw):
        gaps.append({"reason": "closing_account_valuation_timing_required"})
        return result
    if converted[0]["base_value"] <= 0:
        gaps.append({"reason": "positive_starting_capital_required"})
        return result
    wealth, returns = 1.0, []
    curve = [{"date": start, "wealth_index": 1.0}]
    for previous, row in zip(converted, converted[1:]):
        if previous["base_value"] <= 0:
            gaps.append({"reason": "positive_subperiod_starting_capital_required"})
            return result
        flow = sum(r["signed_value"] for r in flows if r["date"] == row["date"])
        fee = sum(r["base_value"] for r in fees if r["date"] == row["date"])
        factor = (row["base_value"] - flow - fee) / previous["base_value"]
        if factor < 0:
            gaps.append({"reason": "negative_subperiod_wealth_requires_separate_leverage_accounting"})
            return result
        returns.append(factor-1)
        wealth *= factor
        curve.append({"date": row["date"], "wealth_index": wealth})
    result["return_curve"] = curve
    metrics["time_weighted_return"] = _value(wealth-1, method="geometrically_linked_end_of_day_external_flow_adjusted")
    days = (date.fromisoformat(end)-date.fromisoformat(start)).days
    metrics["annualized_return"] = (_value(wealth**(365/days)-1, day_basis=365) if days >= 365
                                     else _missing("at_least_one_year_required_for_annualized_return"))
    calendar_name = data.get("valuation_calendar")
    try:
        if calendar_name == "calendar_day":
            complete = len(raw) == days+1
            periods = 365
        elif calendar_name in {"US", "HK", "CN"}:
            expected = [d.isoformat() for d in calendar.sessions(calendar_name, date.fromisoformat(start), date.fromisoformat(end))]
            complete = expected == [r["date"] for r in raw]
            periods = 252
        else:
            complete, periods = False, None
    except ValueError:
        complete, periods = False, None
    risk_reason = "complete_declared_daily_valuation_calendar_required"
    for key in ("max_drawdown", "annualized_volatility", "sharpe_ratio"):
        metrics[key] = _missing(risk_reason)
    if complete:
        peak, drawdown = 1.0, 0.0
        for point in curve:
            peak = max(peak, point["wealth_index"])
            drawdown = min(drawdown, point["wealth_index"]/peak-1)
        metrics["max_drawdown"] = _value(drawdown, frequency="declared_daily_closes", observations=len(curve))
        if len(returns) > 1:
            volatility = stdev(returns)
            metrics["annualized_volatility"] = _value(volatility*sqrt(periods), periods_per_year=periods, observations=len(returns))
            rf = data.get("risk_free", {})
            if (rf.get("currency") == base and rf.get("start", "9999") <= start and rf.get("end", "") >= end
                    and rf.get("source_refs") and rf.get("annual_rate") is not None):
                try:
                    rate = number(rf["annual_rate"])
                except ValueError:
                    rate = -1
                if rate > -1 and volatility > 0:
                    excess = [r-((1+rate)**(1/periods)-1) for r in returns]
                    metrics["sharpe_ratio"] = _value(mean(excess)/volatility*sqrt(periods), observations=len(returns), periods_per_year=periods, risk_free=rf)
                else:
                    metrics["sharpe_ratio"] = _missing("positive_return_variance_and_valid_risk_free_rate_required")
            else:
                metrics["sharpe_ratio"] = _missing("matching_currency_period_risk_free_series_required")
    result["benchmark_comparisons"] = []
    for benchmark in data.get("benchmarks", []):
        comparison = {"name": benchmark.get("name"), "return_kind": benchmark.get("return_kind"),
            "source_refs": benchmark.get("source_refs", []), "return": None, "active_return": None}
        try:
            if benchmark.get("return_kind") != "total_return" or not benchmark.get("source_refs"):
                raise ValueError("matching_total_return_benchmark_required")
            points = {p["date"]: p for p in benchmark.get("values", [])}
            first, last = money(points[start], base), money(points[end], base)
            if first <= 0 or last < 0:
                raise ValueError("valid_benchmark_endpoints_required")
            comparison.update(status="available", **{"return": last/first-1, "active_return": wealth-1-(last/first-1)})
        except (ValueError, KeyError, TypeError) as exc:
            comparison.update(status="missing_data", reason=str(exc))
        result["benchmark_comparisons"].append(comparison)
    return result


def _trade_links(result, data):
    trades = {t["id"]: t for t in data.get("trades", [])
              if not t.get("voided") and t.get("status") not in {"void", "voided", "cancelled"}}
    decisions = data.get("decision_assets", {})
    linked = set()
    for link in data.get("trade_links", []):
        trade = trades.get(link.get("trade_id"))
        assets = decisions.get(link.get("decision_id"), [])
        if trade and assets and link.get("source_refs") and ("all" in assets or trade.get("asset") in assets):
            result["trade_research_links"].append({**link, "trade_status": trade.get("status", trade.get("type")),
                "meaning": "explicit_recorded_link_not_causal_attribution_or_verified_fill"})
            linked.add(trade["id"])
        else:
            result["unresolved_trade_links"].append({**link, "reason": "explicit_matching_trade_decision_and_sources_required"})
    result["unlinked_trade_ids"] = sorted(set(trades)-linked)
