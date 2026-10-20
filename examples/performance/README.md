# 成绩报告合成示例

本目录全部是 **SYNTHETIC 合成示例**，没有任何真实账户或真实投资成绩。

research_performance 演示预先归档的两个明确条件在未来窗口得到支持/反驳；live_portfolio_performance 演示 500 入金、200 出金和已嵌入市值的 5 元费用。期末市值与期初市值之差不是投资收益，嵌入费用不重复扣除。

shareable/ 是通过同一导出器生成的可选公开摘要，只含明确允许的统计字段，不含账户金额、持仓、交易明细或来源路径。实际报告仍由私人工作空间生成，不上传这里。

在公开仓库根目录复现（目标目录必须不存在或为空）：

```sh
python -m examples.performance_demo --workspace runtime/new-synthetic-demo
```

读取目标 exports/ 下的同名 JSON / Markdown 及 shareable/。三个日期的风险统计仅展示计算口径，不能作为长期能力证据；不足一年不生成年化收益。
