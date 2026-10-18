# `schedule_management` 应用包

日程管理系统的领域模型、服务、存储与图形界面模块。界面层已落地，其余层按三人分工推进。

## 分层与目录约定

| 目录 / 文件 | 归谁 | 职责 | 状态 |
| --- | --- | --- | --- |
| `domain/` | zch | 领域对象与不变量、错误类型 | 未落地 |
| `application/` | zch | 用例编排：解析日期文本、校验、调用仓储 | 未落地 |
| `infrastructure/` | xhy | SQLite 仓储、数据文件位置 | 未落地 |
| `ui/` | ljj | 界面：与呈现无关的交互逻辑 + Qt 窗口适配器 | 已落地（P09 / P10） |
| `dev_stub_service.py` | ljj | 开发期替身服务，真服务到位后删除 | 临时，勿依赖 |

依赖方向单向：`ui` →（端口协议）→ `application` → `domain` ← `infrastructure`。
界面不依赖后端实现，只依赖 `ui/ports.py` 里的两个 Protocol；理由与验收判据见
`docs/figures/ui-interaction.md` 第 11 节。

## 界面层内部的两类模块

- **与呈现无关**：`view_models.py`、`ports.py`、`presenters.py`、`controller.py`。
  不许 import 任何 GUI 框架，也不许 import `sqlite3`——交互规则要能在没有显示
  服务的机器上被完整测试，也要能在换前端时一处不改。
- **窗口适配器**：`app.py`、`main_window.py`、`calendar_view.py`、`date_picker.py`、
  `schedule_form.py`。允许 import `PySide6`，但仍不许碰存储。

这条边界由 `tests/unit/test_ui_layering.py` 用 AST 扫描强制，新增模块必须登记进
两张名单之一，否则守卫会失败。

## 启动

```bash
uv sync                                      # 首次安装运行时依赖（PySide6）
uv run python -m schedule_management.ui.app  # 启动界面
```

GUI 目标平台是 Windows；Linux 端不做界面适配。存储用标准库 `sqlite3`。
