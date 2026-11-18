# QuantItera 研究入口（通用 AI 助手协议）

本文件属于私有工作空间。不要把个人数据发到公开引擎仓库。

1. 先读取 `exports/manifest.json` 和 `exports/current_state.json`。讨论资产时必须读取该资产及相关 `all` 条目的 `review_feedback`；按需读其 `detail_path`。不得只看最新观点而忽略历史反驳。

   使用 `discuss` 命令时会先检查到期结果；`current_research` 对应资产，`global_research` 对应 `all` 通用经验；新资产也应读取 `global_research`。`forward_observations` 单列已有客观观察，不代表机制已验证。
2. 再读 `exports/mechanisms.json` 的对应资产：研究假说、期限、原始证据、事前预期、反证、竞争解释、证伪条件与下一观察。来源引用不等于本次已经独立下载核实；预期差不等于因果，价格走势不能代替事前预期。
3. 下一轮研究明确说明得到支持/反驳的部分、错误与证据缺口、仍适用机制及需继续检验的新假设。复杂经济判断由研究者或对话助手完成；程序只做有明确条件和成熟数据的对照。
4. 正式研究形成判断后，保存为 `inbox/<唯一编号>.json`。格式：`{"version":1,"operation":"save_decision","inputs":{...}}`。`inputs` 值用字符串，填写 `reference`/`asset`/`conclusion` 及 `record_kind=research`，并登记 `review_at` 和 `review_spec`；建议同时提供 `facts`、`invalidation` 和 `source_refs`。多资产用 `assets` JSON 数组字符串，新的判断用 `supersedes` 连接被替代判断。未结构化保存的聊天不会自动归档；`record_kind` 省略时保持 `unclassified`，不自动当作研究成绩。
5. `review_spec` 为 JSON 对象字符串，`kind` 为 `market`/`research`/`policy`，`checks` 声明同标的 `symbol`/`venue`/`currency`/`return_kind`、`history_key`、`claim`、`metric`、`start`/`end`、`operator`、`threshold`。支持 `close_return_pct`（百分比）/`close_level` 及 `gte`/`lte`。`market` 可完成客观验证；`research` 保留经济机制评价；`policy` 核对原约束/期限，不按价格涨跌打分。
6. `record_evidence` 保存经济证据，`event`/`expectation`/`mechanism_evidence` 分开，必须有原始来源、观察期间、发布时间、捕获/可获知时间、单位与版本。机制定义在 `config/research.json`；证据不直接转换成模型权重。
7. `review_queue` 中的 `due` 是新到期，`awaiting_evaluation` 已有证据但仍待评价。完成复杂评价仍用 `record_review`，`status` 为 `reviewed` 或 `awaiting_evaluation`，`facts`/`conclusion`/`source_refs` 必须齐全。`review_result` JSON 字符串包括 `supported`/`refuted`/`errors`/`evidence_gaps`/`mechanisms`/`next_hypotheses`/`competing_explanations` 字符串数组。无法确定时列明缺口并保留 `awaiting_evaluation`。
8. 核对 `outbox` 同编号 `status=succeeded`，再读 `current_state`/`review_queue` 确认反馈与任务状态。提交成功不等于处理完成。引擎不推断成交、不改变投资策略、不授予交易权限。
9. 使用私人模型时核对输入 `research_context` 和 `manifest.model_feedback_matches_workspace`。新可检验机制通过私人已有候选系统登记；启用 `factor_candidates` 能力后，可在 `save_decision` 或 `record_review` 中附同名 JSON 数组字符串。只有原系统登记回执和验证结果才代表进入候选流程，普通来源数量、价格涨跌或待检验假设不授予权重。
10. `refresh` 自动更新 `exports/research_performance` 和 `live_portfolio_performance` 的 JSON / Markdown；也可单独执行 `performance`。研究统计不把政策、工作流、未知分类或代理窗口当成判断命中率；实盘统计不把持仓盈亏、回测和模拟当成累计收益。可选资金流、费用、汇率和基准事实按 https://github.com/wysking/quantitera/blob/v0.5.0/docs/performance.md 放在 `inputs/live_performance.json`，不覆盖原账户快照。`config/performance.json` 选择分享范围，`exports/shareable` 仅是本工作空间内的可选摘要，不自动发布到公开仓库。

## Gemini（Google AI Pro）与 GitHub MCP 工具约定

- 请通过自定义远程 GitHub MCP 连接器（`https://api.githubcopilot.com/mcp/`）访问仓库；不要使用 Gemini 内置的静态 GitHub 代码导入功能（只读快照、不可写入且有文件数与体积上限）。
- 读取仓库文件使用 `get_file_contents`；归档请求使用 `create_or_update_file`，分支固定为工作空间默认分支（通常为 `main`），路径严格限定为新建 `inbox/<唯一编号>.json`，不得覆盖已有请求或直接修改 `data/`、`exports/`、`config/`。
