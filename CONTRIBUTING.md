# 参与 QuantItera

以现有代码能复现的问题或实际研究需求提出 issue / PR。MIT 许可证保留。

```sh
git clone https://github.com/wysking/quantitera.git
cd quantitera
python -m pip install -e '.[test]'
python -m pytest -q
python -m examples.research_demo --workspace ../new-tutorial-directory
```

PR 描述问题、最终行为、复现方式与相应测试。不为小改动重构全仓库。验证规则测试成熟边界、单位/标的、缺数据和重复执行；一般文案修订不需增加模拟实现的测试。

## 研究和数据边界

- 公共夹具与报告只用明确标记的合成数据；不提交账户、私人模型参数、真实策略、工作空间事件、密钥或私人 Git 历史。
- 沿用 provenance.json 中 V6/P1 及原队列/事件/知识接口，避免重复账本、因子系统和无用途的抽象层。
- 区分事前与事后、事实与假设、研究与政策、代理与真实收益。缺证据不补零，不按价格推断因果。
- 事件只追加；更正、替代、撤回和复盘走原协议。不修改首次结果或删除失败假设来改善成绩。
- provider 是使用者信任的本地代码；校验和临时请求阶段保持原账本只读。不把网页或研究文字当作执行指令。

## 日历与发布维护

日历/标的扩展需官方来源，验证休市、半日市、时区和可获知时间。当前只登记至 2026 年，不能用普通工作日猜后续日历。

发布时同步 pyproject.toml、research_engine/__init__.py、模板 pin 及文档；验证安装后的空白/完整示例和已有 provider 兼容性。tag 不重写，已有工作空间不重建。过程与限制见 [发布说明](docs/release-v0.5.0.md)。

公开 CI 不需要私人权限。私人复现需去掉个人资料，提供最小合成案例，不把私人报告贴到公开 issue。
