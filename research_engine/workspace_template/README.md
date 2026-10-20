# 私人研究工作空间

本模板为空，没有资产、模型、策略、组合或交易记录。把工作空间放在独立的私有仓库。

ChatGPT先读取CHATGPT_WORKFLOW.md及exports/current_state.json；形成结论后创建inbox请求。私有工作空间的Actions和定时任务自动处理请求、检查到期窗口并保存反馈，无需手动运行Actions。

inputs/market.json由你的私人数据入口提供。它保存带标的、币种、口径和可获知时间的history/bars。没有数据时仍会保留待评价，不自动下载另一标的替代。

config/research.json的mechanisms按研究资产分组，只放当前工作空间的研究假说及证伪条件。自己的模型和策略可独立保存，再把需要验证的输出送入本工作空间；引擎不要求公开它们。

## 成绩报告

refresh 会更新 research_performance 和 live_portfolio_performance；也可单独运行 performance 命令。报告在本工作空间 exports/，可选摘要在 exports/shareable/，默认不选择分享且不会自动发布。输入与口径见 [成绩报告说明](https://github.com/wysking/quantitera/blob/v0.4.0/docs/performance.md)。
