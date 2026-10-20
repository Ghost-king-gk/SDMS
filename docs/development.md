# 开发与验证

本文件承接原 README 中的环境配置、构建、测试、验证结果与架构说明。README 只保留面向使用者的快速开始，开发细节以本文件为准。

## 1. 项目状态与架构

当前 `main` 已经完成：

- **界面层**：`ui/view_models.py`、`ui/ports.py`、`ui/presenters.py`、`ui/controller.py` 与 PySide6 窗口实现（`app.py`、`main_window.py`、`calendar_view.py`、`date_picker.py`、`schedule_form.py`）；
- **服务层**：`application/service.py` 实现 `ScheduleUseCases`，负责用例编排、原始字符串解析与仓储 `bool` 到 `ScheduleNotFoundError` 的翻译；
- **存储层**：`domain/` 的领域对象、`application/contracts.py` 的仓储契约、`infrastructure/sqlite_repository.py` 的 SQLite 适配器；
- **入口**：`ui/app.py` 默认通过 `composition.connect()` + `composition.build_service()` 使用 SQLite，退出时在 `finally` 关闭连接；
- **演示模式**：`main(seed_demo_data=True)` 使用内存替身 `DevStubScheduleService`，只用于截图/演示，不打开数据库。

仍在人工验收中的部分：Windows 真窗口的字体、DPI、原生样式、截图与美术效果。V-14「重启后数据仍在」已由 `scripts/shoot_ui.py` 的真服务场景在真 SQLite 临时库上验过并留截图，机器可判定的 38 项断言全过（32 项界面回归 + 6 项真服务）。

### 分层与依赖方向

```text
ui  ->  application  ->  domain
              ^
       infrastructure（实现 application.contracts.ScheduleRepository）
composition.py（包根，唯一同时认识 application 与 infrastructure 的模块）
```

- 业务规则在 `domain/`，用例编排与输入解析在 `application/`，SQL 与持久化在 `infrastructure/`；
- UI 只通过 `application.contracts.ScheduleUseCases` 调用服务，不直接 import `infrastructure`；
- `composition.py` 是组合根：`connect()` 负责数据库连接，`build_service(connection)` 负责装配；
- `ui/controller.py` 与 `ui/presenters.py` 不 import PySide6，由 `tests/unit/test_ui_layering.py` 用 AST 强制。

### 数据库与连接

- 默认路径由 `composition.default_database_path()` 决定：
  - Windows：`%LOCALAPPDATA%\sdms\schedules.db`，未设置时 `~/AppData/Local/sdms/schedules.db`；
  - macOS：`~/Library/Application Support/sdms/schedules.db`；
  - Linux/其他：`$XDG_DATA_HOME/sdms/schedules.db`，未设置时 `~/.local/share/sdms/schedules.db`。
- `composition.connect(path=None)` 自动创建父目录，`sqlite3.connect(..., timeout=5.0)`；连接归入口所有，由 `main()` 的 `finally` 关闭。
- 一个服务一个连接，只在 GUI 线程使用（`check_same_thread` 默认开启）；仓储不会修改注入连接的 `row_factory`。
- 首次启动是空库，不预置演示数据；演示数据只来自显式 `seed_demo_data=True` 或测试夹具。

## 2. 环境配置

需要安装：

- Python 3.12 或更高版本：由 uv 下载和管理，通常不需要手动安装 Python；
- uv：负责虚拟环境、依赖解析和锁文件；
- Git：版本管理。

Windows 和 Linux 共用同一套 uv 工作流。差异只在安装 uv、虚拟环境路径、激活命令、终端编码、图形显示和截图工具；Python 版本、`uv.lock`、`uv run` 命令、静态检查与测试命令、代码和目录结构在两个平台上一致。

不要向全局 Python 安装本项目依赖。系统 Python 通常受 PEP 668 保护，全局安装既会失败也会污染其他项目。

### Windows 开发环境

以下命令在 PowerShell 中执行。

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

- 换行符已由 `.gitattributes` 约定：普通文本入库为 LF，`*.bat` 和 `*.ps1` 为 CRLF。保持 Git 默认配置即可，不要手工设置 `core.autocrlf`；
- 文件名大小写不敏感：Windows 认为 `Schedule.py` 和 `schedule.py` 是同一个文件，Linux 认为不同。导入名必须与文件名大小写完全一致；
- 路径拼接统一使用 `pathlib.Path`，不要在代码里手写反斜杠字符串。

### Linux 开发环境

以下步骤已在 Ubuntu 26.04 上完整验证。

1. 安装 uv：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

默认安装到 `~/.local/bin`。如果希望安装脚本不修改 shell 配置文件：

```bash
curl -LsSf https://astral.sh/uv/install.sh | env INSTALLER_NO_MODIFY_PATH=1 sh
```

2. 创建虚拟环境并同步依赖：

```bash
uv venv --python 3.12
uv sync --dev --locked
uv run python --version
```

3. 如需显式激活环境：

```bash
source .venv/bin/activate
```

日常建议直接用 `uv run <命令>`，它会自动使用 `.venv`，不必先激活。

4. 图形界面依赖 PySide6（第三方包，由 uv 管理）。本机实测 PySide6 6.12.0 / Qt 6.12.0，包目录约 646.7 MB，首次安装耗时较长。GUI 目标平台是 Windows，Linux 端不做界面适配（理由见 `figures/ui-interaction.md` 第 1.1 节与第 11 节）。

5. Linux 上仍可运行测试、静态检查与后端代码；GUI 验收请在 Windows 桌面会话中进行。

### 平台差异

| 项目 | Windows | Linux |
| --- | --- | --- |
| 安装 uv | 官方 irm 脚本或 winget | 官方 curl 脚本 |
| uv 安装位置 | `%USERPROFILE%\.local\bin` | `~/.local/bin` |
| 虚拟环境解释器 | `.venv\Scripts\python.exe` | `.venv/bin/python` |
| 激活命令 | `.\.venv\Scripts\Activate.ps1` | `source .venv/bin/activate` |
| 终端编码 | 旧版 PowerShell 需 `chcp 65001` | 通常已是 UTF-8 |
| 图形显示 | 桌面会话，界面可用 | 命令行可用，**界面不适配** |
| 截图工具 | Win + Shift + S | gnome-screenshot / grim / import |

结论：平台差异只影响“怎么装、怎么激活、怎么截图”，不影响“怎么写代码、怎么测试”。

### 常见环境问题

| 现象 | 处理方向 |
| --- | --- |
| `uv: command not found` | 确认安装目录在 PATH，并重开终端 |
| 命令用了系统 Python | 统一改用 `uv run <命令>`；确认 `uv run python` 打印的是 `.venv` 内路径 |
| `import PySide6` 失败 | 在仓库根目录运行 `uv sync`；不要在全局环境里 pip install |
| GUI 窗口打不开 | 检查显示环境；无桌面时改用自动化测试或由有桌面的成员截图 |
| 依赖安装失败 | 检查网络与 pypi 可达性，不要用全局 pip 绕过 |
| `uv.lock` 合并冲突 | 不要手改 `uv.lock`，交给 uv 重新解析并评审差异 |

依赖声明以 `pyproject.toml` 为准，精确解析结果以 `uv.lock` 为准。GUI 框架为 **PySide6**（`>=6.11.2,<7.0`，桌面端只做 Windows），存储用标准库 `sqlite3`。

## 3. 项目包与可安装布局

`pyproject.toml` 中 `[tool.uv] package = true`，并声明了 `[build-system]`，因此本项目自身就是一个可安装包，而不只是一堆源码文件。

在 src 布局下，Python 导入时只看 `sys.path`，不会自动搜索 `src/`。如果不把项目安装成包，`tests/` 中的代码就无法 `import schedule_management`，只能靠临时设置 `PYTHONPATH` 掩盖；环境变量与个人机器绑定，无法进仓库、无法复现。

`uv sync` 会以 editable（开发模式）安装本项目：

- `import schedule_management` 在任何工作目录下都可用；
- 源码没有被复制，导入的仍是仓库内的 `src/schedule_management/`，改代码立即生效；
- `uv.lock` 中该项目的条目为 `source = { editable = "." }`。

验证：

```text
uv run python -c "import schedule_management as m; print(m.__file__)"
```

输出应以 `src/schedule_management/__init__.py` 结尾。

构建分发文件：

```text
uv build
```

生成 `dist/` 下的 `.whl` 与 `.tar.gz`。`dist/` 已在 `.gitignore` 中，不会提交。

## 4. 编译与静态检查

Python 项目没有独立的传统编译步骤。提交前使用字节码编译检查和质量工具：

```powershell
uv run python -m compileall src
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

四套命令在 Windows 和 Linux 上完全相同，不需要先激活虚拟环境。`ruff format --check` 只检查格式，不会修改文件；需要自动修复时去掉 `--check`。

## 5. 运行

```bash
uv sync                                   # 首次需要下载 PySide6（约 650 MB）
uv run python -m schedule_management.ui.app
```

Windows 上若不想同时弹出控制台窗口，可用 `pythonw`；调试阶段建议保留控制台以便看到日志。Linux 端不作为 GUI 验收平台；Linux 上仍可跑测试、静态检查与后端代码。

默认入口使用 SQLite，数据库路径见第 1 节；首次启动为空库。`main(seed_demo_data=True)` 只给演示/截图用，走内存替身 `dev_stub_service.py`，不打开数据库、退出即丢：

```bash
uv run python -c "from schedule_management.ui.app import main; main(seed_demo_data=True)"
```

需要复现 [`screenshots/`](screenshots/) 里的图，或把可机器判定的验收项跑一遍：

```bash
uv run python scripts/shoot_ui.py         # 必须在有桌面的 Windows 会话里跑
```

离屏模式（`QT_QPA_PLATFORM=offscreen`）可以创建窗口并抓图，但依赖系统字体；本机有 Noto CJK，所以中文正常。离屏截图只用于验证布局与数据绑定，不能替代 Windows 原生外观验收。

## 6. 测试

测试框架为 pytest，测试目录为 `tests/`：

```text
uv run pytest
uv run pytest --cov=src --cov-report=term-missing
```

当前测试总数 **284**，`mypy src tests` 检查 **44** 个源文件，`ruff format --check` 检查 **68** 个文件。测试命令在两个平台上完全一致。

### 环境门禁

`tests/test_environment.py` 共 9 个用例，验证运行环境和打包配置，而不是业务功能：

| 测试 | 验证内容 |
| --- | --- |
| `test_python_version_meets_requirement` | Python 版本满足 `requires-python >= 3.12` |
| `test_running_inside_virtual_environment` | 测试确实运行在虚拟环境内 |
| `test_required_stdlib_module_importable` | `sqlite3`、`datetime`、`calendar` 能被真正导入 |
| `test_gui_framework_is_importable` | PySide6 能导入且版本落在 `>=6.11.2,<7.0` |
| `test_sqlite3_can_open_in_memory_database` | 能打开内存 SQLite 库并执行查询 |
| `test_project_package_is_importable` | 项目包可导入，且 editable 指向仓库 `src/` |
| `test_installed_version_matches_package_version` | 分发版本与包内 `__version__` 一致 |

环境门禁的作用：在三人各自的机器上，先把“环境或打包配置不对”和“业务代码不对”区分开。

### 业务测试

- 界面层：`test_controller.py`、`test_presenters.py`、`test_ui_layering.py`、`test_dev_stub_service.py`、`test_app_demo_service.py`；
- 存储/服务层：`tests/unit/test_schedule.py`、`tests/unit/test_service.py`、`tests/unit/test_parsing.py`、`tests/contract/`、`tests/integration/`；
- 入口装配：`tests/integration/test_app_entrypoint.py` 验证默认入口打开 SQLite、开箱为空且连接被关闭。

判断真实性的原则：如果某次运行显示 `collected 0 items`，那是“没有测试”而不是“测试通过”；测试通过必须有明确的 `N passed` 和退出码 0。

关于中文标点：`pyproject.toml` 中的 `allowed-confusables` 显式放行了常见中文全角标点。修改这部分配置前请先确认原因，不要为了让某次检查通过而放宽规则。

## 7. 验证结果

下表是 Linux 开发环境下实际执行得到的输出：

| 检查项 | 命令 | 实际结果 |
| --- | --- | --- |
| 操作系统 | `cat /etc/os-release` | Ubuntu 26.04 LTS |
| uv 版本 | `uv --version` | 0.13.1（`~/.local/bin/uv`） |
| Python 版本 | `uv run python --version` | Python 3.12.15 |
| 依赖同步 | `uv sync --frozen --dev` | 通过 |
| 锁文件一致性 | `uv lock --check` | 通过 |
| 代码规范 | `uv run ruff check .` | `All checks passed!` |
| 代码格式 | `uv run ruff format --check .` | `68 files already formatted` |
| 字节码编译 | `uv run python -m compileall -q src tests` | 通过 |
| 项目包导入 | `uv run python -c "import schedule_management as m; print(m.__file__)"` | 指向 `src/schedule_management/__init__.py` |
| PySide6 可用性 | `uv run python -c "import PySide6; print(PySide6.__version__)"` | 6.12.0（Qt 6.12.0） |
| 自动化测试 | `uv run pytest -q` | `284 passed` |
| 类型检查 | `uv run mypy src tests` | `Success: no issues found in 44 source files` |
| 入口冒烟 | `app.main(..., db_path=临时库)` offscreen | 窗口 2 行、退出码 0、关连接重开数据仍在 |

说明：

- `scripts/shoot_ui.py` 用于在 Windows 桌面上生成截图与断言，输出写入 `screenshots/`：32 项界面回归跑内存替身（种子确定、不进磁盘），6 项真服务场景走 `composition.connect() -> build_service()` 真链路 + 临时目录真 SQLite，并产出 `main-window-real-service.png` / `main-window-real-restart.png` 两张真服务截图。
- V-14「重启后数据仍在」已由上述真服务场景验证（关窗、关连接、重开同一库，数据仍在）；Windows 端剩余人工项是字体、DPI 缩放与原生样式在各分辨率下的目视检查。
- Windows 环境结果待拥有 Windows 设备的成员按第 2 节执行后补充，请勿照抄 Linux 数据。

更详细的设计与契约见：

- [`design/contracts.md`](design/contracts.md)
- [`figures/ui-interaction.md`](figures/ui-interaction.md)
- [`design/storage-design.md`](design/storage-design.md)
