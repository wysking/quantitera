# QuantItera 研究入口

本文件属于私有工作空间。不要把个人数据发到公开引擎仓库。

1. 先读取exports/manifest.json和exports/current_state.json。讨论资产时必须读取该资产及相关all条目的review_feedback；按需读其detail_path。不得只看最新观点而忽略历史反驳。
2. 再读exports/mechanisms.json的对应资产：研究假说、期限、原始证据、事前预期、反证、竞争解释、证伪条件与下一观察。来源引用不等于本次已经独立下载核实；预期差不等于因果，价格走势不能代替事前预期。
3. 下一轮研究明确说明得到支持/反驳的部分、错误与证据缺口、仍适用机制及需继续检验的新假设。复杂经济判断由ChatGPT研究；程序只做有明确条件和成熟数据的对照。
4. 保存判断使用inbox/<唯一编号>.json。格式：{"version":1,"operation":"save_decision","inputs":{...}}。inputs值用字符串，reference/asset/conclusion为基本字段，建议同时提供facts、invalidation、review_at、review_spec；多资产用assets JSON数组字符串。新的判断用supersedes连接被替代判断。
5. review_spec为JSON对象字符串，kind为market/research/policy，checks声明同标的symbol/venue/currency/return_kind、history_key、claim、metric、start/end、operator、threshold。支持close_return_pct（百分比）/close_level及gte/lte。market可完成客观验证；research保留经济机制评价；policy核对原约束/期限，不按价格涨跌打分。
6. record_evidence保存经济证据，event/expectation/mechanism_evidence分开，必须有原始来源、观察期间、发布时间、捕获/可获知时间、单位与版本。机制定义在config/research.json；证据不直接转换成模型权重。
7. review_queue中的due是新到期，awaiting_evaluation已有证据但仍待评价。完成复杂评价仍用record_review，status为reviewed或awaiting_evaluation，facts/conclusion/source_refs必须齐全。review_result JSON字符串包括supported/refuted/errors/evidence_gaps/mechanisms/next_hypotheses/competing_explanations字符串数组。无法确定时列明缺口并保留awaiting_evaluation。
8. 核对outbox同编号status=succeeded，再读current_state/review_queue确认反馈与任务状态。提交成功不等于处理完成。引擎不推断成交、不改变投资策略、不授予交易权限。
