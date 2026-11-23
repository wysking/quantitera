<div align="center">

<p>
  <a href="README.md"><b>🇨🇳 简体中文</b></a> ·
  <b>🇺🇸 English</b> ·
  <a href="docs/overview.en.md"><b>📖 Full Technical Guide</b></a> ·
  <a href="docs/ai-integration.en.md"><b>🤖 Dual-Track AI Bridge</b></a> ·
  <a href="https://colab.research.google.com/github/wysking/quantitera/blob/main/demo.ipynb"><b>🚀 Run in Colab</b></a>
</p>

<img src="docs/assets/hero-banner.svg" alt="QuantItera — AI agent that validates its own predictions" width="100%" />

<h3>AI agent that validates its own predictions · Open Autonomous Iterative Quant Research Engine</h3>
<p><b>Discover. Reason. Validate. Evolve.</b></p>

<p>
  <a href="https://colab.research.google.com/github/wysking/quantitera/blob/main/demo.ipynb"><img src="https://img.shields.io/badge/Open_in_Colab-F9AB00?style=for-the-badge&logo=googlecolab&logoColor=white" alt="Open In Colab" /></a>
  <a href="docs/ai-integration.en.md"><img src="https://img.shields.io/badge/AI_Workflow-ChatGPT_%26_Gemini_Bridge-6366F1?style=for-the-badge&logo=googlegemini&logoColor=white" alt="ChatGPT & Gemini Bridge" /></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/Python-3.12%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.12+" /></a>
  <a href="https://github.com/wysking/quantitera/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/wysking/quantitera/ci.yml?branch=main&label=CI&style=for-the-badge&logo=githubactions&logoColor=white" alt="CI Status" /></a>
  <a href="https://github.com/wysking/quantitera/releases"><img src="https://img.shields.io/github/v/release/wysking/quantitera?style=for-the-badge&color=14B8A6" alt="Release" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-0EA5E9?style=for-the-badge" alt="License: MIT" /></a>
</p>

<blockquote>
  <b>💡 The Pain Point: 99% of AI research assistants and backtest scripts only generate opinions — they never keep an immutable ledger or check whether their past predictions actually came true at maturity. QuantItera closes the loop from timestamped judgements to automated outcome validation and reusable feedback.</b>
</blockquote>

<img src="docs/assets/demo.png" alt="QuantItera real CLI and research report output from examples/research_demo.py" width="100%" />

</div>

### ⚡ Run the Full Closed Loop in 3 Lines (No API Key Needed)

```sh
git clone https://github.com/wysking/quantitera.git && cd quantitera
python -m pip install -e .
python -m examples.research_demo --workspace ../quantitera-tutorial
```

> [!TIP]
> ⭐ **If an open-source quant research engine that validates its own predictions at maturity resonates with you, please give us a Star in the top-right corner!**
> The full architecture, capability matrix, and 10-step walkthrough are available in the **[Full Technical Guide (docs/overview.en.md)](docs/overview.en.md)**.

---

## 🔥 Why QuantItera (vs. Traditional Tools)

| Dimension | Traditional Backtest Scripts | Ad-Hoc AI Chat Research | **QuantItera Closed-Loop Engine** |
| :--- | :--- | :--- | :--- |
| **Ex-Ante Traceability** | ❌ Prone to overfitting & rewritten parameters | ❌ Scattered chats, no timestamped ledger | ✅ **Immutable Event Ledger** (anchors publication, availability & prior expectations) |
| **Maturity Validation** | ⚠️ Backward-looking only, no forward horizon checks | ❌ Generates opinions and forgets them | ✅ **Automated `review_at` Horizon Checks** (scores `supported` / `refuted` objectively) |
| **Mechanism vs. Price** | ❌ Equates price moves directly with thesis validity | ⚠️ Free-text subjective notes without tracked gaps | ✅ **Separates Price Checks from Mechanism Attribution** (preserves competing explanations & `evidence_gaps`) |
| **Compounding Memory** | ❌ Past wrong calls never inform future runs | ❌ New chat session loses prior refutations | ✅ **Auto-Injects Refutations & Surviving Mechanisms** into every `discuss` and model run |
| **Data & Model Privacy** | ✅ Local execution | ❌ Manual copy-pasting or broad repo tokens | ✅ **Public Engine + Private Workspace Split** (supports local `provider` & zero-drop Google-Native Bridge) |

---

## 🧩 4-Stage Self-Evolving Loop (`Discover → Reason → Validate → Evolve`)

<table>
<tr>
<td width="25%" valign="top">

### 1️⃣ Discover
**Primary Evidence & Priors**
Separately records macro/fundamental events, consensus expectations, and mechanism evidence while enforcing `published_at` vs. `available_at` boundaries.

</td>
<td width="25%" valign="top">

### 2️⃣ Reason
**Mechanism & Judgement Archive**
Evaluates supporting/counter evidence and competing explanations, calls private asset/portfolio models, and commits judgements with `review_at` / `review_spec`.

</td>
<td width="25%" valign="top">

### 3️⃣ Validate
**Automated Maturity Checks**
Verifies full-window returns or price thresholds automatically once market data matures; queues complex mechanism and policy claims with explicit evidence gaps.

</td>
<td width="25%" valign="top">

### 4️⃣ Evolve
**Feedback & Dual Track Records**
Every `discuss` call recalls historical refutations, errors, and new hypotheses into model context, while generating **Research** and **Live TWR Portfolio** reports.

</td>
</tr>
</table>

---

## 🤖 Dual-Track AI Integration (ChatGPT & Gemini Google-Native Bridge)

QuantItera provides two production-tested AI integration routes, **complete with open-source bridge code and copy-ready prompts** (see **[Dual-Track AI Integration & Google-Native Bridge Guide (docs/ai-integration.en.md)](docs/ai-integration.en.md)**):

<table>
<tr>
<td width="50%" valign="top">

### 🅰️ Route A: ChatGPT / Claude / Universal MCP
**`GitHub Connector / Remote MCP` ⇄ `Private GitHub Repo`**

- **Best For**: ChatGPT Plus / Pro (Projects + Scheduled Tasks), Claude Desktop, Cursor, and MCP clients.
- **How It Works**:
  1. The AI assistant reads [AI_WORKFLOW.md](research_engine/workspace_template/AI_WORKFLOW.md) and `exports/current_state.json` directly from your private repository.
  2. When a formal judgement is reached, it commits `inbox/<request_id>.json`.
  3. GitHub Actions serially runs `refresh` and outputs `outbox/<request_id>.json` receipts.
- 👉 **[View Copy-Ready ChatGPT Project & Task Prompts](docs/ai-integration.en.md#%EF%B8%8F-route-a-chatgpt-projects--scheduled-tasks--universal-mcp-setup)**

</td>
<td width="50%" valign="top">

### 🅱️ Route B: Gemini Google-Native Bridge ⭐
**`Google Drive + Gmail` ⇄ `Google Apps Script` ⇄ `GitHub Actions`**

- **Best For**: Gemini (Google AI Pro / Workspace) Skills (Gems) and Scheduled Tasks.
- **Why We Recommend It**: **100% first-party Google connectors** — completely eliminates third-party remote MCP disconnections, 7-day OAuth expirations, and unattended scheduled task write failures!
- **How It Works**:
  1. **Downlink Read-Only Mirrors**: Latest protocols, state, reports, and sync logs mirror into **4 fixed-ID Google Docs** (`Quant-1` ~ `Quant-4`) inside `QuantItera-Cloud/`, read instantly by Gemini via `@Google Drive`.
  2. **Uplink Multi-Channel Delivery**: Gemini creates a `[QUANT-INBOX] <id>` draft via `@Gmail` (or drops JSON into Drive `Quant-Inbox`).
  3. **5-Minute Offline Schema Validation & Sync**: Self-hosted **[google_bridge/Code.gs](google_bridge/Code.gs)** validates schemas every 5 minutes, blocks curly quotes or invalid fields, and pushes immutably to GitHub.
- 👉 **[5-Min Deployment Guide & Gemini Skill Prompts](docs/ai-integration.en.md#%EF%B8%8F-route-b-gemini-google-native-bridge-google-drive--gmail--apps-script)** · **[View `Code.gs` Source](google_bridge/Code.gs)**

</td>
</tr>
</table>

---

## 📚 Documentation & Live Sample Outputs

<table>
<tr>
<td width="50%" valign="top">

### 📖 Core Guides & Reference
- 📘 **[Full Technical Guide (Architecture & 10-Step Tutorial)](docs/overview.en.md)** · **[中文详版](docs/overview.md)**
- 🤖 **[Dual-Track AI & Google-Native Bridge Guide](docs/ai-integration.en.md)** · **[中文桥接指南](docs/ai-integration.md)**
- 🚀 **[10-Step Getting Started Guide](docs/getting-started.md)** · **[Automated Refresh Guide](docs/automation.md)**
- 🏗️ **[Architecture Guide](docs/architecture.md)** · **[Research Methodology](docs/research-method.md)**
- 🔌 **[Private Model Interface (`provider`)](docs/providers.md)** · **[Performance Reporting Rules](docs/performance.md)**
- 📦 **[v0.5.0 Release Notes](docs/release-v0.5.0.md)** · **[Changelog](CHANGELOG.md)** · **[Contributing](CONTRIBUTING.md)** · **[Provenance](docs/reuse.md)**

</td>
<td width="50%" valign="top">

### 📊 Browse Real Engine Outputs Online
Click to inspect the exact reports generated by `examples/`:
- 🔬 **[Closed-Loop Research Report (`research_report.md`)](examples/research/research_report.md)**
  *Prior expectation surprise, supporting/counter evidence, maturity checks & next-round feedback*
- 🗂️ **[Structured Tutorial Summary (`summary.json`)](examples/research/summary.json)**
  *Model version tracking, `review_feedback`, and idempotency verification*
- 🎯 **[Long-Term Research Track Record (`research_performance.md`)](examples/research/research_performance.md)**
  *Supported, refuted, and unscored review counts by asset, horizon, and model version*
- 💹 **[Live Portfolio TWR Report (`live_portfolio_performance.md`)](examples/performance/live_portfolio_performance.md)**
  *Cash-flow adjusted time-weighted return (TWR), fee handling, and benchmark comparison*
- 🌐 **[Optional Shareable Summary (`shareable/`)](examples/performance/shareable/live_portfolio_performance.md)**

</td>
</tr>
</table>

<div align="center">

---

Released under the [MIT License](LICENSE) · **Discover. Reason. Validate. Evolve.**

</div>
