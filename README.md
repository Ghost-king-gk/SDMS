# Python 日程管理系统

- zch 已阅
- xhy 已阅
- ljj 已阅


基于 Python 的图形化简易日程管理系统课程项目，需求来源见 [`Requests/`](Requests/)。项目目标是提供日程的添加、查看、修改、删除和按日期查看能力，并对非法输入和异常情况给出友好提示。

## 当前状态

当前提交是项目开发骨架初始化：已建立 `src` 布局、测试和交付文档目录、uv 配置、质量工具配置以及 Git/智能体协作规范。按照本次任务要求，尚未编写业务实现代码。

## 需求摘要

- 图形用户界面：日程列表、日历选择和新增/查看/修改/删除操作。
- 日程字段：标题、日期、时间、备注等必要信息。
- 日期筛选：选择日期后显示当天全部日程。
- 可靠性：校验不合法输入，处理未选中记录、删除确认和异常情况。
- 课程交付：每人 Word 设计文档、组级 PowerPoint、`src/` 下源代码和本 README。

完整需求材料保留在 [`Requests/`](Requests/)，项目侧的整理版见 [`docs/requirements.md`](docs/requirements.md)。

## 目录结构

```text
.
├── AGENT.md / AGENTS.md      # 智能体与开发规范
├── README.md                 # 项目说明
├── Requests/                 # 原始需求，只读
├── pyproject.toml            # 项目元数据与开发工具配置
├── uv.lock                   # uv 依赖锁定文件
├── .python-version           # Python 3.12
├── src/
│   ├── schedule_management/  # 待实现的应用包
│   └── lib/                  # 课程要求的第三方包随源代码提交位置
├── tests/                    # 自动化测试
└── docs/
    ├── design/               # 成员 Word 设计文档
    ├── presentation/         # 组级 PowerPoint
    ├── figures/              # 流程图、示意图、统计图表
    └── screenshots/           # 测试截图
```

## 环境配置

需要安装：

- Python 3.12 或更高版本：由 uv 负责下载和管理，通常不需要手动安装 Python；
- uv：负责虚拟环境、依赖解析和锁文件；
- Git：版本管理。

Windows 和 Linux 共用同一套 uv 工作流。差异只在安装 uv、虚拟环境路径、激活命令、终端编码、图形显示和截图工具；Python 版本、`uv.lock`、`uv run` 命令、静态检查与测试命令、代码和目录结构在两个平台上完全一致。

不要向全局 Python 安装本项目依赖。系统 Python 通常受 PEP 668 保护，全局安装既会失败也会污染其他项目。

### Windows 开发环境

以下命令在 PowerShell 中执行。本轮没有 Windows 机器可以验证，因此本节状态为**待成员验证**；第一次执行后请把实际版本号和结果补到本节。

1. 安装 uv（两种方式任选一种）：

```powershell
# 方式一：官方脚本
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 方式二：winget
winget install --id=astral-sh.uv -e
```

装完重开一个 PowerShell，确认：

```powershell
uv --version
```

如果提示找不到 uv，检查 `%USERPROFILE%\.local\bin` 是否在 PATH 中。

2. 在仓库根目录创建虚拟环境并同步依赖：

```powershell
uv venv --python 3.12
uv sync --dev --locked
uv run python --version
```

`--locked` 表示严格按 `uv.lock` 安装，锁文件不一致会直接报错。这是团队复现环境的一致做法。

3. 如需显式激活环境（多数情况下不需要）：

```powershell
.\.venv\Scripts\Activate.ps1
```

若被执行策略拦住，只对当前会话放开即可，不要改全局策略：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

4. 终端中文与编码：PowerShell 7 默认 UTF-8；旧版 Windows PowerShell 5.1 打印中文可能乱码，先执行：

```powershell
chcp 65001
$env:PYTHONUTF8 = "1"
```

5. 图形界面必须运行在桌面会话中，纯 SSH 或无桌面环境无法显示窗口。

6. 截图使用 Win + Shift + S，另存到 `docs/screenshots/`。

Windows 注意事项：

- 换行符已由 `.gitattributes` 约定：普通文本入库为 LF，`*.bat` 和 `*.ps1` 为 CRLF。保持 Git 默认配置即可，不要手工设置 `core.autocrlf`；如果出现整文件换行差异，先看 `git diff --stat` 再判断，不要盲目提交。
- 文件名大小写不敏感：Windows 认为 `Schedule.py` 和 `schedule.py` 是同一个文件，Linux 认为不同。导入名必须与文件名大小写完全一致，否则会出现“本机通过、别人失败”。
- 路径拼接统一使用 `pathlib.Path`，不要在代码里手写反斜杠字符串。

### Linux 开发环境

以下步骤已在 Ubuntu 26.04 上完整验证，结果见“结果记录”。

1. 安装 uv：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

默认安装到 `~/.local/bin`。如果希望安装脚本不修改 shell 配置文件，可以跳过：

```bash
curl -LsSf https://astral.sh/uv/install.sh | env INSTALLER_NO_MODIFY_PATH=1 sh
```

2. 创建虚拟环境并同步依赖（与 Windows 完全相同的三条命令）：

```bash
uv venv --python 3.12
uv sync --dev --locked
uv run python --version
```

3. 如需显式激活环境（多数情况下不需要）：

```bash
source .venv/bin/activate
```

日常建议直接用 `uv run <命令>`，它会自动使用 `.venv`，不必先激活；这样也不会误用系统 Python。

4. Tkinter 不需要额外安装系统包。uv 下载的 CPython 自带 Tcl/Tk，本机实测 `import tkinter` 成功，Tk 版本 9.0。只有改用系统 Python（而非 uv 环境）时，才需要安装发行版包，例如 Debian/Ubuntu 的 `python3-tk`。

5. 图形界面需要 X11 或 Wayland 会话，检查显示环境：

```bash
echo "$DISPLAY $WAYLAND_DISPLAY"
```

本机结果：`DISPLAY=:0`、`WAYLAND_DISPLAY=wayland-0`，窗口可以正常创建。在服务器、容器或无 X 转发的环境下无法显示窗口，此时不要把“GUI 起不来”当成业务代码错误。

6. 截图可用 `gnome-screenshot`、Wayland 下的 `grim` 或 ImageMagick 的 `import`，保存到 `docs/screenshots/`。

### 两个平台的差异对照

| 项目 | Windows | Linux |
| --- | --- | --- |
| 安装 uv | 官方 irm 脚本或 winget | 官方 curl 脚本 |
| uv 安装位置 | `%USERPROFILE%\.local\bin` | `~/.local/bin` |
| 虚拟环境解释器 | `.venv\Scripts\python.exe` | `.venv/bin/python` |
| 激活命令 | `.\.venv\Scripts\Activate.ps1` | `source .venv/bin/activate` |
| 终端编码 | 旧版 PowerShell 需 `chcp 65001` | 通常已是 UTF-8 |
| 图形显示 | 桌面会话 | 需要 `DISPLAY` 或 `WAYLAND_DISPLAY` |
| 截图工具 | Win + Shift + S | gnome-screenshot / grim / import |

结论：平台差异只影响“怎么装、怎么激活、怎么截图”，不影响“怎么写代码、怎么测试”。任何人都不应把只适用于自己系统的变体写进 README 的通用命令。

### 常见环境问题

| 现象 | 处理方向 |
| --- | --- |
| `uv: command not found` | 确认安装目录在 PATH，并重开终端 |
| 命令用了系统 Python | 统一改用 `uv run <命令>`；确认 `uv run python` 打印的是 `.venv` 内路径 |
| `import tkinter` 失败 | 确认在 uv 环境中；若确实用系统 Python 则安装 `python3-tk` |
| GUI 窗口打不开 | 检查显示环境；无桌面时改用自动化测试或由有桌面的成员截图 |
| 依赖安装失败 | 检查网络与 pypi 可达性，不要用全局 pip 绕过 |
| `uv.lock` 合并冲突 | 不要手改 `uv.lock`，交给 uv 重新解析并评审差异 |

本项目的依赖声明以 `pyproject.toml` 为准，精确解析结果以 `uv.lock` 为准。GUI 框架尚未选定，因此当前没有运行时第三方 GUI 依赖；实现阶段应在设计文档中记录 Tkinter 或 PyQt 的选择及其依赖处理方式。

## 编译与静态检查

Python 项目没有独立的传统编译步骤。提交前使用字节码编译检查和质量工具：

```powershell
uv run python -m compileall src
uv run ruff check .
uv run mypy src
```

当实现可安装的应用包后，再根据最终入口补充打包/构建命令；当前骨架不包含可运行入口。

下面四套命令在 Windows 和 Linux 上完全相同，不区分平台，也不需要先激活虚拟环境：

```text
uv run python -m compileall src
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

其中 `ruff format --check` 只检查格式是否符合统一风格，不会修改文件；需要自动修复时去掉 `--check` 再执行。

## 运行

业务入口将在实现阶段确定，并同步更新本节。统一使用 uv 执行，避免调用错误的全局 Python：

```text
uv run <项目启动命令>
```

平台相关提醒：

- 两个平台都使用同一个启动命令，不要为 Windows 单独写一套入口。
- Windows 上如果用窗口方式启动，可用 `pythonw` 避免弹出控制台窗口；调试阶段仍建议保留控制台以便看到日志。
- Linux 上启动 GUI 前确认显示环境可用（见“环境配置”中的检查命令）。

当前阶段没有可运行的日程管理模块，不能以占位命令宣称系统已完成。

## 测试

测试框架已配置为 pytest，测试目录为 `tests/`：

```text
uv run pytest
uv run pytest --cov=src --cov-report=term-missing
```

测试命令在两个平台上完全一致。当前 `tests/` 已包含环境门禁测试 `tests/test_environment.py`，它验证的是运行环境而不是业务功能：

| 测试 | 验证内容 |
| --- | --- |
| `test_python_version_meets_requirement` | Python 版本满足 `requires-python >= 3.12` |
| `test_running_inside_virtual_environment` | 测试确实运行在虚拟环境内，而不是系统 Python |
| `test_required_stdlib_module_importable` | `tkinter`、`sqlite3`、`datetime`、`calendar` 能被真正导入 |
| `test_sqlite3_can_open_in_memory_database` | 能打开内存 SQLite 库并执行一次查询 |

环境门禁测试的作用：在三人各自的 Windows / Linux 机器上，先把“环境不对”和“代码不对”区分开。环境缺少 Tkinter 时，失败信息会直接指出解释器路径，而不是让程序在打开窗口时抛出难以理解的异常。

业务测试（新增、按日期查询、修改、删除、删除确认、空/非法输入、未选中记录和异常提示）尚未编写，由各模块作者按模块补充。约定位置为 `tests/unit/`、`tests/contract/`、`tests/integration/`。GUI 测试结果与截图归档到 `docs/screenshots/`，并记录操作系统与 Python/Tk 版本、前置数据、操作步骤、预期结果和实际结果。

判断真实性的原则：如果某次运行显示 `collected 0 items`，那是“没有测试”而不是“测试通过”；测试通过必须有明确的 `N passed` 和退出码 0。

关于中文标点：`pyproject.toml` 中的 `allowed-confusables` 显式放行了常见中文全角标点，因为本项目的注释、文档字符串和用户提示都使用中文。修改这部分配置前请先确认原因，不要为了让某次检查通过而放宽规则。

## 结果记录

环境状态使用以下命令记录，两个平台一致：

```text
uv run python --version
uv lock --check
git status --short --branch
```

### 已验证的环境结果

下表是 Linux 开发环境下实际执行得到的输出，作为团队复现的参照基线：

| 检查项 | 命令 | 实际结果 |
| --- | --- | --- |
| 操作系统 | `cat /etc/os-release` | Ubuntu 26.04 LTS |
| uv 版本 | `uv --version` | 0.12.13（`~/.local/bin/uv`） |
| Python 版本 | `uv run python --version` | Python 3.12.14 |
| 依赖同步 | `uv sync --dev --locked` | 14 个包，锁文件无需变更 |
| 锁文件一致性 | `uv lock --check` | 通过 |
| 代码规范 | `uv run ruff check .` | `All checks passed!` |
| 代码格式 | `uv run ruff format --check .` | `16 files already formatted` |
| 字节码编译 | `uv run python -m compileall -q src tests` | 通过 |
| Tkinter 可用性 | `uv run python -c "import tkinter; print(tkinter.TkVersion)"` | 成功，Tk 9.0 |
| 窗口创建 | `tkinter.Tk()` 后 `destroy()` | 成功（`DISPLAY=:0`） |
| 自动化测试 | `uv run pytest -q` | `7 passed`，退出码 0（环境门禁测试） |
| 类型检查 | `uv run mypy src` | `src` 下暂无 `.py` 文件，**不算通过** |

类型检查一行仍是空集，必须如实说明：`src/` 目录下目前只有说明文档，还没有任何 `.py` 文件，因此 `uv run mypy src` 只能报告“没有可检查的文件”。这不代表类型检查通过，也不代表类型配置有问题——等第一个业务模块（`src/schedule_management/`）落地后，本行才会有真实结果。

Windows 环境结果待拥有 Windows 设备的成员按“Windows 开发环境”步骤执行后补充，请勿照抄上面的数据。

业务完成后的结果应补充功能清单、测试数量与通过情况、已知限制和运行截图；不要把“工程骨架已建立”写成“功能已实现”。

## GitHub 多人协作快速指南

第一次参与 GitHub 协作时，只记住这条主线：从 main 更新代码，创建个人分支，在个人分支完成一个清晰的小任务，提交并 push，然后通过 Pull Request 请求审查和合并。不要直接修改或 push main。

完整协议见 [GITHUB_COLLABORATION.md](GITHUB_COLLABORATION.md)，其中包含 Git/GitHub 基础概念、分支命名、提交格式、Issue/PR 沟通、冲突处理、恢复命令和 AI 协作提示词。

### 新人常用命令

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

### Pull Request 提交前

PR 应说明改动内容、对应 Issue/需求、验证方式、测试结果和已知限制。GUI 改动附运行或测试截图，文档改动注明对应章节。建议运行：

~~~powershell
uv lock --check
uv run ruff check .
uv run pytest
uv run python -m compileall src
~~~

### 可以直接复制给 AI 的提示词

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

## 交付材料

- `docs/design/`：每位成员一份 Word 设计文档，正文不少于 20 页（附录不计入），清楚标注分工并包含流程图、示意图、统计图表和测试截图。
- `docs/presentation/`：每组一份不少于 20 页的 PowerPoint，首页列出按贡献排序的姓名和学号，页内标注具体贡献。
- `src/`：全部 Python 源代码；如使用并随作业提交第三方包，按要求放入 `src/lib/` 并记录许可证和版本。
- `README.md`：持续维护环境配置、编译/检查、运行、测试和结果说明。

更详细的协作约定见 [`AGENTS.md`](AGENTS.md)。
