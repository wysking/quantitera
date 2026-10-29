# 最小拆分与复用

本仓库从 V6 与已验收的 V7 P1 代码中按文件/函数白名单提取，没有导入私人仓库的 Git 历史。`provenance.json` 保留来源文件、被提取函数与内容指纹，便于核对复用关系；不包含真实研究事件或个人模型配置。

| 已有能力 | 新位置 | 必要改动 |
| --- | --- | --- |
| 判断归档、复盘保存、原子请求与幂等回执 | workspace.py / processor.py | 去除账户、成交及模型操作，只保留通用研究操作 |
| 知识规范化、替代关系、索引与复盘反馈 | knowledge.py | 资产由工作空间显式提供；去掉个人资产别名和旧账本迁移 |
| 到期判断、客观条件对照、去重、反馈提取 | reviews.py / review_cycle.py | 导入改指向独立包；去掉旧个人任务、黄金归档和私人宏观模型适配器 |
| 市场身份、完整窗口、交易日与可获知时间 | identity.py / quantitera_calendars / market_data.py | 只取身份/时间/窗口工具，去掉持仓映射及私人数据抓取入口 |
| 经济证据、事前预期、冲突与机制卡片 | evidence.py / expectations.py / conflicts.py / mechanisms.py | 研究对象和机制定义由工作空间提供；去掉固定个人模型定义和权重 |

V6 经济研究并没有被缩减为价格回测：引擎仍保存原始来源、观察期间、发布时间、首次获知时间、单位、修订、事前预期、支持/反证、竞争解释和下一观察。研究机制与技术模型、预测校准、个人配置及真实执行分别处理。

原 P1 的私有代码、真实案例夹具和完整测试成果保持原样。这里只迁移可公开的函数及合成回归案例；为了调整仓库没有重新实现判断与反馈算法。私人入口暂不改成依赖新公开包，避免未经验证地改变现有运行。

这是首次最小拆分，未加入插件框架、事件总线、因子系统副本或通用服务层。公开模型源、个人数据或策略参数均不是使用引擎的前提。


## Public reference corpus boundary

The XERJ application selects `research_engine`, `docs`, `examples`, `tests`,
and `licenses` at a fixed public commit. It is a research-engine reference
subset, not a complete installable distribution or an exchange calendar corpus.
The complete source package still installs `quantitera_calendars`; the existing
`research_engine.calendar` API forwards to it without changing the algorithms.
Both the finite calendar implementation and its historical JSON are outside the
Hub subset, pending a separately established redistribution basis for the
source-derived tables. No real calendar is relabelled as synthetic.

`provenance.json` retains the original extraction paths and fingerprints as
historical provenance. Those references do not grant access to private sources;
this review used only this public repository. Licensing detail is in
[`licenses/README.md`](../licenses/README.md).
