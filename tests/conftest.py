"""测试级的环境隔离。

只有一件事：**别让测试写进用户真正的配置**。

窗口几何、分栏位置、列宽、排序、主题开关都存在 `QSettings("SDMS", "SDMS")`，
Windows 上默认落到注册表。测试每开一次窗口就会 `close()` 一次，每次 close 都会
把窗口状态写回去——不隔离的话，跑一次 pytest 就把用户调好的窗口布局重置成
测试用的 1040x680，而且下次启动会"记住"这个被覆盖的值。
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

# 必须在任何测试模块 import PySide6 之前设好：offscreen 平台没有窗口系统。
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def pytest_configure() -> None:
    """把 QSettings 落到临时目录，格式用 INI（不需要注册表权限）。"""
    from PySide6.QtCore import QSettings

    root = Path(tempfile.gettempdir()) / "sdms-pytest-qsettings"
    root.mkdir(parents=True, exist_ok=True)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(root))


@pytest.fixture(autouse=True)
def isolated_settings() -> Iterator[None]:
    """每个测试都从"什么都没存过"开始。

    窗口关掉时会把几何、分栏、列宽、排序写回 QSettings，同一个 session 里的
    下一个测试就会继承上一个测试留下的排序方向——那不是被测行为，是状态泄漏。
    这里在每个测试前清一次，让"启动时的默认状态"始终是真的默认。
    """
    from PySide6.QtCore import QSettings

    settings = QSettings("SDMS", "SDMS")
    settings.clear()
    settings.sync()
    yield
