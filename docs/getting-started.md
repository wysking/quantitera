# 新用户：从源码到个人研究工作空间

本指南对应 v0.5.0。需要 Git 和 Python 3.12+；示例不访问行情服务、不调用大模型、不需要私人资料。

## 1. 获取源码与安装

```sh
git clone --branch v0.5.0 https://github.com/wysking/quantitera.git
cd quantitera
python -m venv .venv
```

激活虚拟环境：Linux/macOS 用 `. .venv/bin/activate`，Windows PowerShell 用 `.\.venv\Scripts\Activate.ps1`。已有 Python 环境也可直接使用。

```sh
python -m pip install -e .
```

本项目未要求从 PyPI 获取同名包。也可安装明确的 Git tag：

```sh
python -m pip install 'git+https://github.com/wysking/quantitera.git@v0.5.0'
```

Git 安装包含引擎与空白模板；要运行 examples 模块，仍需获取源码并从仓库根目录运行。

## 2. 初始化空白个人工作空间

```sh
python -m research_engine init --workspace ../my-research
python -m research_engine refresh --workspace ../my-research
```

只接受新目录或空目录，防止覆盖已有工作空间。生成：

```text
my-research/
  CHATGPT_WORKFLOW.md       正式研究入口
  config/research.json     机制假设、可选私人 provider
  config/performance.json  分享选项，默认关闭
  inputs/market.json       带身份/时间的市场输入
  data/events/             追加的判断、证据、复盘
  inbox/  outbox/          请求及处理回执
  exports/                 知识、队列、机制与成绩报告
  .github/workflows/       私人仓库定时模板
```

工作空间可以没有账户、模型和任何历史；报告会显示无记录或缺数据。

## 3. 添加自己的研究对象

asset 是你定义的稳定研究编号，如 my_asset。保存判断时写 asset；经济机制定义放 config/research.json 的 mechanisms.<asset>。没有必填的全局资产注册服务。

使用自己的模型时，provider.snapshot 返回 assets 字典作为调用清单。教程的 config/tutorial_assets.json 是**示例 provider 的本地格式**，不是引擎新增的注册契约。示例会把 tutorial_models.py 复制进新工作空间；在该目录运行 CLI 即可导入它。正式项目也可安装自己的 Python 包。

研究编号可自由定义；客观市场验证的 symbol/venue/currency/return_kind 必须是引擎支持的身份。例如 my_asset 可以研究 QQQ，但结果仍是 QQQ 美元 ETF 代理，不能替代自己持有基金的份额净值。支持清单见 [identity.py](../research_engine/identity.py)；新标的需要有来源的身份/日历扩展。

## 4. 导入市场数据

自己的数据入口写 inputs/market.json，或由 provider.market_data 返回同格式 bundle。运行教程后可读取完整合成输入；字段定义见 [workspace.md](workspace.md)。

每份 history 提供 symbol、venue、currency、return_kind、source_url 和 bars。每根 bar 有 date、open/high/low/close、adjusted_close、close_at、available_at。保留真实可获知时间，不因文件存在而提前使用未来价格。缺交易日、标的不同或未知日历时不自动替换。

引擎不内置行情下载服务；演示中的 example.org 是虚构引用，不是数据接口。

## 5. 配置自己的模型和策略

```json
{"schema_version":1,"mechanisms":{},"provider":"my_models:provide"}
```

provide(workspace, clock, operation, **kwargs) 处理 history、market_data、snapshot、asset_model、portfolio_model。已有历史以只读事件视图接入；模型和组合计算仍在私人代码中。资产模型取得本资产和 all 通用反馈，组合取得所有资产，包括未登记模型和缺数据状态。

```sh
python -m research_engine model --workspace ../my-research --asset my_asset
python -m research_engine portfolio --workspace ../my-research
```

没有 provider 时返回 not_configured，不强制建立模型。可选能力和原系统接入见 [providers.md](providers.md)。

## 6. 开始研究与经济机制探索

```sh
python -m research_engine discuss --workspace ../my-research --asset my_asset
```

ChatGPT 先读工作空间 CHATGPT_WORKFLOW.md。discuss 推进到期检查，并返回历史支持/反驳、错误、缺口、仍有效机制及新假设。研究者随后核对新原始信息、事前预期、发布时间和竞争解释。方法见 [research-method.md](research-method.md)。

## 7. 归档判断，自动登记未来验证

正式研究结束后，创建 inbox/<新编号>.json。示例由 examples/research_demo.py 的 request 调用展示，也可直接读取运行后 inbox/002-judgement.json。inputs 值为字符串；review_spec 是 JSON 对象字符串。

明确 reference、asset、record_kind=research、conclusion、review_at、review_spec。market 提供同标的、口径、窗口和阈值；research 记录机制、缺口和竞争解释；policy 检查约束和期限。

```sh
python -m research_engine refresh --workspace ../my-research
```

引擎自动处理请求、归档并登记任务。核对 outbox/<同编号>.json 的 status=succeeded，再读 exports/review_queue.json。命令执行成功不等于每个请求均成功；拒绝理由保留在回执。已处理请求不能原地修改。

**普通聊天不会自行同步进账本。** ChatGPT 或用户必须保存结构化请求，随后本地 refresh 或工作流自动处理。省略 record_kind 时保留 unclassified，不编造研究数量。

## 8. 自动检查成熟结果

refresh 和正式 discuss 都检查到期任务。完整成熟的市场数据才能支持/反驳；复杂机制保留证据缺口和待评价。研究者用 record_review 保存 facts、conclusion、source_refs 和 review_result，价格结果不能替代因果判断。

部署在自己的私有 GitHub 仓库后由模板定时执行，详见 [automation.md](automation.md)。原数据入口仍需持续更新行情。

## 9. 下一轮使用个人知识

新的 discuss 自动取得相关复盘，即使旧观点已被 supersedes 替代。研究者说明反馈如何影响新判断，并登记新的期限。模型输入携带同样反馈；manifest.model_feedback_matches_workspace 提醒旧组合结果是否需要重新计算。没有自动参数训练或收益调权。

## 10. 生成研究与投资成绩

refresh 自动生成 exports/research_performance 和 live_portfolio_performance 的 JSON / Markdown；单独重建报告用：

```sh
python -m research_engine performance --workspace ../my-research
```

真实账户由 provider.performance_inputs 提供，空白工作空间也可使用 inputs/live_performance.json。资金流、费用、净值、汇率或基准不足的指标明确缺失。分享默认关闭；选择后也仅在私人工作空间生成摘要，不上传公开引擎。口径见 [performance.md](performance.md)。

## 一次跑完整教程

源码仓库根目录运行，目标目录须不存在或为空：

```sh
python -m examples.research_demo --workspace ../quantitera-tutorial
python -m examples.performance_demo --workspace ../quantitera-performance-demo
```

第一份输出 exports/tutorial/research_report.md 与 summary.json，经历事前预期→事件→机制支持/反证→两条市场判断→复杂评价→下一轮判断→模型反馈。重复刷新新增复盘为 0，原判断不改写。第二份输出可计算的合成账户报告。

在教程工作空间目录，还能独立调用复制出的模型：

```sh
cd ../quantitera-tutorial
python -m research_engine portfolio --workspace . --as-of '2026-01-06T12:05:00+08:00'
```

教程固定 as-of 只用于复现合成时序。真实日常运行使用当前时钟，不能伪装首次获知或事前登记。
