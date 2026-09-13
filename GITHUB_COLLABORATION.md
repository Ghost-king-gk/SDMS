# GitHub 多人协作与沟通协议

这份协议写给第一次参加 GitHub 多人协作的同学。请把它理解成团队共同遵守的“交通规则”：先同步，再开发；一个任务一个分支；通过 Pull Request 合并；遇到问题及时说明，不要默默覆盖别人的工作。

## 1. 先分清 Git 和 GitHub

- Git 是电脑上的版本管理工具，负责记录文件变化、创建分支、提交和合并。
- GitHub 是网上的协作平台，负责保存远程仓库、管理 Issue、发起 Pull Request 和进行代码审查。
- commit 是保存到本地仓库；push 是上传到 GitHub；pull 是把 GitHub 的更新取回本地。
- 本地提交不会自动让别人看到，只有 push 到远程仓库后，团队成员才能在 GitHub 上看到。

## 2. 团队统一规则

### 2.1 主分支规则

- main 是稳定分支，只放已经审查和验证过的内容。
- 普通成员不要直接在 main 上写代码，也不要直接 push 到 main。
- 维护者应在 GitHub 开启分支保护：必须通过 Pull Request、至少一名成员审查，并通过必要检查后才能合并。
- 当前项目的需求材料在 Requests/，默认按只读资料处理，不要在功能开发中直接改动。

### 2.2 分支命名

每个任务单独创建分支，分支名要让别人一眼看懂：

~~~text
feature/schedule-crud       # 新功能
fix/invalid-date            # 修复问题
docs/github-workflow        # 文档
test/schedule-service       # 测试
refactor/storage-layer      # 重构
~~~

建议一个 Issue 对应一个分支和一个 Pull Request。不要在同一分支里混合多个无关任务。

### 2.3 提交信息

使用 Conventional Commits 格式：

~~~text
<类型>(<范围>): <简短说明>
~~~

常用类型：

~~~text
feat(ui): add schedule list
fix(validation): reject invalid date
docs(readme): explain GitHub workflow
test(schedule): cover delete confirmation
refactor(storage): separate persistence logic
chore(project): update development tools
~~~

提交信息说明“做了什么”，不要写成“修改一下”“代码更新”。一次提交尽量只表达一个完整的小变化。

## 3. 新成员第一次加入项目

先确认已经获得仓库访问权限，并在本机安装 Git、Python 3.12+ 和 uv。然后执行：

~~~powershell
git clone <GitHub仓库地址>
cd SDMS
git remote -v
uv venv --python 3.12
uv sync --dev
~~~

如果要设置自己的提交身份，只需在本机设置一次。邮箱可以使用 GitHub 提供的隐私邮箱：

~~~powershell
git config --global user.name "你的姓名"
git config --global user.email "你的GitHub邮箱"
~~~

不要把密码、访问令牌或私钥写进仓库，也不要把令牌直接放进远程地址或聊天记录。

## 4. 开始一个新任务

### 4.1 开工前同步

~~~powershell
git switch main
git pull --ff-only origin main
git switch -c feature/your-task
~~~

--ff-only 表示只接受没有分叉的安全更新。如果它报错，不要强行处理，先查看状态并向维护者说明。

### 4.2 开发中随时检查

~~~powershell
git status
git diff
git diff --check
~~~

这些命令分别用于查看工作区状态、查看未暂存的修改和检查空格/格式问题。不要等到提交前才第一次查看差异。

### 4.3 提交本地修改

推荐逐个指定文件加入暂存区：

~~~powershell
git add path/to/changed-file
git diff --cached
git diff --cached --check
git commit -m "docs(readme): explain GitHub workflow"
~~~

如果改动很多，可以分组暂存，但必须先审阅差异。不要未经检查就直接使用宽泛的 git add .，更不要把 .venv/、.uv-cache/、密钥或临时文件提交进去。

### 4.4 上传个人分支

~~~powershell
git push -u origin feature/your-task
~~~

第一次 push 使用 -u 建立本地分支与远程分支的关联，之后可以直接使用：

~~~powershell
git push
~~~

## 5. Pull Request 怎么写

在 GitHub 上从个人分支创建 Pull Request，目标分支选择 main。标题也使用 Conventional Commits，例如：

~~~text
feat(ui): add schedule list and date filter
~~~

正文至少说明：

~~~markdown
## 做了什么
- 完成了哪些功能或文档变更

## 为什么做
- 对应哪个 Issue 或需求条目

## 如何验证
- 运行了哪些命令
- 结果是什么

## 截图或材料
- GUI 改动附运行截图
- 文档改动说明页码或章节

## 注意事项
- 已知限制、待办事项或需要审查者重点关注的地方
~~~

本项目建议在 PR 中附上：

~~~powershell
uv lock --check
uv run ruff check .
uv run pytest
uv run python -m compileall src
~~~

业务代码完成后，还应补充对应的测试结果；GUI 变化应附测试或运行截图。可以在 PR 描述中使用 Closes #123 关联 Issue。

## 6. 代码审查和沟通规则

### 6.1 发起者

- PR 创建后主动邀请一名合适的审查者，不要只发一句“帮忙看一下”。
- 在 PR 描述中说明改动范围、验证方式和希望审查的重点。
- 收到意见后逐条回复，说明“已修改”“暂不修改的原因”或“需要进一步讨论”。
- 新增修改后，在 PR 中再次说明验证结果，不要让审查者猜测。

### 6.2 审查者

评论应针对代码、文档或需求，不针对个人。推荐使用下面的标签开头：

~~~text
[必须] 不处理会导致功能错误、测试失败或违反需求。
[建议] 可以提升质量，但不一定阻塞本次合并。
[提问] 我没有理解这里的意图，请补充说明。
[认可] 说明具体做得好的地方，帮助团队形成经验。
~~~

审查重点包括：需求是否覆盖、是否引入无关改动、异常情况是否处理、测试是否充分、文档和截图是否同步。审查通过表示改动达到合并标准，不代表作者不能继续改进。

### 6.3 沟通渠道

- Issue：记录任务、缺陷、需求讨论和待办事项。
- Pull Request：讨论具体改动和审查意见，重要结论留在 PR 中。
- GitHub Discussions 或团队群：讨论方案、排期和需要多人参与的问题。
- 紧急问题可以先在群里提醒，再把最终结论补到 Issue/PR，避免关键信息只存在聊天记录里。

沟通时尽量写清楚四件事：当前状态、已经尝试的操作、具体错误、希望别人提供什么帮助。例如：

~~~text
我在 feature/invalid-date 分支运行 uv run pytest 时失败。
已确认 uv sync --dev 成功，错误发生在 test_create_schedule。
当前现象是非法日期没有被拒绝，期望是显示输入提示。
请帮忙确认校验规则是否应放在服务层，而不是 GUI 层。
~~~

## 7. 如何同步主分支和处理冲突

PR 开发时间较长时，先保存自己的修改，再同步最新的 main：

~~~powershell
git status
git add path/to/changed-file
git commit -m "feat(schedule): save current progress"
git fetch origin
git merge origin/main
~~~

如果出现冲突：

1. 执行 git status，确认冲突文件。
2. 打开冲突文件，理解双方修改，再手工保留正确内容。
3. 删除 <<<<<<<、=======、>>>>>>> 等冲突标记。
4. 运行检查和测试。
5. 暂存已解决的文件并完成合并提交。

~~~powershell
git add path/to/resolved-file
git diff --cached
git commit -m "chore: resolve merge conflict"
git push
~~~

不要盲目选择“全部使用我的版本”或“全部使用对方版本”。如果不确定，可以中止本次合并并求助：

~~~powershell
git merge --abort
~~~

只有在团队明确约定、且个人分支没有被别人共同使用时，才考虑 rebase。不要对已经被别人拉取的共享分支执行普通 git push --force。

## 8. 合并后清理

PR 合并后在本地更新 main 并删除已经完成的个人分支：

~~~powershell
git switch main
git pull --ff-only origin main
git branch -d feature/your-task
~~~

如果远程分支没有由 GitHub 自动删除，并且确认没有人再使用它，可以由分支创建者删除：

~~~powershell
git push origin --delete feature/your-task
~~~

## 9. 常见恢复命令

下面的命令可能丢弃本地修改，执行前必须确认目标文件和状态：

~~~powershell
# 撤销暂存，但保留文件修改
git restore --staged path/to/file

# 暂存当前工作，稍后恢复
git stash push -u -m "wip: schedule ui"
git stash list
git stash pop

# 查看本地历史指针，找回误操作前的位置
git reflog
~~~

如果已经提交但尚未 push，先不要继续尝试多个 reset 命令；把 git status、git log --oneline --decorate -5 和 git reflog -5 发给维护者或 AI，请对方先解释风险。

## 10. 明确禁止的操作

- 直接向 main push，或未经沟通修改他人的分支。
- 对 main 使用 git push --force。
- 提交密码、API 密钥、个人隐私、.env、.venv/、.uv-cache/ 和构建缓存。
- 为了“让测试通过”删除失败测试、跳过异常或修改需求。
- 把多个无关功能、格式化全仓库和个人临时修改混在一个 PR 中。
- 复制来源不明的第三方包或素材；使用第三方包时记录版本、来源和许可证。
- 让 AI 在没有明确授权的情况下自动提交、push、关闭 Issue 或合并 PR。

## 11. AI 协作提示词

AI 可以帮助理解仓库、整理计划、检查差异和解释错误，但最终提交者仍然是人。每次让 AI 操作前，先说清楚是“只读分析”还是“允许修改”，不要把密钥、令牌和隐私数据发给 AI。

### 11.1 只读了解仓库

~~~text
请只读分析这个仓库，不修改文件、不提交、不推送。
先阅读 README.md、AGENTS.md、GITHUB_COLLABORATION.md 和 Requests/ 下的需求，
用通俗语言告诉我：项目目标、目录职责、当前分支、当前工作区状态，以及我开始任务前必须运行的命令。
如果发现不确定的地方，请列出问题，不要自行猜测或改文件。
~~~

### 11.2 开始任务前制定计划

~~~text
我准备处理 Issue #<编号>：<任务描述>。
请只做实现计划，不修改文件。
请说明：需要阅读哪些文件、预计修改哪些文件、测试如何覆盖、是否会影响其他人的工作，
并给出建议的分支名和 Conventional Commit 提交信息。
~~~

### 11.3 修改后检查差异

~~~text
请审阅当前工作区和暂存区差异，只读检查，不修改文件。
重点检查：是否有无关改动、是否误改 Requests/、是否包含密钥或缓存、是否符合需求、
是否缺少测试/文档/截图。请按“必须修改、建议修改、已通过”分类，并引用文件路径。
~~~

### 11.4 解释冲突

~~~text
我在执行 Git 合并时遇到冲突。
请先解释每个冲突文件中两边修改的意图和可能影响，不要直接替我选择版本，也不要执行 Git 命令。
等我确认方案后，再给出逐文件的解决步骤和验证命令。
~~~

### 11.5 生成 Pull Request 内容

~~~text
请根据当前分支的 git diff、测试结果和 Issue #<编号>，帮我生成 Pull Request 标题和正文。
不要夸大完成情况，不要虚构测试结果；明确写出未完成事项、已知限制和需要审查者重点关注的地方。
~~~

### 11.6 本项目专用质量检查

~~~text
请按照本项目 AGENTS.md 和 README.md 的规范检查当前改动。
只读执行或建议以下检查：uv lock --check、uv run ruff check .、
uv run pytest、uv run python -m compileall src。
如果当前没有业务代码或测试用例，请明确说明“暂无可检查内容”，不要把空结果描述成已完成。
~~~

## 12. 一页式速查

~~~powershell
# 开始任务
git switch main
git pull --ff-only origin main
git switch -c feature/your-task

# 检查和提交
git status
git diff
git add path/to/file
git diff --cached
git commit -m "type(scope): short description"

# 推送并创建 PR
git push -u origin feature/your-task

# 更新个人分支
git fetch origin
git merge origin/main

# 项目检查
uv lock --check
uv run ruff check .
uv run pytest
uv run python -m compileall src
~~~
