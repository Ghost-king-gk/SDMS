"""窗口层冒烟测试：日期列、搜索标题、未来 7 天列表与点击跳转。

这些行为只有把真控件建出来才看得见：列头与列宽、`DayHeading` 的文案、
摘要列表的条目与点击后的联动。controller 单测覆盖调用规则，这里覆盖
“规则确实接到了控件上”，两者不重复。

运行在 offscreen 平台，不需要桌面会话；中文字体是否存在不影响断言，
因为这里只读文本与数据角色，不比较像素。
"""

from __future__ import annotations

import datetime as dt
import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTableWidget,
)

from schedule_management.ui.main_window import MainWindow
from tests.unit.ui_fakes import FakeScheduleService, StubSchedule

TODAY = dt.date(2026, 10, 20)
TOMORROW = dt.date(2026, 10, 21)
NEXT_WEEK = dt.date(2026, 10, 26)


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication([])
    yield app


def build_window() -> tuple[MainWindow, FakeScheduleService]:
    service = FakeScheduleService(
        (
            StubSchedule(id="today", title="写周报", date=TODAY, time=dt.time(9, 30), notes=""),
            StubSchedule(id="tomorrow", title="体检", date=TOMORROW, time=dt.time(8, 0)),
            StubSchedule(id="week", title="整理周报笔记", date=NEXT_WEEK, time=None),
        )
    )
    window = MainWindow(service=service, clock=lambda: TODAY)
    QApplication.processEvents()
    return window, service


def cell_text(table: QTableWidget, row: int, column: int) -> str:
    item = table.item(row, column)
    assert item is not None
    return item.text()


def header_text(table: QTableWidget, column: int) -> str:
    item = table.horizontalHeaderItem(column)
    assert item is not None
    return item.text()


def test_table_has_date_column_and_shows_iso_date(qapp: QApplication) -> None:
    window, _service = build_window()
    try:
        table = window.findChild(QTableWidget)
        assert table is not None
        headers = [header_text(table, index) for index in range(table.columnCount())]
        assert headers == ["日期", "时间", "标题", "备注"]
        assert table.columnWidth(0) == 105
        assert table.columnWidth(1) == 90
        assert table.columnWidth(2) == 240
        assert cell_text(table, 0, 0) == "2026-10-20"
        assert cell_text(table, 0, 1) == "09:30"
    finally:
        window.close()


def test_upcoming_list_shows_seven_day_summary(qapp: QApplication) -> None:
    window, _service = build_window()
    try:
        upcoming = window.findChild(QListWidget, "UpcomingList")
        assert upcoming is not None
        texts = [upcoming.item(index).text() for index in range(upcoming.count())]
        assert texts == [
            "10-20 周二 · 09:30 · 写周报",
            "10-21 周三 · 08:00 · 体检",
            "10-26 周一 · 全天 · 整理周报笔记",
        ]
    finally:
        window.close()


def test_search_input_debounces_before_calling_service(qapp: QApplication) -> None:
    """输入本身不查服务：停下 250 ms 才发一次查询。"""
    window, service = build_window()
    try:
        search = window.findChild(QLineEdit, "SearchInput")
        assert search is not None
        calls_before = len(service.calls_of("search"))

        search.setText("周报")

        assert len(service.calls_of("search")) == calls_before, "每次按键都查服务会把库打爆"
        QTest.qWait(320)
        assert service.calls_of("search")[-1] == ("search", "周报")
    finally:
        window.close()


def test_search_updates_heading_rows_dates_and_clear_restores_day(qapp: QApplication) -> None:
    window, _service = build_window()
    try:
        search = window.findChild(QLineEdit, "SearchInput")
        heading = window.findChild(QLabel, "DayHeading")
        table = window.findChild(QTableWidget)
        clear = window.findChild(QPushButton, "ClearSearch")
        assert search is not None and heading is not None and table is not None
        assert clear is not None

        search.setText("周报")
        search.returnPressed.emit()
        QApplication.processEvents()

        assert heading.text() == "搜索“周报” · 共 2 条"
        assert table.rowCount() == 2
        assert [cell_text(table, row, 0) for row in range(2)] == ["2026-10-20", "2026-10-26"]

        clear.click()
        QApplication.processEvents()

        assert search.text() == "", "清空按钮必须同时清掉输入框"
        assert heading.text().startswith("2026-10-20 周二")
        assert table.rowCount() == 1

        search.setText("没有这个日程")
        search.returnPressed.emit()
        QApplication.processEvents()

        assert heading.text() == "搜索“没有这个日程” · 共 0 条"
        assert "没有找到匹配" in cell_text(table, 0, 0)
    finally:
        window.close()


def test_clicking_upcoming_item_jumps_to_that_day(qapp: QApplication) -> None:
    window, _service = build_window()
    try:
        upcoming = window.findChild(QListWidget, "UpcomingList")
        table = window.findChild(QTableWidget)
        assert upcoming is not None and table is not None

        window._on_upcoming_clicked(upcoming.item(1))
        QApplication.processEvents()

        assert window._controller.current_day == TOMORROW
        assert window._controller.selected_id == "tomorrow"
        assert cell_text(table, 0, 0) == "2026-10-21"
    finally:
        window.close()
