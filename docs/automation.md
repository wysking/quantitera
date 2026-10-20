# 使用 GitHub Actions 自动刷新

公开引擎 CI 只做测试。工作空间模板的日程在自己的**私有仓库**运行，结果仍保存在该仓库，没有付费数据 API、付费 runner、缓存或报告工件上传。

## 一次性部署

1. 用 init 生成工作空间，或保留已有项目并配置 provider。
2. 保存到自己的私有 GitHub 仓库，使用 main 为默认分支；个人目录不加进公开引擎。
3. 提交模板 .github/workflows/research.yml、.gitattributes 和空目录占位文件。Actions 需允许官方 checkout/setup-python 及本仓库 GITHUB_TOKEN 写 contents；模板已声明 contents: write。仓库规则和分支保护仍须允许保存结果。
4. 如 provider 依赖私人 Python 包，在安装引擎后安装这些依赖；工作空间根目录也可导入该目录的模块。原项目有写入者时沿用同一并发组，在其完成后刷新，避免同时改账本。
5. 自己的数据入口更新 inputs/market.json；ChatGPT 按入口协议写 inbox。配置完成后等待正常输入提交或日程，无需每天手动运行 Actions。

模板安装公开 tag v0.5.0。升级时在自己的工作流提交新 pin，保留原数据，不对已有目录重新 init。

## 运行与保存

模板在输入/config/inbox 更新和定时触发时调用同一个 refresh：处理请求、推进成熟验证、导出知识与机制、更新成绩，只提交 data/events、exports、outbox。inbox 原请求由用户提交，处理后不改写。并发组串行写入，push 冲突最多重试三次，失败明确结束。

默认日程为 UTC 05:15（周一至周六）和 UTC 09:15（周一至周五），即 UTC+8 的 13:15 / 17:15。模板未填写 timezone，所以按 UTC 解释；它们是检查时点，不保证每个市场刚收盘或上游已更新。

定时工作流运行默认分支，PR 中的模板不会开始日程。调度可能延迟，不是精确时钟。[GitHub 官方触发事件说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)

GITHUB_TOKEN 推送普通提交不会再次触发 push 工作流，避免递归刷新。输入由其他工作流提交时，须在原任务内刷新、接 workflow_run，或等待下次日程。[官方 GITHUB_TOKEN 说明](https://docs.github.com/en/actions/concepts/security/github_token)

标准 Ubuntu runner 仍受账户免费额度和组织策略约束；代码不开通额外计费服务，也不承诺无限分钟。权限与额度应在自己的仓库设置核对。[官方 Actions 设置说明](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository)

## 核对结果

| 情况 | 读取位置或处理 |
| --- | --- |
| 判断未进队列 | 读 outbox/<同编号>.json；拒绝请求用新编号修正，不能改已处理文件 |
| 到期没有明确结果 | 看 awaiting_evaluation 和缺口；更新同标的完整行情，复杂机制交给研究者 |
| 模型似乎未读新反馈 | 看 manifest.model_feedback_matches_workspace；重新调用 portfolio 并核对 research_context |
| 报告未更新 | 检查任务结果、生成时间、输入日期及写入权限；生成时间不等于行情或快照日期 |
| 工作流不启动 | 确认私有仓库、main 默认分支、Actions 启用及路径条件；PR 中的 schedule 不运行 |
| 不能提交生成文件 | 检查 contents 权限、组织限制和 main 保护；不需要跨私人仓库 token |
| 未登记年份/标的 | 保留缺失；按官方来源扩展日历和身份，不以普通工作日或其他标的替代 |

公开 CI 从安装后的 wheel 初始化/克隆空白工作空间，执行模板的刷新和保存路径，再在源码目录之外跑完整合成示例。它验证执行路径；真实日程和上游数据仍取决于私人仓库部署状态。
