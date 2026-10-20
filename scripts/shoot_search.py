"""离屏重拍搜索页截图：固定 today=2026-10-20，预置 5 条跨日数据后搜索「周报」。

用法：

    QT_QPA_PLATFORM=offscreen uv run python scripts/shoot_search.py

只用于 Linux 容器里的布局复核：容器装有 Noto Sans CJK，中文不会变成方块。
它**不能替代** Windows 真机验收（字体、DPI、原生样式仍要人工看）。

数据刻意覆盖三种情形：今天两条（含全天）、次日两条、第 6 天一条。这样一张图
能同时看到日历徽标、搜索结果表格与「接下来 7 天」摘要的相对位置。
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QTableView

from schedule_management.dev_stub_service import DevStubScheduleService
from schedule_management.ui.main_window import MainWindow

TODAY = dt.date(2026, 10, 20)
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "docs" / "screenshots"

#: (相对今天的天数, 时间文本, 标题, 备注)；时间留空表示全天。
_SEED: tuple[tuple[int, str, str, str], ...] = (
    (0, "09:30", "写周报", "整理本周进展，周五前发"),
    (0, "", "整理课程笔记", "全天，不限时间"),
    (1, "08:00", "体检", "空腹"),
    (1, "15:00", "周报终稿", "给导师过一遍"),
    (6, "", "下周计划", ""),
)


def _seed_service() -> DevStubScheduleService:
    service = DevStubScheduleService()
    for offset, time_text, title, notes in _SEED:
        service.create_schedule(
            title, (TODAY + dt.timedelta(days=offset)).isoformat(), time_text, notes
        )
    return service


def _settle(app: QApplication, rounds: int = 5) -> None:
    for _ in range(rounds):
        app.processEvents()


def _check(condition: bool, message: str) -> None:
    """截图脚本也要自检：布局退化时先让脚本红，而不是生成一张坏图。"""
    if not condition:
        raise SystemExit(f"布局自检失败：{message}")


def _report(window: MainWindow) -> None:
    panel = window._calendar
    calendar_view = panel.findChild(QTableView)
    rows = [calendar_view.rowHeight(row) for row in range(6)] if calendar_view else []
    print(f"窗口：{window.width()}x{window.height()}")
    print(f"日历面板：{panel.height()}px，月历控件：{panel._calendar.height()}px")
    print(f"日期行高：{rows}")
    print(f"表格：{window._table.height()}px，摘要列表：{window._upcoming_list.height()}px")
    print(f"搜索结果：{window._table.rowCount()} 行；摘要：{window._upcoming_list.count()} 条")


def _save(window: MainWindow, name: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / name
    if not window.grab().save(str(path)):
        raise SystemExit(f"截图保存失败：{path}")
    return path


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow(service=_seed_service(), clock=lambda: TODAY)
    window.resize(1040, 680)
    window.show()
    _settle(app)

    # 主题存在 QSettings 里，先显式回到浅色，避免上一次运行留下的深色状态。
    window._on_dark_toggled(False)
    window._search_input.setText("周报")
    window._trigger_search()
    _settle(app)

    _check(window._table.rowCount() == 2, f"搜索「周报」应有 2 行，实际 {window._table.rowCount()}")
    _check(
        window._upcoming_list.count() == 5,
        f"未来 7 天应有 5 条，实际 {window._upcoming_list.count()}",
    )
    _check(window._calendar.height() >= 360, f"日历面板被压到 {window._calendar.height()}px")
    _check(
        110 <= window._upcoming_list.height() <= 170,
        f"摘要列表高度 {window._upcoming_list.height()}px 不在 110 到 170 之间",
    )

    _report(window)
    print(f"浅色截图：{_save(window, 'search-light-2026-10-20.png')}")

    window._on_dark_toggled(True)
    _settle(app)
    print(f"深色截图：{_save(window, 'search-dark-2026-10-20.png')}")

    window.close()
    return 0


__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
