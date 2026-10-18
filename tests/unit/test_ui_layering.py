"""界面层的分层守卫：用 AST 扫描源码，而不是靠自觉。

controller 与 presenters 一旦不小心 import 了 `PySide6` 或 `tkinter`，
在这台有图形界面的 Windows 机器上**测试照样会通过**——但换到没有显示服务的
环境（CI、服务器、纯命令行会话）就会在收集阶段直接挂掉，而且报错信息跟业务
毫无关系。与其事后排查，不如在这里挡住。

这条守卫同时也是「前端可替换」的地基：交互规则不依附于任何一种呈现技术，
将来才能在不碰 `controller.py` 与 `presenters.py` 的前提下换掉呈现方式
（见 `docs/figures/ui-interaction.md` 第 11 节）。

P10 把真正的 Qt 窗口写了进来，守卫因此按**角色**而不是按路径一刀切：

- 与呈现无关的那几个模块（下表 `VIEW_AGNOSTIC_MODULES`）连 GUI 框架都不许碰；
- 窗口适配器天然需要 Qt，允许 `PySide6`，但仍然是界面，**不许碰数据库**；
- 任何 ui 模块都必须在这两张名单里，新增一个没有被归类的模块会让测试失败——
  宁可让人多登记一行，也不让"不知道归哪类"的模块悄悄溜过守卫。

`sqlite3` 是全包红线：界面层不许碰存储，这条是分工的红线而不是风格偏好，
不因为某个模块是窗口就放宽。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import schedule_management

_PACKAGE_ROOT = schedule_management.__file__
assert _PACKAGE_ROOT is not None, "包必须有源文件路径，否则守卫测试本身失效"
UI_PACKAGE = Path(_PACKAGE_ROOT).parent / "ui"

#: 与呈现方式无关的模块：只有这些粒度上的东西才要求"换前端一处不用改"。
VIEW_AGNOSTIC_MODULES = frozenset(
    {"__init__.py", "view_models.py", "ports.py", "presenters.py", "controller.py"}
)

#: 窗口适配器：允许 import `PySide6`，因为它们就是把端口接到 Qt 控件上。
WINDOW_MODULES = frozenset(
    {"app.py", "main_window.py", "calendar_view.py", "date_picker.py", "schedule_form.py"}
)

GUI_FRAMEWORKS = ("PySide6", "tkinter")
STORAGE_MODULES = ("sqlite3",)

#: 两张名单的并集，用于"是否都登记了"那条检查。
CLASSIFIED_MODULES = VIEW_AGNOSTIC_MODULES | WINDOW_MODULES

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


def test_every_ui_module_is_explicitly_classified() -> None:
    """每个模块都必须落在其中一张名单里。

    这条是守卫的"入口关"：新加的模块如果没人归类，上面的名单会把它漏掉，
    后面的检查也就不会跑。宁可逼出一行登记，也不留"不知道归哪类"的模块。
    """
    unclassified = sorted(p.name for p in ALL_UI_MODULES if p.name not in CLASSIFIED_MODULES)
    assert not unclassified, (
        f"这些模块没有被归类，守卫检查不到它们：{unclassified}。"
        f"请把它们加进 VIEW_AGNOSTIC_MODULES（与呈现无关）或 WINDOW_MODULES（Qt 适配器）。"
    )


@pytest.mark.parametrize("module_name", sorted(VIEW_AGNOSTIC_MODULES))
@pytest.mark.parametrize("forbidden", GUI_FRAMEWORKS + STORAGE_MODULES)
def test_view_agnostic_module_stays_ui_framework_free(module_name: str, forbidden: str) -> None:
    """界面逻辑不许依赖任何一种 GUI 框架。

    这条一旦破了，测试用例就得在有显示服务的机器上跑，换前端也得重写交互规则。
    """
    module_path = UI_PACKAGE / module_name
    assert module_path.exists(), f"{module_name} 不存在，名单本身写错了"

    imported = imported_toplevel_names(module_path.read_text(encoding="utf-8"))
    assert forbidden not in imported, (
        f"{module_name} 不应在导入期依赖 {forbidden}："
        "交互规则必须与呈现方式无关，才能在换掉前端时一处不用改"
        "（ui-interaction.md 第 11 节）。GUI 只允许出现在窗口适配器里。"
    )


@pytest.mark.parametrize("module_path", ALL_UI_MODULES, ids=lambda path: path.name)
def test_no_ui_module_touches_storage(module_path: Path) -> None:
    """界面层不许碰存储，窗口也不行。

    这条不因为"它是窗口"就放宽：碰到 SQL 的那一刻，分工边界就被打破了。
    """
    imported = imported_toplevel_names(module_path.read_text(encoding="utf-8"))
    assert "sqlite3" not in imported, (
        f"{module_path.name} 不应直接依赖 sqlite3："
        "存储与检索归 infrastructure，界面只通过端口拿数据。"
    )


@pytest.mark.parametrize("module_name", sorted(WINDOW_MODULES))
def test_window_adapter_declares_its_qt_dependency(module_name: str) -> None:
    """登记成 Qt 适配器的模块应当确实注册在 View agnostic 之外。

    反向核对：别把"与呈现无关"的模块随手塞进窗口名单来绕过上一条检查。
    """
    assert module_name not in VIEW_AGNOSTIC_MODULES, (
        f"{module_name} 同时出现在两张名单里，守卫会自相矛盾"
    )


def test_ui_core_modules_import_cleanly() -> None:
    """能干净地导入，即导入期没有副作用：不开窗口、不连库、不读环境变量。"""
    from schedule_management.ui import controller, presenters

    assert callable(controller.ScheduleController)
    assert callable(presenters.describe_error)
