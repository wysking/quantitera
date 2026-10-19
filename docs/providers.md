# 私人工作空间接入（0.3.0）

保留原项目的账户、资产模型、策略、数据和档案，在标准工作空间中配置一个可选 Python 入口。公开包只负责调用和知识反馈，不包含具体资产模型或账户政策。

```json
{"schema_version":1,"mechanisms":{},"provider":"my_research.adapter:provide"}
```

`my_research.adapter` 由自己的私人项目提供并安装到运行环境，或从该项目根目录运行命令。入口签名为 `provide(workspace, clock, operation, **kwargs)`。它是明确授权的本地 Python 代码，应保持原账本只读；不是上传脚本或远程执行服务。

| operation | 返回值/用途 |
| --- | --- |
| history | 原账本中可供知识系统使用的事件列表；支持 discussion_decision / knowledge_annotation / review_completion，原ID和带时区 recorded_at 保持稳定 |
| market_data | 同一行情 bundle 格式；每份数据保留标的、币种、口径、可获知时间和源路径 |
| snapshot | 含 assets 字典的对象；账户、资金、偏好、机制、因子、验证、策略及历史档案由私人实现提供 |
| asset_model | 接收 asset 和 research_context（asset_feedback / global_feedback），调用对应私人模型并返回结果；未登记的模型明确缺失 |
| portfolio_model | 接收 assets 字典及按资产组织的 research_context，包含全部资产及模型结果（包括缺失项）；调用用户级组合模型 |

研究入口：

```sh
python -m research_engine workspace --workspace ./workspace
python -m research_engine model --workspace ./workspace --asset alpha
python -m research_engine portfolio --workspace ./workspace
python -m research_engine discuss --workspace ./workspace --asset alpha
python -m research_engine refresh --workspace ./workspace
```

workspace 导出为 exports/workspace.json，portfolio 计算并保存 exports/portfolio_model.json；manifest 提供路径及 model_source_matches_workspace。discuss 的 workspace_research 返回该资产的私人研究档案，并继续返回 current_research / global_research 的验证反馈。

discuss 在正式研究前推进到期验证，不依赖用户手动先 refresh。模型输入始终带本资产与全局反馈；资产之间不互相替代。feedback_revision 标记该批反馈，manifest.model_feedback_matches_workspace 会在反馈更新后将旧组合结果标为不匹配，重新计算后恢复；原账户版本检查仍独立保留。

原项目已有前向验证时，可在 history 中提供稳定的原判断视图及已冻结的 review_completion，保留原发布和成熟时间、原路径与口径。仅完成客观观察的记录使用 review_kind=forward_observation、verdict=observed_only，反馈单列 forward_observations，避免冲淡原判断的错误与经验。不得据方向或价格走势补造原本未登记的收益预测，不新增独立样本或自动判断因果。

可选能力通过 config/research.json 的 provider_capabilities 数组显式启用：

| 能力 | 输入与用途 |
| --- | --- |
| review_evidence | task / original；返回机制支持与反证、缺失证据、竞争解释及来源的对象，附在复盘 research_evidence 中。research/policy 保持待评价，market 仍只按原条件验证价格事实 |
| factor_candidates | candidates / event；复用私人已有因子契约，返回核对后的候选数组。save_decision / record_review 的 factor_candidates 为 JSON 数组字符串，拒绝时整笔请求不落账 |

未启用能力的 provider 无需实现额外操作。候选因子只作为判断或复盘的附属研究定义保存；私人单写入流程再交给原候选系统登记与验证，不能在 provider 校验或临时请求处理中写外部账本。原因子校验、权重资格与失败结果均由原系统维护；公开引擎没有另一套因子账本。

history 为只读穿透视图，原记录不复制进新账本。引擎只追加新的判断与复盘；新事件与来源 ID 冲突会拒绝。原始来源、legacy_record 和 origin 可保留在知识详情中，复盘结果继续按原队列、状态和幂等规则处理。本地行情覆盖同名外部 history 时分别保留实际输入路径，不把本地数据引用成外部档案。

请求会先在临时工作空间中验证。provider 不应把该临时目录的父目录当作原项目位置；应通过私人模块自身位置或明确配置定位稳定的原数据源。原事件必须有稳定身份和已解释的时间；旧记录的时区假设应保留原文及说明，不能伪装成已验证的首次发布。

各模型输出、组合模型输出的执行许可始终为 false。模型的模拟金额、代理收益和来源数量不能代替账户成交、真实收益或因果证据。provider 应核对来源的账本版本、账户日期和研究状态；缺口及故障不能用旧结果冒充当前有效模型。

不配置 provider 时，这三个扩展命令返回 not_configured，原有空白工作空间的归档、客观验证和反馈不受影响。没有新增资产注册框架、因子系统或第二份交易账本。

0.2.1 的模板携带 .gitattributes，统一 LF；JSON 写入也固定 LF，避免 Windows 与 Ubuntu 克隆造成已处理 inbox 的字节摘要改变。既有工作空间可添加同一属性文件，不重建或修改原私人账本。
