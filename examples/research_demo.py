"""A runnable source tutorial, using the real CLI/inbox and entirely synthetic inputs."""
import argparse
from datetime import date
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from research_engine.market_data import _bar
from research_engine.workspace import read_json, write_json

CREATED = "2026-01-01T12:00:00+08:00"
RELEASED = "2026-01-02T12:00:00+08:00"
MATURE = "2026-01-06T12:00:00+08:00"
NEXT = "2026-01-06T12:05:00+08:00"


def cli(root, command, clock, *extra):
    result = subprocess.run([sys.executable, "-X", "utf8", "-m", "research_engine", command,
                             "--workspace", str(root), "--as-of", clock, *extra],
                            cwd=root if root.exists() else root.parent,
                            env={**os.environ, "PYTHONUTF8": "1"},
                            capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(result.stdout)


def request(root, identity, operation, **inputs):
    write_json(root / f"inbox/{identity}.json", {"version": 1, "operation": operation, "inputs": inputs})


def market(root, matured=False):
    histories = {}
    for asset, symbol, end in (("sample_growth", "QQQ", 98), ("sample_defensive", "SPY", 102)):
        identity = {"symbol": symbol, "venue": "US", "currency": "USD", "return_kind": "provider_adjusted_etf_price"}
        prices = [("2025-12-30", 99), ("2025-12-31", 100)]
        if matured:
            prices += [("2026-01-02", 100), ("2026-01-05", end)]
        histories[asset] = {**identity, "source_url": "https://example.org/synthetic-prices",
                            "bars": [_bar(date.fromisoformat(day), (value, value, value, value), value, identity)
                                     for day, value in prices]}
    write_json(root / "inputs/market.json", {"histories": histories})


def evidence(kind, identity, value, published, **extra):
    return {"schema_version": 1, "asset": "sample_growth", "kind": kind, "fact_id": identity,
            "metric": "financing_rate", "unit": "percentage_points", "value": value, "horizon": "medium",
            "observation_period": "2026-01", "published_at": published, "available_at": published,
            "source_captured_at": published, "source_url": "https://example.org/synthetic-economics",
            "source_excerpt": "SYNTHETIC invented example; not a real release, survey or downloaded source",
            "vintage_status": "original", **extra}


def run_demo(root):
    root = root.resolve()
    root.parent.mkdir(parents=True, exist_ok=True)
    cli(root, "init", CREATED)  # Refuses an existing nonempty workspace.
    blank = cli(root, "refresh", CREATED)
    assert blank["review_cycle"]["discovered"] == 0
    shutil.copyfile(Path(__file__).with_name("tutorial_models.py"), root / "tutorial_models.py")
    assets = {asset: {"label": label, "history_key": asset,
                      "model": {"version": "tutorial-v1", "lookback_bars": 2}}
              for asset, label in (("sample_growth", "合成成长资产"), ("sample_defensive", "合成防御资产"))}
    write_json(root / "config/tutorial_assets.json", assets)
    write_json(root / "config/research.json", {"schema_version": 1, "provider": "tutorial_models:provide",
        "mechanisms": {"sample_growth": {"financing_channel": {
            "hypothesis": "SYNTHETIC cheaper financing may support investment and cash flows",
            "horizon": "medium", "alternative_explanations": ["SYNTHETIC weaker final demand"],
            "invalidation": "SYNTHETIC investment does not respond despite lower funding costs",
            "next_observation": "SYNTHETIC comparable investment and cash-flow disclosures"}}}})
    write_json(root / "config/performance.json", {"example_only": True,
        "sharing": {"research": False, "live": False}})
    market(root)
    prior = evidence("expectation", "synthetic-prior", 3.0, "2026-01-01T10:00:00+08:00",
                     event_id="synthetic-release", expectation_kind="survey_consensus",
                     population="SYNTHETIC invented respondents", expectation_cutoff_at="2026-01-01T09:00:00+08:00")
    request(root, "001-prior", "record_evidence", reference="synthetic-prior", evidence=json.dumps(prior))
    for number, (asset, symbol) in enumerate((("sample_growth", "QQQ"), ("sample_defensive", "SPY")), 2):
        check = {"symbol": symbol, "venue": "US", "currency": "USD", "return_kind": "provider_adjusted_etf_price",
                 "history_key": asset, "claim": "SYNTHETIC window return >=1%", "metric": "close_return_pct",
                 "start": "2026-01-02", "end": "2026-01-05", "operator": "gte", "threshold": 1}
        request(root, f"00{number}-judgement", "save_decision", reference="synthetic-"+asset, asset=asset,
                record_kind="research", conclusion="SYNTHETIC >=1% future proxy-window claim",
                review_at="2026-01-06", review_spec=json.dumps({"kind": "market", "checks": [check]}))
    request(root, "004-channel", "save_decision", reference="synthetic-channel", asset="sample_growth",
            record_kind="research", conclusion="SYNTHETIC financing transmission remains a mechanism hypothesis",
            review_at="2026-01-06", review_spec=json.dumps({"kind": "research",
                "mechanisms": ["SYNTHETIC financing channel"],
                "evidence_gaps": ["SYNTHETIC independent investment mediator missing"],
                "competing_explanations": ["SYNTHETIC weaker final demand"]}))
    initial = cli(root, "refresh", CREATED)
    assert initial["review_cycle"]["written"] == 0
    original = (root / "data/events/synthetic-sample_growth.json").read_bytes()
    value = evidence("event", "synthetic-release-fact", 2.75, "2026-01-02T10:00:00+08:00",
                     event_id="synthetic-release")
    request(root, "005-release", "record_evidence", reference="synthetic-release-fact", evidence=json.dumps(value))
    for number, role in enumerate(("supporting", "counter"), 6):
        value = evidence("mechanism_evidence", "synthetic-"+role, -0.25 if role == "supporting" else -0.2,
                         "2026-01-02T10:00:00+08:00", mechanism_id="financing_channel", evidence_role=role,
                         metric="funding_cost_change" if role == "supporting" else "investment_order_growth",
                         unit="percentage_points" if role == "supporting" else "percent",
                         counter_evidence=["SYNTHETIC weaker orders despite lower cost"],
                         alternative_explanations=["SYNTHETIC demand rather than financing may dominate"])
        request(root, f"00{number}-evidence", "record_evidence", reference="synthetic-"+role, evidence=json.dumps(value))
    cli(root, "refresh", RELEASED)
    market(root, matured=True)
    cycle = cli(root, "refresh", MATURE)["review_cycle"]
    packet = cli(root, "discuss", MATURE, "--asset", "sample_growth")
    write_json(root / "exports/tutorial/next_research.json", packet)
    cards = packet["economic_research"]["economic_mechanisms"]
    prior_comparison = packet["economic_research"]["expectations"]["events"][0]
    request(root, "008-manual-review", "record_review", reference="synthetic-channel-review", review_id="synthetic-channel",
            facts="SYNTHETIC rate difference and conflicting channel observations checked",
            conclusion="SYNTHETIC evidence review complete; causal attribution remains unidentified",
            source_refs='["https://example.org/synthetic-economics"]', review_result=json.dumps({
                "supported": ["SYNTHETIC prior/event rate difference documented"],
                "errors": ["SYNTHETIC original channel lacked an independent investment mediator"],
                "evidence_gaps": ["SYNTHETIC causal identification still missing"],
                "mechanisms": ["SYNTHETIC financing remains a candidate channel"],
                "next_hypotheses": ["SYNTHETIC test demand-conditioned investment response"],
                "competing_explanations": ["SYNTHETIC final demand"]}))
    request(root, "009-next-judgement", "save_decision", reference="synthetic-iteration-2", asset="sample_growth",
            record_kind="research", conclusion="SYNTHETIC next investigation incorporates refuted price claim and channel gaps",
            related_ids='["synthetic-sample_growth","synthetic-channel"]', supersedes='["synthetic-sample_growth"]',
            source_refs='["exports/tutorial/next_research.json"]', review_at="2026-01-07",
            review_spec=json.dumps({"kind": "research", "evidence_gaps": ["SYNTHETIC next investment disclosure missing"]}))
    cli(root, "refresh", NEXT)
    portfolio = cli(root, "portfolio", NEXT)
    updated_packet = cli(root, "discuss", NEXT, "--asset", "sample_growth")
    write_json(root / "exports/tutorial/next_research.json", updated_packet)
    repeated = cli(root, "refresh", NEXT)["review_cycle"]
    research = read_json(root / "exports/research_performance.json")
    summary = {"example_only": True, "as_of": NEXT, "assets": sorted(assets), "maturity_cycle": cycle,
               "expectation_difference": prior_comparison["surprise"], "unit": "percentage_points",
               "mechanism_card": cards[0], "research_counts": research["counts"],
               "next_research_feedback": updated_packet["current_research"]["review_feedback"],
               "portfolio": {key: portfolio[key] for key in ("status", "assets_received", "model_statuses", "requires_recheck")},
               "model_versions": {asset: model["model_version"] for asset, model in portfolio["asset_models"].items()},
               "repeat_review_events_written": repeated["written"],
               "original_judgement_unchanged": original == (root / "data/events/synthetic-sample_growth.json").read_bytes(),
               "execution_allowed": False}
    write_json(root / "exports/tutorial/summary.json", summary)
    report = ["# QuantItera · 经济机制与研究闭环示例", "", "**全部为合成数据，不是真实研究、调查、行情或投资成绩。**", "",
              "运行期间：2026-01-01 至 2026-01-06（UTC+8）。", "",
              "## 研究了什么", "", "先记录融资利率的事前预期，再记录事件及支持/反证，检验融资成本是否通过投资与现金流传导。", "",
              f"原预期 3.00，事件 2.75；实际引擎比较差值为 {summary['expectation_difference']:.2f} 个百分点。来源为虚构示例，不是抓取的真实调查。", "",
              f"机制状态：{cards[0]['causal_status']}。支持证据与反证同时保留，需求变化是竞争解释。", "",
              "## 判断到下一轮研究", "", "| 已登记判断 | 成熟结果 |", "| --- | --- |"]
    labels = {"supported": "得到支持", "refuted": "被反驳"}
    for review in read_json(root / "exports/reviews.json")["items"]:
        if review.get("status", "reviewed") == "reviewed":
            report.append(f"| {review['decision_id']} | {labels.get(review.get('verdict'), '已复盘，未整体打分')} |")
    report += ["", f"全部资产汇总：判断 {research['counts']['judgements']} 项，明确支持 {research['counts']['supported']} 项、反驳 {research['counts']['refuted']} 项、已复盘但未整体打分 {research['counts']['unscored_completed']} 项。", "",
               "成长资产代理窗口为 -2%，防御资产为 +2%；只验证原阈值，不把价格结果反推为融资机制的因果证据。", "",
               "复杂机制先留待评价，再由示例人工请求保存支持部分、错误、竞争解释、仍缺证据及新假设。新判断引用前轮结果，并登记下一观察期限。", "",
               f"组合接口收到：{', '.join(portfolio['assets_received'])}。成长模型读取反驳后要求人工复核；模型参数和版本保持不变，没有自动调权。", "",
               f"重复刷新新增复盘：{repeated['written']}；原判断字节保持不变：{summary['original_judgement_unchanged']}。", "",
               "## 查看工作空间", "", "完整证据与机制在 exports/mechanisms.json；下一研究包在 exports/tutorial/next_research.json；判断、队列、回执与两份成绩报告均由同一引擎生成。", "",
               "本示例未提供真实账户资料，live_portfolio_performance 明确缺数据；可计算的合成账户示例另见 examples/performance_demo.py。分享默认关闭，真实成绩不自动公开。", ""]
    (root / "exports/tutorial/research_report.md").write_text("\n".join(report), encoding="utf-8", newline="\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True, help="New empty tutorial directory only")
    result = run_demo(parser.parse_args().workspace)
    print(json.dumps({"example_only": True, "report": "exports/tutorial/research_report.md",
                      "counts": result["research_counts"], "repeat_review_events_written": result["repeat_review_events_written"]},
                     ensure_ascii=False, indent=2))
