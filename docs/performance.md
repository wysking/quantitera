# 研究成绩与真实投资成绩（v0.4.0）

两份报告由工作空间生成，不向公开引擎上传个人资料，也不需要服务器或收费 API。运行：

```sh
python -m research_engine refresh --workspace ./workspace
python -m research_engine performance --workspace ./workspace
```

exports/research_performance.json / .md 和 live_portfolio_performance.json / .md 是完整私人报告。每日 refresh 自动更新；JSON 保留明细与来源，Markdown 提供统计表、解释和缺失资料。历史来自原事件和原档案，报告本身不是另一份账本。

## 研究口径

- 只有明确 record_kind=research 的记录进入研究判断统计。政策检查、工作流、账户背景、未分类记录分别计数；不通过关键词猜测成功或失败。
- 同一旧判断的归档和窗口视图在来源、原文、资产与类别相同时去重；别名保留，原文件不修改。多资产判断可出现于多行，各行不能相加。已撤回/替代且未复盘的旧期限不重新激活。
- 完成窗口按 review_id 保留最后有效结果，已完成状态不能被后来的缺口快照覆盖。整体 supported/refuted/mixed 必须明确登记；旧文字复盘及仅部分支持的记录保持未整体打分，不编造命中率。
- 原冻结前向结果按资产、模型版本、期限单列登记、成熟、未来和待评价窗口及代理收益。窗口可能重叠，正收益比例不是预测准确率，多个版本不能直接比高低。
- 原机制、候选因子、历史检验及模型模拟由私人 provider 的 performance_inputs 能力提供。没有第二套因子或模拟系统；研究因子资格不等于因果识别或生产权重。
- 月度 cohort 按判断月份分组，但复盘进度截至当前报告时间。可以观察记录规范和复盘覆盖，尚无可比资产/期限/基准、独立样本与不确定性检验时，不认定预测方法已改善。

## 实盘输入

私人 provider 可返回 live 中的 valuations、trades 等原始账户视图。空白工作空间可直接使用 inputs/live_performance.json。已有 provider 时，该文件只能补充资金流/费用/口径/基准/明确交易关联，不能替换其原快照、交易或币种；更正走原账户协议。

最小可计算例子见 examples/performance_demo.py，全部是合成数据。字段：

- base_currency：账户统计币种；valuation_timezone 默认 Asia/Shanghai，可显式设置其他时区。
- valuations：date、value、currency、source_refs、complete_account。真实日终估值用 timing=end_of_day；必须包含现金、分红和账户内成本。仅有日期的旧快照可以展示市值，但不能冒充连续日终净值。
- coverage：start/end、external_flows_complete、costs_complete 和非空 source_refs。这是完整性声明，不从零条记录推断“没有入金或费用”。起点是首个收盘估值之后，期初同日资金已经在初值中。
- cash_flows：date、无符号 value、currency、kind（deposit/withdrawal/distribution/internal_transfer）、timing=end_of_day、source_refs。买卖、基金申赎在账户内发生时不是外部出入金。账户内分红已含于估值，不能另加；向外支付的分红按 distribution 记录。
- fees：date/value/currency、included_in_valuation 布尔值、source_refs。已含于 NAV/现金余额的费用不重复扣；账户外支付的费用须明确 timing=end_of_day 并单独扣除。未知费用不补零。
- 外币 value 使用同日期 fx：rate（每单位本币折基准币）、base_currency/date/source_refs。没有匹配汇率就缺失；已由平台报告的基准币种市值不再用外国代理价格重算。
- valuation_calendar：calendar_day、US、HK 或 CN。日度风险指标要求完整对应日历，不插值补快照；当天尚未结束的日终估值不使用。
- risk_free：同币种、覆盖相同 start/end 的 annual_rate 和 source_refs。不默认零利率。年化波动和夏普同时披露样本数量与年化频次，短样本不代表长期能力。
- benchmarks：name、return_kind=total_return、source_refs、values（相同期间端点与币种/汇率）。价格指数不冒充含分红总回报；收益差不是风险 alpha。
- trade_links：明确 trade_id、decision_id 和 source_refs。只有原交易记录与匹配资产判断存在才关联，不因同日、同资产、金额相似而猜测。用户报告成交仍保持其原证据等级。

区间收益额为期末估值减期初估值、净外部流入和账户外费用。时间加权收益在有估值的资金流日期分段，日终约定下 `(期末值 - 当日外部净流入 - 账户外费用) / 前一估值 - 1`，再几何链接。中间资金流缺估值或时点不明确时，收益额可能可算，但精确 TWR 不可算；不自动使用近似 Dietz。期初市值和剩余持仓成本都不冒充投入本金。

至少一年才给年化收益；最大回撤用资金流调整后的净值高水位计算，波动采用样本标准差乘年化频次平方根，夏普使用相同频次的无风险收益。使用者的资金、费用与净值必须真实完整，计算通过不证明投资能力。

方法参考 [CFA Institute / GIPS Asset Owner Handbook](https://www.gipsstandards.org/standards/gips-standards-for-asset-owners/gips-standards-handbook-for-asset-owners/) 对外部资金流、估值、交易成本及不足一年不年化的说明。本工具采用保守的资料要求，**不声称符合或通过 GIPS 认证**。

## 可选分享

config/performance.json 的 sharing.research / sharing.live 默认 false，topics 是主动选择的研究主题文字。exports/shareable/ 中仍只是在私人工作空间生成的文件，没有发布操作。公开摘要按字段白名单生成：研究总数/进度，或经选择的组合收益百分比、风险指标及期间；不含资产金额、持仓、交易、原文、来源路径、模型参数或候选定义。未选择分享时，连账户观察期间也不输出。

公开示例位于 [examples/performance](../examples/performance/README.md)，全部明确标记合成示例，不能用作真实成绩。
