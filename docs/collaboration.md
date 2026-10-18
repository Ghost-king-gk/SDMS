# 团队协作快速指南

完整协议见 [`../GITHUB_COLLABORATION.md`](../GITHUB_COLLABORATION.md)，其中包含 Git/GitHub 基础概念、分支命名、提交格式、Issue/PR 沟通、冲突处理、恢复命令和 AI 协作提示词。本文件只保留第一次参与协作时最常用的主线。

## 主线

从 `main` 更新代码 → 创建个人分支 → 在分支完成一个清晰的小任务 → 提交并 push → 通过 Pull Request 请求审查和合并。不要直接修改或 push `main`。

## 新人常用命令

~~~powershell
git clone <GitHub仓库地址>
cd SDMS
uv venv --python 3.12
uv sync --dev

git switch main
git pull --ff-only origin main
git switch -c feature/your-task

git status
git diff
git add path/to/changed-file
git diff --cached
git diff --cached --check
git commit -m 'type(scope): short description'
git push -u origin feature/your-task
~~~

## Pull Request 提交前

PR 应说明改动内容、对应 Issue/需求、验证方式、测试结果和已知限制。GUI 改动附运行或测试截图，文档改动注明对应章节。建议运行：

~~~powershell
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run python -m compileall src
~~~

更完整的开发、测试与环境说明见 [`development.md`](development.md)。

## 可以直接复制给 AI 的提示词

~~~text
请只读分析本仓库，不修改文件、不提交、不推送。
先阅读 README.md、AGENTS.md、GITHUB_COLLABORATION.md 和 Requests/ 下的需求，
说明当前任务需要改哪些文件、如何测试，以及可能影响哪些协作者。
~~~

~~~text
请审阅当前 git diff，只读检查，不修改文件。
重点检查需求覆盖、无关改动、密钥/缓存泄露、测试和文档缺失，
并按“必须修改、建议修改、已通过”分类，不要虚构测试结果。
~~~

AI 只能辅助分析和检查，提交、push、关闭 Issue、合并 PR 等动作必须由成员明确确认。不要把密码、令牌、私钥或个人隐私发给 AI。

## 分支与提交

- 功能：`feature/<简短主题>`；修复：`fix/<简短主题>`；文档：`docs/<简短主题>`；测试：`test/<简短主题>`；
- 提交信息使用 Conventional Commits，例如 `feat(ui): 增加按日期筛选`、`fix(storage): 转换坏行错误`；
- 一个 Issue 对应一个分支和一个 PR，不要在同一分支混合多个无关任务。

详细规则与冲突处理见 [`../GITHUB_COLLABORATION.md`](../GITHUB_COLLABORATION.md) 与 [`../AGENTS.md`](../AGENTS.md)。
