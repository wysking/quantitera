# QuantItera

Economic mechanism research → archived judgement → due validation → knowledge feedback → next research iteration.

QuantItera 是从已运行的 V6 研究能力与 V7 P1 闭环中拆出的通用研究引擎。它保留经济机制、事前预期、反证和竞争解释，也保留判断归档、到期验证及下一轮研究反馈。核心算法沿用原实现，拆分说明见 [docs/reuse.md](docs/reuse.md)。

公开仓库只保存引擎、空白工作空间模板和合成测试。个人资产数据、模型、策略、组合、交易记录与真实研究档案保存在独立私有工作空间；公开引擎不读取任何原私人仓库。

## 开始使用

Python 3.12+：

```sh
python -m pip install -e '.[test]'
python -m pytest -q
python -m research_engine init --workspace ../my-private-research
python -m research_engine refresh --workspace ../my-private-research
python -m research_engine discuss --workspace ../my-private-research --asset demo
```

新工作空间为空，不带持仓或默认策略。把它放在独立的**私有** GitHub 仓库后，模板中的免费 Actions 会处理 inbox、检查到期任务并保存反馈。公开引擎仓库的 CI 只运行测试，不保存私人研究记录。

ChatGPT 从工作空间的 `CHATGPT_WORKFLOW.md` 进入，先读取 `current_state.review_feedback` 和经济机制证据，再形成并归档下一次判断。`discuss` 命令生成同样的研究上下文，不调用收费 API 或后台大模型服务。

## 引擎包含什么

- V6：原始证据与可获知时间、事前预期对照、按期限组织的机制卡片、反证与竞争解释、重复事实及冲突诊断。
- P1：判断归档、统一到期队列、同标的完整窗口验证、待人工评价状态、不可覆盖的复盘记录、下一轮研究自动读取反馈。
- 空白工作空间：输入、inbox/outbox、知识导出、私人研究机制定义，以及串行写入的定时任务模板。

市场判断可根据明确条件自动支持或反驳；投资政策核对约束与期限；复杂宏观判断保留证据缺口，继续由 ChatGPT 研究。预期差、相关性和来源数量都不会自动变成因果结论或模型权重。

自己的模型与数据入口继续独立运行，把需要验证的判断及带身份/时间的行情传给引擎即可。当前价格验证沿用已登记的美股、港股和沪市日历与公共标的身份；未知标的或未登记年份会明确缺失，不猜测。模型评分、组合优化、账户适配器、真实交易权限和原个人策略没有搬入此仓库。

数据格式和验收见 [docs/workspace.md](docs/workspace.md)。MIT License。
