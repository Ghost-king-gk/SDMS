"""程序入口：整个进程里唯一创建 `QApplication` 的地方。

第 7 节的硬约束：`QApplication` 只能出现在 `main()` 里，任何模块的导入期都不得
创建窗口。写成模块级 `app = QApplication([])` 会污染 import——pytest 一收集就
可能触发窗口创建，在没有显示服务的环境里直接失败。

这里是唯一知道"用哪个服务和哪个窗口"的地方：

- 服务注入 `DevStubScheduleService`（开发替身），真人版 `application/service.py`
  落地后，换掉这一处即可，界面与 controller 一行不改；
- 时钟注入 `dt.date.today`，测试与截图脚本可以换成固定日期。
"""

from __future__ import annotations

import datetime as dt
import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication

from schedule_management.dev_stub_service import DevStubScheduleService

from .main_window import MainWindow
from .ports import ScheduleServicePort, TodayProvider


def build_service(*, seed_demo_data: bool, today: dt.date) -> ScheduleServicePort:
    """装配一个服务。**真后端落地时只需要改这一个函数。**"""
    if not seed_demo_data:
        return DevStubScheduleService()

    service = DevStubScheduleService()
    service.seed_defaults(today)
    return service


def main(
    argv: Sequence[str] | None = None,
    *,
    seed_demo_data: bool = True,
    today: dt.date | None = None,
    clock: TodayProvider | None = None,
) -> int:
    """跑起图形界面。`today` / `clock` 只给脚本用，让人能固定第一天。"""
    arguments = list(sys.argv[1:] if argv is None else argv)
    app = QApplication(arguments)

    resolved_clock = clock or (lambda: today or dt.date.today())
    service = build_service(seed_demo_data=seed_demo_data, today=resolved_clock())

    window = MainWindow(service=service, clock=resolved_clock)
    window.show()
    return app.exec()


__all__ = ["build_service", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
