"""环境门禁测试。

本文件只验证运行环境和打包配置是否满足项目要求，不验证任何业务功能。

存在的意义：当环境或打包配置不满足要求时，先在环境层给出明确失败，而不是让问题以
"导入报错""窗口打不开""文件没写入"等形式出现在业务代码里，浪费排查时间。
在三人各自不同的 Windows / Linux 机器上，这些测试是最先运行、最容易解释的一层。

业务测试（日程的新增、查询、修改、删除和异常处理）由各模块作者按模块补充，
不要写进本文件。
"""

import importlib
import sqlite3
import sys
from contextlib import closing
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pytest

# 与 pyproject.toml 的 requires-python 和仓库根目录 .python-version 保持一致。
MINIMUM_PYTHON: tuple[int, int] = (3, 12)

# 本项目计划使用的标准库能力：GUI、持久化、日期时间处理、日历网格。
REQUIRED_STDLIB_MODULES = ("tkinter", "sqlite3", "datetime", "calendar")


def test_python_version_meets_requirement() -> None:
    """Python 版本必须满足项目声明的最低要求。"""
    assert sys.version_info[:2] >= MINIMUM_PYTHON, (
        f"项目要求 Python {MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]} 或更高，"
        f"当前为 {sys.version.split()[0]}（解释器：{sys.executable}）"
    )


def test_running_inside_virtual_environment() -> None:
    """测试必须运行在项目虚拟环境内，避免误用系统 Python 掩盖环境问题。"""
    assert sys.prefix != sys.base_prefix, (
        f"测试运行在系统解释器而不是虚拟环境中：{sys.executable}。请使用 uv run pytest 运行测试。"
    )


@pytest.mark.parametrize("module_name", REQUIRED_STDLIB_MODULES)
def test_required_stdlib_module_importable(module_name: str) -> None:
    """要求的标准库模块必须能被真正导入，而不只是存在文件。"""
    try:
        importlib.import_module(module_name)
    except ImportError as exc:
        pytest.fail(f"当前解释器无法导入 {module_name}：{exc}（解释器：{sys.executable}）")


def test_sqlite3_can_open_in_memory_database() -> None:
    """验证计划使用的持久化能力真的可用，而不只是模块存在。

    注意：sqlite3 连接对象用作 with 上下文管理器时只提交/回滚事务，并不会关闭连接，
    因此这里使用 contextlib.closing 确保连接被释放。
    """
    with closing(sqlite3.connect(":memory:")) as connection:
        assert connection.execute("select 1").fetchone() == (1,)


def test_project_package_is_importable() -> None:
    """项目包必须能被导入。

    这是所有业务测试和类型检查的前提。本测试失败说明 pyproject.toml 的
    src 布局或打包配置有问题，而不是业务代码有问题。
    """
    package = importlib.import_module("schedule_management")
    assert package.__file__ is not None, "包没有对应的源文件路径"

    # 以路径层级判断，避免依赖平台相关的分隔符（Windows 用反斜杠）。
    source = Path(package.__file__).resolve()
    assert source.parent.name == "schedule_management", f"导入到了意外的位置：{source}"
    assert source.parent.parent.name == "src", (
        f"应以 editable 方式指向仓库 src 目录，实际为：{source}"
    )


def test_installed_version_matches_package_version() -> None:
    """分发版本必须与包内 __version__ 一致。

    版本号写在两处（pyproject.toml 与 __init__.py），本测试防止两处漂移：
    否则会出现"安装的是 0.1.0，导入报的却是别的版本"这类难以察觉的问题。
    """
    package = importlib.import_module("schedule_management")
    try:
        installed = version("schedule-management-system")
    except PackageNotFoundError:
        pytest.fail("项目尚未作为可安装包装入当前环境，请先运行 uv sync --dev --locked")

    assert installed == package.__version__, (
        f"pyproject.toml 声明 {installed}，包内声明 {package.__version__}"
    )
