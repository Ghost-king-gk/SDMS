# Python 日程管理系统

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

- Python 3.12 或更高版本；
- uv；
- Git。

推荐使用 uv 在项目根目录初始化并同步环境：

```powershell
uv venv --python 3.12
uv sync --dev
uv run python --version
```

如需显式激活环境（PowerShell）：

```powershell
.\.venv\Scripts\Activate.ps1
```

本项目的依赖声明以 `pyproject.toml` 为准，精确解析结果以 `uv.lock` 为准。GUI 框架尚未选定，因此当前没有运行时第三方 GUI 依赖；实现阶段应在设计文档中记录 Tkinter 或 PyQt 的选择及其依赖处理方式。

## 编译与静态检查

Python 项目没有独立的传统编译步骤。提交前使用字节码编译检查和质量工具：

```powershell
uv run python -m compileall src
uv run ruff check .
uv run mypy src
```

当实现可安装的应用包后，再根据最终入口补充打包/构建命令；当前骨架不包含可运行入口。

## 运行

业务入口将在实现阶段确定，并同步更新本节。建议统一使用 uv 执行，避免调用错误的全局 Python：

```powershell
uv run <项目启动命令>
```

当前阶段没有可运行的日程管理模块，不能以占位命令宣称系统已完成。

## 测试

测试框架已配置为 pytest，测试目录为 `tests/`：

```powershell
uv run pytest
uv run pytest --cov=src --cov-report=term-missing
```

业务实现后，测试至少应覆盖：新增、按日期查询、修改、删除、删除确认、空/非法输入、未选中记录和异常提示。GUI 测试结果与截图归档到 `docs/screenshots/`。

## 结果记录

初始化完成后，使用以下命令记录环境和仓库状态：

```powershell
uv run python --version
uv lock --check
git status --short --branch
```

业务完成后的结果应补充功能清单、测试数量与通过情况、已知限制和运行截图；不要把“工程骨架已建立”写成“功能已实现”。

## 交付材料

- `docs/design/`：每位成员一份 Word 设计文档，正文不少于 20 页（附录不计入），清楚标注分工并包含流程图、示意图、统计图表和测试截图。
- `docs/presentation/`：每组一份不少于 20 页的 PowerPoint，首页列出按贡献排序的姓名和学号，页内标注具体贡献。
- `src/`：全部 Python 源代码；如使用并随作业提交第三方包，按要求放入 `src/lib/` 并记录许可证和版本。
- `README.md`：持续维护环境配置、编译/检查、运行、测试和结果说明。

更详细的协作约定见 [`AGENTS.md`](AGENTS.md)。
