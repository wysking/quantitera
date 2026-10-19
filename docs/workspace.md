# 工作空间与验收

## 边界

`research_engine/` 是公开代码。`quantitera init` 生成的目录是独立私人工作空间，拥有自己的data/events、inputs、inbox/outbox和exports。事件只追加，复盘完成后不重算首次结果。公开仓库的workspace/、runtime/默认忽略；部署工作空间时使用私有仓库。

引擎不获取个人账户、不嵌入个人模型和交易策略。自己的免费数据入口更新inputs/market.json；缺数据时任务保留awaiting_evaluation，不把空值当0。已有私有系统保持独立运行，不自动迁移或更改真实账本。

## 判断

以下仅为合成格式示例，不能当作真实预测或行情：

```json
{
  "version": 1,
  "operation": "save_decision",
  "inputs": {
    "reference": "synthetic-demo-judgement",
    "asset": "demo",
    "record_kind": "research",
    "conclusion": "SYNTHETIC: test a future QQQ proxy window",
    "review_at": "2026-10-06",
    "review_spec": "{\"kind\":\"market\",\"checks\":[{\"claim\":\"SYNTHETIC return >= 1%\",\"history_key\":\"demo\",\"symbol\":\"QQQ\",\"venue\":\"US\",\"currency\":\"USD\",\"return_kind\":\"provider_adjusted_etf_price\",\"metric\":\"close_return_pct\",\"start\":\"2026-10-01\",\"end\":\"2026-10-05\",\"operator\":\"gte\",\"threshold\":1}]}"
  }
}
```

输入histories.demo必须声明同样的symbol/venue/currency/return_kind，bars逐项提供date、open/high/low/close、adjusted_close、close_at与available_at。收益用声明口径的adjusted_close，点位用原始close。端点和中间应有交易日都须齐全，尚未到可获知时间的价格不会参与验证。

`research`类型仅整理证据；`policy`检查原约束与milestones；`market`在结果成熟且无缺口时才自动完成。复杂复盘由record_review保存facts/conclusion/source_refs与review_result；status=reviewed关闭任务，awaiting_evaluation继续保留。使用同一请求编号重试不会重复写入；新评价用新编号，原判断不覆盖。

## 经济机制

config/research.json的mechanisms按资产和机制ID分组，每个机制提供hypothesis、horizon（short/medium/structural）、alternative_explanations、invalidation和next_observation。模板为{}，没有任何个人机制或默认模型权重。

record_evidence的evidence JSON字符串沿用V6字段：schema_version、asset、kind（event/expectation/mechanism_evidence）、fact_id、metric、unit、value、horizon、observation_period、published_at、source_captured_at、available_at、source_url、source_excerpt、vintage_status。expectation另需event_id、expectation_kind、population和expectation_cutoff_at；event另需event_id；机制证据另需mechanism_id、evidence_role、counter_evidence和alternative_explanations。修订保留revision_of；来源引用不是该操作已经下载验证的声明。

只有事件之前已在账本获知、目标/单位/期限相同的原始预期才能参与预期差比较。互相冲突的来源不会静默平均，单一分析师看法不称市场意外，价格变化不能代替事前预期。机制卡片保留支持、反证及竞争解释，不能直接推出涨跌、配置比例或真实成交。

## 验收

```sh
python -m pytest -q
```

合成闭环测试沿用P1的真实inbox处理路径：创建判断→未成熟时等待→完整窗口成熟→条件被反驳→保存错误和新假设→下一讨论自动取得反馈→观点被替代后仍可读取学习。另测复杂政策/经济判断的待评价与人工完成、100天后任务保留、重复刷新不新增记录、V6事前预期/冲突/可获知边界，以及空白模板无需个人数据即可运行。

日历目前只登记2021—2026。未知年份明确拒绝，不按普通工作日猜测；更新时应核对官方交易所日历。当前代码没有预测概率、自动调权或交易执行。
