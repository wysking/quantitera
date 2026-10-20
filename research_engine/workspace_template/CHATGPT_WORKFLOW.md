# QuantItera 研究入口

本文件属于私有工作空间。不要把个人数据发到公开引擎仓库。

1. 先读取exports/manifest.json和exports/current_state.json。讨论资产时必须读取该资产及相关all条目的review_feedback；按需读其detail_path。不得只看最新观点而忽略历史反驳。

   使用discuss命令时会先检查到期结果；current_research对应资产，global_research对应all通用经验；新资产也应读取global_research。forward_observations单列已有客观观察，不代表机制已验证。
2. 再读exports/mechanisms.json的对应资产：研究假说、期限、原始证据、事前预期、反证、竞争解释、证伪条件与下一观察。来源引用不等于本次已经独立下载核实；预期差不等于因果，价格走势不能代替事前预期。
3. 下一轮研究明确说明得到支持/反驳的部分、错误与证据缺口、仍适用机制及需继续检验的新假设。复杂经济判断由ChatGPT研究；程序只做有明确条件和成熟数据的对照。
4. 正式研究形成判断后，保存为inbox/<唯一编号>.json。格式：{"version":1,"operation":"save_decision","inputs":{...}}。inputs值用字符串，填写reference/asset/conclusion及record_kind=research，并登记review_at和review_spec；建议同时提供facts、invalidation和source_refs。多资产用assets JSON数组字符串，新的判断用supersedes连接被替代判断。未结构化保存的聊天不会自动归档；record_kind省略时保持unclassified，不自动当作研究成绩。
5. review_spec为JSON对象字符串，kind为market/research/policy，checks声明同标的symbol/venue/currency/return_kind、history_key、claim、metric、start/end、operator、threshold。支持close_return_pct（百分比）/close_level及gte/lte。market可完成客观验证；research保留经济机制评价；policy核对原约束/期限，不按价格涨跌打分。
6. record_evidence保存经济证据，event/expectation/mechanism_evidence分开，必须有原始来源、观察期间、发布时间、捕获/可获知时间、单位与版本。机制定义在config/research.json；证据不直接转换成模型权重。
7. review_queue中的due是新到期，awaiting_evaluation已有证据但仍待评价。完成复杂评价仍用record_review，status为reviewed或awaiting_evaluation，facts/conclusion/source_refs必须齐全。review_result JSON字符串包括supported/refuted/errors/evidence_gaps/mechanisms/next_hypotheses/competing_explanations字符串数组。无法确定时列明缺口并保留awaiting_evaluation。
8. 核对outbox同编号status=succeeded，再读current_state/review_queue确认反馈与任务状态。提交成功不等于处理完成。引擎不推断成交、不改变投资策略、不授予交易权限。
9. 使用私人模型时核对输入research_context和manifest.model_feedback_matches_workspace。新可检验机制通过私人已有候选系统登记；启用factor_candidates能力后，可在save_decision或record_review中附同名JSON数组字符串。只有原系统登记回执和验证结果才代表进入候选流程，普通来源数量、价格涨跌或待检验假设不授予权重。
10. refresh 自动更新 exports/research_performance 和 live_portfolio_performance 的 JSON / Markdown；也可单独执行 performance。研究统计不把政策、工作流、未知分类或代理窗口当成判断命中率；实盘统计不把持仓盈亏、回测和模拟当成累计收益。可选资金流、费用、汇率和基准事实按 https://github.com/wysking/quantitera/blob/v0.5.0/docs/performance.md 放在 inputs/live_performance.json，不覆盖原账户快照。config/performance.json 选择分享范围，exports/shareable 仅是本工作空间内的可选摘要，不自动发布到公开仓库。
