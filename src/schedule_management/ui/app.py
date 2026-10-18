"""程序入口：整个进程里唯一创建 `QApplication` 的地方，也是组合根的使用者。

第 7 节的硬约束：`QApplication` 只能出现在 `main()` 里，任何模块的导入期都不得
创建窗口。写成模块级 `app = QApplication([])` 会污染 import——pytest 一收集就
可能触发窗口创建，在没有显示服务的环境里直接失败。

默认入口走真实后端：`composition.connect()` 打开（必要时创建）SQLite 数据库，
`composition.build_service()` 在连接上装配仓储与服务，窗口关闭后由 `main()` 的
`finally` 关闭连接。数据库路径由 `composition.default_database_path()` 决定，
首次启动是空库；`main(seed_demo_data=True)` 只给演示/截图用，此时改用内存里的
`DevStubScheduleService`，不打开任何数据库文件。
"""

from __future__ import annotations

import datetime as dt
import sys
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtWidgets import QApplication

from schedule_management import composition
from schedule_management.dev_stub_service import DevStubScheduleService

from .main_window import MainWindow
from .ports import ScheduleServicePort, TodayProvider


def build_demo_service(today: dt.date) -> ScheduleServicePort:
    """装配演示用服务：内存替身加 5 条虚构种子数据。

    仅供截图和答辩演示；数据退出即丢，不是默认入口，也不写 SQLite。
    """
    service = DevStubScheduleService()
    service.seed_defaults(today)
    return service


def _run_window(app: QApplication, service: ScheduleServicePort, clock: TodayProvider) -> int:
    """创建并显示主窗口，进入 Qt 事件循环；两条入口路径共用。"""
    window = MainWindow(service=service, clock=clock)
    window.show()
    return app.exec()


def main(
    argv: Sequence[str] | None = None,
    *,
    seed_demo_data: bool = False,
    today: dt.date | None = None,
    clock: TodayProvider | None = None,
    db_path: Path | None = None,
) -> int:
    """跑起图形界面。

    默认使用真实服务并写入 SQLite；`seed_demo_data=True` 时改用内存替身，
    但不打开数据库。`today` / `clock` 只给脚本和测试用，让人能固定“今天”；
    `db_path` 透传给 `composition.connect()`，测试可注入临时路径。
    """
    arguments = list(sys.argv[1:] if argv is None else argv)
    app = QApplication(arguments)

    resolved_clock = clock or (lambda: today or dt.date.today())

    if seed_demo_data:
        service = build_demo_service(resolved_clock())
        return _run_window(app, service, resolved_clock)

    connection = composition.connect(db_path)
    try:
        service = composition.build_service(connection)
        return _run_window(app, service, resolved_clock)
    finally:
        connection.close()


__all__ = ["build_demo_service", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
