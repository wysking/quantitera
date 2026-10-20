"""Two factual scorecards, with an explicit allowlist for optional sharing."""
from collections import Counter, defaultdict
from datetime import datetime
from statistics import mean, median

from research_engine.live_performance import live_portfolio_performance
from research_engine.review_cycle import latest_reviews
from research_engine.reviews import is_review_due
from research_engine.workspace import context, read_json, write_json
from research_engine.market_data import digest


def _period(rows, field):
    dates = sorted(str(r[field])[:10] for r in rows if r.get(field))
    return {"start": dates[0] if dates else None, "end": dates[-1] if dates else None}


def _summary(decisions, reviews, clock):
    ids = {d["id"] for d in decisions}
    selected = [r for r in reviews if (r.get("decision_id") or r["review_id"]) in ids]
    completed = [r for r in selected if r.get("status", "reviewed") == "reviewed"]
    reviewed = {r.get("decision_id") or r["review_id"] for r in completed}
    historical_due = {d["id"] for d in decisions if any(is_review_due(day, clock) for day in d.get("review_deadlines", [d.get("review_at")]) if day)}
    active_due = {d["id"] for d in decisions if any(is_review_due(day, clock) for day in d.get("active_review_deadlines",
        [d.get("review_at")] if d.get("status", "active") in {"active", "unresolved"} else []) if day)}
    dated_due = historical_due & (active_due | reviewed)
    verdicts = Counter(r.get("verdict", "unscored") for r in completed)
    return {"judgements": len(decisions), "due_or_reviewed_judgements": len(dated_due | reviewed),
        "known_deadline_due_judgements": len(dated_due), "reviewed_judgements": len(reviewed),
        "historical_deadlines_passed_including_retired": len(historical_due),
        "unprocessed_due_judgements": len(dated_due - {r.get("decision_id") or r["review_id"] for r in selected}),
        "completed_review_tasks": len(completed), "awaiting_review_tasks": sum(r.get("status") == "awaiting_evaluation" for r in selected),
        "supported": verdicts["supported"], "refuted": verdicts["refuted"], "mixed": verdicts["mixed"],
        "unscored_completed": sum(count for verdict, count in verdicts.items() if verdict not in {"supported", "refuted", "mixed"}),
        "supported_parts_reviews": sum(bool(r.get("learning", {}).get("supported")) for r in completed),
        "refuted_parts_reviews": sum(bool(r.get("learning", {}).get("refuted")) for r in completed),
        "documented_errors_reviews": sum(bool(r.get("learning", {}).get("errors")) for r in completed),
        "evidence_insufficient_reviews": sum(r.get("status") == "awaiting_evaluation" and bool(r.get("learning", {}).get("evidence_gaps")) for r in selected),
        "without_review_deadline": sum(not d.get("review_at") for d in decisions)}


def research_performance(decisions, reviews, extra, clock):
    human, aliases, identities = [], {}, {}
    for decision in decisions:
        if decision.get("source_kind") == "v6_forward_observation":
            continue
        legacy, origin = decision.get("legacy_record"), decision.get("origin", {}).get("path")
        payload = legacy.get("decision", legacy) if isinstance(legacy, dict) else None
        identity = (origin, digest(payload), tuple(decision["assets"]), decision["record_kind"]) if origin and payload else (decision["id"],)
        if identity in identities:
            previous = identities[identity]
            aliases[decision["id"]] = previous["id"]
            if decision.get("review_at") and not previous.get("review_at"):
                previous["review_at"] = decision["review_at"]
            previous["review_deadlines"] = list(dict.fromkeys([*previous.get("review_deadlines", []), *([decision["review_at"]] if decision.get("review_at") else [])]))
            if decision.get("status", "active") in {"active", "unresolved"} and decision.get("review_at"):
                previous["active_review_deadlines"] = list(dict.fromkeys([*previous["active_review_deadlines"], decision["review_at"]]))
        else:
            item = dict(decision)
            item["review_deadlines"] = [item["review_at"]] if item.get("review_at") else []
            item["active_review_deadlines"] = list(item["review_deadlines"]) if item.get("status", "active") in {"active", "unresolved"} else []
            identities[identity] = item
            human.append(item)
    latest = [dict(review, decision_id=aliases.get(review.get("decision_id") or review["review_id"], review.get("decision_id") or review["review_id"]))
              for review in latest_reviews(reviews).values()]
    research = [d for d in human if d["record_kind"] == "research"]
    policies = [d for d in human if d["record_kind"] in {"constraint", "baseline_plan", "execution_plan"}]
    assets = sorted({a for d in research for a in d["assets"]})
    result = {"category": "research_not_live_returns", "period": _period(research, "decision_date"),
        "evidence_status": extra.get("data_status", "not_configured"),
        "asset_labels": extra.get("asset_labels", {}),
        "counts": {"knowledge_records": len(decisions), "human_records": len(human),
            "unclassified_records": sum(d["record_kind"] == "unclassified" for d in human),
            "workflow_and_account_records": sum(d["record_kind"] in {"workflow", "account_context"} for d in human),
            **_summary(research, latest, clock)},
        "by_asset": {a: _summary([d for d in research if a in d["assets"]], latest, clock) for a in assets},
        "policy_checks": _summary(policies, latest, clock), "forward_observations": [],
        "mechanisms": extra.get("mechanisms", []), "factors": extra.get("factors", []),
        "historical_backtests": extra.get("historical_backtests", []), "model_simulations": extra.get("model_simulations", []),
        "process_cohorts": [], "method_improvement": {"status": "not_established",
            "reason": "Comparable asset, horizon, benchmark, costs, independent samples and uncertainty are required; version chronology or price gains do not prove improvement."},
        "definitions": ["Only explicitly classified research records enter research-judgement counts; unclassified, policy and workflow records stay separate.",
            "Completed tasks are counted once by review_id; one judgement may have multiple windows. A completed review can remain unscored.",
            "Due-or-reviewed includes legacy completed reviews without a structured deadline. Supported/refuted counts require an explicit verdict, not prose inference.",
            "Per-asset counts can overlap for multi-asset judgements and must not be summed into a total.",
            "A legacy archive and its window view with the same original payload/source are one judgement; aliases remain traceable.",
            "Forward means/positive frequencies describe proxy price episodes, not forecast hit rates, causal evidence or actual account returns. Windows may overlap."]}
    result["representation_aliases"] = aliases
    result["judgement_results"] = [{"id": d["id"], "assets": d["assets"], "decision_date": d["decision_date"],
        "status": d.get("status"), "review_deadlines": d["review_deadlines"], "detail_path": f"exports/knowledge/{d['id']}.json",
        "reviews": [{"review_id": r["review_id"], "recorded_at": r["recorded_at"], "status": r.get("status", "reviewed"),
            "verdict": r.get("verdict", "unscored"), "conclusion": r.get("conclusion", ""), "learning": r.get("learning", {}),
            "source_refs": r.get("source_refs", []), "detail_path": r.get("origin", {}).get("path") or f"data/events/{r['id']}.json"}
            for r in latest if r["decision_id"] == d["id"]]} for d in research]
    by_id = {d["id"]: d for d in decisions}
    registrations = defaultdict(list)
    latest_by_task = latest_reviews(reviews)
    for decision in decisions:
        if decision.get("source_kind") == "v6_forward_observation":
            legacy = decision.get("legacy_record", {})
            key = (tuple(decision["assets"]), legacy.get("signal", {}).get("model_version", "unspecified"), legacy.get("horizon", "unspecified"))
            registrations[key].append(decision)
    windows = defaultdict(list)
    for review in latest:
        if review.get("review_kind") != "forward_observation" or review.get("status", "reviewed") != "reviewed":
            continue
        decision = by_id.get(review.get("decision_id") or review["review_id"], {})
        legacy = decision.get("legacy_record", {})
        signal = legacy.get("signal", {})
        import json
        try:
            outcome = json.loads(review.get("facts", "{}"))
            value = outcome.get("proxy_return")
            if outcome.get("status") != "matured" or not isinstance(value, (int, float)) or isinstance(value, bool):
                continue
            key = (tuple(decision.get("assets", [])), signal.get("model_version", "unspecified"), legacy.get("horizon", "unspecified"))
            windows[key].append({"value": value, "entry_date": outcome.get("entry_date"), "exit_date": outcome.get("exit_date"),
                "review_id": review["review_id"], "source_refs": review.get("source_refs", [])})
        except (ValueError, TypeError):
            continue
    for scope, version, horizon in sorted(set(windows) | set(registrations)):
        rows = windows[(scope, version, horizon)]
        registered = registrations[(scope, version, horizon)]
        values = [r["value"] for r in rows]
        result["forward_observations"].append({"assets": list(scope), "model_version": version, "horizon": horizon,
            "registered_windows": len(registered), "matured_windows": len(rows),
            "future_windows": sum(not latest_by_task.get(d["id"]) and not is_review_due(d["review_at"], clock) for d in registered),
            "awaiting_windows": sum(latest_by_task.get(d["id"], {}).get("status") == "awaiting_evaluation" for d in registered),
            "unprocessed_due_windows": sum(not latest_by_task.get(d["id"]) and is_review_due(d["review_at"], clock) for d in registered),
            "mean_proxy_return": mean(values) if values else None, "median_proxy_return": median(values) if values else None,
            "min_proxy_return": min(values) if values else None, "max_proxy_return": max(values) if values else None,
            "positive_proxy_fraction": sum(v > 0 for v in values)/len(values) if values else None,
            "period": {"start": min(r["entry_date"] for r in rows) if rows else None, "end": max(r["exit_date"] for r in rows) if rows else None},
            "independent_sample_count": None, "forecast_hit_rate": None, "windows": rows})
    for month in sorted({d["decision_date"][:7] for d in research}):
        cohort = [d for d in research if d["decision_date"].startswith(month)]
        result["process_cohorts"].append({"month": month, **_summary(cohort, latest, clock),
            "explicit_review_specs": sum(bool(d.get("review_spec")) for d in cohort),
            "dated_review_fraction": sum(bool(d.get("review_at")) for d in cohort)/len(cohort)})
    result["mechanism_progress"] = {"hypotheses": len(result["mechanisms"]),
        "causally_validated": sum(m.get("causal_status") == "identified" for m in result["mechanisms"]),
        "with_missing_evidence": sum(bool(m.get("missing_evidence")) for m in result["mechanisms"])}
    result["factor_progress"] = {"candidate_versions": len({(f["candidate_id"], f["version"]) for f in result["factors"]}),
        "asset_version_research_qualified": sum(f.get("research_factor_eligible") is True for f in result["factors"]),
        "production_included": sum(f.get("production_included") is True for f in result["factors"])}
    return result


def export(root, clock):
    from research_engine.integration import optional, export as export_workspace
    from research_engine.mechanisms import export as export_mechanisms
    views = context(root, clock)
    export_mechanisms(root, clock)
    export_workspace(root, clock)
    decisions = [read_json(root / item["detail_path"]) for item in views["index"]]
    reviews = read_json(root / "exports/reviews.json")["items"]
    inputs = optional(root, clock, "performance_inputs") or {}
    live = dict(inputs.get("live", {}))
    supplement = read_json(root / "inputs/live_performance.json", {})
    for field in ("valuations", "trades", "base_currency"):
        if field in supplement and live.get(field) and live[field] != supplement[field]:
            raise ValueError(f"supplement cannot replace canonical {field}; use the original account correction workflow")
    live.update(supplement)
    live["decision_assets"] = {d["id"]: d["assets"] for d in decisions}
    evidence = read_json(root / "exports/mechanisms.json", {}).get("assets", {})
    extra = {"mechanisms": [{"asset": asset, **card} for asset, value in evidence.items() for card in value.get("economic_mechanisms", [])],
             **inputs.get("research", {})}
    research = research_performance(decisions, reviews, extra, clock)
    actual = live_portfolio_performance(live, clock)
    settings = read_json(root / "config/performance.json", {})
    common = {"schema_version": 1, "generated_at": clock.isoformat(), "source": inputs.get("source"), "execution_allowed": False}
    if settings.get("example_only") is True:
        common["example_only"] = True
    research, actual = {**common, **research}, {**common, **actual}
    for name, report in (("research_performance", research), ("live_portfolio_performance", actual)):
        write_json(root / f"exports/{name}.json", report)
        _write_text(root / f"exports/{name}.md", render(name, report))
        shared = shareable(name, report, settings.get("sharing", {}))
        write_json(root / f"exports/shareable/{name}.json", shared)
        _write_text(root / f"exports/shareable/{name}.md", render(name, shared))
    manifest = read_json(root / "exports/manifest.json", {})
    manifest.setdefault("paths", {}).update({"research_performance": "exports/research_performance.json",
        "live_portfolio_performance": "exports/live_portfolio_performance.json", "shareable_performance": "exports/shareable/"})
    write_json(root / "exports/manifest.json", manifest)
    return {"research_performance": "exports/research_performance.json", "live_portfolio_performance": "exports/live_portfolio_performance.json",
            "shareable": "exports/shareable/", "publication": "not_published"}


def shareable(name, report, settings):
    selected = settings.get("research" if name == "research_performance" else "live") is True
    result = {"schema_version": 1, "report": name, "audience": "optional_shareable_summary", "selected_for_sharing": selected,
        "publication": "not_published", "generated_at": report["generated_at"],
        "period": dict(report["period"]) if selected else {"start": None, "end": None}}
    if not selected:
        result["status"] = "not_selected"
        return result
    if report.get("example_only"):
        result["example_only"] = True
    if name == "research_performance":
        fields = ("judgements", "due_or_reviewed_judgements", "reviewed_judgements", "completed_review_tasks", "awaiting_review_tasks",
                  "supported", "refuted", "mixed", "unscored_completed", "documented_errors_reviews", "evidence_insufficient_reviews", "unclassified_records")
        result["counts"] = {key: report["counts"][key] for key in fields}
        result["topics"] = list(settings.get("topics", []))
        result["frozen_proxy_windows"] = sum(row["matured_windows"] for row in report["forward_observations"])
        result["method_improvement"] = {"status": "not_established"}
        result["semantics"] = "Proxy observations, qualitative reviews and unscored records are not a forecast success rate or causal proof."
    else:
        fields = ("time_weighted_return", "annualized_return", "max_drawdown", "annualized_volatility", "sharpe_ratio")
        result["metrics"] = {key: {"value": report["metrics"][key]["value"], "status": report["metrics"][key]["status"],
            "reason": report["metrics"][key].get("reason") if report["metrics"][key].get("reason") in REASONS else
                      "missing_inputs" if report["metrics"][key]["value"] is None else None,
            **{field: report["metrics"][key][field] for field in ("observations", "periods_per_year") if field in report["metrics"][key]}}
            for key in fields}
        result["coverage"] = {"valuation_observations": len(report["asset_value_history"])}
        result["semantics"] = "Declared account-period returns; missing metrics remain unavailable. No balances, holdings, trade amounts or source paths are shared."
    return result


REASONS = {
    "complete_account_values_and_external_flows_required": "缺完整账户估值、出入金及费用资料",
    "documented_invested_principal_since_inception_required": "缺自投资开始的本金记录",
    "complete_external_flow_coverage_required": "缺该期间完整入金、出金和分红流记录",
    "complete_net_cost_coverage_required": "缺完整费用口径",
    "at_least_one_year_required_for_annualized_return": "观察不足一年，暂不年化",
    "complete_declared_daily_valuation_calendar_required": "缺连续、口径一致的日度净值序列及日历",
    "matching_currency_period_risk_free_series_required": "缺同币种、同期间无风险利率",
    "positive_return_variance_and_valid_risk_free_rate_required": "收益方差为零或无风险利率无效",
    "dated_base_currency_fx_required": "缺有日期和来源的基准币种汇率",
    "valuation_at_each_flow_and_explicit_end_of_day_timing_required": "缺资金流时点的估值或明确日终约定",
    "closing_account_valuation_timing_required": "快照没有明确日终估值时点",
    "valid_time_weighted_return_and_one_year_required": "缺可靠时间加权收益，且须有至少一年记录",
    "complete_flow_adjusted_daily_valuations_required": "缺完整资金流调整后的日度真实净值",
    "complete_daily_net_returns_and_risk_free_required": "缺日度真实净收益与同币种、同期间无风险利率",
}


def _pct(value):
    return "—" if value is None else f"{value*100:.2f}%"


def _cell(value):
    return str(value).replace("|", "/").replace("\n", " ")


def _write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def render(name, report):
    research = name == "research_performance"
    title = "研究成绩" if research else "真实投资成绩"
    if report.get("audience") and not report["selected_for_sharing"]:
        return f"# QuantItera · {title}\n\n尚未选择分享本报告；完整报告保留在私人工作空间。没有发布到任何公开仓库。\n"
    period = report["period"]
    lines = [f"# QuantItera · {title}", "", f"统计期间：{period['start'] or '尚无记录'} 至 {period['end'] or '尚无记录'}。生成时间：{report['generated_at']}。", ""]
    if report.get("example_only"):
        lines += ["**合成示例，不是真实成绩。**", ""]
    if report.get("audience"):
        lines += ["这是由个人工作空间生成的可选分享摘要，尚未发布。", ""]
        if not report["selected_for_sharing"]:
            return "\n".join(lines+["尚未选择分享本报告；完整报告保留在私人工作空间。", ""])
    if research:
        c = report["counts"]
        asset_label = lambda key: _cell(report.get("asset_labels", {}).get(key, key))
        lines += ["本报告统计已明确分类的研究判断；政策、工作流、未分类记录和模型代理观察分别处理。完成复盘不等于判断得到支持。", "",
            "| 项目 | 数量 |", "| --- | ---: |"]
        for key, label in (("judgements", "历史研究判断"), ("due_or_reviewed_judgements", "已到期或已有复盘的判断"),
            ("reviewed_judgements", "至少完成一次复盘的判断"), ("completed_review_tasks", "已完成复盘窗口"),
            ("supported", "明确得到支持"), ("refuted", "明确被反驳"), ("mixed", "部分支持、部分反驳"),
            ("awaiting_review_tasks", "尚待评价"), ("unscored_completed", "已复盘但未做整体打分"),
            ("evidence_insufficient_reviews", "其中证据不足、暂无法验证"),
            ("unclassified_records", "尚待分类的历史记录")):
            lines.append(f"| {label} | {c[key]} |")
        if report.get("topics"):
            lines += ["", "研究主题："+"、".join(map(_cell, report["topics"]))+"。"]
        if "by_asset" in report:
            policy = report["policy_checks"]
            lines += ["", f"另有政策/约束记录 {policy['judgements']} 项，已完成检查 {policy['completed_review_tasks']} 次，待评价 {policy['awaiting_review_tasks']} 项；未混入市场预测统计。"]
            lines += ["", "## 各资产研究判断", "", "| 资产 | 判断 | 到期或已复盘 | 已复盘 | 支持 | 反驳 | 待评价 | 未打分 |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
            for asset, row in report["by_asset"].items():
                lines.append("| "+asset_label(asset)+" | "+" | ".join(str(row[k]) for k in ("judgements", "due_or_reviewed_judgements", "reviewed_judgements", "supported", "refuted", "awaiting_review_tasks", "unscored_completed"))+" |")
            lines += ["", "多资产判断会在各资产出现，各行不能相加当作总判断数。政策检查单列，不按价格涨跌评分。", "", "## 模型版本与前向观察", "",
                "| 资产 | 版本 | 期限 | 登记 / 成熟 / 未来 / 待评价 | 平均代理收益 | 正收益窗口占比 | 成熟观察期间 |", "| --- | --- | --- | ---: | ---: | ---: | --- |"]
            for row in report["forward_observations"]:
                lines.append(f"| {','.join(asset_label(asset) for asset in row['assets'])} | {_cell(row['model_version'])} | {_cell(row['horizon'])} | {row['registered_windows']} / {row['matured_windows']} / {row['future_windows']} / {row['awaiting_windows']} | {_pct(row['mean_proxy_return'])} | {_pct(row['positive_proxy_fraction'])} | {row['period']['start'] or '尚未成熟'}—{row['period']['end'] or '尚未成熟'} |")
            lines += ["", "这些是原冻结窗口的代理观察，窗口可能重叠；正收益占比不是判断命中率，不是实盘收益，也不证明经济原因。不同版本的样本与期间不可直接比高低。", "",
                "## 机制与因子进展", "", f"机制假设 {report['mechanism_progress']['hypotheses']} 项，明确标记因果已识别 {report['mechanism_progress']['causally_validated']} 项；候选因子版本 {report['factor_progress']['candidate_versions']} 个，资产/版本研究资格通过 {report['factor_progress']['asset_version_research_qualified']} 项。研究资格不等于生产模型集成。", "",
                "| 候选因子 | 版本 | 资产 | 阶段 | 研究通过期限 |", "| --- | --- | --- | --- | --- |"]
            for row in report["factors"]:
                lines.append(f"| {_cell(row['candidate_id'])} | {_cell(row['version'])} | {asset_label(row['asset'])} | {_cell(row['status'])} | {_cell(','.join(row.get('eligible_horizons', [])) or '无')} |")
            lines += ["", "## 研究迭代", "", "| 判断月份 | 判断数 | 有明确验证规格 | 有复盘日期占比 | 至少完成复盘 |", "| --- | ---: | ---: | ---: | ---: |"]
            for row in report["process_cohorts"]:
                lines.append(f"| {row['month']} | {row['judgements']} | {row['explicit_review_specs']} | {_pct(row['dated_review_fraction'])} | {row['reviewed_judgements']} |")
            lines += ["", "按判断月份分组，复盘状态截至本报告生成时；这不是当月时点已知的历史成绩。"]
            lines += ["", f"历史回测档案 {len(report['historical_backtests'])} 类、模型模拟档案 {len(report['model_simulations'])} 类分别保留在完整 JSON 中，没有计入实盘成绩。"]
            rows = sorted((r for d in report["judgement_results"] for r in d["reviews"]), key=lambda r: r["recorded_at"], reverse=True)[:10]
            lines += ["", "## 最近复盘摘要", "", "原文与详细支持、反证及缺口保留在完整 JSON 和原知识档案中；旧文字复盘没有强行转换成命中分数。", ""]
            for row in rows:
                lines.append(f"- {row['recorded_at'][:10]} · {_cell(row['review_id'])} · {_cell(row['status'])}/{_cell(row['verdict'])}：{_cell(row['conclusion'][:220])}")
        else:
            lines += ["", f"已复用冻结代理窗口：{report['frozen_proxy_windows']} 个；不视为相互独立的预测样本。"]
        lines += ["", "目前尚不能证明研究方法的预测能力随迭代改善。这里可以观察记录完整度和复盘进展；严谨改善结论仍缺可比资产、期限、基准、独立样本与不确定性评审。", ""]
    else:
        lines += ["本报告只使用实际账户记录。持仓盈亏、历史回测、模型模拟和市场代理收益均不代替累计真实投资收益。", "",
            "| 指标 | 结果 | 口径或缺失资料 |", "| --- | ---: | --- |"]
        labels = {"investment_principal": "期初已记录投入本金", "net_external_flows": "统计期间净外部资金流",
            "cumulative_profit": "统计期间累计投资收益额", "time_weighted_return": "组合时间加权收益率", "annualized_return": "年化收益率",
            "max_drawdown": "最大回撤（日终）", "annualized_volatility": "收益波动（年化估计）", "sharpe_ratio": "夏普比率"}
        for key, item in report["metrics"].items():
            value = item["value"]
            shown = "缺数据" if value is None else (_pct(value) if key in {"time_weighted_return", "annualized_return", "max_drawdown", "annualized_volatility"} else f"{value:.2f}")
            reason = REASONS.get(item.get("reason"), "来源资料不足或口径不一致") if value is None else item.get("meaning", "按所列账户、期间与费用口径计算")
            if value is not None and key in {"annualized_volatility", "sharpe_ratio"}:
                reason = f"样本 {item['observations']} 个日收益；年化频次 {item['periods_per_year']}；短样本不证明长期能力"
            lines.append(f"| {labels[key]} | {shown} | {_cell(reason)} |")
        if "asset_value_history" in report:
            lines += ["", "## 已登记账户资产历史", "", "| 快照日期 | 资产市值（基准币种） |", "| --- | ---: |"]
            for row in report["asset_value_history"]:
                lines.append(f"| {row['date']} | {row['base_value']:.2f} {report['base_currency']} |")
            lines += ["", "市值变化含资金进出和持仓范围变化，不能直接称为收益曲线。缺失日期不插值。", "", "## 各资产实际记录", "",
                "| 资产/敞口 | 期末市值 | 已知持仓盈亏 | 缺失盈亏条数 | 期间总收益 |", "| --- | ---: | ---: | ---: | --- |"]
            for row in report["asset_performance"]:
                pnl = row.get("known_holding_pnl")
                missing = row.get("missing_holding_pnl_count", 0)
                pnl_text = "缺数据" if pnl is None else f"{pnl:.2f}"+("（部分已知）" if missing else "")
                period_return = row.get("period_return")
                performance = "缺完整资产级资金流/分红/费用" if period_return is None else _pct(period_return)
                lines.append(f"| {_cell(row.get('label', row['asset']))} | {row['market_value']:.2f} | {pnl_text} | {missing} | {performance} |")
            lines += ["", f"有明确研究对应关系的交易 {len(report['trade_research_links'])} 条；尚无明确关联 {len(report['unlinked_trade_ids'])} 条。仅同资产、同日期或金额相似不会自动建立关联。", "",
                "## 市场基准", "", "基准比较需要同币种、同期间及可比总回报口径；主动收益差不是风险调整后的 alpha。"]
            for row in report["benchmark_comparisons"]:
                lines.append(f"- {_cell(row['name'])}：{_pct(row['return'])}；与实盘差额 {_pct(row['active_return'])}；{_cell(row.get('reason', row['status']))}。")
            if not report["benchmark_comparisons"]:
                lines.append("- 暂无可比较的完整实盘收益与对应总回报基准。")
            if report["data_gaps"]:
                lines += ["", "## 缺失资料", ""]
                for row in report["data_gaps"]:
                    lines.append("- "+REASONS.get(row["reason"], _cell(row["reason"]))+"。")
        lines += ["", "不足一年的收益不年化；风险统计只对完整日度、资金流调整后的净值计算。费用与汇率缺失不补零，基金 NAV 与不同份额、市场代理分别保留。", ""]
    return "\n".join(lines)
