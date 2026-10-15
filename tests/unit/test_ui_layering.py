"""界面层的分层守卫：用 AST 扫描源码，而不是靠自觉。

controller 与 presenters 一旦不小心 import 了 `PySide6` 或 `tkinter`，
在这台有图形界面的 Windows 机器上**测试照样会通过**——但换到没有显示服务的
Linux CI（或者组长的机器上）就会在收集阶段直接挂掉，而且报错信息跟业务毫无关系。
与其事后排查，不如在这里挡住。

同理挡住 `sqlite3`：界面层不能碰存储，这条是分工的红线而不是风格偏好。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import schedule_management

_PACKAGE_ROOT = schedule_management.__file__
assert _PACKAGE_ROOT is not None, "包必须有源文件路径，否则守卫测试本身失效"
UI_PACKAGE = Path(_PACKAGE_ROOT).parent / "ui"
FORBIDDEN_MODULES = ("PySide6", "tkinter", "sqlite3")

ALL_UI_MODULES = sorted(UI_PACKAGE.glob("*.py"))


def imported_toplevel_names(source: str) -> set[str]:
    """收集源码里所有 import 的顶层模块名（`from x.y import z` 只取 `x`）。"""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_ui_package_has_modules_to_check() -> None:
    assert ALL_UI_MODULES, "ui 包里没有找到模块，守卫测试本身失效了"


@pytest.mark.parametrize("module_path", ALL_UI_MODULES, ids=lambda path: path.name)
@pytest.mark.parametrize("forbidden", FORBIDDEN_MODULES)
def test_ui_module_does_not_import_forbidden_runtime(module_path: Path, forbidden: str) -> None:
    source = module_path.read_text(encoding="utf-8")

    assert forbidden not in imported_toplevel_names(source), (
        f"{module_path.name} 不应在导入期依赖 {forbidden}："
        "界面逻辑必须能在没有显示服务、没有数据库的机器上被测试。"
        "Qt/SQL 只允许出现在窗口适配器与基础设施模块里。"
    )


def test_ui_core_modules_import_cleanly() -> None:
    """能干净地导入，即导入期没有副作用：不开窗口、不连库、不读环境变量。"""
    from schedule_management.ui import controller, presenters

    assert callable(controller.ScheduleController)
    assert callable(presenters.describe_error)
