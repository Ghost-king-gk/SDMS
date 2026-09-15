"""环境门禁测试。

本文件只验证运行环境是否满足项目要求，不验证任何业务功能。

存在的意义：当环境不满足要求时，先在环境层给出明确失败，而不是让问题以
"导入报错""窗口打不开""文件没写入"等形式出现在业务代码里，浪费排查时间。
在三人各自不同的 Windows / Linux 机器上，这些测试是最先运行、最容易解释的一层。

业务测试（日程的新增、查询、修改、删除和异常处理）由各模块作者按模块补充，
不要写进本文件。
"""

import importlib
import sqlite3
import sys
from contextlib import closing

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
