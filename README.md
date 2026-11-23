<div align="center">

<p>
  <b>🇨🇳 简体中文</b> ·
  <a href="README.en.md"><b>🇺🇸 English</b></a> ·
  <a href="docs/overview.md"><b>📖 完整技术指南</b></a> ·
  <a href="docs/ai-integration.md"><b>🤖 双轨 AI 桥接</b></a> ·
  <a href="https://colab.research.google.com/github/wysking/quantitera/blob/main/demo.ipynb"><b>🚀 Colab 在线体验</b></a>
</p>

<img src="docs/assets/hero-banner.svg" alt="QuantItera — AI agent that validates its own predictions" width="100%" />

<h3>AI agent that validates its own predictions · 开放式自主迭代量化研究引擎</h3>
<p><b>Discover. Reason. Validate. Evolve.</b></p>

<p>
  <a href="https://colab.research.google.com/github/wysking/quantitera/blob/main/demo.ipynb"><img src="https://img.shields.io/badge/Open_in_Colab-F9AB00?style=for-the-badge&logo=googlecolab&logoColor=white" alt="Open In Colab" /></a>
  <a href="docs/ai-integration.md"><img src="https://img.shields.io/badge/AI_Workflow-ChatGPT_%26_Gemini_Bridge-6366F1?style=for-the-badge&logo=googlegemini&logoColor=white" alt="ChatGPT & Gemini Bridge" /></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/Python-3.12%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.12+" /></a>
  <a href="https://github.com/wysking/quantitera/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/wysking/quantitera/ci.yml?branch=main&label=CI&style=for-the-badge&logo=githubactions&logoColor=white" alt="CI Status" /></a>
  <a href="https://github.com/wysking/quantitera/releases"><img src="https://img.shields.io/github/v/release/wysking/quantitera?style=for-the-badge&color=14B8A6" alt="Release" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-0EA5E9?style=for-the-badge" alt="License: MIT" /></a>
</p>

<blockquote>
  <b>💡 痛点：99% 的 AI 投研助手和回测脚本只管生成观点，从不记账，更不会在到期后验证自己当初说得对不对——QuantItera 把每一次事前判断、到期自动验证与复盘经验回流连成真正能自我进化的闭环。</b>
</blockquote>

<img src="docs/assets/demo.png" alt="QuantItera real CLI and research report output from examples/research_demo.py" width="100%" />

</div>

### ⚡ 3 行跑通完整闭环（无需 API Key）

```sh
git clone https://github.com/wysking/quantitera.git && cd quantitera
python -m pip install -e .
python -m examples.research_demo --workspace ../quantitera-tutorial
```

> [!TIP]
> ⭐ **如果这个「会到期验证自己判断」的开源量化研究引擎对你有启发，请点亮右上角 Star 支持项目持续迭代！**
> 完整系统架构、核心能力矩阵与 10 步教程见 **[《QuantItera 完整技术指南》(docs/overview.md)](docs/overview.md)**。

---

## 🔥 为什么选择 QuantItera（对比传统方案）

| 维度 | 传统回测脚本 | 普通 AI 聊天投研 | **QuantItera 闭环引擎** |
| :--- | :--- | :--- | :--- |
| **事前可追溯性** | ❌ 易过拟合、事后调参改写历史 | ❌ 对话散落，无统一时间戳账本 | ✅ **不可变事件账本**（绑定发布时间、首次获知时间与事前预期） |
| **到期结果验证** | ⚠️ 仅回看历史，无前向到期检验 | ❌ 说完即忘，从不回头核对预测 | ✅ **按 `review_at` 自动核对成熟窗口**（自动判定 `supported` / `refuted`） |
| **复杂机制与归因** | ❌ 价格涨跌直接等同于策略有效 | ⚠️ 纯文字主观复盘，无结构化缺口 | ✅ **价格验证与机制归因分离**（保留竞争解释与 `evidence_gaps`） |
| **经验复利回流** | ❌ 历史错判不会自动提醒下轮研究 | ❌ 新开会话即丢失历史反驳教训 | ✅ **每次 `discuss` 与模型运行自动注入历史反驳与有效机制** |
| **数据与模型隐私** | ✅ 本地运行 | ❌ 需手动搬运数据或暴露整仓权限 | ✅ **公开引擎 + 私有工作空间分层**（支持本地 `provider` 与全谷歌原生零断连桥接） |

---

## 🧩 四步自我演进闭环（`Discover → Reason → Validate → Evolve`）

<table>
<tr>
<td width="25%" valign="top">

### 1️⃣ Discover
**原始证据与事前预期**
分开记录宏观/行业事件、市场一致预期与机制证据，严格保留 `published_at` 与 `available_at` 时间边界。

</td>
<td width="25%" valign="top">

### 2️⃣ Reason
**机制推演与判断归档**
结合支持/反证与竞争解释，调用个人资产与组合模型，将判断与验证条件（`review_at` / `review_spec`）写入不可变账本。

</td>
<td width="25%" valign="top">

### 3️⃣ Validate
**到期自动客观检验**
窗口成熟后自动对照同标的完整交易日收益或点位阈值；复杂机制与政策判断自动整理证据缺口进入复盘队列。

</td>
<td width="25%" valign="top">

### 4️⃣ Evolve
**经验回流与双轨成绩**
每次 `discuss` 自动召回历史反驳、错误与新假设并喂给模型，同步生成**研究成绩**与**实盘资金流调整（TWR）绩效**。

</td>
</tr>
</table>

---

## 🤖 双轨 AI 助手接入方案（ChatGPT & Gemini 全谷歌原生桥接）

QuantItera 原生提供两套经过实战检验的 AI 接入方案，**全套桥接源码与可复制提示词已随本仓开源**（详见 **[《双轨 AI 接入与全谷歌原生桥接指南》(docs/ai-integration.md)](docs/ai-integration.md)**）：

<table>
<tr>
<td width="50%" valign="top">

### 🅰️ 方案 A：ChatGPT / Claude / 通用 MCP 路线
**`GitHub Connector / Remote MCP` ⇄ `Private GitHub Repo`**

- **适用环境**：ChatGPT Plus / Pro（Projects + Scheduled Tasks）、Claude Desktop、Cursor 等。
- **工作链路**：
  1. AI 助手直接读取私有仓库中的 [AI_WORKFLOW.md](research_engine/workspace_template/AI_WORKFLOW.md) 与 `exports/current_state.json`。
  2. 讨论形成判断后，直接向 `inbox/<request_id>.json` 提交结构化请求。
  3. GitHub Actions 自动串行运行 `refresh` 并生成 `outbox/<request_id>.json` 回执。
- 👉 **[查看 ChatGPT Project 指令与定时任务模板](docs/ai-integration.md#%EF%B8%8F-方案-achatgptprojects--scheduled-tasks-通用-mcp-配置)**

</td>
<td width="50%" valign="top">

### 🅱️ 方案 B：Gemini 全谷歌原生桥接路线 ⭐
**`Google Drive + Gmail` ⇄ `Google Apps Script` ⇄ `GitHub Actions`**

- **适用环境**：Gemini（Google AI Pro / Workspace）Skills（Gems）与 Scheduled Tasks（定时任务）。
- **为什么极力推荐**：**100% 调用 Google 第一方原生连接器**，彻底根治第三方远程 MCP 断连、7 天 OAuth 过期与后台定时任务无法无确认落盘的顽疾！
- **工作链路**：
  1. **下行只读镜像**：GitHub 最新协议、状态、研究报告与同步日志自动同步至 Google Drive `QuantItera-Cloud/` 下的 **4 份固定 ID Google Docs**（`Quant-1` ~ `Quant-4`），Gemini 通过 `@Google Drive` 实时秒读。
  2. **上行多通道投递**：Gemini 通过 `@Gmail` 创建主题为 `[QUANT-INBOX] <id>` 的草稿（或写入 Drive `Quant-Inbox`）。
  3. **5 分钟离线强校验同步**：托管在你个人账号下的 **[google_bridge/Code.gs](google_bridge/Code.gs)** 每 5 分钟自动校验 Schema、拦截弯引号/非法字段并单向推入 GitHub。
- 👉 **[5 分钟部署指南 & 可复制 Gemini Skill 指令](docs/ai-integration.md#%EF%B8%8F-方案-bgemini-全谷歌原生桥接google-drive--gmail--apps-script)** · **[查看 `Code.gs` 源码](google_bridge/Code.gs)**

</td>
</tr>
</table>

---

## 📚 文档与真实报告导航

<table>
<tr>
<td width="50%" valign="top">

### 📖 核心文档与开发指南
- 📘 **[完整技术指南（架构全景与 10 步教程）](docs/overview.md)** · **[English Guide](docs/overview.en.md)**
- 🤖 **[双轨 AI 接入与全谷歌原生桥接指南](docs/ai-integration.md)** · **[English Bridge Guide](docs/ai-integration.en.md)**
- 🚀 **[新用户从零上手指南](docs/getting-started.md)** · **[自动刷新运维指南](docs/automation.md)**
- 🏗️ **[系统架构说明](docs/architecture.md)** · **[研究方法论](docs/research-method.md)**
- 🔌 **[接入个人模型 (`provider` 接口)](docs/providers.md)** · **[成绩统计口径](docs/performance.md)**
- 📦 **[v0.5.0 发布说明](docs/release-v0.5.0.md)** · **[更新日志](CHANGELOG.md)** · **[贡献指南](CONTRIBUTING.md)** · **[来源边界](docs/reuse.md)**

</td>
<td width="50%" valign="top">

### 📊 在线预览引擎真实输出样例
无需安装，直接点击查看 `examples/` 运行生成的结构化报告：
- 🔬 **[研究闭环报告 (`research_report.md`)](examples/research/research_report.md)**
  *展示事前预期对照、机制支持/反证、到期验证与下一轮反馈*
- 🗂️ **[完整结构化摘要 (`summary.json`)](examples/research/summary.json)**
  *展示模型版本追踪、`review_feedback` 与幂等检查结果*
- 🎯 **[长期研究成绩单 (`research_performance.md`)](examples/research/research_performance.md)**
  *按资产、期限与版本统计支持/反驳/未打分复盘进度*
- 💹 **[账户 TWR 实盘绩效报告 (`live_portfolio_performance.md`)](examples/performance/live_portfolio_performance.md)**
  *处理外部出入金、费用与基准对比的时间加权收益报告*
- 🌐 **[可选脱敏公开摘要 (`shareable/`)](examples/performance/shareable/live_portfolio_performance.md)**

</td>
</tr>
</table>

<div align="center">

---

Released under the [MIT License](LICENSE) · **Discover. Reason. Validate. Evolve.**

</div>
